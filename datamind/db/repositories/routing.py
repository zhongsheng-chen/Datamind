# datamind/db/repositories/routing.py

"""路由仓储

提供模型流量分发策略的查询与管理能力，用于控制请求如何分配到不同版本或部署。

核心功能：
  - get_routing_policy: 获取启用的路由策略
  - list_routing_policies: 获取模型所有路由策略
  - create_routing_policy: 创建路由策略
  - update_routing_policy: 更新路由策略
  - enable_routing_policy: 启用路由策略
  - disable_routing_policy: 禁用路由策略

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import RoutingRepository, RoutingPatch

  async with UnitOfWork() as uow:
      repo = RoutingRepository(uow.session)

      routing = await repo.create_routing_policy(
          routing_id="rtn_a1b2c3d4",
          model_id="mdl_a1b2c3d4",
          strategy="consistent",
          config={
              "rules": [
                  {"version": "v1", "weight": 0.7},
                  {"version": "v2", "weight": 0.3},
              ]
          },
          enabled=True,
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
    """路由策略更新结构

    属性：
        strategy: 路由策略
        config: 策略配置
    """
    strategy: str | None = None
    config: dict | None = None


class RoutingRepository(BaseRepository):
    """路由仓储"""

    async def get_routing_policy(self, model_id: str) -> Routing | None:
        """获取启用的路由策略

        参数：
            model_id: 模型 ID

        返回：
            启用的路由策略对象，不存在时返回 None
        """
        stmt = select(Routing).where(
            Routing.model_id == model_id,
            Routing.enabled == True,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_routing_policies(self, model_id: str) -> list[Routing]:
        """获取模型所有路由策略

        参数：
            model_id: 模型 ID

        返回：
            路由策略列表，按创建时间倒序排列
        """
        stmt = (
            select(Routing)
            .where(Routing.model_id == model_id)
            .order_by(Routing.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_routing_policy(
        self,
        *,
        routing_id: str,
        model_id: str,
        strategy: str,
        config: dict | None = None,
        enabled: bool = True,
        created_by: str | None = None,
    ) -> Routing:
        """创建路由策略

        参数：
            routing_id: 路由策略 ID
            model_id: 模型 ID
            strategy: 路由策略
            config: 策略配置（可选）
            enabled: 是否启用
            created_by: 创建人（可选）

        返回：
            创建后的路由策略对象
        """
        obj = Routing(
            routing_id=routing_id,
            model_id=model_id,
            strategy=strategy,
            config=config,
            enabled=enabled,
            created_by=created_by,
        )

        self.add(obj)
        return obj

    def update_routing_policy(
        self,
        routing: Routing,
        patch: RoutingPatch,
        updated_by: str | None = None,
    ) -> Routing:
        """更新路由策略

        参数：
            routing: 路由策略对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的路由策略对象
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

    def enable_routing_policy(
        self,
        routing: Routing,
        updated_by: str | None = None,
    ) -> Routing:
        """启用路由策略

        参数：
            routing: 路由策略对象
            updated_by: 更新人（可选）

        返回：
            启用后的路由策略对象
        """
        routing.enabled = True

        if updated_by:
            routing.updated_by = updated_by

        return routing

    def disable_routing_policy(
        self,
        routing: Routing,
        updated_by: str | None = None,
    ) -> Routing:
        """禁用路由策略

        参数：
            routing: 路由策略对象
            updated_by: 更新人（可选）

        返回：
            禁用后的路由策略对象
        """
        routing.enabled = False

        if updated_by:
            routing.updated_by = updated_by

        return routing