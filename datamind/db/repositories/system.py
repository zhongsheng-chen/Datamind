"""系统状态仓储.

提供系统初始化状态的读取、行锁定和完成标记能力。

核心功能：
  - SystemStateRepository.get_state: 获取系统状态
  - SystemStateRepository.get_or_create_state: 原子获取或创建系统状态
  - SystemStateRepository.mark_initialized: 标记系统已初始化

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.system import (
      SystemStateRepository,
  )

  async with UnitOfWork() as uow:
      repo = SystemStateRepository(
          uow.session
      )
      state = await repo.get_state(
          for_update=True
      )
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from datamind.db.models.system import SystemState
from datamind.db.repositories.base import BaseRepository


class SystemStateRepository(BaseRepository):
    """系统状态仓储."""

    async def get_state(
            self,
            *,
            system_id: str = "datamind",
            for_update: bool = False,
    ) -> SystemState | None:
        """获取系统状态.

        参数：
            system_id: 系统标识
            for_update: 是否锁定状态记录

        返回：
            系统状态，不存在时返回 None
        """
        stmt = select(
            SystemState
        ).where(
            SystemState.system_id == system_id
        )

        if for_update:
            stmt = stmt.with_for_update()

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_or_create_state(
            self,
            *,
            system_id: str = "datamind",
    ) -> SystemState:
        """原子获取或创建系统状态.

        使用唯一索引避免并发初始化创建重复状态，并在读取时锁定状态记录。

        参数：
            system_id: 系统标识

        返回：
            已锁定的系统状态

        异常：
            RuntimeError: 状态记录创建后无法读取
        """
        stmt = insert(
            SystemState
        ).values(
            system_id=system_id
        ).on_conflict_do_nothing(
            index_elements=[
                SystemState.system_id
            ]
        )

        await self.session.execute(
            stmt
        )

        state = await self.get_state(
            system_id=system_id,
            for_update=True,
        )

        if state is None:
            raise RuntimeError(
                "系统初始化状态创建失败"
            )

        return state

    @staticmethod
    def mark_initialized(
            state: SystemState,
            *,
            initialized_at: datetime,
            initialized_by: str,
    ) -> SystemState:
        """标记系统已初始化.

        参数：
            state: 系统状态
            initialized_at: 初始化完成时间
            initialized_by: 初始化操作者

        返回：
            更新后的系统状态
        """
        state.initialized = True
        state.initialized_at = initialized_at
        state.initialized_by = initialized_by

        return state


__all__ = [
    "SystemStateRepository",
]
