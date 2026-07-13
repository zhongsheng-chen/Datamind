# tests/audit/test_policy.py

"""审计失败策略测试

验证审计失败处理策略枚举的取值与字符串转换行为。

核心功能：
  - test_failure_mode_values:
    验证 Fail-open 和 Fail-closed 策略的字符串值
"""

from datamind.audit.policy import AuditFailureMode


def test_failure_mode_values() -> None:
    """测试失败策略枚举值"""
    assert str(AuditFailureMode.OPEN) == "open"
    assert str(AuditFailureMode.CLOSED) == "closed"
