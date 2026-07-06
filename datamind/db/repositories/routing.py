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

      routing = repo.create_routing(
          routing_id="rtn_a1b2c3d4",
          deployment_id="dep_a1b2c3d4",
          environment="production",
          rollout_type="canary",
          rollout_group="group",
          traffic_ratio=0.1,
          rules={
              "bucket_key": "user_id",
              "bucket_range": [0, 10],
          },
          description="10% 灰度流量",
          created_by="system"
      )
"""

from dataclasses import dataclass, fields

from sqlalchemy import select

from datamind.db.models.routing import Routing
from datamind.db.repositories.base import BaseRepository


@dataclass(slots=True)
class RoutingPatch:
    """路由更新结构

    注意：
        不允许通过 patch 修改 enabled，由生命周期方法控制

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
        stmt = select(Routing).where(
            Routing.routing_id == routing_id
        )
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def list_routings(
            self,
            *,
            limit: int | None = None,
            offset: int | None = None,
            **filters,
    ) -> list[Routing]:
        """获取路由规则列表

        参数：
            limit: 返回数量限制
            offset: 分页偏移
            **filters: 过滤条件
                支持字段：
                    deployment_id
                    rollout_type
                    rollout_group
                    environment
                    enabled
                    created_by

        返回：
            路由规则列表，按更新时间倒序排列
        """
        stmt = select(Routing)

        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = stmt.order_by(
            Routing.updated_at.desc(),
            Routing.created_at.desc(),
        )

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def list_enabled_routings(
            self,
            *,
            deployment_id: str | None = None,
            environment: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Routing]:
        """获取启用的路由规则

        参数：
            deployment_id: 部署 ID（可选）
            environment: 环境（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            启用的路由规则列表，按更新时间倒序排列
        """
        filters = {
            "enabled": True,
        }

        if deployment_id is not None:
            filters["deployment_id"] = deployment_id

        if environment is not None:
            filters["environment"] = environment

        return await self.list_routings(
            limit=limit,
            offset=offset,
            **filters,
        )

    def create_routing(
            self,
            *,
            routing_id: str,
            deployment_id: str,
            environment: str,
            rollout_type: str = "full",
            rollout_group: str | None = None,
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
            environment: 路由环境
            rollout_type: 发布类型（可选）
            rollout_group: 发布分组（可选）
            traffic_ratio: 流量占比（可选）
            enabled: 是否启用（可选）
            rules: 路由规则配置（可选）
            description: 描述（可选）
            created_by: 创建人（可选）

        返回：
            创建后的路由对象

        异常：
            ValueError: traffic_ratio 不在 0 到 1 之间
        """
        if traffic_ratio < 0 or traffic_ratio > 1:
            raise ValueError(
                "路由 traffic_ratio 必须在 0 到 1 之间"
            )

        obj = Routing(
            routing_id=routing_id,
            deployment_id=deployment_id,
            environment=environment,
            rollout_type=rollout_type,
            rollout_group=rollout_group,
            traffic_ratio=traffic_ratio,
            enabled=enabled,
            rules=rules,
            description=description,
            created_by=created_by,
        )

        self.add(obj)

        return obj

    def update_routing(
            self,
            routing: Routing,
            patch: RoutingPatch,
            *,
            updated_by: str | None = None,
    ) -> Routing:
        """更新路由规则

        参数：
            routing: 路由对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的路由对象

        异常：
            ValueError: traffic_ratio 不在 0 到 1 之间
        """
        if patch.traffic_ratio is not None:
            if patch.traffic_ratio < 0 or patch.traffic_ratio > 1:
                raise ValueError(
                    "路由 traffic_ratio 必须在 0 到 1 之间"
                )

        for field in fields(RoutingPatch):
            value = getattr(patch, field.name)

            if value is None:
                continue

            setattr(routing, field.name, value)

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
