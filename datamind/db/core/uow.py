"""工作单元.

统一事务管理器，确保一个请求中的所有数据库操作
在同一个事务中完成。

核心功能：
  - UnitOfWork: 管理数据库会话和事务生命周期

使用示例：
  from datamind.db.core.uow import UnitOfWork
  from datamind.db.repositories import MetadataRepository

  async with UnitOfWork() as uow:
      repo = MetadataRepository(
          uow.session
      )

      repo.create_model(
          model_id="mdl_0123456789abcdef",
          name="scorecard",
          model_type="logistic_regression",
          task_type="scoring",
          framework="sklearn",
      )
"""

import asyncio
import inspect
from types import TracebackType
from collections.abc import Callable
from typing import (
    Any,
    Literal,
)

from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.core.session import get_session_factory


class UnitOfWork:
    """工作单元.

    属性：
        session: 当前数据库会话
    """

    def __init__(
            self,
    ) -> None:
        """初始化工作单元."""
        self._session: AsyncSession | None = None
        self._rollback_only = False
        self._after_commit: list[Callable[[], Any]] = []
        self._after_rollback: list[Callable[[], Any]] = []

    @property
    def session(self) -> AsyncSession:
        """获取当前数据库会话.

        异常：
            RuntimeError: 工作单元未进入上下文或已经关闭
        """
        if self._session is None:
            raise RuntimeError(
                "工作单元未初始化，"
                "请在 async with UnitOfWork() 上下文中使用"
            )

        return self._session

    def mark_rollback(
            self,
    ) -> None:
        """标记当前事务必须回滚."""
        self._rollback_only = True

    def on_commit(self, callback: Callable[[], Any]) -> None:
        """注册数据库提交成功后执行的回调."""
        self._after_commit.append(callback)

    def on_rollback(self, callback: Callable[[], Any]) -> None:
        """注册数据库回滚后执行的补偿回调."""
        self._after_rollback.append(callback)

    async def __aenter__(
            self,
    ) -> "UnitOfWork":
        """进入事务上下文."""
        if self._session is not None:
            raise RuntimeError(
                "工作单元已经初始化"
            )

        self._rollback_only = False

        session_factory = get_session_factory()
        self._session = session_factory()

        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            _exc_value: BaseException | None,
            _traceback: TracebackType | None,
    ) -> Literal[False]:
        """退出事务上下文.

        正常退出时提交事务；
        发生异常或已标记回滚时回滚事务。
        """
        exit_task = asyncio.create_task(
            self._finish(
                exc_type
            )
        )

        try:
            await asyncio.shield(
                exit_task
            )
        except asyncio.CancelledError as cancellation:
            while not exit_task.done():
                try:
                    await asyncio.shield(
                        exit_task
                    )
                except asyncio.CancelledError:
                    continue

            exit_task.result()
            raise cancellation

        return False

    async def _finish(
            self,
            exc_type: type[BaseException] | None,
    ) -> None:
        """完成事务并关闭会话."""
        session = self.session

        try:
            if (
                    exc_type is not None
                    or self._rollback_only
            ):
                await session.rollback()
                await self._run_callbacks(
                    self._after_rollback,
                    suppress_errors=exc_type is not None,
                )
            else:
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
                    await self._run_callbacks(
                        self._after_rollback,
                        suppress_errors=True,
                    )
                    raise
                else:
                    await self._run_callbacks(
                        self._after_commit,
                        suppress_errors=False,
                    )
        finally:
            await self.close()

    @staticmethod
    async def _run_callbacks(
            callbacks: list[Callable[[], Any]],
            *,
            suppress_errors: bool,
    ) -> None:
        """依次执行事务完成回调."""
        first_error: Exception | None = None

        for callback in callbacks:
            try:
                result = callback()

                if inspect.isawaitable(result):
                    await result
            except Exception as exc:
                if first_error is None:
                    first_error = exc

        if first_error is not None and not suppress_errors:
            raise first_error

    async def close(
            self,
    ) -> None:
        """关闭当前数据库会话.

        该方法支持重复调用。关闭后不再允许通过
        session 属性访问原会话。
        """
        session = self._session

        self._session = None
        self._rollback_only = False
        self._after_commit.clear()
        self._after_rollback.clear()

        if session is not None:
            await session.close()
