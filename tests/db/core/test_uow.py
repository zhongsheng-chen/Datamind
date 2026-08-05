# tests/db/core/test_uow.py

"""数据库工作单元测试

验证 UnitOfWork 对异步数据库会话和事务生命周期的管理。

核心功能：
  - test_session_is_unavailable_before_enter:
    验证进入上下文前不能访问会话
  - test_enter_creates_session:
    验证进入上下文时创建并暴露会话
  - test_enter_rejects_repeated_initialization:
    验证同一工作单元不能重复进入
  - test_normal_exit_commits_and_closes:
    验证正常退出时提交并关闭会话
  - test_exception_exit_rolls_back_and_closes:
    验证发生异常时回滚并关闭会话
  - test_mark_rollback_forces_rollback:
    验证显式回滚标记
  - test_enter_resets_previous_rollback_mark:
    验证进入上下文时重置旧回滚标记
  - test_commit_failure_rolls_back_and_closes:
    验证提交失败时回滚并关闭会话
  - test_rollback_failure_still_closes_session:
    验证回滚失败时仍关闭会话
  - test_cancellation_waits_for_session_close:
    验证任务取消时仍等待会话关闭
  - test_close_is_idempotent:
    验证重复关闭保持幂等
  - test_close_clears_state_before_session_close:
    验证会话关闭失败时内部状态仍被清理
  - test_commit_runs_only_commit_callbacks:
    验证提交时仅执行提交回调
  - test_rollback_runs_only_rollback_callbacks:
    验证回滚时仅执行回滚回调
  - test_context_manager_propagates_exception:
    验证上下文管理器继续抛出业务异常
  - test_uow_can_be_reused_after_close:
    验证关闭后的工作单元可以复用
"""

import asyncio
from collections.abc import Iterator
from typing import cast
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
)

import datamind.db.core.uow as uow_module
from datamind.db.core.uow import UnitOfWork


