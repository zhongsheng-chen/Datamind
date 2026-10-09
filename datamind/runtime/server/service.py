"""运行时模型服务.

基于 BentoML 提供多 Worker 模型推理服务。

核心功能：
  - login: 使用本地账户登录
  - refresh: 续期并轮换刷新令牌
  - logout: 撤销刷新令牌
  - predict: 支持路由与实验分配的单条模型推理
  - predict_batch: 提交支持路由与实验分配的异步批量模型推理
  - batch_status: 查询异步预测批次状态和结果
  - cancel_batch: 取消异步预测批次
  - retry_batch: 重新提交失败或已取消的预测批次
  - reload: 请求重新加载部署模型
  - status: 查询部署控制状态和 Worker 运行状态
  - services: 查询当前 Worker 的运行时服务
  - health: 服务健康检查
  - ready: 服务就绪检查

使用示例：
  bentoml serve \
    datamind.runtime.server.service:DatamindRuntimeService \
    --host 0.0.0.0 \
    --port 8700
"""

import asyncio
import json
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

import bentoml
import structlog
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from datamind.audit import AuditRecorder
from datamind.config import (
    get_logging_config,
    get_runtime_config,
    get_service_config,
)
from datamind.db.core import UnitOfWork
from datamind.logging import setup_logging
from datamind.models.errors import (
    BackendError,
    RuntimeRouteError,
)
from datamind.runtime.executor import (
    PredictionExecutor,
)
from datamind.runtime.manager import RuntimeManager
from datamind.runtime.reconciler import RuntimeReconciler
from datamind.runtime.routing import RuntimeRouter
from datamind.runtime.task_queue import TaskPublisher
from datamind.runtime.server.security import (
    RuntimeIdentity,
    RuntimeSecurity,
)
from datamind.runtime.server.authentication import auth_app
from datamind.runtime.server.cache import ServiceCacheEntry
from datamind.runtime.server.control import RuntimeControlMixin
from datamind.runtime.server.prediction import PredictionMixin
from datamind.runtime.server.timeout import (
    REQUEST_TIMEOUT_GRACE_SECONDS,
)
from datamind.services import RuntimeControlService

logger = structlog.get_logger(__name__)

service_config = get_service_config()
runtime_config = get_runtime_config()


def _get_service_instance_id() -> str | None:
    """获取当前服务实例 ID."""
    service_instance_id = os.environ.get(
        "DATAMIND_SERVICE_INSTANCE_ID"
    )

    if not service_instance_id:
        return None

    return service_instance_id


def _get_ready_dir() -> Path | None:
    """获取 Worker 就绪标记目录."""
    ready_dir = os.environ.get(
        "DATAMIND_SERVICE_READY_DIR"
    )

    if not ready_dir:
        return None

    return Path(
        ready_dir
    )


