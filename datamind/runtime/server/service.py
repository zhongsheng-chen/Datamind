# datamind/runtime/server/service.py

"""Datamind 运行时模型服务

基于 BentoML 提供多 Worker 模型推理服务。

核心功能：
  - predict: 单条模型推理
  - predict_batch: 指定部署批量推理
  - load: 设置部署期望状态为 loaded
  - unload: 设置部署期望状态为 unloaded
  - reload: 请求重新加载部署模型
  - status: 查询部署控制状态和 Worker 运行状态
  - services: 查询当前 Worker 的运行时服务
  - health: 服务健康检查

说明：
  BentoML Service 使用多 Worker 运行模式。

  每个 Worker 独立持有：
    - RuntimeManager
    - RuntimeRegistry
    - RuntimeReconciler
    - RuntimeService 缓存

  所有 Worker 共享：
    - controls 表中的期望运行状态
    - runtimes 表中的 Worker 实际运行状态

  每个 RuntimeReconciler 只读取当前
  Service environment 对应的 Control。

  load / unload / reload API
  只允许操作当前 Service environment
  对应的 Deployment。

  通过环境校验后，
  再由 RuntimeController 更新 controls 表。

  各 Worker 的 RuntimeReconciler
  定期读取当前环境的 controls 表记录并执行：
    - start
    - stop
    - restart

  服务运行参数统一由 ServiceConfig 提供。

使用示例：
  bentoml serve \
    datamind.runtime.server.service:DatamindRuntimeService \
    --host 0.0.0.0 \
    --port 3000
"""

import asyncio
import os
import socket
import time
from dataclasses import dataclass
from typing import Any

import bentoml
import structlog
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from datamind.config import get_settings
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DecisionRepository,
    DeploymentRepository,
    RequestRepository,
)
from datamind.logging import setup_logging
from datamind.models.enums import DecisionStrategy
from datamind.models.errors import (
    BackendError,
    RuntimeRouteError,
)
from datamind.runtime.manager import RuntimeManager
from datamind.runtime.reconciler import RuntimeReconciler
from datamind.runtime.router import RouteResult, RuntimeRouter
from datamind.runtime.server.errors import (
    ServiceDeploymentNotFoundError,
    ServiceEnvironmentMismatchError,
)
from datamind.runtime.serving.base import BaseRuntimeService
from datamind.runtime.serving.factory import (
    RuntimeServiceFactory,
)
from datamind.services import RuntimeController
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)

service_config = get_settings().service


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


class ControlRequest(BaseModel):
    """运行控制请求"""

    deployment_id: str = Field(
        min_length=1,
    )

    operator: str = Field(
        default="system",
        min_length=1,
    )


class DeploymentRequest(BaseModel):
    """部署查询请求"""

    deployment_id: str = Field(
        min_length=1,
    )


class PredictRequest(BaseModel):
    """单条预测请求"""

    model_id: str = Field(
        min_length=1,
    )

    features: dict[str, Any]

    deployment_id: str | None = None

    subject_key: str | None = None

    subject_type: str | None = None


