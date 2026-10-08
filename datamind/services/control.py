"""运行时控制服务.

负责部署重载和运行状态查询。

核心功能：
  - reload: 请求重新加载部署模型
  - get_status: 查询部署运行状态
  - list_services: 查询运行服务列表

使用示例：
  from datamind.services.control import RuntimeControlService

  service = RuntimeControlService()

  result = await service.reload(
      deployment_id="dep_0123456789abcdef",
      operator="admin",
  )

  status = await service.get_status(
      deployment_id="dep_0123456789abcdef",
  )
"""

from typing import Any

import structlog

from datamind.db.core import UnitOfWork
from datamind.db.models.controls import Control
from datamind.db.models.deployments import Deployment
from datamind.db.models.runtimes import Runtime
from datamind.db.repositories import (
    ControlRepository,
    DeploymentRepository,
    RuntimeRepository,
)
from datamind.models.enums import (
    DeploymentStatus,
    RuntimeControlStatus,
)
from datamind.models.errors import (
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
)

logger = structlog.get_logger(__name__)


class RuntimeControlService:
    """运行时控制服务.

    负责提交部署重载请求，并查询各 Worker 的实际运行状态。
    """

    async def reload(
            self,
            *,
            deployment_id: str,
            operator: str = "system",
    ) -> dict[str, Any]:
        """请求重新加载部署模型.

        保持 desired_status 为 loaded，
        通过递增 generation 通知所属环境的所有 Worker
        重新加载模型。

        参数：
            deployment_id: 部署 ID
            operator: 操作人

        返回：
            控制请求结果

        异常：
            DeploymentNotFoundError:
                部署不存在

            InvalidDeploymentStateError:
                部署不是启用状态

            RuntimeError:
                运行控制记录不存在，
                或 Control 与 Deployment 环境不一致

            ValueError:
                当前期望状态不是 loaded
        """
        logger.info(
            "开始提交模型重新加载控制请求",
            deployment_id=deployment_id,
            operator=operator,
        )

        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )

            control_repo = ControlRepository(
                uow.session
            )

            deployment = await self._validate_active_deployment(
                deployment_repo=deployment_repo,
                deployment_id=deployment_id,
            )

            control = (
                await control_repo.get_deployment_control(
                    deployment_id
                )
            )

            if control is None:
                raise RuntimeError(
                    "运行控制记录不存在，"
                    "请先停用后重新启用部署: "
                    f"{deployment_id}"
                )

            self._validate_control_environment(
                control=control,
                deployment=deployment,
            )

            control = control_repo.request_reload(
                control,
                updated_by=operator,
            )

            await uow.session.flush()
            await uow.session.refresh(control)

            control_info = self._control_to_dict(
                control
            )

        logger.info(
            "模型重新加载控制请求提交完成",
            deployment_id=deployment_id,
            environment=control_info["environment"],
            operator=operator,
            generation=control_info["generation"],
        )

        return {
            "action": "reload",
            "accepted": True,
            "control": control_info,
        }

    async def get_status(
            self,
            *,
            deployment_id: str,
    ) -> dict[str, Any]:
        """查询部署运行状态.

        查询：
          - Deployment 基本信息
          - Control 期望运行状态
          - 所有 Worker 的 Runtime 实际状态

        参数：
            deployment_id: 部署 ID

        返回：
            部署运行状态

        异常：
            DeploymentNotFoundError:
                部署不存在
        """
        logger.info(
            "开始查询部署运行状态",
            deployment_id=deployment_id,
        )

        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(
                uow.session
            )

            control_repo = ControlRepository(
                uow.session
            )

            runtime_repo = RuntimeRepository(
                uow.session
            )

            deployment = (
                await deployment_repo.get_deployment(
                    deployment_id
                )
            )

            if deployment is None:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            control = (
                await control_repo.get_deployment_control(
                    deployment_id
                )
            )

            runtimes = await runtime_repo.list_runtimes(
                deployment_id=deployment_id
            )

            deployment_info = {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "framework": deployment.framework,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
            }

            control_info = (
                self._control_to_dict(
                    control
                )
                if control is not None
                else None
            )

            runtime_info = [
                self._runtime_to_dict(
                    runtime
                )
                for runtime in runtimes
            ]

        return {
            "deployment": deployment_info,
            "control": control_info,
            "runtimes": runtime_info,
        }

    async def list_services(
            self,
            *,
            environment: str | None = None,
            desired_status: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """查询运行服务列表.

        以 controls 表中的运行控制记录为主，
        汇总每个 Deployment 的 Worker 和 Runtime 状态。

        参数：
            environment:
                按运行环境过滤

            desired_status:
                按期望状态过滤，可选值 loaded / unloaded

            limit:
                返回数量限制

            offset:
                分页偏移量

        返回：
            运行服务状态列表

        统计字段：
          - worker_count:
              当前非 unloaded 状态的 Worker 数量

          - runtime_count:
              Runtime 记录总数，包括历史记录

          - starting_count:
              starting 状态的 Runtime 数量

          - running_count:
              running 状态的 Runtime 数量

          - stopping_count:
              stopping 状态的 Runtime 数量
          - stopped_count:
              stopped 状态的 Runtime 数量

          - failed_count:
              failed 状态的 Runtime 数量

        异常：
            ValueError:
                查询参数不合法
        """
        if desired_status is not None:
            desired_status_value = RuntimeControlStatus(
                desired_status
            )
        else:
            desired_status_value = None

        if limit is not None and limit <= 0:
            raise ValueError(
                "limit 必须大于 0"
            )

        if offset is not None and offset < 0:
            raise ValueError(
                "offset 不能小于 0"
            )

        filters = {}

        if environment is not None:
            filters["environment"] = environment

        if desired_status_value is not None:
            filters["desired_status"] = (
                desired_status_value
            )

        logger.info(
            "开始查询运行服务列表",
            environment=environment,
            desired_status=desired_status,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            control_repo = ControlRepository(
                uow.session
            )

            runtime_repo = RuntimeRepository(
                uow.session
            )

            controls = await control_repo.list_controls(
                limit=limit,
                offset=offset,
                **filters,
            )

            runtimes = await runtime_repo.list_runtimes()

            runtime_map: dict[
                str,
                list[Runtime],
            ] = {}

            for runtime in runtimes:
                runtime_map.setdefault(
                    runtime.deployment_id,
                    [],
                ).append(
                    runtime
                )

            result = []

            for control in controls:
                deployment_runtimes = runtime_map.get(
                    control.deployment_id,
                    [],
                )

                status_counts = {
                    "starting": 0,
                    "running": 0,
                    "stopping": 0,
                    "stopped": 0,
                    "failed": 0,
                }

                for runtime in deployment_runtimes:
                    runtime_status = str(
                        runtime.status
                    )

                    if runtime_status in status_counts:
                        status_counts[
                            runtime_status
                        ] += 1

                worker_count = (
                        status_counts["starting"]
                        + status_counts["running"]
                        + status_counts["stopping"]
                        + status_counts["failed"]
                )

                runtime_count = len(
                    deployment_runtimes
                )

                result.append({
                    "control_id": control.control_id,
                    "deployment_id": control.deployment_id,
                    "environment": control.environment,
                    "desired_status": str(
                        control.desired_status
                    ),
                    "generation": int(
                        control.generation
                    ),
                    "worker_count": worker_count,
                    "runtime_count": runtime_count,
                    "starting_count": status_counts["starting"],
                    "running_count": status_counts["running"],
                    "stopping_count": status_counts["stopping"],
                    "stopped_count": status_counts["stopped"],
                    "failed_count": status_counts["failed"],
                    "updated_by": control.updated_by,
                    "updated_at": (
                        control.updated_at.isoformat()
                        if control.updated_at
                        else None
                    ),
                    "runtimes": [
                        self._runtime_to_dict(
                            runtime
                        )
                        for runtime
                        in deployment_runtimes
                    ],
                })

        return result

    @staticmethod
    async def _validate_active_deployment(
            *,
            deployment_repo: DeploymentRepository,
            deployment_id: str,
    ) -> Deployment:
        """校验并返回启用部署.

        参数：
            deployment_repo:
                部署仓储

            deployment_id:
                部署 ID

        返回：
            Deployment 对象

        异常：
            DeploymentNotFoundError:
                部署不存在

            InvalidDeploymentStateError:
                部署状态不允许执行控制操作
        """
        deployment = (
            await deployment_repo.get_deployment(
                deployment_id
            )
        )

        if deployment is None:
            raise DeploymentNotFoundError(
                f"部署不存在: {deployment_id}"
            )

        current_status = DeploymentStatus(
            deployment.status
        )

        if current_status is DeploymentStatus.ACTIVE:
            return deployment

        raise InvalidDeploymentStateError(
            "部署不是启用状态，不能重新加载: "
            f"{deployment_id}"
        )

    @staticmethod
    def _validate_control_environment(
            *,
            control: Control,
            deployment: Deployment,
    ) -> None:
        """校验 Control 与 Deployment 环境一致性.

        参数：
            control:
                运行控制对象

            deployment:
                部署对象

        异常：
            RuntimeError:
                Control 与 Deployment 环境不一致
        """
        if (
                control.environment
                == deployment.environment
        ):
            return

        raise RuntimeError(
            "运行控制环境与部署环境不一致: "
            f"deployment_id={deployment.deployment_id}, "
            f"control_environment={control.environment}, "
            f"deployment_environment={deployment.environment}"
        )

    @staticmethod
    def _control_to_dict(
            control: Control,
    ) -> dict[str, Any]:
        """转换 Control 为字典.

        参数：
            control: 运行控制对象

        返回：
            运行控制信息字典
        """
        return {
            "control_id": control.control_id,
            "deployment_id": (
                control.deployment_id
            ),
            "environment": control.environment,
            "desired_status": str(
                control.desired_status
            ),
            "generation": int(
                control.generation
            ),
            "created_by": control.created_by,
            "updated_by": control.updated_by,
            "created_at": (
                control.created_at.isoformat()
                if control.created_at
                else None
            ),
            "updated_at": (
                control.updated_at.isoformat()
                if control.updated_at
                else None
            ),
        }

    @staticmethod
    def _runtime_to_dict(
            runtime: Runtime,
    ) -> dict[str, Any]:
        """转换 Runtime 为字典.

        参数：
            runtime: Worker 运行记录

        返回：
            Worker 运行状态字典
        """
        return {
            "runtime_id": runtime.runtime_id,
            "deployment_id": (
                runtime.deployment_id
            ),
            "model_id": runtime.model_id,
            "version_id": runtime.version_id,
            "framework": runtime.framework,
            "status": runtime.status,
            "worker_id": runtime.worker_id,
            "applied_generation": (
                runtime.applied_generation
            ),
            "loaded_at": (
                runtime.loaded_at.isoformat()
                if runtime.loaded_at
                else None
            ),
            "unloaded_at": (
                runtime.unloaded_at.isoformat()
                if runtime.unloaded_at
                else None
            ),
            "last_heartbeat_at": (
                runtime.last_heartbeat_at.isoformat()
                if runtime.last_heartbeat_at
                else None
            ),
            "error": runtime.error,
            "context": runtime.context,
        }
