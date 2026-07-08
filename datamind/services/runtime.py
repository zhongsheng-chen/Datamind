# datamind/services/runtime.py

"""运行时控制服务

负责模型运行控制和状态查询。

核心功能：
  - load: 请求加载部署模型
  - unload: 请求卸载部署模型
  - reload: 请求重新加载部署模型
  - get_status: 查询部署运行状态
  - list_services: 查询运行服务列表

使用示例：
  from datamind.services.runtime import RuntimeController

  controller = RuntimeController()

  result = await controller.load(
      deployment_id="dep_a1b2c3d4",
      operator="admin",
  )

  status = await controller.get_status(
      deployment_id="dep_a1b2c3d4",
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
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)


class RuntimeController:
    """运行时控制服务

    负责管理模型部署的期望运行状态，
    并查询各 Worker 的实际运行状态。
    """

    async def load(
            self,
            *,
            deployment_id: str,
            operator: str = "system",
    ) -> dict[str, Any]:
        """请求加载部署模型

        设置部署的期望运行状态为 loaded。

        如果运行控制记录不存在，则创建控制记录，
        再将期望状态设置为 loaded；
        如果已经是 loaded，则保持幂等；
        如果当前为 unloaded，则切换为 loaded，
        并递增 generation。

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
                Control 与 Deployment 环境不一致
        """
        logger.info(
            "开始提交模型加载控制请求",
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

            deployment = await self._validate_deployment(
                deployment_repo=deployment_repo,
                deployment_id=deployment_id,
                require_active=True,
            )

            control = (
                await control_repo.get_deployment_control(
                    deployment_id
                )
            )

            if control is None:
                control = control_repo.create_control(
                    control_id=generate_random_id(
                        prefix="ctl"
                    ),
                    deployment_id=deployment_id,
                    environment=deployment.environment,
                    created_by=operator,
                )

            else:
                self._validate_control_environment(
                    control=control,
                    deployment=deployment,
                )

            control = control_repo.set_loaded(
                control,
                updated_by=operator,
            )

            control_info = self._control_to_dict(
                control
            )

        logger.info(
            "模型加载控制请求提交完成",
            deployment_id=deployment_id,
            environment=control_info["environment"],
            operator=operator,
            generation=control_info["generation"],
        )

        return {
            "action": "load",
            "accepted": True,
            "control": control_info,
        }

    async def unload(
            self,
            *,
            deployment_id: str,
            operator: str = "system",
    ) -> dict[str, Any]:
        """请求卸载部署模型

        设置部署的期望运行状态为 unloaded。

        如果运行控制记录不存在，则创建默认状态为
        unloaded 的控制记录；
        如果已经是 unloaded，则保持幂等；
        如果当前为 loaded，则切换为 unloaded，
        并递增 generation。

        参数：
            deployment_id: 部署 ID
            operator: 操作人

        返回：
            控制请求结果

        异常：
            DeploymentNotFoundError:
                部署不存在

            RuntimeError:
                Control 与 Deployment 环境不一致
        """
        logger.info(
            "开始提交模型卸载控制请求",
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

            deployment = await self._validate_deployment(
                deployment_repo=deployment_repo,
                deployment_id=deployment_id,
                require_active=False,
            )

            control = (
                await control_repo.get_deployment_control(
                    deployment_id
                )
            )

            if control is None:
                control = control_repo.create_control(
                    control_id=generate_random_id(
                        prefix="ctl"
                    ),
                    deployment_id=deployment_id,
                    environment=deployment.environment,
                    created_by=operator,
                )

            else:
                self._validate_control_environment(
                    control=control,
                    deployment=deployment,
                )

                control = control_repo.set_unloaded(
                    control,
                    updated_by=operator,
                )

            control_info = self._control_to_dict(
                control
            )

        logger.info(
            "模型卸载控制请求提交完成",
            deployment_id=deployment_id,
            environment=control_info["environment"],
            operator=operator,
            generation=control_info["generation"],
        )

        return {
            "action": "unload",
            "accepted": True,
            "control": control_info,
        }

    async def reload(
            self,
            *,
            deployment_id: str,
            operator: str = "system",
    ) -> dict[str, Any]:
        """请求重新加载部署模型

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

            deployment = await self._validate_deployment(
                deployment_repo=deployment_repo,
                deployment_id=deployment_id,
                require_active=True,
            )

            control = (
                await control_repo.get_deployment_control(
                    deployment_id
                )
            )

            if control is None:
                raise RuntimeError(
                    "运行控制记录不存在，"
                    "请先执行 service load: "
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
        """查询部署运行状态

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
                "status": self._status_value(
                    deployment.status
                ),
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
        """查询运行服务列表

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

          - loading_count:
              loading 状态的 Runtime 数量

          - loaded_count:
              loaded 状态的 Runtime 数量

          - unloaded_count:
              unloaded 状态的 Runtime 数量

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
                    "loading": 0,
                    "loaded": 0,
                    "unloaded": 0,
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
                        status_counts["loading"]
                        + status_counts["loaded"]
                        + status_counts["failed"]
                )

                runtime_count = len(
                    deployment_runtimes
                )

                result.append({
                    "control_id": control.control_id,
                    "deployment_id": control.deployment_id,
                    "environment": control.environment,
                    "desired_status": self._control_status_value(
                        control.desired_status
                    ),
                    "generation": int(
                        control.generation
                    ),
                    "worker_count": worker_count,
                    "runtime_count": runtime_count,
                    "loading_count": status_counts["loading"],
                    "loaded_count": status_counts["loaded"],
                    "unloaded_count": status_counts["unloaded"],
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
    async def _validate_deployment(
            *,
            deployment_repo: DeploymentRepository,
            deployment_id: str,
            require_active: bool,
    ) -> Deployment:
        """校验并返回部署对象

        参数：
            deployment_repo:
                部署仓储

            deployment_id:
                部署 ID

            require_active:
                是否要求部署必须为 active

        返回：
            Deployment 对象

        异常：
            DeploymentNotFoundError:
                部署不存在

            InvalidDeploymentStateError:
                部署状态不允许加载
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

        if not require_active:
            return deployment

        status = deployment.status

        if not isinstance(
                status,
                DeploymentStatus,
        ):
            status = DeploymentStatus(
                status
            )

        if status != DeploymentStatus.ACTIVE:
            raise InvalidDeploymentStateError(
                "部署不是启用状态，不能加载: "
                f"{deployment_id}"
            )

        return deployment

    @staticmethod
    def _validate_control_environment(
            *,
            control: Control,
            deployment: Deployment,
    ) -> None:
        """校验 Control 与 Deployment 环境一致性

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
        """转换 Control 为字典

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
            "desired_status": (
                RuntimeController._control_status_value(
                    control.desired_status
                )
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
        """转换 Runtime 为字典

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

    @staticmethod
    def _control_status_value(
            status: RuntimeControlStatus | str,
    ) -> str:
        """获取运行控制状态字符串"""
        if isinstance(
                status,
                RuntimeControlStatus,
        ):
            return status.value

        return str(
            status
        )

    @staticmethod
    def _status_value(
            status: DeploymentStatus | str,
    ) -> str:
        """获取部署状态字符串"""
        if isinstance(
                status,
                DeploymentStatus,
        ):
            return status.value

        return str(
            status
        )
