"""审计服务测试

验证审计持久化结果、失败策略、瞬时故障重试和审计开关行为。

核心功能：
  - test_record_success:
    验证成功记录
  - test_disabled_service_skips_sink:
    验证关闭审计
  - test_open_mode_returns_failure:
    验证 Fail-open
  - test_closed_mode_raises:
    验证 Fail-closed
  - test_transient_error_retries:
    验证瞬时错误重试
  - test_transient_error_uses_exponential_backoff:
    验证指数退避
  - test_permanent_error_does_not_retry:
    验证永久错误不重试
"""

from unittest.mock import (
    AsyncMock,
    call,
)

import pytest
from sqlalchemy.exc import OperationalError

from datamind.audit import service as service_module
from datamind.audit.errors import AuditWriteError
from datamind.audit.event import AuditEvent
from datamind.audit.policy import AuditFailureMode
from datamind.audit.service import AuditService
from datamind.config.audit import AuditConfig
from datamind.db.models.audit import Audit


class SinkStub:
    """可配置失败序列的存储端"""

    def __init__(
            self,
            outcomes: list[Audit | Exception],
    ) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def write(
            self,
            event: AuditEvent,
    ) -> Audit:
        _ = event
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


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
        trace_id=None,
        request_id=None,
        source="cli",
        user=None,
        ip=None,
        hostname=None,
        before=None,
        after=None,
        context=None,
    )


def create_service(
        sink: SinkStub,
        *,
        enabled: bool = True,
        failure_mode: AuditFailureMode = AuditFailureMode.OPEN,
        max_retries: int = 2,
) -> AuditService:
    """创建隔离配置的审计服务"""
    return AuditService(
        sink=sink,
        config=AuditConfig.model_validate({
            "enabled": enabled,
            "failure_mode": failure_mode,
            "max_retries": max_retries,
            "retry_base_delay": 0.001,
        }),
    )


@pytest.mark.asyncio
async def test_record_success() -> None:
    """测试成功写入返回成功结果"""
    sink = SinkStub([Audit()])
    result = await create_service(sink).record(create_event())
    assert result.recorded is True
    assert sink.calls == 1


@pytest.mark.asyncio
async def test_disabled_service_skips_sink() -> None:
    """测试关闭审计后不调用存储端"""
    sink = SinkStub([Audit()])

    result = await create_service(
        sink,
        enabled=False,
    ).record(
        create_event()
    )

    assert result.recorded is False
    assert result.error is None
    assert sink.calls == 0


@pytest.mark.asyncio
async def test_open_mode_returns_failure() -> None:
    """测试 Fail-open 返回失败结果"""
    sink = SinkStub([ValueError("invalid")])
    result = await create_service(sink).record(create_event())
    assert result.recorded is False
    assert result.error == "invalid"
    assert sink.calls == 1


@pytest.mark.asyncio
async def test_closed_mode_raises() -> None:
    """测试 Fail-closed 抛出写入异常"""
    sink = SinkStub([ValueError("invalid")])
    service = create_service(
        sink,
        failure_mode=AuditFailureMode.CLOSED,
    )
    with pytest.raises(AuditWriteError, match="invalid"):
        await service.record(create_event())


@pytest.mark.asyncio
async def test_record_overrides_default_failure_mode() -> None:
    """测试单次记录可以覆盖默认失败策略"""
    sink = SinkStub([
        ValueError("invalid")
    ])
    service = create_service(
        sink,
        failure_mode=AuditFailureMode.OPEN,
    )

    with pytest.raises(
            AuditWriteError,
            match="invalid",
    ):
        await service.record(
            create_event(),
            failure_mode=AuditFailureMode.CLOSED,
        )


@pytest.mark.asyncio
async def test_transient_error_retries() -> None:
    """测试瞬时数据库错误进行重试"""
    error = OperationalError("sql", {}, RuntimeError("offline"))
    sink = SinkStub([error, Audit()])
    result = await create_service(sink).record(create_event())
    assert result.recorded is True
    assert sink.calls == 2


@pytest.mark.asyncio
async def test_transient_error_uses_exponential_backoff(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试连续瞬时错误按照指数间隔重试"""
    first_error = OperationalError(
        "sql",
        {},
        RuntimeError("offline"),
    )
    second_error = OperationalError(
        "sql",
        {},
        RuntimeError("offline"),
    )
    sink = SinkStub([
        first_error,
        second_error,
        Audit(),
    ])
    sleep = AsyncMock()
    monkeypatch.setitem(
        vars(service_module.asyncio),
        "sleep",
        sleep,
    )

    result = await create_service(
        sink,
        max_retries=3,
    ).record(
        create_event()
    )

    assert result.recorded is True
    assert sink.calls == 3
    assert sleep.await_args_list == [
        call(0.001),
        call(0.002),
    ]


@pytest.mark.asyncio
async def test_transient_error_returns_after_retries_exhausted() -> None:
    """测试 Fail-open 在瞬时错误重试耗尽后返回失败"""
    errors: list[Audit | Exception] = [
        OperationalError(
            "sql",
            {},
            RuntimeError("offline"),
        )
        for _ in range(2)
    ]
    sink = SinkStub(errors)

    result = await create_service(
        sink,
        max_retries=2,
    ).record(
        create_event()
    )

    assert result.recorded is False
    assert result.error is not None
    assert "offline" in result.error
    assert sink.calls == 2


@pytest.mark.asyncio
async def test_permanent_error_does_not_retry() -> None:
    """测试永久错误不进行重试"""
    sink = SinkStub([ValueError("invalid")])
    result = await create_service(sink).record(create_event())
    assert result.recorded is False
    assert sink.calls == 1
