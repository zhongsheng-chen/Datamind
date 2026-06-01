# datamind/services/deployer.py

"""模型部署器

负责模型部署生命周期管理，包括部署实例的创建、启用、禁用与查询。

核心功能：
  - create_deployment: 创建部署实例
  - enable_deployment: 启用部署
  - disable_deployment: 禁用部署

使用示例：
  from datamind.services.deployer import ModelDeployer

  deployer = ModelDeployer()

  # 创建分类模型部署
  result = await deployer.create_deployment(
      model_id="mdl_xxx",
      version_id="ver_xxx",
      framework="sklearn",
      task_type="classification",
      environment="production",
      config={
          "threshold": 0.5
      },
      deployed_by="system"
  )

  # 创建评分卡模型部署
  result = await deployer.create_deployment(
      model_id="mdl_xxx",
      version_id="ver_xxx",
      framework="sklearn",
      task_type="scorecard",
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

import structlog
from typing import Any

from datamind.utils.generator import generate_random_id
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    MetadataRepository,
    VersionRepository,
    DeploymentRepository
)
from datamind.models.resolver import ModelResolver
from datamind.models.enums import DeploymentStatus
from datamind.models.errors import (
    DeploymentError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
)

from datamind.config.classification import ClassificationConfig
from datamind.config.scorecard import ScorecardConfig

logger = structlog.get_logger(__name__)


class ModelDeployer:
    """模型部署器"""

    def __init__(self) -> None:
        """初始化模型部署器"""
        self.logger = logger

    async def create_deployment(
        self,
        *,
        model_id: str | None = None,
        name: str | None = None,
        version_id: str | None = None,
        version: str | None = None,
        environment: str = "production",
        rollout_type: str = "full",
        role: str = "champion",
        config: dict | None = None,
        description: str | None = None,
        endpoint: str | None = None,
        deployed_by: str | None = None,
    ) -> dict[str, Any] | None:
        """创建部署

        参数：
            model_id: 模型 ID（可选）
            name: 模型名称（可选）
            version_id: 版本 ID（可选）
            version: 版本号（可选）
            environment: 部署环境
            rollout_type: 发布类型
            role: 部署角色
            config: 运行时配置（可选）
            description: 部署说明（可选）
            endpoint: 服务地址（可选）
            deployed_by: 部署人（可选）

        返回：
            部署信息字典，包含 deployment_id、model_id、version_id、status
        """
        deployment_id = generate_random_id(prefix="dep")

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

            ver = await resolver.resolve_version(
                model_id=model.model_id,
                version_id=version_id,
                version=version,
            )

            self._validate_config(
                task_type=model.task_type,
                config=config,
            )

            deployment = deployment_repo.create_deployment(
                deployment_id=deployment_id,
                model_id=model.model_id,
                version_id=ver.version_id,
                framework=model.framework,
                environment=environment,
                rollout_type=rollout_type,
                role=role,
                config=config,
                description=description,
                endpoint=endpoint,
                deployed_by=deployed_by,
            )

            self.logger.info(
                "创建部署成功",
                deployment_id=deployment_id,
                model_id=model.model_id,
                version_id=ver.version_id,
            )

            return {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "status": deployment.status,
            }

        return None

    async def enable_deployment(
        self,
        *,
        deployment_id: str,
        updated_by: str | None = None,
    ) -> dict[str, Any] | None:
        """启用部署

        参数：
            deployment_id: 部署 ID
            updated_by: 更新人（可选）

        返回：
            部署信息字典，包含 deployment_id、status

        异常：
            DeploymentNotFoundError: 部署不存在
            InvalidDeploymentStateError: 部署已处于启用状态
        """
        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployment = await repo.get_deployment(deployment_id)
            if not deployment:
                raise DeploymentNotFoundError(f"部署不存在: {deployment_id}")

            if deployment.status == DeploymentStatus.ACTIVE:
                raise InvalidDeploymentStateError(
                    f"部署已处于 ACTIVE 状态: {deployment_id}"
                )

            repo.activate_deployment(
                deployment,
                updated_by=updated_by,
            )

            self.logger.info(
                "启用部署成功",
                deployment_id=deployment_id,
            )

            return {
                "deployment_id": deployment_id,
                "status": deployment.status,
            }

        return None

    async def disable_deployment(
        self,
        *,
        deployment_id: str,
        updated_by: str | None = None,
    ) -> dict[str, Any] | None:
        """禁用部署

        参数：
            deployment_id: 部署 ID
            updated_by: 更新人（可选）

        返回：
            部署信息字典，包含 deployment_id、status

        异常：
            DeploymentNotFoundError: 部署不存在
            InvalidDeploymentStateError: 部署已处于禁用状态
        """
        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployment = await repo.get_deployment(deployment_id)
            if not deployment:
                raise DeploymentNotFoundError(f"部署不存在: {deployment_id}")

            if deployment.status == DeploymentStatus.INACTIVE:
                raise InvalidDeploymentStateError(
                    f"部署已处于 INACTIVE 状态: {deployment_id}"
                )

            repo.deactivate_deployment(
                deployment,
                updated_by=updated_by,
            )

            self.logger.info(
                "禁用部署成功",
                deployment_id=deployment_id,
            )

            return {
                "deployment_id": deployment_id,
                "status": deployment.status,
            }

        return None

    def _validate_config(
        self,
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

            raise DeploymentError(f"不支持的任务类型: {task_type}")

        except Exception as e:
            raise DeploymentError(f"配置校验失败: {e}") from e