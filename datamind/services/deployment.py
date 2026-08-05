# datamind/services/deployment.py

"""模型部署服务

负责模型部署生命周期管理，包括部署实例的创建、启用与禁用。

核心功能：
  - create_deployment: 创建部署实例
  - enable_deployment: 启用部署
  - disable_deployment: 禁用部署

使用示例：
  from datamind.services.deployment import DeploymentLifecycleService

  service = DeploymentLifecycleService()

  # 创建分类模型部署
  result = await service.create_deployment(
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      environment="production",
      config={
          "threshold": 0.5
      },
      deployed_by="system"
  )

  # 创建评分卡模型部署
  result = await service.create_deployment(
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      environment="production",
      config={
          "base_score": 600.0,
          "base_odds": 50.0,
          "pdo": 20.0,
          "min_score": 0,
          "max_score": 1000
      },
      deployed_by="system"
  )
"""

from typing import Any

import structlog

from datamind.config.classification import ClassificationConfig
from datamind.config.scorecard import ScorecardConfig
from datamind.constants import Environment
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    ControlRepository,
    DeploymentRepository,
    ExperimentRepository,
    MetadataRepository,
    VariantRepository,
    VersionRepository,
)
from datamind.models.enums import (
    DeploymentStatus,
    ExperimentVariantStatus,
    MetadataStatus,
    VersionStatus,
)
from datamind.models.errors import (
    DeploymentError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
)
from datamind.models.guard import ModelGuard
from datamind.models.resolver import ModelResolver
from datamind.utils.generator import generate_random_id

logger = structlog.get_logger(__name__)


