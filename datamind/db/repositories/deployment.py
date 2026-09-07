# datamind/db/repositories/deployment.py

"""部署仓储

提供模型部署记录的查询与管理能力。

核心功能：
  - get_deployment: 获取部署记录
  - list_deployments: 获取部署记录列表
  - list_active_deployments: 获取活跃部署记录列表
  - create_deployment: 创建部署
  - update_deployment: 更新部署
  - activate_deployment: 启用部署
  - deactivate_deployment: 停用部署
  - mark_deleted: 逻辑删除部署
  - restore_deployment: 恢复部署

使用示例：
  from datamind.constants import (
      Environment,
      Framework,
  )
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.deployment import (
      DeploymentPatch,
      DeploymentRepository,
  )

  async with UnitOfWork() as uow:
      repo = DeploymentRepository(
          uow.session
      )

      deployment = repo.create_deployment(
          deployment_id="dep_0123456789abcdef",
          model_id="mdl_0123456789abcdef",
          version_id="ver_0123456789abcdef",
          framework=Framework.SKLEARN,
          environment=Environment.PRODUCTION,
          rollout_type="full",
          deployed_by="admin",
      )
"""

from dataclasses import (
    dataclass,
    fields,
)
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.constants import (
    Environment,
    Framework,
)
from datamind.db.models.deployments import Deployment
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import DeploymentStatus


@dataclass(slots=True)
class DeploymentPatch:
    """部署更新结构

    注意：
        不允许通过 patch 修改 status，
        部署状态由生命周期方法控制。

    属性：
        framework: 框架类型
        environment: 部署环境
        rollout_type: 发布类型
        role: 部署角色
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        threshold: 决策阈值
        description: 部署描述
    """

    framework: Framework | None = None
    environment: Environment | None = None
    rollout_type: str | None = None
    role: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    threshold: float | None = None
    description: str | None = None


