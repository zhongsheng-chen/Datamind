"""运行时管理器.

负责加载、卸载与重载各部署绑定的模型。

核心功能：
  - load: 加载指定部署绑定的模型
  - unload: 卸载指定部署绑定的模型
  - reload: 重新加载指定部署绑定的模型
  - get_status: 获取指定部署的运行状态

使用示例：
  from datamind.runtime.manager import RuntimeManager

  manager = RuntimeManager()

  runtime_model = await manager.load(
      deployment_id="dep_0123456789abcdef",
      operator="admin",
  )

  await manager.unload(
      deployment_id="dep_0123456789abcdef",
      operator="admin",
  )
"""

import asyncio
from time import perf_counter
from typing import Any

import structlog

from datamind.constants import Framework
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    DeploymentRepository,
    MetadataRepository,
    RuntimeRepository,
    VersionRepository,
)
from datamind.models.enums import DeploymentStatus
from datamind.models.errors import (
    BackendError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    ModelNotFoundError,
    RuntimeRouteError,
    VersionNotFoundError,
)
from datamind.runtime.loader import ModelLoader
from datamind.runtime.registry import RuntimeModel, RuntimeRegistry
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)

DEFAULT_WORKER_ID = "default"


class RuntimeManager:
    """运行时管理器."""

    def __init__(
            self,
            *,
            loader: ModelLoader | None = None,
            registry: RuntimeRegistry | None = None,
            worker_id: str = DEFAULT_WORKER_ID,
            service_id: str | None = None,
    ):
        """初始化运行时管理器.

        参数：
            loader: 模型加载器，默认使用 ModelLoader
            registry: 运行时模型注册表，默认使用 RuntimeRegistry
            worker_id: 运行 Worker 标识，单机模式默认 default
        """
        self.loader = loader or ModelLoader()
        self.registry = registry or RuntimeRegistry()
        self.service_id = service_id
        self.worker_id = worker_id
        self._operation_locks: dict[str, asyncio.Lock] = {}
        self._operation_locks_guard = asyncio.Lock()

    async def load(
            self,
            deployment_id: str,
            *,
            operator: str = "system",
    ) -> RuntimeModel:
        """串行加载指定部署绑定的模型."""
        operation_lock = await self._get_operation_lock(deployment_id)

        async with operation_lock:
            return await self._load(
                deployment_id,
                operator=operator,
                force=False,
            )

    async def _load(
            self,
            deployment_id: str,
            *,
            operator: str = "system",
            force: bool = False,
    ) -> RuntimeModel:
        """加载指定部署绑定的模型.

        参数：
            deployment_id: 部署 ID
            operator: 操作人
            force: 是否强制重新加载。为 True 时，如果模型已加载，会先卸载再重新加载

        返回：
            运行时模型对象

        异常：
            DeploymentNotFoundError: 部署不存在
            ModelNotFoundError: 模型元数据不存在
            VersionNotFoundError: 版本不存在
            InvalidDeploymentStateError: 部署状态不可加载
            BackendError: 模型加载失败
            RuntimeRouteError: 参数为空
        """
        self._validate_required("deployment_id", deployment_id)

        previous_runtime = self.registry.get(
            deployment_id,
            touch=False,
        )

        if previous_runtime is not None:
            if not force:
                logger.debug(
                    "模型已加载，直接返回",
                    deployment_id=deployment_id,
                )
                return previous_runtime

        started_at = perf_counter()
        operation_logger = self._operation_logger(deployment_id)
        operation_logger.debug(
            "开始重载模型" if force else "开始加载模型",
            deployment_id=deployment_id,
            operator=operator,
            worker_id=self.worker_id,
        )

        runtime_id = ""
        model_id = ""
        version_id = ""
        framework = ""
        model_type = ""
        task_type = ""
        bento_tag = ""
        model_path = None
        model_key = ""
        environment = ""
        rollout_type = ""
        role = None
        threshold = None
        runtime_context: dict[str, Any] = {}

        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(uow.session)
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            runtime_repo = RuntimeRepository(uow.session)

            deployment = await deployment_repo.get_deployment(
                deployment_id,
            )

            if deployment is None:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            if deployment.status != str(DeploymentStatus.ACTIVE):
                raise InvalidDeploymentStateError(
                    f"部署不是启用状态，不能加载: {deployment_id}"
                )

            metadata = await metadata_repo.get_model(
                model_id=deployment.model_id,
            )

            if metadata is None:
                raise ModelNotFoundError(
                    f"模型元数据不存在: {deployment.model_id}"
                )

            version = await version_repo.get_version(
                deployment.version_id,
            )

            if version is None:
                raise VersionNotFoundError(
                    f"版本不存在: {deployment.version_id}"
                )

            if not version.model_key:
                raise VersionNotFoundError(
                    "版本缺少模型制品存储键: "
                    f"{deployment.version_id}"
                )

            if not version.bento_tag:
                raise VersionNotFoundError(
                    "版本缺少 BentoML 模型标签: "
                    f"{deployment.version_id}"
                )

            runtime = await self._get_or_create_runtime(
                runtime_repo=runtime_repo,
                deployment_id=deployment.deployment_id,
                model_id=deployment.model_id,
                version_id=deployment.version_id,
                framework=deployment.framework,
                operator=operator,
            )

            runtime_id = runtime.runtime_id
            model_id = deployment.model_id
            version_id = deployment.version_id
            framework = deployment.framework
            model_type = metadata.model_type
            task_type = metadata.task_type
            bento_tag = version.bento_tag
            model_path = version.model_path
            model_key = version.model_key
            environment = deployment.environment
            rollout_type = deployment.rollout_type
            role = deployment.role
            threshold = deployment.threshold

            runtime_context = {
                "worker_id": self.worker_id,
                "bento_tag": bento_tag,
                "model_path": model_path,
                "model_key": model_key,
                "model_type": model_type,
                "task_type": task_type,
                "environment": environment,
                "rollout_type": rollout_type,
                "role": role,
                "threshold": threshold,
            }

            runtime_repo.mark_starting(
                runtime,
                started_by=operator,
                context=runtime_context,
            )

        runtime_model: RuntimeModel | None = None
        load_error: Exception | None = None

        try:
            model = await asyncio.to_thread(
                self.loader.load,
                framework=framework,
                bento_tag=bento_tag,
                model_key=model_key,
            )

            runtime_model = self.registry.register(
                deployment_id=deployment_id,
                model_id=model_id,
                version_id=version_id,
                framework=framework,
                model=model,
                metadata={
                    "runtime_id": runtime_id,
                    "worker_id": self.worker_id,
                    "bento_tag": bento_tag,
                    "model_path": model_path,
                    "model_key": model_key,
                    "model_type": model_type,
                    "task_type": task_type,
                    "environment": environment,
                    "rollout_type": rollout_type,
                    "role": role,
                    "threshold": threshold,
                },
            )

            async with UnitOfWork() as uow:
                runtime_repo = RuntimeRepository(uow.session)

                runtime = await runtime_repo.get_deployment_runtime(
                    deployment_id=deployment_id,
                    worker_id=self.worker_id,
                )

                if runtime is not None:
                    runtime_repo.mark_running(
                        runtime,
                        started_by=operator,
                        context=runtime_context,
                    )

            operation_logger.info(
                "模型重载成功" if force else "模型加载成功",
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
                environment=environment,
                deployment_id=deployment_id,
                model_id=model_id,
                version_id=version_id,
                bento_tag=bento_tag,
                model_key=model_key,
            )

        except Exception as exc:
            load_error = exc

            if previous_runtime is None:
                self.registry.unregister(
                    deployment_id,
                )
            else:
                self.registry.restore(
                    previous_runtime
                )

            async with UnitOfWork() as uow:
                runtime_repo = RuntimeRepository(uow.session)

                runtime = await runtime_repo.get_deployment_runtime(
                    deployment_id=deployment_id,
                    worker_id=self.worker_id,
                )

                if runtime is not None:
                    if previous_runtime is None:
                        runtime_repo.mark_failed(
                            runtime,
                            error=str(exc),
                            started_by=operator,
                            context=runtime_context,
                        )
                    else:
                        runtime_repo.mark_running(
                            runtime,
                            started_by=operator,
                            context={
                                **runtime_context,
                                "reload_error": str(exc),
                            },
                        )

            operation_logger.exception(
                "模型重载失败" if force else "模型加载失败",
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
                environment=environment,
                model_id=model_id,
                deployment_id=deployment_id,
                version_id=version_id,
                bento_tag=bento_tag,
                model_key=model_key,
            )

        if load_error is not None:
            raise BackendError(
                f"模型加载失败: {deployment_id}"
            ) from load_error

        if runtime_model is None:
            raise BackendError(
                f"模型加载失败: {deployment_id}"
            )

        return runtime_model

    async def unload(
            self,
            deployment_id: str,
            *,
            operator: str = "system",
    ) -> RuntimeModel | None:
        """串行卸载指定部署绑定的模型."""
        operation_lock = await self._get_operation_lock(deployment_id)

        async with operation_lock:
            return await self._unload(
                deployment_id,
                operator=operator,
            )

    async def _unload(
            self,
            deployment_id: str,
            *,
            operator: str = "system",
    ) -> RuntimeModel | None:
        """记录卸载异常，并保持原有异常传播语义."""
        started_at = perf_counter()
        previous = self.registry.get(deployment_id, touch=False)
        try:
            return await self._unload_model(deployment_id, operator=operator)
        except Exception:
            self._operation_logger(deployment_id).exception(
                "模型卸载失败",
                duration_ms=round((perf_counter() - started_at) * 1000, 3),
                **({
                    "model_id": previous.model_id,
                    "version_id": previous.version_id,
                    "environment": previous.metadata.get("environment"),
                } if previous is not None else {}),
            )
            raise

    async def _unload_model(
            self,
            deployment_id: str,
            *,
            operator: str = "system",
    ) -> RuntimeModel | None:
        """卸载指定部署绑定的模型.

        参数：
            deployment_id: 部署 ID
            operator: 操作人

        返回：
            被卸载的运行时模型对象；未加载时返回 None

        异常：
            RuntimeRouteError: 参数为空
        """
        self._validate_required("deployment_id", deployment_id)

        started_at = perf_counter()
        operation_logger = self._operation_logger(deployment_id)
        operation_logger.debug(
            "开始卸载模型",
            deployment_id=deployment_id,
            operator=operator,
            worker_id=self.worker_id,
        )

        async with UnitOfWork() as uow:
            runtime_repo = RuntimeRepository(uow.session)

            runtime = await runtime_repo.get_deployment_runtime(
                deployment_id=deployment_id,
                worker_id=self.worker_id,
            )

            if runtime is not None:
                runtime_repo.mark_stopping(
                    runtime,
                    stopped_by=operator,
                )

        runtime_model = self.registry.unregister(
            deployment_id,
        )

        async with UnitOfWork() as uow:
            runtime_repo = RuntimeRepository(uow.session)
            runtime = await runtime_repo.get_deployment_runtime(
                deployment_id=deployment_id,
                worker_id=self.worker_id,
            )

            if runtime is not None:
                runtime_repo.mark_stopped(
                    runtime,
                    stopped_by=operator,
                    context={
                        "worker_id": self.worker_id,
                    },
                )

        log_result = operation_logger.info if runtime_model is not None else operation_logger.debug
        log_result(
            "模型卸载完成",
            deployment_id=deployment_id,
            unloaded=runtime_model is not None,
            duration_ms=round((perf_counter() - started_at) * 1000, 3),
            **({
                "model_id": runtime_model.model_id,
                "version_id": runtime_model.version_id,
                "environment": runtime_model.metadata.get("environment"),
            } if runtime_model is not None else {}),
        )

        return runtime_model

    async def reload(
            self,
            deployment_id: str,
            *,
            operator: str = "system",
    ) -> RuntimeModel:
        """重新加载指定部署绑定的模型.

        参数：
            deployment_id: 部署 ID
            operator: 操作人

        返回：
            重新加载后的运行时模型对象
        """
        operation_lock = await self._get_operation_lock(deployment_id)

        async with operation_lock:
            return await self._load(
                deployment_id,
                operator=operator,
                force=True,
            )

    async def get_status(
            self,
            deployment_id: str,
    ) -> dict:
        """查看指定部署的运行状态.

        参数：
            deployment_id: 部署 ID

        返回：
            运行状态字典

        异常：
            RuntimeRouteError: 参数为空
        """
        self._validate_required("deployment_id", deployment_id)

        runtime_model = self.registry.get(
            deployment_id,
            touch=False,
        )

        runtime_info = None

        async with UnitOfWork() as uow:
            runtime_repo = RuntimeRepository(uow.session)

            runtime = await runtime_repo.get_deployment_runtime(
                deployment_id=deployment_id,
                worker_id=self.worker_id,
            )

            if runtime is not None:
                runtime_info = {
                    "runtime_id": runtime.runtime_id,
                    "deployment_id": runtime.deployment_id,
                    "model_id": runtime.model_id,
                    "version_id": runtime.version_id,
                    "framework": runtime.framework,
                    "status": runtime.status,
                    "worker_id": runtime.worker_id,
                    "loaded_at": runtime.loaded_at.isoformat() if runtime.loaded_at else None,
                    "unloaded_at": runtime.unloaded_at.isoformat() if runtime.unloaded_at else None,
                    "last_heartbeat_at": (
                        runtime.last_heartbeat_at.isoformat()
                        if runtime.last_heartbeat_at
                        else None
                    ),
                    "error": runtime.error,
                    "context": runtime.context,
                }

        return {
            "deployment_id": deployment_id,
            "worker_id": self.worker_id,
            "loaded_in_memory": runtime_model is not None,
            "memory": runtime_model.to_dict() if runtime_model is not None else None,
            "runtime": runtime_info,
        }

    async def _get_or_create_runtime(
            self,
            *,
            runtime_repo: RuntimeRepository,
            deployment_id: str,
            model_id: str,
            version_id: str,
            framework: str,
            operator: str,
    ):
        """获取或创建运行记录."""
        runtime = await runtime_repo.get_deployment_runtime(
            deployment_id=deployment_id,
            worker_id=self.worker_id,
        )

        if runtime is not None:
            runtime.model_id = model_id
            runtime.version_id = version_id
            runtime.framework = framework
            runtime.started_by = operator

            return runtime

        return runtime_repo.create_runtime(
            runtime_id=generate_random_id(
                prefix="rtm"
            ),
            deployment_id=deployment_id,
            model_id=model_id,
            version_id=version_id,
            framework=Framework(
                framework
            ),
            worker_id=self.worker_id,
            started_by=operator,
            context={
                "worker_id": self.worker_id,
            },
        )

    def _operation_logger(self, deployment_id: str):
        """关联当前 Worker 及协调操作的实际上下文."""
        context = structlog.contextvars.get_contextvars()
        if self.service_id is not None:
            context = {**context, "service_id": self.service_id}
        return logger.bind(
            worker_id=self.worker_id,
            deployment_id=deployment_id,
            **{
                key: context[key]
                for key in ("generation", "service_id", "environment")
                if context.get(key) is not None
            },
        )

    async def _get_operation_lock(
            self,
            deployment_id: str,
    ) -> asyncio.Lock:
        """获取指定部署的异步操作锁."""
        async with self._operation_locks_guard:
            return self._operation_locks.setdefault(
                deployment_id,
                asyncio.Lock(),
            )

    @staticmethod
    def _validate_required(
            name: str,
            value: str,
    ) -> None:
        """校验必填字符串参数.

        参数：
            name: 参数名称
            value: 参数值

        异常：
            RuntimeRouteError: 参数为空
        """
        if not value:
            raise RuntimeRouteError(f"{name} 不能为空")
