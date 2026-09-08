"""路由仓储

提供模型流量分发策略的查询与管理能力，
用于控制请求如何分配到不同部署实例。

核心功能：
  - get_routing: 获取路由规则
  - list_routings: 获取路由规则列表
  - list_enabled_routings: 获取启用的路由规则
  - create_routing: 创建路由规则
  - update_routing: 更新路由规则
  - enable_routing: 启用路由规则
  - disable_routing: 禁用路由规则
  - mark_deleted: 逻辑删除路由规则
  - restore_routing: 恢复路由规则

使用示例：
  from datamind.constants import Environment
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.routing import (
      RoutingPatch,
      RoutingRepository,
  )

  async with UnitOfWork() as uow:
      repo = RoutingRepository(
          uow.session
      )

      routing = repo.create_routing(
          routing_id="rtn_0123456789abcdef",
          name="scorecard-route",
          deployment_id="dep_0123456789abcdef",
          environment=Environment.PRODUCTION,
          rollout_type="canary",
          rollout_group="challenger",
          traffic_ratio=0.1,
          rules={
              "bucket_key": "user_id",
              "bucket_range": [
                  0,
                  10,
              ],
          },
          description="10% 灰度流量",
          created_by="system",
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

from datamind.constants import Environment
from datamind.db.models.deployments import Deployment
from datamind.db.models.routing import Routing
from datamind.db.repositories.base import BaseRepository


@dataclass(slots=True)
class RoutingPatch:
    """路由更新结构

    注意：
        不允许通过 patch 修改 enabled，
        启用状态由生命周期方法控制。

    属性：
        name: 路由名称
        rollout_type: 发布类型
        rollout_group: 发布分组
        environment: 路由环境
        traffic_ratio: 流量占比
        rules: 路由规则配置
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        description: 路由说明
    """

    name: str | None = None
    rollout_type: str | None = None
    rollout_group: str | None = None
    environment: Environment | None = None
    traffic_ratio: float | None = None
    rules: dict | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    description: str | None = None


class RoutingRepository(BaseRepository):
    """路由仓储"""

    @staticmethod
    def _validate_traffic_ratio(
            traffic_ratio: float,
    ) -> None:
        """校验流量占比"""
        if (
                traffic_ratio < 0
                or traffic_ratio > 1
        ):
            raise ValueError(
                "路由 traffic_ratio 必须在 0 到 1 之间"
            )

    async def get_routing(
            self,
            routing_id: str,
            *,
            include_deleted: bool = False,
    ) -> Routing | None:
        """获取路由规则

        参数：
            routing_id: 路由 ID
            include_deleted: 是否包含逻辑删除记录

        返回：
            路由规则对象，不存在时返回 None
        """
        stmt = select(
            Routing
        ).where(
            Routing.routing_id
            == routing_id
        )

        if not include_deleted:
            stmt = stmt.where(
                Routing.deleted_at.is_(
                    None
                )
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_routings(
            self,
            *,
            routing_id: str | None = None,
            name: str | None = None,
            deployment_id: str | None = None,
            rollout_type: str | None = None,
            rollout_group: str | None = None,
            environment: Environment | None = None,
            enabled: bool | None = None,
            created_by: str | None = None,
            include_deleted: bool = False,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Routing]:
        """获取路由规则列表

        参数：
            routing_id: 路由 ID（可选）
            name: 路由名称（可选）
            deployment_id: 部署 ID（可选）
            rollout_type: 发布类型（可选）
            rollout_group: 发布分组（可选）
            environment: 路由环境（可选）
            enabled: 是否启用（可选）
            created_by: 创建人（可选）
            include_deleted: 是否包含逻辑删除记录
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            路由规则列表，按更新时间和创建时间倒序排列

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

        stmt = select(Routing)

        if any(
                value is not None
                for value in (
                    environment,
                    rollout_type,
                    rollout_group,
                )
        ):
            stmt = stmt.join(
                Deployment,
                Deployment.deployment_id
                == Routing.deployment_id,
            )

        if not include_deleted:
            stmt = stmt.where(
                Routing.deleted_at.is_(
                    None
                )
            )

        if routing_id is not None:
            stmt = stmt.where(
                Routing.routing_id
                == routing_id
            )

        if deployment_id is not None:
            stmt = stmt.where(
                Routing.deployment_id
                == deployment_id
            )

        if rollout_type is not None:
            stmt = stmt.where(
                Deployment.rollout_type
                == rollout_type
            )

        if name is not None:
            stmt = stmt.where(
                Routing.name == name
            )

        if rollout_group is not None:
            stmt = stmt.where(
                Deployment.role
                == rollout_group
            )

        if environment is not None:
            stmt = stmt.where(
                Deployment.environment
                == str(
                    environment
                )
            )

        if enabled is not None:
            stmt = stmt.where(
                Routing.enabled
                == enabled
            )

        if created_by is not None:
            stmt = stmt.where(
                Routing.created_by
                == created_by
            )

        stmt = stmt.order_by(
            Routing.updated_at.desc(),
            Routing.created_at.desc(),
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

    async def list_enabled_routings(
            self,
            *,
            deployment_id: str | None = None,
            environment: Environment | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Routing]:
        """获取启用的路由规则

        参数：
            deployment_id: 部署 ID（可选）
            environment: 路由环境（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            启用的路由规则列表
        """
        return await self.list_routings(
            deployment_id=deployment_id,
            environment=environment,
            enabled=True,
            limit=limit,
            offset=offset,
        )

    def create_routing(
            self,
            *,
            routing_id: str,
            name: str,
            deployment_id: str,
            environment: Environment,
            rollout_type: str = "full",
            rollout_group: str | None = None,
            traffic_ratio: float = 0.0,
            enabled: bool = False,
            rules: dict | None = None,
            effective_from: datetime | None = None,
            effective_to: datetime | None = None,
            description: str | None = None,
            created_by: str | None = None,
    ) -> Routing:
        """创建路由规则

        参数：
            routing_id: 路由 ID
            name: 路由名称
            deployment_id: 部署 ID
            environment: 路由环境
            rollout_type: 发布类型（可选）
            rollout_group: 发布分组（可选）
            traffic_ratio: 流量占比（可选）
            enabled: 是否启用（可选）
            rules: 路由规则配置（可选）
            effective_from: 生效开始时间（可选）
            effective_to: 生效结束时间（可选）
            description: 路由说明（可选）
            created_by: 创建人（可选）

        返回：
            创建后的路由规则对象

        异常：
            ValueError: traffic_ratio 不在 0 到 1 之间
        """
        self._validate_traffic_ratio(
            traffic_ratio
        )

        new_routing = Routing(
            routing_id=routing_id,
            name=name,
            deployment_id=deployment_id,
            environment=str(
                environment
            ),
            rollout_type=rollout_type,
            traffic_ratio=float(
                traffic_ratio
            ),
            enabled=enabled,
            rules=rules,
        )

        if effective_from is not None:
            new_routing.effective_from = effective_from

        if effective_to is not None:
            new_routing.effective_to = effective_to

        if rollout_group is not None:
            new_routing.rollout_group = rollout_group

        if description is not None:
            new_routing.description = description

        if created_by is not None:
            new_routing.created_by = created_by

        self.add(
            new_routing
        )

        return new_routing

    def update_routing(
            self,
            routing: Routing,
            patch: RoutingPatch,
            *,
            updated_by: str | None = None,
    ) -> Routing:
        """更新路由规则

        参数：
            routing: 路由规则对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的路由规则对象

        异常：
            ValueError: traffic_ratio 不在 0 到 1 之间
        """
        if patch.traffic_ratio is not None:
            self._validate_traffic_ratio(
                patch.traffic_ratio
            )

        for field in fields(
                RoutingPatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            if isinstance(
                    value,
                    Environment,
            ):
                value = str(
                    value
                )

            setattr(
                routing,
                field.name,
                value,
            )

        if updated_by is not None:
            routing.updated_by = updated_by

        return routing

    def enable_routing(
            self,
            routing: Routing,
            *,
            updated_by: str | None = None,
    ) -> Routing:
        """启用路由规则

        参数：
            routing: 路由规则对象
            updated_by: 更新人（可选）

        返回：
            启用后的路由规则对象
        """
        if routing.enabled:
            return routing

        routing.enabled = True

        if updated_by is not None:
            routing.updated_by = updated_by

        return routing

    def disable_routing(
            self,
            routing: Routing,
            *,
            updated_by: str | None = None,
    ) -> Routing:
        """禁用路由规则

        参数：
            routing: 路由规则对象
            updated_by: 更新人（可选）

        返回：
            禁用后的路由规则对象
        """
        if not routing.enabled:
            return routing

        routing.enabled = False

        if updated_by is not None:
            routing.updated_by = updated_by

        return routing

    @staticmethod
    def mark_deleted(
            routing: Routing,
            *,
            deleted_at: datetime | None = None,
            deleted_by: str | None = None,
            deletion_reason: str | None = None,
    ) -> Routing:
        """逻辑删除路由规则"""
        routing.deleted_at = (
            deleted_at
            if deleted_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        routing.deleted_by = deleted_by
        routing.deletion_reason = deletion_reason
        routing.updated_by = deleted_by

        return routing

    @staticmethod
    def restore_routing(
            routing: Routing,
            *,
            restored_by: str | None = None,
    ) -> Routing:
        """恢复逻辑删除的路由规则"""
        routing.deleted_at = None
        routing.deleted_by = None
        routing.deletion_reason = None
        routing.enabled = False
        routing.updated_by = restored_by

        return routing
