# tests/audit/sinks/test_database.py

"""数据库审计存储端测试

验证审计事件字段映射、重复写入和并发唯一键冲突恢复行为。

核心功能：
  - test_database_sink_maps_event: 验证字段映射
  - test_database_sink_returns_existing_event: 验证幂等写入
  - test_database_sink_recovers_from_concurrent_insert:
    验证并发写入冲突后返回已有记录
  - test_database_sink_reraises_unresolved_integrity_error:
    验证无法恢复的唯一键冲突继续抛出
"""

from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import IntegrityError

from datamind.audit.enums import (
    AuditSource,
    AuditStatus,
)
from datamind.audit.event import AuditEvent
from datamind.audit.sinks.database import DatabaseAuditSink


class FakeUnitOfWork:
    """异步工作单元桩"""

    session = object()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


class FakeRepository:
    """审计仓储桩"""

    existing: object | None = None
    created: object = object()
    values: dict[str, Any] | None = None

    def __init__(self, session: object) -> None:
        assert session is FakeUnitOfWork.session

    async def get_by_audit_id(self, _audit_id: str) -> object | None:
        return self.existing

    def create_audit(self, **values: Any) -> object:
        type(self).values = values
        return self.created


def create_event() -> AuditEvent:
    """创建审计事件"""
    return AuditEvent(
        action="model.register",
        resource="model",
        operation="register",
        target_type="model",
        target_id="mdl_1",
        status="success",
        error=None,
        trace_id="trace",
        request_id="request",
        source="cli",
        user="admin",
        ip="127.0.0.1",
        hostname="client",
        before=None,
        after={"name": "scorecard"},
        context={"reason": "test"},
    )


@pytest.fixture(autouse=True)
def configure_database_sink(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """替换数据库基础设施"""
    FakeRepository.existing = None
    FakeRepository.created = object()
    FakeRepository.values = None
    monkeypatch.setattr(
        "datamind.audit.sinks.database.UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setattr(
        "datamind.db.repositories.audit.AuditRepository",
        FakeRepository,
    )


@pytest.mark.asyncio
async def test_database_sink_maps_event() -> None:
    """测试完整映射事件字段"""
    event = create_event()

    result = await DatabaseAuditSink().write(event)

    assert result is FakeRepository.created
    assert FakeRepository.values is not None
    assert FakeRepository.values["audit_id"] == event.audit_id
    assert (
        FakeRepository.values["source"]
        is AuditSource.CLI
    )
    assert (
        FakeRepository.values["status"]
        is AuditStatus.SUCCESS
    )
    assert FakeRepository.values["after"] == event.after


@pytest.mark.asyncio
async def test_database_sink_returns_existing_event() -> None:
    """测试重复事件直接返回已有记录"""
    existing = object()
    FakeRepository.existing = existing

    assert await DatabaseAuditSink().write(create_event()) is existing
    assert FakeRepository.values is None


@pytest.mark.asyncio
async def test_database_sink_recovers_from_concurrent_insert(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试并发写入冲突后返回另一事务写入的记录"""
    existing = object()
    FakeRepository.existing = existing
    error = IntegrityError(
        None,
        {},
        RuntimeError("duplicate audit_id"),
    )
    write_once = AsyncMock(
        side_effect=error
    )
    monkeypatch.setattr(
        DatabaseAuditSink,
        "_write_once",
        write_once,
    )

    event = create_event()
    result = await DatabaseAuditSink().write(
        event
    )

    assert result is existing
    write_once.assert_awaited_once_with(
        event
    )


@pytest.mark.asyncio
async def test_database_sink_reraises_unresolved_integrity_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试并发冲突后找不到已有记录时继续抛出原异常"""
    error = IntegrityError(
        None,
        {},
        RuntimeError("duplicate audit_id"),
    )
    monkeypatch.setattr(
        DatabaseAuditSink,
        "_write_once",
        AsyncMock(
            side_effect=error
        ),
    )

    with pytest.raises(
            IntegrityError
    ) as exc_info:
        await DatabaseAuditSink().write(
            create_event()
        )

    assert exc_info.value is error