class DeploymentLifecycleService:
    """模型部署服务"""

    async def create_deployment(
            self,
            *,
            name: str | None = None,
            model_id: str | None = None,
            version_id: str | None = None,
            version: str | None = None,
            environment: str = "production",
            rollout_type: str = "full",
            role: str = "champion",
            config: dict | None = None,
            description: str | None = None,
            deployed_by: str | None = None,
    ) -> dict[str, Any]:
        """创建部署

        参数：
            name: 模型名称（可选）
            model_id: 模型 ID（可选）
            version_id: 版本 ID（可选）
            version: 版本号（可选）
            environment: 部署环境
            rollout_type: 发布类型
            role: 部署角色
            config: 运行时配置（可选）
            description: 部署说明（可选）
            deployed_by: 部署人（可选）

        返回：
            部署信息字典，包含：
                - deployment_id
                - model_id
                - version_id
                - environment
                - rollout_type
                - role
                - status
        """
        deployment_id = generate_random_id(
            prefix="dep"
        )

        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            model = await resolver.resolve_model(
                model_id=model_id,
                name=name,
            )

            if not model:
                raise DeploymentError("模型不存在")

            ModelGuard.validate_model_deployable(model.status)

            ver = await resolver.resolve_version(
                model_id=model.model_id,
                version_id=version_id,
                version=version,
            )

            if not ver:
                raise DeploymentError("模型版本不存在")

            ModelGuard.validate_version_deployable(ver.status)

            self._validate_config(
                task_type=model.task_type,
                config=config,
            )

            deployment = deployment_repo.create_deployment(
                deployment_id=deployment_id,
                model_id=model.model_id,
                version_id=ver.version_id,
                framework=model.framework,
                environment=Environment(environment),
                rollout_type=rollout_type,
                role=role,
                config=config,
                description=description,
                deployed_by=deployed_by,
            )

            logger.info(
                "创建部署成功",
                deployment_id=deployment_id,
                model_id=model.model_id,
                version_id=ver.version_id,
            )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
            }

    async def enable_deployment(
            self,
            *,
            deployment_id: str,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """启用部署

        参数：
            deployment_id: 部署 ID
            updated_by: 更新人（可选）

        返回：
            部署信息字典，包含：
                - deployment_id
                - model_id
                - version_id
                - environment
                - rollout_type
                - role
                - status

        异常：
            DeploymentNotFoundError: 部署不存在
            InvalidDeploymentStateError: 部署已处于启用状态
        """
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=MetadataRepository(uow.session),
                version_repo=VersionRepository(uow.session),
            )

            deployment = await deployment_repo.get_deployment(deployment_id)
            if not deployment:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            model = await resolver.resolve_model(model_id=deployment.model_id)
            if not model:
                raise DeploymentError("模型不存在")

            current_status = DeploymentStatus(deployment.status)
            metadata_status = MetadataStatus(model.status)

            version = await resolver.resolve_version(
                model_id=deployment.model_id,
                version_id=deployment.version_id,
            )

            ModelGuard.validate_version_deployable(
                VersionStatus(version.status)
            )

            ModelGuard.validate_enable_deployment(
                current=current_status,
                metadata_status=metadata_status,
            )

            deployment_repo.activate_deployment(
                deployment,
                updated_by=updated_by,
            )

            logger.info(
                "启用部署成功",
                deployment_id=deployment_id,
                model_id=deployment.model_id,
            )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
            }

    async def disable_deployment(
            self,
            *,
            deployment_id: str,
            updated_by: str | None = None,
    ) -> dict[str, Any]:
        """禁用部署

        参数：
            deployment_id: 部署 ID
            updated_by: 更新人（可选）

        返回：
            部署信息字典，包含：
                - deployment_id
                - model_id
                - version_id
                - environment
                - rollout_type
                - role
                - status

        异常：
            DeploymentNotFoundError: 部署不存在
            InvalidDeploymentStateError: 部署已处于禁用状态
        """
        async with UnitOfWork() as uow:
            deployment_repo = DeploymentRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=MetadataRepository(uow.session),
                version_repo=VersionRepository(uow.session),
            )

            deployment = await deployment_repo.get_deployment(deployment_id)
            if not deployment:
                raise DeploymentNotFoundError(
                    f"部署不存在: {deployment_id}"
                )

            model = await resolver.resolve_model(model_id=deployment.model_id)
            if not model:
                raise DeploymentError("模型不存在")

            current_status = DeploymentStatus(deployment.status)

            ModelGuard.validate_disable_deployment(
                current=current_status,
            )

            experiment_repo = ExperimentRepository(
                uow.session
            )
            running_experiment = (
                await experiment_repo.get_running_experiment(
                    model_id=deployment.model_id,
                    environment=Environment(
                        deployment.environment
                    ),
                )
            )

            if running_experiment is not None:
                variant_repo = VariantRepository(
                    uow.session
                )
                variants = await variant_repo.list_variants(
                    experiment_id=running_experiment.experiment_id,
                    deployment_id=deployment_id,
                    status=ExperimentVariantStatus.ACTIVE,
                    limit=1,
                )

                if variants:
                    raise InvalidDeploymentStateError(
                        "部署正在被运行中的实验引用，不能禁用\n"
                        f"部署 ID: {deployment_id}\n"
                        "实验 ID: "
                        f"{running_experiment.experiment_id}"
                    )

            deployment_repo.deactivate_deployment(
                deployment,
                updated_by=updated_by,
            )

            control_repo = ControlRepository(uow.session)
            control = await control_repo.get_deployment_control(
                deployment_id
            )

            if control is None:
                control_repo.create_control(
                    control_id=generate_random_id(prefix="ctl"),
                    deployment_id=deployment_id,
                    environment=Environment(
                        deployment.environment
                    ),
                    created_by=updated_by,
                )
            else:
                control_repo.set_unloaded(
                    control,
                    updated_by=updated_by,
                )

            logger.info(
                "禁用部署成功",
                deployment_id=deployment_id,
                model_id=deployment.model_id,
            )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
            }

    @staticmethod
    def _validate_config(
            *,
            task_type: str,
            config: dict | None,
    ) -> None:
        """配置校验（内部方法）

        参数：
            task_type: 任务类型
            config: 配置字典

        异常：
            DeploymentError: 不支持的任务类型或配置校验失败
        """
        if not config:
            return

        try:
            if task_type == "classification":
                ClassificationConfig.model_validate(config)
                return

            if task_type == "scoring":
                ScorecardConfig.model_validate(config)
                return

            raise DeploymentError(
                f"不支持的任务类型: {task_type}"
            )

        except DeploymentError:
            raise
        except Exception as exc:
            raise DeploymentError(
                f"配置校验失败: {exc}"
            ) from exc
