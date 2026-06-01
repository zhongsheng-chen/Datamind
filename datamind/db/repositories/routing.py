# datamind/db/repositories/routing.py

"""路由仓储

提供模型流量分发策略的查询与管理能力，用于控制请求如何分配到不同部署实例。

核心功能：
  - get_routing: 获取路由规则
  - list_routings: 获取路由规则列表
  - list_enabled_routings: 获取启用的路由规则
  - create_routing: 创建路由规则
  - update_routing: 更新路由规则
  - enable_routing: 启用路由规则
  - disable_routing: 禁用路由规则

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import RoutingRepository, RoutingPatch

  async with UnitOfWork() as uow:
      repo = RoutingRepository(uow.session)

      routing = await repo.create_routing(
          routing_id="rtn_a1b2c3d4",
          deployment_id="dep_a1b2c3d4",
          rollout_type="canary",
          rollout_group="group",
          environment="production",
          traffic_ratio=0.1,
          enabled=True,
          rules={
              "bucket_key": "user_id",
              "bucket_range": [0, 10],
          },
          description="10% 灰度流量",
          created_by="system"
      )
"""

from datetime import datetime, timezone
from dataclasses import dataclass, fields
from sqlalchemy import select

from datamind.db.models.routing import Routing
from datamind.db.repositories.base import BaseRepository


@dataclass(slots=True)
class RoutingPatch:
    """路由更新结构

    属性：
        rollout_type: 发布类型
        rollout_group: 发布分组
        environment: 路由环境
        traffic_ratio: 流量占比
        rules: 路由规则配置
        description: 描述
    """
    rollout_type: str | None = None
    rollout_group: str | None = None
    environment: str | None = None
    enabled: bool | None = None
    traffic_ratio: float | None = None
    rules: dict | None = None
    description: str | None = None


class RoutingRepository(BaseRepository):
    """路由仓储"""

    async def get_routing(
        self,
        routing_id: str,
    ) -> Routing | None:
        """获取路由规则

        参数：
            routing_id: 路由 ID

        返回：
            路由对象，不存在返回 None
        """
        stmt = select(Routing).where(Routing.routing_id == routing_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_routings(
        self,
        deployment_id: str,
        *,
        environment: str | None = None,
    ) -> list[Routing]:
        """获取路由规则列表

        参数：
            deployment_id: 部署 ID
            environment: 环境（可选）

        返回：
            路由规则列表，按创建时间倒序排列
        """
        stmt = (
            select(Routing)
            .where(Routing.deployment_id == deployment_id)
            .order_by(Routing.created_at.desc())
        )

        if environment:
            stmt = stmt.where(
                Routing.environment == environment
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_enabled_routings(
        self,
        deployment_id: str,
         *,
        environment: str | None = None,
    ) -> list[Routing]:
        """获取启用的路由规则

        参数：
            deployment_id: 部署 ID
            environment: 环境（可选）

        返回：
            启用的路由规则列表，按创建时间倒序排列
        """
        stmt = (
            select(Routing)
            .where(
                Routing.deployment_id == deployment_id,
                Routing.enabled.is_(True),
            )
            .order_by(Routing.created_at.desc())
        )

        if environment:
            stmt = stmt.where(Routing.environment == environment)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_routings_by_group(
            self,
            rollout_group: str,
            *,
            environment: str | None = None,
    ) -> list[Routing]:
        """获取发布分组下的路由规则列表

        参数：
            rollout_group: 发布分组
            environment: 环境（可选）

        返回：
            路由规则列表，按创建时间倒序排列
        """
        stmt = (
            select(Routing)
            .where(
                Routing.rollout_group == rollout_group
            )
            .order_by(Routing.created_at.desc())
        )

        if environment:
            stmt = stmt.where(
                Routing.environment == environment
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_routing(
        self,
        *,
        routing_id: str,
        deployment_id: str,
        rollout_type: str = "full",
        rollout_group: str | None = None,
        environment: str = "production",
        traffic_ratio: float = 0.0,
        enabled: bool = True,
        rules: dict | None = None,
        description: str | None = None,
        created_by: str | None = None,
    ) -> Routing:
        """创建路由规则

        参数：
            routing_id: 路由 ID
            deployment_id: 部署 ID
            rollout_type: 发布类型
            rollout_group: 发布分组
            environment: 路由环境
            traffic_ratio: 流量占比
            enabled: 是否启用
            rules: 路由规则配置（可选）
            description: 描述（可选）
            created_by: 创建人（可选）

        返回：
            创建后的路由对象
        """
        obj = Routing(
            routing_id=routing_id,
            deployment_id=deployment_id,
            rollout_type=rollout_type,
            rollout_group=rollout_group,
            environment=environment,
            traffic_ratio=traffic_ratio,
            rules=rules,
            description=description,
            enabled=enabled,
            created_by=created_by,
        )

        self.add(obj)
        return obj

    def update_routing(
        self,
        routing: Routing,
        patch: RoutingPatch,
        updated_by: str | None = None,
    ) -> Routing:
        """更新路由规则

        参数：
            routing: 路由对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的路由对象

        注意：
            - enabled 字段不允许通过 patch 修改，会被直接忽略
            - patch 中为 None 的字段不会覆盖原值
        """
        for field in fields(RoutingPatch):
            field_name = field.name

            if field_name == "enabled":
                continue

            value = getattr(patch, field_name)

            if value is None:
                continue

            setattr(routing, field_name, value)

        if updated_by:
            routing.updated_by = updated_by

        routing.updated_at = datetime.now(timezone.utc)

        return routing

    def enable_routing(
        self,
        routing: Routing,
        *,
        updated_by: str | None = None,
    ) -> Routing:
        """启用路由规则

        参数：
            routing: 路由对象
            updated_by: 更新人（可选）

        返回：
            启用后的路由对象
        """
        routing.enabled = True

        if updated_by:
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
            routing: 路由对象
            updated_by: 更新人（可选）

        返回：
            禁用后的路由对象
        """
        routing.enabled = False

        if updated_by:
            routing.updated_by = updated_by

        return routing