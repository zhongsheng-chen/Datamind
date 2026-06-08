# datamind/db/repositories/deployment.py

"""部署仓储

提供模型部署记录的查询与管理能力。

核心功能：
  - get_deployment: 获取部署记录
  - list_deployments: 获取所有部署记录列表
  - list_active_deployments: 获取活跃部署记录列表
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
          deployed_by="admin"
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
        role: 部署角色
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        config: 运行时配置
        description: 部署描述
        endpoint: 推理服务地址
    """
    framework: str | None = None
    environment: str | None = None
    rollout_type: str | None = None
    role: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    config: dict | None = None
    description: str | None = None
    endpoint: str | None = None


class DeploymentRepository(BaseRepository):
    """部署仓储"""

    async def get_deployment(
        self,
        deployment_id: str,
    ) -> Deployment | None:
        """获取部署记录

        参数：
            deployment_id: 部署 ID

        返回：
            部署记录对象，不存在时返回 None
        """
        stmt = select(Deployment).where(Deployment.deployment_id == deployment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_deployments(
            self,
            *,
            exclude_status: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
            **filters,
    ) -> list[Deployment]:
        """获取所有部署列表

        参数：
            exclude_status: 排除指定状态
            limit: 返回数量限制
            offset: 分页偏移
            **filters: 过滤条件
                支持字段：
                    model_id
                    version_id
                    framework
                    environment
                    rollout_type
                    role
                    status
                    deployed_by

        返回：
            部署列表，按创建时间倒序排列
        """
        stmt = select(Deployment)

        if filters:
            stmt = stmt.filter_by(**filters)

        if exclude_status:
            stmt = stmt.where(Deployment.status != exclude_status)

        stmt = stmt.order_by(
            Deployment.created_at.desc()
        )

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def list_active_deployments(
            self,
            model_id: str,
            *,
            version_id: str | None = None,
            environment: str | None = None,
    ) -> list[Deployment]:
        """获取活跃部署记录列表

        参数：
            model_id: 模型 ID
            version_id: 版本 ID（可选）
            environment: 部署环境（可选）

        返回：
            活跃部署记录列表，按创建时间倒序排列
        """
        stmt = (
            select(Deployment)
            .where(
                Deployment.model_id == model_id,
                Deployment.status == DeploymentStatus.ACTIVE,
            )
            .order_by(Deployment.created_at.desc())
        )

        if version_id:
            stmt = stmt.where(Deployment.version_id == version_id)

        if environment:
            stmt = stmt.where(Deployment.environment == environment)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_deployment(
        self,
        *,
        deployment_id: str,
        model_id: str,
        version_id: str,
        framework: str,
        environment: str = "production",
        rollout_type: str = "full",
        role: str = "champion",
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        config: dict | None = None,
        description: str | None = None,
        endpoint: str | None = None,
        deployed_by: str | None = None,
    ) -> Deployment:
        """创建部署

        参数：
            deployment_id: 部署 ID
            model_id: 模型 ID
            version_id: 版本 ID
            framework: 框架类型
            environment: 部署环境
            rollout_type: 发布类型
            role: 部署角色（可选）
            effective_from: 生效开始时间（可选）
            effective_to: 生效结束时间（可选）
            config: 运行时配置（可选）
            description: 部署描述（可选）
            endpoint: 推理服务地址（可选）
            deployed_by: 部署人（可选）

        返回：
            创建后的部署记录对象
        """
        obj = Deployment(
            deployment_id=deployment_id,
            model_id=model_id,
            version_id=version_id,
            framework=framework,
            environment=environment,
            status=DeploymentStatus.INACTIVE,
            rollout_type=rollout_type,
            role=role,
            effective_from=effective_from,
            effective_to=effective_to,
            config=config,
            description=description,
            endpoint=endpoint,
            deployed_by=deployed_by,
        )

        self.add(obj)
        return obj

    def update_deployment(
        self,
        deployment: Deployment,
        patch: DeploymentPatch,
        *,
        updated_by: str | None = None,
    ) -> Deployment:
        """更新部署

        参数：
            deployment: 部署记录对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的部署记录对象

        注意：
            - status 字段不允许通过 patch 修改，会被直接忽略
            - patch 中为 None 的字段不会覆盖原值
        """
        for field in fields(DeploymentPatch):
            field_name = field.name

            if field_name == "status":
                continue

            value = getattr(patch, field_name)

            if value is None:
                continue

            setattr(deployment, field_name, value)

        if updated_by is not None:
            deployment.updated_by = updated_by

        deployment.updated_at = datetime.now(timezone.utc)

        return deployment

    def activate_deployment(
        self,
        deployment: Deployment,
        *,
        updated_by: str | None = None,
    ) -> Deployment:
        """启用部署

        参数：
            deployment: 部署记录对象

        返回：
            启用后的部署记录对象
        """
        deployment.status = DeploymentStatus.ACTIVE

        if deployment.effective_from is None:
            deployment.effective_from = datetime.now(timezone.utc)

        if updated_by:
            deployment.updated_by = updated_by

        return deployment

    def deactivate_deployment(
        self,
        deployment: Deployment,
        *,
        updated_by: str | None = None,
    ) -> Deployment:
        """停用部署

        参数：
            deployment: 部署记录对象

        返回：
            停用后的部署记录对象
        """
        deployment.status = DeploymentStatus.INACTIVE

        if deployment.effective_to is None:
            deployment.effective_to = datetime.now(timezone.utc)

        if updated_by:
            deployment.updated_by = updated_by

        return deployment