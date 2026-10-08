"""运行时部署控制接口.

提供部署重载和 Worker 运行状态查询接口。

核心功能：
  - RuntimeControlMixin: 提供运行时部署控制相关的 BentoML 接口

使用示例：
  from datamind.runtime.server.control import RuntimeControlMixin

  class RuntimeService(RuntimeControlMixin):
      pass
"""

from collections.abc import Awaitable, Callable
from typing import Any

import bentoml
from structlog.typing import FilteringBoundLogger

from datamind.config import get_service_config
from datamind.models.errors import InvalidDeploymentStateError
from datamind.runtime.manager import RuntimeManager
from datamind.runtime.reconciler import RuntimeReconciler
from datamind.runtime.server.cache import ServiceCacheEntry
from datamind.runtime.server.errors import (
    ServiceDeploymentNotFoundError,
    ServiceEnvironmentMismatchError,
)
from datamind.runtime.server.schemas import ControlRequest, DeploymentRequest
from datamind.runtime.serving.base import BaseRuntimeService
from datamind.services import RuntimeControlService
from datamind.utils.generator import generate_random_id

service_config = get_service_config()


class RuntimeControlMixin:
    """部署重载与运行状态查询接口能力."""

    controller: RuntimeControlService
    manager: RuntimeManager
    reconciler: RuntimeReconciler
    _logger: FilteringBoundLogger
    _service_cache: dict[str, ServiceCacheEntry]
    _execute_secured: Callable[..., Awaitable[dict[str, Any]]]
    _validate_service_environment: Callable[..., Awaitable[None]]
    _build_error_response: Callable[..., dict[str, Any]]
    _get_service: Callable[[str], Awaitable[BaseRuntimeService]]
    _build_service_info: Callable[[BaseRuntimeService], dict[str, Any]]

    @bentoml.api(
        route="/admin/reload",
    )
    async def reload(
            self,
            request: ControlRequest,
            ctx: bentoml.Context,
    ) -> dict[str, Any]:
        """提交已认证的部署重载请求."""
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
        """请求重新加载部署模型.

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
                InvalidDeploymentStateError,
                RuntimeError,
                ValueError,
        ) as exc:
            self._logger.warning(
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
            self._logger.exception(
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
        """查询已认证的部署运行状态."""
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
        """查询部署运行状态.

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

            local_status = await self.manager.get_status(
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
                RuntimeError,
                ValueError,
        ) as exc:
            self._logger.warning(
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
            self._logger.exception(
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
        """查询当前 Worker 的已认证服务列表."""
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
        """查询当前 Worker 服务状态.

        返回：
            当前 Worker 运行时状态
        """
        return {
            "worker_id": self.manager.worker_id,
            "environment": (
                service_config.environment
            ),
            "runtime_count": (
                len(self.manager.registry)
            ),
            "service_cache_count": len(
                self._service_cache
            ),
            "applied_generations": (
                self.reconciler.get_applied_generations()
            ),
            "runtimes": (
                self.manager.registry.snapshot()
            ),
            "services": [
                self._build_service_info(
                    entry.service
                )
                for entry
                in self._service_cache.values()
            ],
        }