def _write_worker_ready_marker(
        *,
        worker_id: str,
        environment: str,
) -> None:
    """写入 Worker 就绪标记.

    参数：
        worker_id: Worker ID
        environment: 服务运行环境
    """
    service_instance_id = _get_service_instance_id()
    ready_dir = _get_ready_dir()

    if service_instance_id is None or ready_dir is None:
        return

    ready_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "service_instance_id": service_instance_id,
        "worker_id": worker_id,
        "pid": os.getpid(),
        "environment": environment,
        "ready": True,
        "ready_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    marker_path = ready_dir / f"{worker_id}.json"
    temp_path = ready_dir / f"{worker_id}.{os.getpid()}.tmp"

    temp_path.write_text(
        json.dumps(
            record,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temp_path.replace(
        marker_path
    )

    logger.debug(
        "运行时 Worker 就绪标记写入完成",
        service_instance_id=service_instance_id,
        worker_id=worker_id,
        environment=environment,
        ready_file=str(marker_path),
    )


def _build_worker_id() -> str:
    """生成当前 Worker 标识.

    使用主机名和进程 ID 组合，
    保证同一服务实例中的 Worker 标识不同。

    返回：
        Worker ID
    """
    hostname = (
            socket.gethostname().strip()
            or "worker"
    )

    worker_id = (
        f"{hostname}-{os.getpid()}"
    )

    return worker_id[:64]


@bentoml.service(
    name="datamind_runtime_service",
    workers=service_config.workers,
    traffic={
        "timeout": service_config.timeout + REQUEST_TIMEOUT_GRACE_SECONDS,
    },
)
@bentoml.asgi_app(
    auth_app,
    path="/auth",
)
class DatamindRuntimeService(
    RuntimeControlMixin,
    PredictionMixin,
):
    """Datamind 多 Worker 运行时模型服务."""

    def __init__(
            self,
    ):
        """初始化当前 Worker 服务状态."""
        setup_logging(get_logging_config())

        worker_id = _build_worker_id()
        service_instance_id = _get_service_instance_id()
        self._logger = logger.bind(
            worker_id=worker_id,
            pid=os.getpid(),
        )
        if service_instance_id is not None:
            self._logger = self._logger.bind(
                service_instance_id=service_instance_id,
            )

        self.manager = RuntimeManager(
            worker_id=worker_id,
        )

        self.router = RuntimeRouter()

        self.controller = RuntimeControlService()

        self.security = RuntimeSecurity()

        self.reconciler = RuntimeReconciler(
            manager=self.manager,
            service_instance_id=service_instance_id,
            environment=(
                service_config.environment
            ),
            interval_seconds=(
                runtime_config.reconcile_interval
            ),
            heartbeat_interval_seconds=(
                runtime_config.heartbeat_interval
            ),
        )

        self._service_cache: dict[
            str,
            ServiceCacheEntry,
        ] = {}

        self._service_lock = asyncio.Lock()

        self._audit_recorder = AuditRecorder()

        self.executor = PredictionExecutor(
            service_loader=self._get_service,
        )

        self.task_publisher = TaskPublisher()

        self._logger.info(
            "运行时 Worker 初始化完成",
            worker_id=worker_id,
            environment=(
                service_config.environment
            ),
            service_workers=(
                service_config.workers
            ),
            reconcile_interval=(
                runtime_config.reconcile_interval
            ),
            heartbeat_interval=(
                runtime_config.heartbeat_interval
            ),
        )

    @bentoml.on_startup
    async def startup(
            self,
    ) -> None:
        """启动当前 Worker.

        启动流程：
          - 执行当前环境首次状态协调
          - 启动后台协调循环
        """
        result: dict[str, int] = {
            "checked": 0,
            "loaded": 0,
            "unloaded": 0,
            "reloaded": 0,
            "unchanged": 0,
            "failed": 0,
        }

        try:
            initial_result = await self.reconciler.reconcile_once()
            result = initial_result.to_dict()

        except (SQLAlchemyError, OSError) as exc:
            # 首次协调失败不阻塞服务启动，后台循环将在依赖恢复后重试。
            self._logger.warning(
                "运行时首次状态协调等待数据库恢复",
                worker_id=self.manager.worker_id,
                environment=service_config.environment,
                error=str(exc),
            )

        await self.reconciler.start()

        self._logger.info(
            "运行时 Worker 启动完成",
            worker_id=self.manager.worker_id,
            environment=(
                service_config.environment
            ),
            **result,
        )

        _write_worker_ready_marker(
            worker_id=self.manager.worker_id,
            environment=service_config.environment,
        )

    @bentoml.on_shutdown
    async def shutdown(
            self,
    ) -> None:
        """关闭当前 Worker.

        关闭流程：
          - 停止 Reconciler
          - 卸载当前 Worker 已加载模型
          - 清理 RuntimeService 缓存
        """
        await self.reconciler.stop()

        deployment_ids = [
            runtime_model.deployment_id
            for runtime_model in self.manager.registry.all()
        ]

        for deployment_id in deployment_ids:
            try:
                await self.manager.unload(
                    deployment_id=deployment_id,
                    operator="system",
                )

            except (
                    BackendError,
                    RuntimeRouteError,
                    SQLAlchemyError,
                    RuntimeError,
            ) as exc:
                self._logger.exception(
                    "Worker 关闭时卸载模型失败",
                    worker_id=self.manager.worker_id,
                    environment=(
                        service_config.environment
                    ),
                    deployment_id=deployment_id,
                    error=str(exc),
                )

        self._service_cache.clear()

        self._logger.info(
            "运行时 Worker 已关闭",
            worker_id=self.manager.worker_id,
            environment=(
                service_config.environment
            ),
        )

    @bentoml.api(
        route="/health",
    )
    def health(
            self,
    ) -> dict[str, Any]:
        """服务健康检查.

        返回：
            当前 Worker 健康状态
        """
        return {
            "status": "ok",
            "worker_id": self.manager.worker_id,
            "environment": (
                service_config.environment
            ),
            "reconciler_running": (
                self.reconciler.is_running
            ),
            "runtime_count": (
                len(self.manager.registry)
            ),
            "service_cache_count": len(
                self._service_cache
            ),
            "configured_workers": (
                service_config.workers
            ),
        }

    @bentoml.api(
        route="/ready",
    )
    async def ready(
            self,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """检查 Worker 是否可以接收请求."""
        database_ready = False

        try:
            async with UnitOfWork() as uow:
                await uow.session.execute(
                    text("SELECT 1")
                )

            database_ready = True

        except (SQLAlchemyError, OSError) as exc:
            self._logger.warning(
                "运行时就绪检查数据库不可用",
                worker_id=self.manager.worker_id,
                error=str(exc),
            )

        ready = (
            database_ready
            and self.reconciler.is_running
        )

        if not ready:
            ctx.response.status_code = 503

        return {
            "status": (
                "ready"
                if ready
                else "not_ready"
            ),
            "database_ready": database_ready,
            "reconciler_running": (
                self.reconciler.is_running
            ),
            "worker_id": self.manager.worker_id,
            "environment": service_config.environment,
        }

    async def _execute_secured(
            self,
            *,
            ctx: bentoml.Context,
            permission: str,
            request_id: str,
            handler: Callable[
                [RuntimeIdentity],
                Awaitable[dict[str, Any]],
            ],
            audit_action: str | None = None,
            target_type: str | None = None,
            target_id: str | None = None,
    ) -> dict[str, Any]:
        """在认证请求作用域内执行接口处理函数."""
        async with self.security.request_scope(
                context=ctx,
                permission=permission,
                request_id=request_id,
        ) as identity:
            response = await handler(
                identity
            )

            self._apply_response_status(
                ctx=ctx,
                response=response,
            )
            successful = bool(
                response.get("success")
            )

            if (
                    audit_action is not None
                    and target_type is not None
                    and target_id is not None
            ):
                await self._audit_recorder.record(
                    action=audit_action,
                    target_type=target_type,
                    target_id=target_id,
                    status=(
                        "success"
                        if successful
                        else "failed"
                    ),
                    error=(
                        None
                        if successful
                        else self._optional_string(
                            response.get("error")
                        )
                    ),
                    after=(
                        response
                        if successful
                        else None
                    ),
                )

            return response

    @staticmethod
    def _apply_response_status(
            *,
            ctx: Any,
            response: dict[str, Any],
    ) -> None:
        """根据错误类型设置 HTTP 响应状态."""
        if response.get("success", True):
            return

        error_type = response.get(
            "error_type"
        )
        status_by_error = {
            "ServiceDeploymentNotFoundError": 404,
            "ServiceEnvironmentMismatchError": 409,
            "InvalidDeploymentStateError": 409,
            "RuntimeRouteError": 400,
            "RequestTimeoutError": 504,
            "TypeError": 400,
            "ValueError": 400,
            "BatchNotFoundError": 404,
            "BatchStateError": 409,
            "TaskDispatchError": 503,
        }

        status_code = (
            status_by_error.get(
                error_type,
                500,
            )
            if isinstance(error_type, str)
            else 500
        )
        ctx.response.status_code = status_code
