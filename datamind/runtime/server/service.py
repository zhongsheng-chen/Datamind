# datamind/runtime/server/service.py

"""运行时模型服务

基于 BentoML 提供多 Worker 模型推理服务。

核心功能：
  - predict: 单条模型推理
  - predict_batch: 指定部署批量推理
  - submit_outcome: 提交延迟业务结果
  - load: 设置部署期望状态为 loaded
  - unload: 设置部署期望状态为 unloaded
  - reload: 请求重新加载部署模型
  - status: 查询部署控制状态和 Worker 运行状态
  - services: 查询当前 Worker 的运行时服务
  - health: 服务健康检查
  - ready: 服务就绪检查

使用示例：
  bentoml serve \
    datamind.runtime.server.service:DatamindRuntimeService \
    --host 0.0.0.0 \
    --port 3000
"""

import asyncio
import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Awaitable, Callable
from typing import Any

import bentoml
import structlog
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from datamind.audit import AuditRecorder
from datamind.config import get_settings
from datamind.context import get_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DecisionRepository,
    DeploymentRepository,
    RequestRepository,
)
from datamind.logging import setup_logging
from datamind.models.enums import DecisionStrategy, DeploymentStatus
from datamind.models.errors import (
    BackendError,
    RuntimeRouteError,
)
from datamind.runtime.manager import RuntimeManager
from datamind.runtime.reconciler import RuntimeReconciler
from datamind.runtime.routing import RouteResult, RuntimeRouter
from datamind.runtime.server.errors import (
    ServiceDeploymentNotFoundError,
    ServiceEnvironmentMismatchError,
)
from datamind.runtime.server.security import (
    RuntimeIdentity,
    RuntimeSecurity,
)
from datamind.runtime.serving.base import BaseRuntimeService
from datamind.runtime.serving.factory import (
    RuntimeServiceFactory,
)
from datamind.services import OutcomeService, RuntimeControlService
from datamind.utils.datetime import format_iso_utc
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)

service_config = get_settings().service


def _get_service_instance_id() -> str | None:
    """获取当前服务实例 ID"""
    service_instance_id = os.environ.get(
        "DATAMIND_SERVICE_INSTANCE_ID"
    )

    if not service_instance_id:
        return None

    return service_instance_id


def _get_ready_dir() -> Path | None:
    """获取 Worker 就绪标记目录"""
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
    """写入 Worker 就绪标记

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
    """生成当前 Worker 标识

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


class RuntimeRequest(BaseModel):
    """运行时接口请求基类"""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class ControlRequest(RuntimeRequest):
    """运行控制请求"""

    deployment_id: str = Field(
        min_length=1,
    )

class DeploymentRequest(RuntimeRequest):
    """部署查询请求"""

    deployment_id: str = Field(
        min_length=1,
    )


class PredictRequest(RuntimeRequest):
    """单条预测请求"""

    model_id: str = Field(
        min_length=1,
    )

    features: dict[str, Any] = Field(
        min_length=1,
    )

    deployment_id: str | None = None

    subject_key: str | None = None

    subject_type: str | None = None


class BatchPredictRequest(RuntimeRequest):
    """批量预测请求"""

    deployment_id: str = Field(
        min_length=1,
    )

    features_list: list[
        dict[str, Any]
    ] = Field(
        min_length=1,
    )


class OutcomeFeedbackRequest(RuntimeRequest):
    """业务结果回流请求"""

    outcome_id: str = Field(
        min_length=1,
        max_length=64,
    )

    subject_key: str = Field(
        min_length=1,
        max_length=128,
    )

    decision_id: str | None = None
    request_id: str | None = None
    subject_type: str | None = None
    approved: bool | None = None
    converted: bool | None = None
    defaulted: bool | None = None
    overdue_days: int | None = Field(
        default=None,
        ge=0,
    )
    amount: float | None = Field(
        default=None,
        ge=0,
    )
    label: str | None = None
    context: dict[str, Any] | None = None
    outcome_time: datetime | None = None


@dataclass(slots=True)
class ServiceCacheEntry:
    """Worker 本地服务缓存项

    属性：
        service:
            RuntimeService 实例

        generation:
            创建该 Service 时已应用的控制版本

        runtime_identity:
            RuntimeModel 对象身份标识
    """

    service: BaseRuntimeService

    generation: int | None

    runtime_identity: int