@pytest.fixture
def session_resources() -> tuple[
    AsyncSession,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    """创建异步会话及事务方法替身"""
    commit = AsyncMock()
    rollback = AsyncMock()
    close = AsyncMock()

    session = MagicMock(
        spec=AsyncSession
    )
    session.commit = commit
    session.rollback = rollback
    session.close = close

    return (
        cast(
            AsyncSession,
            session,
        ),
        commit,
        rollback,
        close,
    )


@pytest.fixture
def session_factory_resources(
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> tuple[
    async_sessionmaker[AsyncSession],
    MagicMock,
]:
    """创建异步会话工厂替身"""
    session = session_resources[
        0
    ]
    factory_mock = MagicMock(
        return_value=session
    )
    session_factory = cast(
        async_sessionmaker[AsyncSession],
        factory_mock,
    )

    return (
        session_factory,
        factory_mock,
    )


@pytest.fixture
def patch_session_factory(
        monkeypatch: pytest.MonkeyPatch,
        session_factory_resources: tuple[
            async_sessionmaker[AsyncSession],
            MagicMock,
        ],
) -> Iterator[MagicMock]:
    """替换工作单元使用的会话工厂"""
    session_factory, factory_mock = (
        session_factory_resources
    )
    get_session_factory = MagicMock(
        return_value=session_factory
    )

    monkeypatch.setitem(
        vars(uow_module),
        "get_session_factory",
        get_session_factory,
    )

    yield get_session_factory

    get_session_factory.reset_mock()
    factory_mock.reset_mock()


def test_session_is_unavailable_before_enter() -> None:
    """验证进入上下文前不能访问会话"""
    uow = UnitOfWork()

    with pytest.raises(
            RuntimeError,
            match="工作单元未初始化",
    ):
        _ = uow.session


@pytest.mark.asyncio
async def test_enter_creates_session(
        patch_session_factory: MagicMock,
        session_factory_resources: tuple[
            async_sessionmaker[AsyncSession],
            MagicMock,
        ],
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证进入上下文时创建并暴露会话"""
    _, factory_mock = session_factory_resources
    session = session_resources[
        0
    ]
    uow = UnitOfWork()

    result = await uow.__aenter__()

    assert result is uow
    assert uow.session is session
    patch_session_factory.assert_called_once_with()
    factory_mock.assert_called_once_with()

    await uow.close()


@pytest.mark.asyncio
async def test_enter_rejects_repeated_initialization(
        patch_session_factory: MagicMock,
        session_factory_resources: tuple[
            async_sessionmaker[AsyncSession],
            MagicMock,
        ],
) -> None:
    """验证同一工作单元不能重复进入"""
    _, factory_mock = session_factory_resources
    uow = UnitOfWork()

    await uow.__aenter__()

    with pytest.raises(
            RuntimeError,
            match="工作单元已经初始化",
    ):
        await uow.__aenter__()

    patch_session_factory.assert_called_once_with()
    factory_mock.assert_called_once_with()

    await uow.close()


@pytest.mark.asyncio
async def test_normal_exit_commits_and_closes(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证正常退出时提交并关闭会话"""
    _, commit, rollback, close = (
        session_resources
    )
    uow = UnitOfWork()

    await uow.__aenter__()

    result = await uow.__aexit__(
        None,
        None,
        None,
    )

    assert result is False
    commit.assert_awaited_once_with()
    rollback.assert_not_awaited()
    close.assert_awaited_once_with()

    with pytest.raises(
            RuntimeError,
            match="工作单元未初始化",
    ):
        _ = uow.session


@pytest.mark.asyncio
async def test_exception_exit_rolls_back_and_closes(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证发生异常时回滚并关闭会话"""
    _, commit, rollback, close = (
        session_resources
    )
    uow = UnitOfWork()
    error = RuntimeError(
        "database operation failed"
    )

    await uow.__aenter__()

    result = await uow.__aexit__(
        RuntimeError,
        error,
        error.__traceback__,
    )

    assert result is False
    commit.assert_not_awaited()
    rollback.assert_awaited_once_with()
    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_context_manager_propagates_exception(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证工作单元不吞掉上下文中的异常"""
    _, commit, rollback, close = (
        session_resources
    )

    with pytest.raises(
            ValueError,
            match="invalid data",
    ):
        async with UnitOfWork():
            raise ValueError(
                "invalid data"
            )

    commit.assert_not_awaited()
    rollback.assert_awaited_once_with()
    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_mark_rollback_forces_rollback(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证显式回滚标记"""
    _, commit, rollback, close = (
        session_resources
    )
    uow = UnitOfWork()

    await uow.__aenter__()
    uow.mark_rollback()

    result = await uow.__aexit__(
        None,
        None,
        None,
    )

    assert result is False
    commit.assert_not_awaited()
    rollback.assert_awaited_once_with()
    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_enter_resets_previous_rollback_mark(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证进入上下文时重置旧回滚标记"""
    _, commit, rollback, close = (
        session_resources
    )
    uow = UnitOfWork()

    uow.mark_rollback()

    await uow.__aenter__()
    await uow.__aexit__(
        None,
        None,
        None,
    )

    commit.assert_awaited_once_with()
    rollback.assert_not_awaited()
    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_commit_failure_rolls_back_and_closes(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证提交失败时回滚并关闭会话"""
    _, commit, rollback, close = (
        session_resources
    )
    commit.side_effect = RuntimeError(
        "commit failed"
    )
    uow = UnitOfWork()

    await uow.__aenter__()

    with pytest.raises(
            RuntimeError,
            match="commit failed",
    ):
        await uow.__aexit__(
            None,
            None,
            None,
        )

    commit.assert_awaited_once_with()
    rollback.assert_awaited_once_with()
    close.assert_awaited_once_with()

    with pytest.raises(
            RuntimeError,
            match="工作单元未初始化",
    ):
        _ = uow.session


@pytest.mark.asyncio
async def test_commit_runs_only_commit_callbacks(
        patch_session_factory: MagicMock,
) -> None:
    """验证提交成功后只执行提交回调"""
    committed = MagicMock()
    rolled_back = MagicMock()
    uow = UnitOfWork()
    uow.on_commit(committed)
    uow.on_rollback(rolled_back)

    await uow.__aenter__()
    await uow.__aexit__(None, None, None)

    committed.assert_called_once_with()
    rolled_back.assert_not_called()


@pytest.mark.asyncio
async def test_rollback_runs_only_rollback_callbacks(
        patch_session_factory: MagicMock,
) -> None:
    """验证事务异常后只执行回滚补偿回调"""
    committed = MagicMock()
    rolled_back = MagicMock()
    uow = UnitOfWork()
    uow.on_commit(committed)
    uow.on_rollback(rolled_back)

    await uow.__aenter__()
    await uow.__aexit__(RuntimeError, RuntimeError("failed"), None)

    committed.assert_not_called()
    rolled_back.assert_called_once_with()


@pytest.mark.asyncio
async def test_rollback_failure_still_closes_session(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证回滚失败时仍关闭会话"""
    _, commit, rollback, close = (
        session_resources
    )
    rollback.side_effect = RuntimeError(
        "rollback failed"
    )
    uow = UnitOfWork()

    await uow.__aenter__()
    uow.mark_rollback()

    with pytest.raises(
            RuntimeError,
            match="rollback failed",
    ):
        await uow.__aexit__(
            None,
            None,
            None,
        )

    commit.assert_not_awaited()
    rollback.assert_awaited_once_with()
    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_cancellation_waits_for_session_close(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证任务取消时仍等待会话关闭"""
    _, commit, rollback, close = (
        session_resources
    )
    entered = asyncio.Event()
    close_started = asyncio.Event()
    allow_close = asyncio.Event()

    async def delayed_close() -> None:
        close_started.set()
        await allow_close.wait()

    close.side_effect = delayed_close

    async def run_transaction() -> None:
        async with UnitOfWork():
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(
        run_transaction()
    )
    await entered.wait()
    task.cancel()
    await close_started.wait()

    for _ in range(3):
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()

    allow_close.set()

    with pytest.raises(
            asyncio.CancelledError,
    ):
        await task

    commit.assert_not_awaited()
    rollback.assert_awaited_once_with()
    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_close_is_idempotent(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证重复关闭保持幂等"""
    _, _, _, close = session_resources
    uow = UnitOfWork()

    await uow.__aenter__()
    await uow.close()
    await uow.close()

    close.assert_awaited_once_with()

    with pytest.raises(
            RuntimeError,
            match="工作单元未初始化",
    ):
        _ = uow.session


@pytest.mark.asyncio
async def test_close_clears_state_before_session_close(
        patch_session_factory: MagicMock,
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证会话关闭失败时内部状态仍被清理"""
    _, _, _, close = session_resources
    close.side_effect = RuntimeError(
        "close failed"
    )
    uow = UnitOfWork()

    await uow.__aenter__()
    uow.mark_rollback()

    with pytest.raises(
            RuntimeError,
            match="close failed",
    ):
        await uow.close()

    with pytest.raises(
            RuntimeError,
            match="工作单元未初始化",
    ):
        _ = uow.session

    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_uow_can_be_reused_after_close(
        patch_session_factory: MagicMock,
        session_factory_resources: tuple[
            async_sessionmaker[AsyncSession],
            MagicMock,
        ],
        session_resources: tuple[
            AsyncSession,
            AsyncMock,
            AsyncMock,
            AsyncMock,
        ],
) -> None:
    """验证关闭后可以重新进入同一工作单元"""
    _, factory_mock = session_factory_resources
    _, commit, rollback, close = (
        session_resources
    )
    uow = UnitOfWork()

    await uow.__aenter__()
    await uow.__aexit__(
        None,
        None,
        None,
    )

    await uow.__aenter__()
    uow.mark_rollback()
    await uow.__aexit__(
        None,
        None,
        None,
    )

    assert factory_mock.call_count == 2
    assert commit.await_count == 1
    assert rollback.await_count == 1
    assert close.await_count == 2
