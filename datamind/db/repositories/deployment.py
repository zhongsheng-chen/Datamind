# datamind/db/repositories/deployment.py

"""部署仓储

提供模型部署记录的查询与管理能力。

核心功能：
  - get_deployment: 获取部署记录
  - list_active_deployments: 获取活跃部署记录列表
  - list_traffic_deployments: 获取有流量的部署记录列表
  - create_deployment: 创建部署
  - update_deployment: 更新部署
  - activate_deployment: 启用部署
  - deactivate_deployment: 停用部署

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import DeploymentRepository, DeploymentPatch

  async with UnitOfWork() as uow:
      repo = DeploymentRepository(uow.session)

      deployment = await repo.create_deployment(
          deployment_id="dep_a1b2c3d4",
          model_id="mdl_a1b2c3d4",
          version_id="ver_a1b2c3d4",
          framework="sklearn",
          status="active",
          environment="production",
          rollout_type="full",
          variant="primary",
          traffic_ratio=1.0,
          deployed_by="system"
      )
"""

from datetime import datetime, timezone
from dataclasses import dataclass, fields
from sqlalchemy import select

from datamind.db.models.deployments import Deployment
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import DeploymentStatus


@dataclass(slots=True)
class DeploymentPatch:
    """部署更新结构

    属性：
        framework: 框架类型
        environment: 部署环境
        rollout_type: 发布类型
        variant: 变体标识
        traffic_ratio: 流量占比
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        deployed_by: 部署人
        description: 部署描述
    """
    framework: str | None = None
    environment: str | None = None
    rollout_type: str | None = None
    variant: str | None = None
    traffic_ratio: float | None = None
    effective_from: object | None = None
    effective_to: object | None = None
    deployed_by: str | None = None
    description: str | None = None


class DeploymentRepository(BaseRepository):
    """部署仓储"""

    async def get_deployment(self, deployment_id: str) -> Deployment | None:
        """获取部署记录

        参数：
            deployment_id: 部署 ID

        返回：
            部署记录对象，不存在时返回 None
        """
        stmt = select(Deployment).where(Deployment.deployment_id == deployment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_deployments(self, model_id: str) -> list[Deployment]:
        """获取活跃部署记录列表

        参数：
            model_id: 模型 ID

        返回：
            活跃部署记录列表
        """
        stmt = select(Deployment).where(
            Deployment.model_id == model_id,
            Deployment.status == DeploymentStatus.ACTIVE,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_traffic_deployments(self, model_id: str) -> list[Deployment]:
        """获取有流量的部署记录列表

        参数：
            model_id: 模型 ID

        返回：
            有流量的部署记录列表
        """
        stmt = select(Deployment).where(
            Deployment.model_id == model_id,
            Deployment.traffic_ratio > 0,
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_deployment(
        self,
        *,
        deployment_id: str,
        model_id: str,
        version_id: str,
        framework: str,
        status: str = "active",
        environment: str = "production",
        rollout_type: str = "full",
        variant: str = "primary",
        traffic_ratio: float = 1.0,
        effective_from: object | None = None,
        effective_to: object | None = None,
        deployed_by: str | None = None,
        description: str | None = None,
    ) -> Deployment:
        """创建部署

        参数：
            deployment_id: 部署 ID
            model_id: 模型 ID
            version_id: 版本 ID
            framework: 框架类型
            status: 部署状态
            environment: 部署环境
            rollout_type: 发布类型
            variant: 变体标识
            traffic_ratio: 流量占比
            effective_from: 生效开始时间（可选）
            effective_to: 生效结束时间（可选）
            deployed_by: 部署人（可选）
            description: 部署描述（可选）

        返回：
            创建后的部署记录对象
        """
        obj = Deployment(
            deployment_id=deployment_id,
            model_id=model_id,
            version_id=version_id,
            framework=framework,
            status=status,
            environment=environment,
            rollout_type=rollout_type,
            variant=variant,
            traffic_ratio=traffic_ratio,
            effective_from=effective_from,
            effective_to=effective_to,
            deployed_by=deployed_by,
            description=description,
        )

        self.add(obj)
        return obj

    def update_deployment(self, deployment: Deployment, patch: DeploymentPatch) -> Deployment:
        """更新部署

        参数：
            deployment: 部署记录对象
            patch: 更新内容

        返回：
            更新后的部署记录对象
        """
        for field in fields(DeploymentPatch):
            field_name = field.name

            if field_name == "status":
                continue

            value = getattr(patch, field_name)

            if value is None:
                continue

            setattr(deployment, field_name, value)

        deployment.updated_at = datetime.now(timezone.utc)

        return deployment

    def activate_deployment(self, deployment: Deployment, *, updated_by: str | None = None) -> Deployment:
        """启用部署

        参数：
            deployment: 部署记录对象

        返回：
            启用后的部署记录对象
        """
        deployment.status = DeploymentStatus.ACTIVE

        if updated_by:
            deployment.updated_by = updated_by

        return deployment

    def deactivate_deployment(self, deployment: Deployment, *, updated_by: str | None = None) -> Deployment:
        """停用部署

        参数：
            deployment: 部署记录对象

        返回：
            停用后的部署记录对象
        """
        deployment.status = DeploymentStatus.INACTIVE
        deployment.traffic_ratio = 0.0

        if updated_by:
            deployment.updated_by = updated_by

        return deployment