@bentoml.service(
    name="datamind_runtime_service",
    workers=service_config.workers,
)
class DatamindRuntimeService:
    """Datamind 多 Worker 运行时模型服务"""

    def __init__(
            self,
    ):
        """初始化当前 Worker 服务状态"""
        settings = get_settings()

        setup_logging(
            settings.logging
        )

        worker_id = _build_worker_id()

        self.manager = RuntimeManager(
            worker_id=worker_id,
        )

        self.router = RuntimeRouter()

        self.controller = RuntimeControlService()

        self.security = RuntimeSecurity()

        self.reconciler = RuntimeReconciler(
            manager=self.manager,
            environment=(
                service_config.environment
            ),
            interval_seconds=(
                service_config.reconcile_interval
            ),
            heartbeat_interval_seconds=(
                service_config.heartbeat_interval
            ),
        )

        self._service_cache: dict[
            str,
            ServiceCacheEntry,
        ] = {}

        self._service_lock = asyncio.Lock()

        self._audit_recorder = AuditRecorder()

        logger.info(
            "运行时 Worker 初始化完成",
            worker_id=worker_id,
            environment=(
                service_config.environment
            ),
            service_workers=(
                service_config.workers
            ),
            reconcile_interval=(
                service_config.reconcile_interval
            ),
            heartbeat_interval=(
                service_config.heartbeat_interval
            ),
        )

    @bentoml.on_startup
    async def startup(
            self,
    ) -> None:
        """启动当前 Worker

        启动流程：
          - 执行当前环境首次状态协调
          - 启动后台协调循环
        """
        result = (
            await self.reconciler.reconcile_once()
        )

        await self.reconciler.start()

        logger.info(
            "运行时 Worker 启动完成",
            worker_id=self.manager.worker_id,
            environment=(
                service_config.environment
            ),
            **result.to_dict(),
        )

        _write_worker_ready_marker(
            worker_id=self.manager.worker_id,
            environment=service_config.environment,
        )

    @bentoml.on_shutdown
    async def shutdown(
            self,
    ) -> None:
        """关闭当前 Worker

        关闭流程：
          - 停止 Reconciler
          - 卸载当前 Worker 已加载模型
          - 清理 RuntimeService 缓存
        """
        await self.reconciler.stop()

        deployment_ids = [
            runtime_model.deployment_id
            for runtime_model in self.manager.all()
        ]

        for deployment_id in deployment_ids:
            try:
                await self.manager.stop(
                    deployment_id=deployment_id,
                    operator="system",
                )

            except (
                    BackendError,
                    RuntimeRouteError,
                    SQLAlchemyError,
                    RuntimeError,
            ) as exc:
                logger.exception(
                    "Worker 关闭时卸载模型失败",
                    worker_id=self.manager.worker_id,
                    environment=(
                        service_config.environment
                    ),
                    deployment_id=deployment_id,
                    error=str(exc),
                )

        self._service_cache.clear()

        logger.info(
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
        """服务健康检查

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
                self.manager.count()
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
        """检查 Worker 是否可以接收请求"""
        database_ready = False

        try:
            async with UnitOfWork() as uow:
                await uow.session.execute(
                    text("SELECT 1")
                )

            database_ready = True

        except SQLAlchemyError as exc:
            logger.warning(
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
        """在认证请求作用域内执行接口处理函数"""
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
        """根据错误类型设置 HTTP 响应状态"""
        if response.get("success", True):
            return

        error_type = response.get(
            "error_type"
        )
        status_by_error = {
            "ServiceDeploymentNotFoundError": 404,
            "ServiceEnvironmentMismatchError": 409,
            "RuntimeRouteError": 400,
            "ValueError": 400,
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

    @bentoml.api(
        route="/admin/load",
    )
    async def load(
            self,
            request: ControlRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """提交已认证的部署加载请求"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="runtime.manage",
            request_id=request_id,
            handler=lambda identity: self._load(
                request=request,
                request_id=request_id,
                operator=identity.username,
            ),
            audit_action="runtime.load",
            target_type="deployment",
            target_id=request.deployment_id,
        )

    async def _load(
            self,
            *,
            request: ControlRequest,
            request_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """设置部署期望状态为 loaded

        只允许操作当前 Service environment
        对应的 Deployment。

        环境校验通过后，
        由 RuntimeControlService 更新共享 controls 表。

        各 Worker 由 RuntimeReconciler
        独立完成模型加载。

        参数：
            request: 运行控制请求

        返回：
            控制请求受理结果
        """
        try:
            await self._validate_service_environment(
                deployment_id=request.deployment_id,
            )

            result = await self.controller.load(
                deployment_id=request.deployment_id,
                operator=operator,
            )

            return {
                "success": True,
                "request_id": request_id,
                **result,
            }

        except (
                ServiceDeploymentNotFoundError,
                ServiceEnvironmentMismatchError,
                RuntimeRouteError,
                RuntimeError,
                ValueError,
        ) as exc:
            logger.warning(
                "请求加载失败",
                request_id=request_id,
                deployment_id=request.deployment_id,
                operator=operator,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

        except Exception as exc:
            logger.exception(
                "请求加载异常",
                request_id=request_id,
                deployment_id=request.deployment_id,
                operator=operator,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

    @bentoml.api(
        route="/admin/unload",
    )
    async def unload(
            self,
            request: ControlRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """提交已认证的部署卸载请求"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="runtime.manage",
            request_id=request_id,
            handler=lambda identity: self._unload(
                request=request,
                request_id=request_id,
                operator=identity.username,
            ),
            audit_action="runtime.unload",
            target_type="deployment",
            target_id=request.deployment_id,
        )

    async def _unload(
            self,
            *,
            request: ControlRequest,
            request_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """设置部署期望状态为 unloaded

        只允许操作当前 Service environment
        对应的 Deployment。

        参数：
            request: 运行控制请求

        返回：
            控制请求受理结果
        """
        try:
            await self._validate_service_environment(
                deployment_id=request.deployment_id,
            )

            result = await self.controller.unload(
                deployment_id=request.deployment_id,
                operator=operator,
            )

            return {
                "success": True,
                "request_id": request_id,
                **result,
            }

        except (
                ServiceDeploymentNotFoundError,
                ServiceEnvironmentMismatchError,
                RuntimeRouteError,
                RuntimeError,
                ValueError,
        ) as exc:
            logger.warning(
                "请求卸载失败",
                request_id=request_id,
                deployment_id=request.deployment_id,
                operator=operator,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

        except Exception as exc:
            logger.exception(
                "请求卸载异常",
                request_id=request_id,
                deployment_id=request.deployment_id,
                operator=operator,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

    @bentoml.api(
        route="/admin/reload",
    )
    async def reload(
            self,
            request: ControlRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """提交已认证的部署重载请求"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="runtime.manage",
            request_id=request_id,
            handler=lambda identity: self._reload(
                request=request,
                request_id=request_id,
                operator=identity.username,
            ),
            audit_action="runtime.reload",
            target_type="deployment",
            target_id=request.deployment_id,
        )

    async def _reload(
            self,
            *,
            request: ControlRequest,
            request_id: str,
            operator: str,
    ) -> dict[str, Any]:
        """请求重新加载部署模型

        只允许操作当前 Service environment
        对应的 Deployment。

        reload 保持 desired_status=loaded，
        通过 generation 递增通知所属环境的 Worker。

        参数：
            request: 运行控制请求

        返回：
            控制请求受理结果
        """
        try:
            await self._validate_service_environment(
                deployment_id=request.deployment_id,
            )

            result = await self.controller.reload(
                deployment_id=request.deployment_id,
                operator=operator,
            )

            return {
                "success": True,
                "request_id": request_id,
                **result,
            }

        except (
                ServiceDeploymentNotFoundError,
                ServiceEnvironmentMismatchError,
                RuntimeRouteError,
                RuntimeError,
                ValueError,
        ) as exc:
            logger.warning(
                "请求重载失败",
                request_id=request_id,
                deployment_id=request.deployment_id,
                operator=operator,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

        except Exception as exc:
            logger.exception(
                "请求重载异常",
                request_id=request_id,
                deployment_id=request.deployment_id,
                operator=operator,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

    @bentoml.api(
        route="/admin/status",
    )
    async def status(
            self,
            request: DeploymentRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """查询已认证的部署运行状态"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="runtime.read",
            request_id=request_id,
            handler=lambda _identity: self._status(
                request=request,
                request_id=request_id,
            ),
        )

    async def _status(
            self,
            *,
            request: DeploymentRequest,
            request_id: str,
    ) -> dict[str, Any]:
        """查询部署运行状态

        返回：
          - controls 期望状态
          - 所有 Worker 的 runtimes 状态
          - 当前 Worker 本地内存状态

        参数：
            request: 部署查询请求

        返回：
            部署运行状态信息
        """
        deployment_id = (
            request.deployment_id
        )

        try:
            await self._validate_service_environment(
                deployment_id=deployment_id,
            )

            status_info = await self.controller.get_status(
                deployment_id=deployment_id,
            )

            local_status = await self.manager.status(
                deployment_id
            )

            return {
                "success": True,
                "request_id": request_id,
                "deployment_id": deployment_id,
                "environment": (
                    service_config.environment
                ),
                "control": status_info["control"],
                "runtimes": status_info["runtimes"],
                "local": local_status,
                "local_generation": (
                    self.reconciler.get_applied_generation(
                        deployment_id
                    )
                ),
            }

        except (
                ServiceDeploymentNotFoundError,
                ServiceEnvironmentMismatchError,
                RuntimeRouteError,
                RuntimeError,
                ValueError,
        ) as exc:
            logger.warning(
                "部署运行状态查询失败",
                request_id=request_id,
                deployment_id=deployment_id,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

        except Exception as exc:
            logger.exception(
                "部署运行状态查询异常",
                request_id=request_id,
                deployment_id=deployment_id,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                error=exc,
            )

    @bentoml.api(
        route="/admin/services",
    )
    async def services(
            self,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """查询当前 Worker 的已认证服务列表"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="runtime.read",
            request_id=request_id,
            handler=lambda _identity: self._services(),
        )

    async def _services(
            self,
    ) -> dict[str, Any]:
        """查询当前 Worker 服务状态

        返回：
            当前 Worker 运行时状态
        """
        return {
            "worker_id": self.manager.worker_id,
            "environment": (
                service_config.environment
            ),
            "runtime_count": (
                self.manager.count()
            ),
            "service_cache_count": len(
                self._service_cache
            ),
            "applied_generations": (
                self.reconciler.get_applied_generations()
            ),
            "runtimes": (
                self.manager.to_dicts()
            ),
            "services": [
                self._build_service_info(
                    entry.service
                )
                for entry
                in self._service_cache.values()
            ],
        }

    @bentoml.api(
        route="/feedback/outcomes",
    )
    async def submit_outcome(
            self,
            request: OutcomeFeedbackRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """提交已认证的延迟业务结果"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="outcome.write",
            request_id=request_id,
            handler=lambda _identity: self._submit_outcome(
                request=request,
                request_id=request_id,
            ),
            audit_action="outcome.submit",
            target_type="outcome",
            target_id=request.outcome_id,
        )

    @staticmethod
    async def _submit_outcome(
            *,
            request: OutcomeFeedbackRequest,
            request_id: str,
    ) -> dict[str, Any]:
        """提交延迟业务结果"""
        result = await OutcomeService().submit(
            outcome_id=request.outcome_id,
            subject_key=request.subject_key,
            decision_id=request.decision_id,
            request_id=request.request_id,
            subject_type=request.subject_type,
            approved=request.approved,
            converted=request.converted,
            defaulted=request.defaulted,
            overdue_days=request.overdue_days,
            amount=request.amount,
            label=request.label,
            context=request.context,
            outcome_time=request.outcome_time,
        )
        outcome = result["outcome"]

        for field in (
                "outcome_time",
                "created_at",
                "updated_at",
        ):
            outcome[field] = format_iso_utc(
                outcome[field]
            )

        return {
            "success": True,
            "request_id": request_id,
            **result,
        }

    @bentoml.api(
        route="/predict",
    )
    async def predict(
            self,
            request: PredictRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """执行已认证的单条模型预测"""
        request_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="prediction.invoke",
            request_id=request_id,
            handler=lambda _identity: self._predict(
                request=request,
                request_id=request_id,
            ),
        )

    async def _predict(
            self,
            *,
            request: PredictRequest,
            request_id: str,
    ) -> dict[str, Any]:
        """执行单条模型预测

        处理流程：
          - 创建请求记录
          - 解析运行时路由
          - 执行模型预测
          - 更新请求状态并创建决策记录
          - 返回预测结果和追踪 ID

        参数：
            request: 单条预测请求

        返回：
            模型预测结果
        """
        started_at = time.perf_counter()

        request_record_created = False

        try:
            payload = self._build_request_payload(
                request
            )

            await self._create_request_record(
                request_id=request_id,
                model_id=request.model_id,
                payload=payload,
            )

            request_record_created = True

            if not request.features:
                raise ValueError(
                    "features 不能为空"
                )

            route = await self.router.resolve(
                model_id=request.model_id,
                environment=(
                    service_config.environment
                ),
                subject_key=request.subject_key,
                subject_type=request.subject_type,
                payload=request.features,
                deployment_id=request.deployment_id,
            )

            service = await self._get_service(
                route.deployment_id
            )

            result = await asyncio.to_thread(
                service.predict,
                request.features,
            )

            latency_ms = (
                                 time.perf_counter() - started_at
                         ) * 1000

            decision_id = generate_random_id(
                prefix="dcs"
            )

            await self._record_prediction_success(
                request_id=request_id,
                decision_id=decision_id,
                route=route,
                result=result,
                latency_ms=latency_ms,
            )

            return {
                "success": True,
                "request_id": request_id,
                "decision_id": decision_id,
                **result,
                "route": route.to_dict(),
                "environment": service_config.environment,
                "worker_id": self.manager.worker_id,
            }

        except (
                RuntimeRouteError,
                RuntimeError,
                ValueError,
        ) as exc:
            latency_ms = (
                                 time.perf_counter() - started_at
                         ) * 1000

            await self._mark_prediction_failed(
                request_id=request_id,
                model_id=request.model_id,
                request_record_created=request_record_created,
                error=str(exc),
                latency_ms=latency_ms,
            )

            logger.warning(
                "预测请求处理失败",
                request_id=request_id,
                model_id=request.model_id,
                deployment_id=request.deployment_id,
                subject_key=request.subject_key,
                subject_type=request.subject_type,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                decision_id=None,
                include_decision_id=True,
                error=exc,
            )

        except Exception as exc:
            latency_ms = (
                                 time.perf_counter() - started_at
                         ) * 1000

            await self._mark_prediction_failed(
                request_id=request_id,
                model_id=request.model_id,
                request_record_created=request_record_created,
                error=str(exc),
                latency_ms=latency_ms,
            )

            logger.exception(
                "预测请求处理异常",
                request_id=request_id,
                model_id=request.model_id,
                deployment_id=request.deployment_id,
                subject_key=request.subject_key,
                subject_type=request.subject_type,
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=request_id,
                decision_id=None,
                include_decision_id=True,
                error=exc,
            )

    @bentoml.api(
        route="/predict/batch",
    )
    async def predict_batch(
            self,
            request: BatchPredictRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """执行已认证的批量模型预测"""
        batch_id = generate_random_id(
            prefix="req"
        )

        return await self._execute_secured(
            ctx=ctx,
            permission="prediction.invoke",
            request_id=batch_id,
            handler=lambda _identity: self._predict_batch(
                request=request,
                batch_id=batch_id,
            ),
        )

    async def _predict_batch(
            self,
            *,
            request: BatchPredictRequest,
            batch_id: str,
    ) -> dict[str, Any]:
        """执行指定部署批量预测

        参数：
            request: 批量预测请求

        返回：
            批量预测结果
        """
        request_ids: list[str] = []
        records_created = False
        started_at = time.perf_counter()

        try:
            if not request.features_list:
                raise ValueError(
                    "features_list 不能为空"
                )

            await self._validate_service_environment(
                deployment_id=request.deployment_id,
            )

            service = await self._get_service(
                request.deployment_id
            )

            request_ids = [
                generate_random_id(
                    prefix="req"
                )
                for _ in request.features_list
            ]
            decision_ids = [
                generate_random_id(
                    prefix="dcs"
                )
                for _ in request.features_list
            ]

            await self._create_batch_request_records(
                batch_id=batch_id,
                request_ids=request_ids,
                model_id=service.model_id,
                deployment_id=request.deployment_id,
                features_list=request.features_list,
            )
            records_created = True

            result = await asyncio.to_thread(
                service.predict_batch,
                request.features_list,
            )

            predictions = result.get(
                "predictions"
            )

            if (
                    not isinstance(predictions, list)
                    or len(predictions)
                    != len(request.features_list)
            ):
                raise RuntimeError(
                    "批量预测结果数量与请求数量不一致"
                )

            latency_ms = (
                                 time.perf_counter()
                                 - started_at
                         ) * 1000

            route = RouteResult(
                model_id=service.model_id,
                version_id=service.version_id,
                deployment_id=service.deployment_id,
                framework=service.framework,
                environment=str(
                    service_config.environment
                ),
                source=str(
                    DecisionStrategy.DEPLOYMENT
                ),
                strategy="manual",
                context={
                    "batch_id": batch_id,
                },
            )

            await self._record_batch_success(
                batch_id=batch_id,
                request_ids=request_ids,
                decision_ids=decision_ids,
                route=route,
                predictions=predictions,
                latency_ms=latency_ms,
            )

            return {
                "success": True,
                "request_id": batch_id,
                "request_ids": request_ids,
                "decision_ids": decision_ids,
                **result,
                "worker_id": self.manager.worker_id,
            }

        except (
                ServiceDeploymentNotFoundError,
                ServiceEnvironmentMismatchError,
                RuntimeRouteError,
                RuntimeError,
                ValueError,
        ) as exc:
            await self._mark_batch_failed(
                request_ids=request_ids,
                records_created=records_created,
                error=str(exc),
                latency_ms=(
                                   time.perf_counter()
                                   - started_at
                           ) * 1000,
            )

            logger.warning(
                "批量预测请求处理失败",
                request_id=batch_id,
                deployment_id=request.deployment_id,
                batch_size=len(request.features_list),
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=batch_id,
                error=exc,
            )

        except Exception as exc:
            await self._mark_batch_failed(
                request_ids=request_ids,
                records_created=records_created,
                error=str(exc),
                latency_ms=(
                                   time.perf_counter()
                                   - started_at
                           ) * 1000,
            )

            logger.exception(
                "批量预测请求处理异常",
                request_id=batch_id,
                deployment_id=request.deployment_id,
                batch_size=len(request.features_list),
                environment=service_config.environment,
                worker_id=self.manager.worker_id,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

            return self._build_error_response(
                request_id=batch_id,
                error=exc,
            )

    @staticmethod
    async def _create_batch_request_records(
            *,
            batch_id: str,
            request_ids: list[str],
            model_id: str,
            deployment_id: str,
            features_list: list[dict[str, Any]],
    ) -> None:
        """在同一事务中创建批量请求记录"""
        request_context = get_context()

        async with UnitOfWork() as uow:
            repository = RequestRepository(
                uow.session
            )

            for index, (request_id, features) in enumerate(
                    zip(
                        request_ids,
                        features_list,
                    )
            ):
                repository.create_request(
                    request_id=request_id,
                    model_id=model_id,
                    payload={
                        "batch_id": batch_id,
                        "batch_index": index,
                        "deployment_id": deployment_id,
                        "features": features,
                    },
                    source="http",
                    user=request_context.get(
                        "user"
                    ),
                    ip=request_context.get(
                        "ip"
                    ),
                )

    async def _record_batch_success(
            self,
            *,
            batch_id: str,
            request_ids: list[str],
            decision_ids: list[str],
            route: RouteResult,
            predictions: list[dict[str, Any]],
            latency_ms: float,
    ) -> None:
        """在同一事务中记录批量请求和决策结果"""
        async with UnitOfWork() as uow:
            request_repo = RequestRepository(
                uow.session
            )
            decision_repo = DecisionRepository(
                uow.session
            )

            for index, (
                    request_id,
                    decision_id,
                    prediction,
            ) in enumerate(
                zip(
                    request_ids,
                    decision_ids,
                    predictions,
                )
            ):
                request_record = await request_repo.get_request(
                    request_id
                )

                if request_record is None:
                    raise RuntimeError(
                        f"批量请求记录不存在: {request_id}"
                    )

                request_repo.mark_success(
                    request_record,
                    latency_ms=latency_ms,
                )
                decision_repo.create_decision(
                    decision_id=decision_id,
                    request_id=request_id,
                    model_id=route.model_id,
                    version_id=route.version_id,
                    source=DecisionStrategy.DEPLOYMENT,
                    deployment_id=route.deployment_id,
                    strategy=route.strategy,
                    prediction=prediction,
                    probability=self._optional_float(
                        prediction.get("probability")
                    ),
                    score=self._optional_float(
                        prediction.get("score")
                    ),
                    decision=self._optional_string(
                        prediction.get("decision")
                    ),
                    latency_ms=latency_ms,
                    context={
                        "batch_id": batch_id,
                        "batch_index": index,
                        "route": route.to_dict(),
                        "worker_id": self.manager.worker_id,
                        "environment": service_config.environment,
                    },
                )

    @staticmethod
    async def _mark_batch_failed(
            *,
            request_ids: list[str],
            records_created: bool,
            error: str,
            latency_ms: float,
    ) -> None:
        """标记已经创建的批量请求为失败"""
        if not records_created:
            return

        try:
            async with UnitOfWork() as uow:
                repository = RequestRepository(
                    uow.session
                )

                for request_id in request_ids:
                    request_record = await repository.get_request(
                        request_id
                    )

                    if request_record is not None:
                        repository.mark_failed(
                            request_record,
                            error=error,
                            latency_ms=latency_ms,
                        )

        except Exception as exc:
            logger.exception(
                "记录批量失败请求状态失败",
                request_ids=request_ids,
                error=str(exc),
            )

    def _build_error_response(
            self,
            *,
            request_id: str,
            error: Exception,
            decision_id: str | None = None,
            include_decision_id: bool = False,
    ) -> dict[str, Any]:
        """构造接口错误响应

        参数：
            request_id: 请求追踪 ID
            error: 异常对象
            decision_id: 决策 ID，预测失败时通常为 None
            include_decision_id: 是否在响应中包含 decision_id 字段

        返回：
            错误响应字典
        """
        response: dict[str, Any] = {
            "success": False,
            "request_id": request_id,
            "error": str(error),
            "error_type": error.__class__.__name__,
            "environment": service_config.environment,
            "worker_id": self.manager.worker_id,
        }

        if include_decision_id or decision_id is not None:
            response["decision_id"] = decision_id

        return response

    async def _mark_prediction_failed(
            self,
            *,
            request_id: str,
            model_id: str,
            request_record_created: bool,
            error: str,
            latency_ms: float,
    ) -> None:
        """标记预测请求失败

        参数：
            request_id: 请求 ID
            model_id: 模型 ID
            request_record_created: 请求记录是否已创建
            error: 错误信息
            latency_ms: 处理耗时
        """
        if not request_record_created:
            return

        try:
            await self._mark_request_failed(
                request_id=request_id,
                error=error,
                latency_ms=latency_ms,
            )

        except Exception as exc:
            logger.exception(
                "记录失败请求状态失败",
                request_id=request_id,
                model_id=model_id,
                error=str(exc),
            )

    @staticmethod
    def _build_request_payload(
            request: PredictRequest,
    ) -> dict[str, Any]:
        """构造请求负载

        参数：
            request: 单条预测请求

        返回：
            请求负载字典
        """
        return {
            "model_id": request.model_id,
            "environment": service_config.environment,
            "deployment_id": request.deployment_id,
            "subject_key": request.subject_key,
            "subject_type": request.subject_type,
            "features": request.features,
        }

    @staticmethod
    async def _create_request_record(
            *,
            request_id: str,
            model_id: str,
            payload: dict[str, Any],
    ) -> None:
        """创建原始请求记录

        参数：
            request_id: 请求 ID
            model_id: 模型 ID
            payload: 请求负载
        """
        request_context = get_context()

        async with UnitOfWork() as uow:
            repo = RequestRepository(
                uow.session
            )

            repo.create_request(
                request_id=request_id,
                model_id=model_id,
                payload=payload,
                source="http",
                user=request_context.get(
                    "user"
                ),
                ip=request_context.get(
                    "ip"
                ),
            )

    async def _record_prediction_success(
            self,
            *,
            request_id: str,
            decision_id: str,
            route: RouteResult,
            result: dict[str, Any],
            latency_ms: float,
    ) -> None:
        """记录成功请求和决策结果

        Request 状态更新和 Decision 创建
        在同一个事务中完成。

        参数：
            request_id: 请求 ID
            decision_id: 决策 ID
            route: 路由结果
            result: 模型预测结果
            latency_ms: 处理耗时
        """
        async with UnitOfWork() as uow:
            request_repo = RequestRepository(
                uow.session
            )

            decision_repo = DecisionRepository(
                uow.session
            )

            request_record = await request_repo.get_request(
                request_id
            )

            if request_record is None:
                raise RuntimeError(
                    f"请求记录不存在: {request_id}"
                )

            request_repo.mark_success(
                request_record,
                latency_ms=latency_ms,
            )

            decision_repo.create_decision(
                decision_id=decision_id,
                request_id=request_id,
                model_id=route.model_id,
                version_id=route.version_id,
                source=DecisionStrategy(
                    route.source
                ),
                deployment_id=route.deployment_id,
                experiment_id=route.experiment_id,
                variant_id=route.variant_id,
                assignment_id=route.assignment_id,
                subject_key=route.subject_key,
                subject_type=route.subject_type,
                strategy=route.strategy,
                bucket=route.bucket,
                group=route.group,
                weight=route.weight,
                prediction=(
                    self._build_prediction_payload(
                        result
                    )
                ),
                probability=self._optional_float(
                    result.get(
                        "probability"
                    )
                ),
                score=self._optional_float(
                    result.get(
                        "score"
                    )
                ),
                decision=self._optional_string(
                    result.get(
                        "decision"
                    )
                ),
                latency_ms=latency_ms,
                context={
                    "route": route.to_dict(),
                    "worker_id": self.manager.worker_id,
                    "environment": (
                        service_config.environment
                    ),
                },
            )

    @staticmethod
    async def _mark_request_failed(
            *,
            request_id: str,
            error: str,
            latency_ms: float,
    ) -> None:
        """标记请求处理失败

        参数：
            request_id: 请求 ID
            error: 错误信息
            latency_ms: 处理耗时
        """
        async with UnitOfWork() as uow:
            repo = RequestRepository(
                uow.session
            )

            request_record = await repo.get_request(
                request_id
            )

            if request_record is None:
                logger.warning(
                    "失败请求记录不存在",
                    request_id=request_id,
                )
                return

            repo.mark_failed(
                request_record,
                error=error,
                latency_ms=latency_ms,
            )

    @staticmethod
    def _build_prediction_payload(
            result: dict[str, Any],
    ) -> dict[str, Any]:
        """构造决策表中的模型预测结果

        去除模型和部署标识字段，
        保留服务类型和实际预测输出。

        参数：
            result: RuntimeService 预测结果

        返回：
            模型预测结果
        """
        identity_fields = {
            "deployment_id",
            "model_id",
            "version_id",
            "framework",
        }

        return {
            key: value
            for key, value in result.items()
            if key not in identity_fields
        }

    @staticmethod
    def _optional_float(
            value: Any,
    ) -> float | None:
        """安全转换可选浮点数"""
        if (
                value is None
                or isinstance(
            value,
            bool,
        )
        ):
            return None

        try:
            return float(
                value
            )

        except (
                TypeError,
                ValueError,
        ):
            return None

    @staticmethod
    def _optional_string(
            value: Any,
    ) -> str | None:
        """安全转换可选字符串"""
        if value is None:
            return None

        if not isinstance(
                value,
                str,
        ):
            return None

        return value

    async def _get_service(
            self,
            deployment_id: str,
    ) -> BaseRuntimeService:
        """获取当前 Worker 的 RuntimeService

        当本地模型尚未加载时，
        主动执行一次 reconcile_once，
        加速当前 Worker 所属环境的状态收敛。

        参数：
            deployment_id: 部署 ID

        返回：
            RuntimeService

        异常：
            RuntimeError:
                当前 Worker 无法提供该部署服务
        """
        runtime_model = self.manager.get(
            deployment_id,
            touch=False,
        )

        if runtime_model is None:
            await self.reconciler.reconcile_once()

            runtime_model = self.manager.get(
                deployment_id,
                touch=False,
            )

        if runtime_model is None:
            self._service_cache.pop(
                deployment_id,
                None,
            )

            raise RuntimeError(
                "当前 Worker 尚未加载部署模型: "
                f"{deployment_id}"
            )

        generation = (
            self.reconciler.get_applied_generation(
                deployment_id
            )
        )

        runtime_identity = id(
            runtime_model
        )

        cached = self._service_cache.get(
            deployment_id
        )

        if (
                cached is not None
                and cached.generation == generation
                and cached.runtime_identity
                == runtime_identity
        ):
            return cached.service

        async with self._service_lock:
            cached = self._service_cache.get(
                deployment_id
            )

            if (
                    cached is not None
                    and cached.generation == generation
                    and cached.runtime_identity
                    == runtime_identity
            ):
                return cached.service

            service = RuntimeServiceFactory.create(
                runtime_model=runtime_model,
            )

            self._service_cache[
                deployment_id
            ] = ServiceCacheEntry(
                service=service,
                generation=generation,
                runtime_identity=runtime_identity,
            )

            logger.info(
                "创建 Worker RuntimeService",
                worker_id=self.manager.worker_id,
                environment=(
                    service_config.environment
                ),
                deployment_id=deployment_id,
                service_type=(
                    service.SERVICE_TYPE
                ),
                generation=generation,
            )

            return service

    @staticmethod
    async def _validate_service_environment(
            *,
            deployment_id: str,
    ) -> None:
        """校验 Deployment 是否属于当前 Service 环境

        参数：
            deployment_id:
                部署 ID

        异常：
            ServiceDeploymentNotFoundError:
                部署不存在

            ServiceEnvironmentMismatchError:
                Deployment 环境与当前 Service
                环境不一致
        """
        async with UnitOfWork() as uow:
            repo = DeploymentRepository(
                uow.session
            )

            deployment = (
                await repo.get_deployment(
                    deployment_id
                )
            )

            if deployment is None:
                raise ServiceDeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            if (
                    deployment.environment
                    != service_config.environment
            ):
                raise ServiceEnvironmentMismatchError(
                    "部署环境与当前服务环境不一致: "
                    f"deployment_id={deployment_id}, "
                    f"deployment_environment="
                    f"{deployment.environment}, "
                    f"service_environment="
                    f"{service_config.environment}"
                )

            if deployment.status != str(DeploymentStatus.ACTIVE):
                raise RuntimeRouteError(
                    f"部署不可用: {deployment_id}"
                )

    @staticmethod
    def _build_service_info(
            service: BaseRuntimeService,
    ) -> dict[str, Any]:
        """构造 RuntimeService 信息

        参数：
            service: RuntimeService

        返回：
            RuntimeService 信息
        """
        return {
            "deployment_id": (
                service.deployment_id
            ),
            "model_id": service.model_id,
            "version_id": service.version_id,
            "framework": service.framework,
            "service_type": (
                service.SERVICE_TYPE
            ),
            "capabilities": (
                service.get_capability_names()
            ),
        }
