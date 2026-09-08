"""控制台事件仓储

提供控制台变更事件的游标查询、断线回放和过期清理能力。

核心功能：
  - get_latest_event_id: 获取最新事件游标
  - get_oldest_event_id: 获取最早事件游标
  - list_events: 查询游标之后的事件
  - delete_events_before: 删除过期事件

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.outbox import OutboxRepository

  async with UnitOfWork() as uow:
      events = await OutboxRepository(
          uow.session
      ).list_events(
          after_event_id=100,
      )
"""

from datetime import datetime

from sqlalchemy import (
    delete,
    func,
    select,
)

from datamind.db.models.outbox import OutboxEvent
from datamind.db.repositories.base import BaseRepository


class OutboxRepository(BaseRepository):
    """控制台事件仓储"""

    async def get_latest_event_id(self) -> int | None:
        """获取最新事件游标"""
        stmt = select(
            func.max(
                OutboxEvent.event_id
            )
        )
        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_oldest_event_id(self) -> int | None:
        """获取最早事件游标"""
        stmt = select(
            func.min(
                OutboxEvent.event_id
            )
        )
        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_events(
            self,
            *,
            after_event_id: int,
            limit: int = 200,
    ) -> list[OutboxEvent]:
        """查询指定游标之后的事件"""
        if after_event_id < 0:
            raise ValueError(
                "after_event_id 必须大于等于 0"
            )

        if limit <= 0 or limit > 1000:
            raise ValueError(
                "limit 必须在 1 到 1000 之间"
            )

        stmt = (
            select(
                OutboxEvent
            )
            .where(
                OutboxEvent.event_id
                > after_event_id
            )
            .order_by(
                OutboxEvent.event_id.asc()
            )
            .limit(
                limit
            )
        )
        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def delete_events_before(
            self,
            occurred_before: datetime,
    ) -> None:
        """删除指定时间之前的事件"""
        stmt = delete(
            OutboxEvent
        ).where(
            OutboxEvent.occurred_at
            < occurred_before
        )
        await self.session.execute(
            stmt
        )