class BatchPredictRequest(BaseModel):
    """批量预测请求"""

    deployment_id: str = Field(
        min_length=1,
    )

    features_list: list[
        dict[str, Any]
    ]


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

        self.controller = RuntimeController()

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
        route="/admin/load",
    )
    async def load(
            self,
            request: ControlRequest,
    ) -> dict[str, Any]:
        """设置部署期望状态为 loaded

        只允许操作当前 Service environment
        对应的 Deployment。

        环境校验通过后，
        由 RuntimeController 更新共享 controls 表。

        各 Worker 由 RuntimeReconciler
        独立完成模型加载。

        参数：
            request: 运行控制请求

        返回：
            控制请求受理结果
        """
        await self._validate_service_environment(
            deployment_id=request.deployment_id,
        )

        return await self.controller.load(
            deployment_id=request.deployment_id,
            operator=request.operator,
        )

    @bentoml.api(
        route="/admin/unload",
    )
    async def unload(
            self,
            request: ControlRequest,
    ) -> dict[str, Any]:
        """设置部署期望状态为 unloaded

        只允许操作当前 Service environment
        对应的 Deployment。

        参数：
            request: 运行控制请求

        返回：
            控制请求受理结果
        """
        await self._validate_service_environment(
            deployment_id=request.deployment_id,
        )

        return await self.controller.unload(
            deployment_id=request.deployment_id,
            operator=request.operator,
        )

    @bentoml.api(
        route="/admin/reload",
    )
    async def reload(
            self,
            request: ControlRequest,
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
        await self._validate_service_environment(
            deployment_id=request.deployment_id,
        )

        return await self.controller.reload(
            deployment_id=request.deployment_id,
            operator=request.operator,
        )

    @bentoml.api(
        route="/admin/status",
    )
    async def status(
            self,
            request: DeploymentRequest,
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

        status_info = await self.controller.get_status(
            deployment_id=deployment_id,
        )

        local_status = await self.manager.status(
            deployment_id
        )

        return {
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

    @bentoml.api(
        route="/admin/services",
    )
    def services(
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
        route="/predict",
    )
    async def predict(
            self,
            request: PredictRequest,
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
        request_id = generate_random_id(
            prefix="req"
        )

        started_at = time.perf_counter()

        payload = self._build_request_payload(
            request
        )

        await self._create_request_record(
            request_id=request_id,
            model_id=request.model_id,
            payload=payload,
        )

        try:
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

        except Exception as exc:
            latency_ms = (
                                 time.perf_counter() - started_at
                         ) * 1000

            try:
                await self._mark_request_failed(
                    request_id=request_id,
                    error=str(exc),
                    latency_ms=latency_ms,
                )

            except Exception as record_exc:
                logger.exception(
                    "记录失败请求状态失败",
                    request_id=request_id,
                    model_id=request.model_id,
                    error=str(record_exc),
                )

            raise

        return {
            "request_id": request_id,
            "decision_id": decision_id,
            **result,
            "route": route.to_dict(),
            "worker_id": self.manager.worker_id,
        }

    @bentoml.api(
        route="/predict/batch",
    )
    async def predict_batch(
            self,
            request: BatchPredictRequest,
    ) -> dict[str, Any]:
        """执行指定部署批量预测

        参数：
            request: 批量预测请求

        返回：
            批量预测结果
        """
        if not request.features_list:
            raise ValueError(
                "features_list 不能为空"
            )

        service = await self._get_service(
            request.deployment_id
        )

        result = await asyncio.to_thread(
            service.predict_batch,
            request.features_list,
        )

        return {
            **result,
            "worker_id": self.manager.worker_id,
        }

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
            "deployment_id": request.deployment_id,
            "subject_key": request.subject_key,
            "subject_type": request.subject_type,
            "features": request.features,
        }

    async def _create_request_record(
            self,
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
        async with UnitOfWork() as uow:
            repo = RequestRepository(
                uow.session
            )

            repo.create_request(
                request_id=request_id,
                model_id=model_id,
                payload=payload,
                source="api",
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
                source=self._resolve_decision_source(
                    route.source
                ),
                deployment_id=route.deployment_id,
                experiment_id=route.experiment_id,
                variant_id=route.variant_id,
                assignment_id=route.assignment_id,
                subject_key=route.subject_key,
                subject_type=route.subject_type,
                strategy=self._string_value(
                    route.strategy
                ),
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

    async def _mark_request_failed(
            self,
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
    def _resolve_decision_source(
            value: str,
    ) -> DecisionStrategy:
        """解析决策来源

        参数：
            value: 路由来源

        返回：
            DecisionStrategy
        """
        if isinstance(
                value,
                DecisionStrategy,
        ):
            return value

        return DecisionStrategy(
            str(value)
        )

    @staticmethod
    def _string_value(
            value: Any,
    ) -> str | None:
        """转换字符串枚举或普通值"""
        if value is None:
            return None

        enum_value = getattr(
            value,
            "value",
            value,
        )

        return str(
            enum_value
        )

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

    async def _validate_service_environment(
            self,
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
