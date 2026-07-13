# tests/db/repositories/test_base.py

"""数据库仓储基类测试

验证 BaseRepository 对异步数据库会话的保存，
以及添加、批量添加、删除、刷新和对象重载操作。

核心功能：
  - test_session_returns_original_session:
    验证公开属性返回原始数据库会话
  - test_add:
    验证添加单个对象
  - test_add_all:
    验证批量添加对象
  - test_add_all_preserves_iterable:
    验证批量添加不会提前消费可迭代对象
  - test_delete:
    验证异步删除对象
  - test_flush:
    验证异步刷新会话
  - test_refresh:
    验证异步刷新对象状态
"""

from collections.abc import Iterable
from typing import (
    Any,
    cast,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from datamind.db.repositories.base import BaseRepository


def create_repository(
) -> tuple[
    BaseRepository,
    AsyncSession,
    MagicMock,
    MagicMock,
    AsyncMock,
    AsyncMock,
    AsyncMock,
]:
    """创建仓储、会话及方法替身"""
    add = MagicMock()
    add_all = MagicMock()
    delete = AsyncMock()
    flush = AsyncMock()
    refresh = AsyncMock()

    session_mock = MagicMock(
        spec=AsyncSession
    )
    session_mock.add = add
    session_mock.add_all = add_all
    session_mock.delete = delete
    session_mock.flush = flush
    session_mock.refresh = refresh

    session = cast(
        AsyncSession,
        session_mock,
    )
    repository = BaseRepository(
        session
    )

    return (
        repository,
        session,
        add,
        add_all,
        delete,
        flush,
        refresh,
    )


def test_session_returns_original_session() -> None:
    """验证公开属性返回原始数据库会话"""
    (
        repository,
        session,
        _,
        _,
        _,
        _,
        _,
    ) = create_repository()

    assert repository.session is session


def test_add() -> None:
    """验证添加单个对象"""
    (
        repository,
        _,
        add,
        _,
        _,
        _,
        _,
    ) = create_repository()
    model = MagicMock()

    repository.add(
        model
    )

    add.assert_called_once_with(
        model
    )


def test_add_all() -> None:
    """验证批量添加对象"""
    (
        repository,
        _,
        _,
        add_all,
        _,
        _,
        _,
    ) = create_repository()
    models = [
        MagicMock(),
        MagicMock(),
    ]

    repository.add_all(
        models
    )

    add_all.assert_called_once_with(
        models
    )


def test_add_all_preserves_iterable() -> None:
    """验证批量添加不会提前消费可迭代对象"""
    (
        repository,
        _,
        _,
        add_all,
        _,
        _,
        _,
    ) = create_repository()
    models = [
        MagicMock(),
        MagicMock(),
    ]
    iterable = cast(
        Iterable[Any],
        (
            model
            for model in models
        ),
    )

    repository.add_all(
        iterable
    )

    add_all.assert_called_once_with(
        iterable
    )


@pytest.mark.asyncio
async def test_delete() -> None:
    """验证异步删除对象"""
    (
        repository,
        _,
        _,
        _,
        delete,
        _,
        _,
    ) = create_repository()
    model = MagicMock()

    await repository.delete(
        model
    )

    delete.assert_awaited_once_with(
        model
    )


@pytest.mark.asyncio
async def test_flush() -> None:
    """验证异步刷新会话"""
    (
        repository,
        _,
        _,
        _,
        _,
        flush,
        _,
    ) = create_repository()

    await repository.flush()

    flush.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_refresh() -> None:
    """验证异步刷新对象状态"""
    (
        repository,
        _,
        _,
        _,
        _,
        _,
        refresh,
    ) = create_repository()
    model = MagicMock()

    await repository.refresh(
        model
    )

    refresh.assert_awaited_once_with(
        model
    )
