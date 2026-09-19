"""审计记录器测试

验证上下文注入、敏感数据净化、失败策略传递和审计开关行为。

核心功能：
  - test_record_builds_sanitized_event:
    验证事件构造与净化
  - test_record_context_overrides_current_context:
    验证显式上下文优先级
  - test_record_uses_system_source_by_default:
    验证缺省来源
  - test_failure_mode_returns_configured_policy:
    验证默认失败策略
  - test_record_returns_when_disabled:
    验证关闭审计
"""

from typing import Any
from unittest.mock import create_autospec

import pytest

from datamind.audit import recorder as recorder_module
from datamind.audit.errors import AuditValidationError
from datamind.audit.policy import AuditFailureMode
from datamind.audit.recorder import AuditRecorder
from datamind.audit.service import (
    AuditResult,
    AuditService,
)
from datamind.config.audit import AuditConfig


def create_recorder(
        monkeypatch: pytest.MonkeyPatch,
        *,
        enabled: bool = True,
        context: dict[str, Any] | None = None,
) -> tuple[AuditRecorder, Any]:
    """创建记录器"""
    config = AuditConfig.model_validate({
        "enabled": enabled,
    })
    service = create_autospec(
        AuditService,
        instance=True,
    )
    service.record.return_value = AuditResult(
        audit_id="aud_test",
        recorded=True,
    )
    monkeypatch.setitem(
        vars(recorder_module),
        "get_audit_config",
        lambda: config,
    )
    monkeypatch.setitem(
        vars(recorder_module),
        "get_context",
        lambda: context or {},
    )
    return AuditRecorder(service=service), service


@pytest.mark.asyncio
async def test_record_builds_sanitized_event(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试构造并净化审计事件"""
    recorder, service = create_recorder(
        monkeypatch,
        context={
            "source": "http",
            "user": "alice",
            "trace_id": "trace-1",
            "request_id": "request-1",
            "ip": "192.168.1.100",
            "hostname": "client",
        },
    )

    result = await recorder.record(
        action="model.register",
        target_type="model",
        target_id="mdl_1",
        error="password=secret",
        before={
            "token": "secret",
            "status": "inactive",
        },
        after={"password": "secret", "name": "scorecard"},
        failure_mode=AuditFailureMode.CLOSED,
    )

    awaited_call = service.record.await_args
    assert awaited_call is not None

    event = awaited_call.args[0]
    mode = awaited_call.kwargs["failure_mode"]
    assert result is not None and result.recorded is True
    assert event.source == "http"
    assert event.user == "alice"
    assert event.trace_id == "trace-1"
    assert event.request_id == "request-1"
    assert event.ip == "192.168.1.100"
    assert event.hostname == "client"
    assert event.error == "password=secret"
    assert event.before == {
        "token": "[REDACTED]",
        "status": "inactive",
    }
    assert event.after == {
        "password": "[REDACTED]",
        "name": "scorecard",
    }
    assert mode is AuditFailureMode.CLOSED


@pytest.mark.asyncio
async def test_record_context_overrides_current_context(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试显式上下文覆盖当前请求上下文"""
    recorder, service = create_recorder(
        monkeypatch,
        context={
            "source": "http",
            "user": "alice",
        },
    )

    await recorder.record(
        action="model.register",
        target_type="model",
        target_id="mdl_1",
        context={
            "source": "cli",
            "user": "admin",
            "api_key": "secret",
        },
    )

    awaited_call = service.record.await_args
    assert awaited_call is not None

    event = awaited_call.args[0]
    assert event.source == "cli"
    assert event.user == "admin"
    assert event.context == {
        "source": "cli",
        "user": "admin",
        "api_key": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_record_uses_system_source_by_default(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试缺少上下文来源时使用 system"""
    recorder, service = create_recorder(monkeypatch)

    await recorder.record(
        action="model.register",
        target_type="model",
        target_id="mdl_1",
    )

    awaited_call = service.record.await_args
    assert awaited_call is not None

    event = awaited_call.args[0]
    assert event.source == "system"


@pytest.mark.asyncio
async def test_record_returns_when_disabled(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试关闭审计后不调用服务"""
    recorder, service = create_recorder(
        monkeypatch,
        enabled=False,
    )

    assert await recorder.record(
        action="model.register",
        target_type="model",
        target_id="mdl_1",
    ) is None
    service.record.assert_not_awaited()


def test_failure_mode_returns_configured_policy(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试记录器返回配置的默认失败策略"""
    config = AuditConfig.model_validate({
        "failure_mode": AuditFailureMode.CLOSED,
    })
    monkeypatch.setitem(
        vars(recorder_module),
        "get_audit_config",
        lambda: config,
    )

    recorder = AuditRecorder(
        service=create_autospec(
            AuditService,
            instance=True,
        )
    )

    assert recorder.failure_mode is AuditFailureMode.CLOSED


@pytest.mark.asyncio
async def test_record_rejects_action_without_operation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试记录器拒绝缺少操作名称的 action"""
    recorder, service = create_recorder(
        monkeypatch
    )

    with pytest.raises(
            AuditValidationError,
            match="operation 不能为空",
    ):
        await recorder.record(
            action="model",
            target_type="model",
            target_id="mdl_1",
        )

    service.record.assert_not_awaited()
