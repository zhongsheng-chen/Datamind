"""审计事件测试

验证审计事件字段、随机 ID 和 UTC 时间生成行为。

核心功能：
  - test_audit_event_preserves_fields:
    验证事件字段
  - test_audit_event_generates_random_id:
    验证审计 ID 生成
  - test_each_audit_event_generates_independent_id:
    验证 ID 独立性
  - test_audit_event_occurred_at_defaults_to_current_utc:
    验证 UTC 时间
  - test_audit_event_accepts_optional_fields_as_none:
    验证可选字段
  - test_audit_event_accepts_failure_information:
    验证失败信息
  - test_audit_event_rejects_blank_required_fields:
    验证必填字段
  - test_audit_event_rejects_oversized_optional_fields:
    验证可选字段长度
"""

from datetime import datetime, timezone
from typing import Any

import pytest

from datamind.audit import event as event_module
from datamind.audit.errors import AuditValidationError
from datamind.audit.event import AuditEvent


def create_event(**overrides: Any) -> AuditEvent:
    """创建审计事件测试对象"""
    values: dict[str, Any] = {
        "action": "model.register",
        "resource": "model",
        "operation": "register",
        "target_type": "model",
        "target_id": "mdl_0123456789abcdef",
        "status": "success",
        "error": None,
        "trace_id": "0123456789abcdef0123456789abcdef",
        "request_id": "req_0123456789abcdef",
        "source": "cli",
        "user": "admin",
        "ip": "192.168.1.100",
        "hostname": "client",
        "before": None,
        "after": {
            "name": "scorecard",
            "version": "1.0.0",
        },
        "context": {
            "operator": "admin",
        },
    }
    values.update(overrides)

    return AuditEvent(**values)


def test_audit_event_preserves_fields() -> None:
    """测试审计事件保留全部业务字段"""
    event = create_event()

    assert event.action == "model.register"
    assert event.resource == "model"
    assert event.operation == "register"
    assert event.target_type == "model"
    assert event.target_id == "mdl_0123456789abcdef"
    assert event.status == "success"
    assert event.error is None
    assert event.trace_id == "0123456789abcdef0123456789abcdef"
    assert event.request_id == "req_0123456789abcdef"
    assert event.source == "cli"
    assert event.user == "admin"
    assert event.ip == "192.168.1.100"
    assert event.hostname == "client"
    assert event.before is None
    assert event.after == {
        "name": "scorecard",
        "version": "1.0.0",
    }
    assert event.context == {
        "operator": "admin",
    }


def test_audit_event_generates_random_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试审计事件使用 aud 前缀生成随机 ID"""
    prefixes: list[str] = []

    def fake_generate_random_id(
        *,
        prefix: str,
    ) -> str:
        prefixes.append(prefix)
        return "aud_123456789abc"

    monkeypatch.setitem(
        vars(event_module),
        "generate_random_id",
        fake_generate_random_id,
    )

    event = create_event()

    assert prefixes == [
        "aud",
    ]
    assert event.audit_id == "aud_123456789abc"


def test_each_audit_event_generates_independent_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试每个审计事件独立生成 ID"""
    generated_ids = iter(
        [
            "aud_111111111111",
            "aud_222222222222",
        ]
    )

    def fake_generate_random_id(
        *,
        prefix: str,
    ) -> str:
        assert prefix == "aud"
        return next(generated_ids)

    monkeypatch.setitem(
        vars(event_module),
        "generate_random_id",
        fake_generate_random_id,
    )

    first_event = create_event()
    second_event = create_event()

    assert first_event.audit_id == "aud_111111111111"
    assert second_event.audit_id == "aud_222222222222"
    assert first_event.audit_id != second_event.audit_id


def test_audit_event_occurred_at_defaults_to_current_utc() -> None:
    """测试事件发生时间默认为当前 UTC 时间"""
    before = datetime.now(timezone.utc)

    event = create_event()

    after = datetime.now(timezone.utc)

    assert event.occurred_at.tzinfo is timezone.utc
    assert before <= event.occurred_at <= after


def test_audit_event_accepts_explicit_identity_and_time() -> None:
    """测试允许显式指定审计 ID 和发生时间"""
    occurred_at = datetime(
        2026,
        7,
        22,
        8,
        30,
        tzinfo=timezone.utc,
    )

    event = create_event(
        audit_id="aud_fixed123456",
        occurred_at=occurred_at,
    )

    assert event.audit_id == "aud_fixed123456"
    assert event.occurred_at is occurred_at


def test_audit_event_accepts_optional_fields_as_none() -> None:
    """测试可选字段允许为空"""
    event = create_event(
        error=None,
        trace_id=None,
        request_id=None,
        source=None,
        user=None,
        ip=None,
        hostname=None,
        before=None,
        after=None,
        context=None,
    )

    assert event.error is None
    assert event.trace_id is None
    assert event.request_id is None
    assert event.source == "system"
    assert event.user is None
    assert event.ip is None
    assert event.hostname is None
    assert event.before is None
    assert event.after is None
    assert event.context is None


def test_audit_event_accepts_failure_information() -> None:
    """测试失败事件保存错误和变更前数据"""
    event = create_event(
        status="failed",
        error="模型文件不存在",
        before={
            "status": "pending",
        },
        after=None,
        context={
            "model_path": "/models/scorecard.pkl",
        },
    )

    assert event.status == "failed"
    assert event.error == "模型文件不存在"
    assert event.before == {
        "status": "pending",
    }
    assert event.after is None
    assert event.context == {
        "model_path": "/models/scorecard.pkl",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source", "api", "审计事件枚举值无效"),
        ("status", "pending", "审计事件枚举值无效"),
        ("target_id", "x" * 65, "target_id 长度不能超过 64"),
    ],
)
def test_audit_event_rejects_invalid_fields(
        field: str,
        value: str,
        message: str,
) -> None:
    """测试事件在写数据库前拒绝非法字段"""
    with pytest.raises(
        AuditValidationError,
        match=message,
    ):
        create_event(**{field: value})


@pytest.mark.parametrize(
    "field",
    [
        "audit_id",
        "action",
        "resource",
        "operation",
        "target_type",
        "target_id",
    ],
)
def test_audit_event_rejects_blank_required_fields(
        field: str,
) -> None:
    """测试必填字段拒绝空白值"""
    with pytest.raises(
            AuditValidationError,
            match=rf"{field} 不能为空",
    ):
        create_event(**{field: " "})


@pytest.mark.parametrize(
    ("field", "max_length"),
    [
        ("trace_id", 64),
        ("request_id", 64),
        ("user", 64),
        ("ip", 64),
        ("hostname", 128),
    ],
)
def test_audit_event_rejects_oversized_optional_fields(
        field: str,
        max_length: int,
) -> None:
    """测试可选字段拒绝超过长度限制的值"""
    with pytest.raises(
            AuditValidationError,
            match=rf"{field} 长度不能超过 {max_length}",
    ):
        create_event(**{
            field: "x" * (max_length + 1),
        })


def test_audit_event_rejects_inconsistent_action() -> None:
    """测试 action 必须与资源和操作名称一致"""
    with pytest.raises(
            AuditValidationError,
            match="action 必须与 resource 和 operation 一致",
    ):
        create_event(
            action="model.delete"
        )


def test_audit_event_rejects_naive_occurred_at() -> None:
    """测试事件发生时间必须包含时区"""
    with pytest.raises(
        AuditValidationError,
        match="occurred_at 必须包含时区",
    ):
        create_event(
            occurred_at=datetime(2026, 7, 27)
        )