class DeploymentRepository(BaseRepository):
    """部署仓储"""

    async def get_deployment(
            self,
            deployment_id: str,
            *,
            include_deleted: bool = False,
    ) -> Deployment | None:
        """获取部署记录

        参数：
            deployment_id: 部署 ID
            include_deleted: 是否包含逻辑删除记录

        返回：
            部署记录对象，不存在时返回 None
        """
        stmt = select(
            Deployment
        ).where(
            Deployment.deployment_id
            == deployment_id
        )

        if not include_deleted:
            stmt = stmt.where(
                Deployment.deleted_at.is_(
                    None
                )
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_deployments(
            self,
            *,
            model_id: str | None = None,
            version_id: str | None = None,
            framework: Framework | None = None,
            environment: Environment | None = None,
            rollout_type: str | None = None,
            role: str | None = None,
            status: DeploymentStatus | None = None,
            deployed_by: str | None = None,
            include_deleted: bool = False,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Deployment]:
        """获取部署记录列表

        参数：
            model_id: 模型 ID（可选）
            version_id: 版本 ID（可选）
            framework: 框架类型（可选）
            environment: 部署环境（可选）
            rollout_type: 发布类型（可选）
            role: 部署角色（可选）
            status: 部署状态（可选）
            deployed_by: 部署人（可选）
            include_deleted: 是否包含逻辑删除记录
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            部署记录列表，按创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        if (
                limit is not None
                and limit < 0
        ):
            raise ValueError(
                "limit 不能小于 0"
            )

        if (
                offset is not None
                and offset < 0
        ):
            raise ValueError(
                "offset 不能小于 0"
            )

        stmt = select(
            Deployment
        )

        if not include_deleted:
            stmt = stmt.where(
                Deployment.deleted_at.is_(
                    None
                )
            )

        if model_id is not None:
            stmt = stmt.where(
                Deployment.model_id
                == model_id
            )

        if version_id is not None:
            stmt = stmt.where(
                Deployment.version_id
                == version_id
            )

        if framework is not None:
            stmt = stmt.where(
                Deployment.framework
                == str(
                    framework
                )
            )

        if environment is not None:
            stmt = stmt.where(
                Deployment.environment
                == str(
                    environment
                )
            )

        if rollout_type is not None:
            stmt = stmt.where(
                Deployment.rollout_type
                == rollout_type
            )

        if role is not None:
            stmt = stmt.where(
                Deployment.role
                == role
            )

        if status is not None:
            stmt = stmt.where(
                Deployment.status
                == str(
                    status
                )
            )

        if deployed_by is not None:
            stmt = stmt.where(
                Deployment.deployed_by
                == deployed_by
            )

        stmt = stmt.order_by(
            Deployment.created_at.desc()
        )

        if offset is not None:
            stmt = stmt.offset(
                offset
            )

        if limit is not None:
            stmt = stmt.limit(
                limit
            )

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def list_active_deployments(
            self,
            model_id: str,
            *,
            version_id: str | None = None,
            environment: Environment | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Deployment]:
        """获取活跃部署记录列表

        参数：
            model_id: 模型 ID
            version_id: 版本 ID（可选）
            environment: 部署环境（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            活跃部署记录列表，按创建时间倒序排列
        """
        return await self.list_deployments(
            model_id=model_id,
            version_id=version_id,
            environment=environment,
            status=DeploymentStatus.ACTIVE,
            limit=limit,
            offset=offset,
        )

    def create_deployment(
            self,
            *,
            deployment_id: str,
            model_id: str,
            version_id: str,
            framework: Framework,
            environment: Environment,
            rollout_type: str = "full",
            role: str = "champion",
            effective_from: datetime | None = None,
            effective_to: datetime | None = None,
            threshold: float | None = None,
            description: str | None = None,
            deployed_by: str | None = None,
    ) -> Deployment:
        """创建部署

        新建部署处于 inactive 状态。

        参数：
            deployment_id: 部署 ID
            model_id: 模型 ID
            version_id: 版本 ID
            framework: 框架类型
            environment: 部署环境
            rollout_type: 发布类型（可选）
            role: 部署角色（可选）
            effective_from: 生效开始时间（可选）
            effective_to: 生效结束时间（可选）
            threshold: 决策阈值（可选）
            description: 部署描述（可选）
            deployed_by: 部署人（可选）

        返回：
            创建后的部署记录对象
        """
        new_deployment = Deployment(
            deployment_id=deployment_id,
            model_id=model_id,
            version_id=version_id,
            framework=str(
                framework
            ),
            environment=str(
                environment
            ),
            status=str(
                DeploymentStatus.INACTIVE
            ),
            rollout_type=rollout_type,
            role=role,
        )

        if threshold is not None:
            new_deployment.threshold = float(
                threshold
            )

        if effective_from is not None:
            new_deployment.effective_from = (
                effective_from
            )

        if effective_to is not None:
            new_deployment.effective_to = effective_to

        if description is not None:
            new_deployment.description = description

        if deployed_by is not None:
            new_deployment.deployed_by = deployed_by

        self.add(
            new_deployment
        )

        return new_deployment

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
        """
        for field in fields(
                DeploymentPatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            if isinstance(
                    value,
                    (
                        Framework,
                        Environment,
                    ),
            ):
                value = str(
                    value
                )

            setattr(
                deployment,
                field.name,
                value,
            )

        if updated_by is not None:
            deployment.updated_by = updated_by

        return deployment

    def activate_deployment(
            self,
            deployment: Deployment,
            *,
            updated_by: str | None = None,
    ) -> Deployment:
        """启用部署

        启用时清除旧的生效结束时间，避免部署状态为 active
        但有效期已经结束的矛盾状态。

        参数：
            deployment: 部署记录对象
            updated_by: 更新人（可选）

        返回：
            启用后的部署记录对象
        """
        deployment.status = str(
            DeploymentStatus.ACTIVE
        )

        if getattr(
            deployment,
            "effective_from",
            None,
        ) is None:
            deployment.effective_from = (
                datetime.now(
                    timezone.utc
                )
            )

        deployment.effective_to = None

        if updated_by is not None:
            deployment.updated_by = updated_by

        return deployment

    def deactivate_deployment(
            self,
            deployment: Deployment,
            *,
            updated_by: str | None = None,
    ) -> Deployment:
        """停用部署

        首次停用时记录生效结束时间；
        重复停用时保留原结束时间。

        参数：
            deployment: 部署记录对象
            updated_by: 更新人（可选）

        返回：
            停用后的部署记录对象
        """
        deployment.status = str(
            DeploymentStatus.INACTIVE
        )

        if getattr(
            deployment,
            "effective_to",
            None,
        ) is None:
            deployment.effective_to = (
                datetime.now(
                    timezone.utc
                )
            )

        if updated_by is not None:
            deployment.updated_by = updated_by

        return deployment

    @staticmethod
    def mark_deleted(
            deployment: Deployment,
            *,
            deleted_at: datetime | None = None,
            deleted_by: str | None = None,
            deletion_reason: str | None = None,
    ) -> Deployment:
        """逻辑删除部署记录"""
        deployment.deleted_at = (
            deleted_at
            if deleted_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        deployment.deleted_by = deleted_by
        deployment.deletion_reason = deletion_reason
        deployment.updated_by = deleted_by

        return deployment

    @staticmethod
    def restore_deployment(
            deployment: Deployment,
            *,
            restored_by: str | None = None,
    ) -> Deployment:
        """恢复逻辑删除的部署记录"""
        deployment.deleted_at = None
        deployment.deleted_by = None
        deployment.deletion_reason = None
        deployment.status = str(
            DeploymentStatus.INACTIVE
        )
        deployment.updated_by = restored_by

        return deployment
