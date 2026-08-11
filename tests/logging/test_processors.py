# tests/logging/test_processors.py

"""日志增强处理器测试

验证时间戳、上下文补充、敏感信息脱敏和日志采样行为。

核心功能：
  - test_add_timestamp_uses_iso_format:
    验证默认使用带时区的 ISO 8601 时间格式
  - test_add_timestamp_uses_custom_format:
    验证支持自定义时间格式
  - test_add_context_adds_current_context:
    验证补充当前请求上下文
  - test_add_context_does_not_override_event_fields:
    验证日志事件字段优先于上下文字段
  - test_add_context_ignores_none_values:
    验证忽略值为 None 的上下文字段
  - test_mask_sensitive_masks_top_level_string:
    验证脱敏顶层字符串字段
  - test_mask_sensitive_masks_short_value_completely:
    验证较短敏感值被完全脱敏
  - test_mask_sensitive_supports_zero_prefix_and_suffix:
    验证前后保留位数均可为零
  - test_mask_sensitive_supports_zero_suffix:
    验证后面保留位数为零时不会泄露原值
  - test_mask_sensitive_recursively_masks_nested_values:
    验证递归脱敏嵌套字典、列表和元组
  - test_mask_sensitive_masks_all_values_in_sensitive_container:
    验证敏感字段容器中的所有叶子值都会被脱敏
  - test_mask_sensitive_propagates_sensitive_state_through_containers:
    验证敏感状态会跨字典、列表和元组持续传播
  - test_mask_sensitive_handles_non_string_values:
    验证脱敏非字符串敏感值并保留 None
  - test_mask_sensitive_preserves_explicit_status_keys:
    验证明确定义的非敏感状态字段保持可读
  - test_mask_sensitive_does_not_modify_original_event:
    验证脱敏处理器不修改原始事件及其嵌套容器
  - test_mask_sensitive_rejects_invalid_parameters:
    验证拒绝无效脱敏参数
  - test_sampling_rate_one_keeps_event:
    验证采样率为 1 时保留日志
  - test_sampling_keeps_sampled_event:
    验证命中采样时保留普通日志
  - test_sampling_drops_unsampled_event:
    验证未命中采样时丢弃普通日志
  - test_sampling_always_keeps_important_levels:
    验证重要级别日志不参与采样
  - test_sampling_always_keeps_exception_logs:
    验证包含异常信息的日志不参与采样
  - test_sampling_rejects_invalid_rate:
    验证拒绝无效采样率
"""

from datetime import datetime
from typing import Any

import pytest
import structlog

from datamind.context import set_context
from datamind.logging.processors import (
    add_context,
    add_timestamp,
    mask_sensitive,
    sampling,
)


def test_add_timestamp_uses_iso_format() -> None:
    """测试默认使用带时区的 ISO 8601 时间格式"""
    processor = add_timestamp("Asia/Shanghai")
    event = {
        "event": "测试日志",
    }

    result = processor(
        None,
        "info",
        event,
    )

    timestamp_value = result["timestamp"]
    assert isinstance(timestamp_value, str)

    timestamp = datetime.fromisoformat(
        timestamp_value
    )
    utc_offset = timestamp.utcoffset()

    assert timestamp.tzinfo is not None
    assert utc_offset is not None
    assert utc_offset.total_seconds() == 8 * 60 * 60


def test_add_timestamp_uses_custom_format() -> None:
    """测试使用自定义时间格式"""
    processor = add_timestamp(
        "UTC",
        "%Y-%m-%d %H:%M:%S",
    )

    result = processor(
        None,
        "info",
        {},
    )

    timestamp = result["timestamp"]
    assert isinstance(timestamp, str)

    datetime.strptime(
        timestamp,
        "%Y-%m-%d %H:%M:%S",
    )


def test_add_context_adds_current_context() -> None:
    """测试补充当前请求上下文"""
    set_context(
        trace_id="a1b2c3d4",
        request_id="9f8e7d6c",
        source="http",
        user="admin",
        ip="192.168.1.100",
        hostname="client",
    )

    result = add_context()(
        None,
        "info",
        {
            "event": "模型注册成功",
        },
    )

    assert result["trace_id"] == "a1b2c3d4"
    assert result["request_id"] == "9f8e7d6c"
    assert result["source"] == "http"
    assert result["user"] == "admin"
    assert result["ip"] == "192.168.1.100"
    assert result["hostname"] == "client"


def test_add_context_does_not_override_event_fields() -> None:
    """测试日志事件字段优先于上下文字段"""
    set_context(
        trace_id="context-trace",
        user="context-user",
    )

    result = add_context()(
        None,
        "info",
        {
            "trace_id": "event-trace",
            "user": "event-user",
        },
    )

    assert result["trace_id"] == "event-trace"
    assert result["user"] == "event-user"


def test_add_context_ignores_none_values() -> None:
    """测试不补充值为 None 的上下文字段"""
    set_context(
        trace_id="a1b2c3d4",
        user=None,
    )

    result = add_context()(
        None,
        "info",
        {},
    )

    assert result["trace_id"] == "a1b2c3d4"
    assert "user" not in result


def test_mask_sensitive_masks_top_level_string() -> None:
    """测试脱敏顶层字符串字段"""
    result = mask_sensitive()(
        None,
        "info",
        {
            "password": "12345678",
            "access_token": "abcdefgh",
            "user": "admin",
        },
    )

    assert result["password"] == "12****78"
    assert result["access_token"] == "ab****gh"
    assert result["user"] == "admin"


def test_mask_sensitive_masks_short_value_completely() -> None:
    """测试较短敏感值被完全脱敏"""
    result = mask_sensitive(
        prefix=2,
        suffix=2,
    )(
        None,
        "info",
        {
            "pwd": "1234",
        },
    )

    assert result["pwd"] == "****"


def test_mask_sensitive_supports_zero_prefix_and_suffix() -> None:
    """测试前后保留位数为零"""
    result = mask_sensitive(
        prefix=0,
        suffix=0,
    )(
        None,
        "info",
        {
            "token": "abcdefgh",
        },
    )

    assert result["token"] == "********"


def test_mask_sensitive_supports_zero_suffix() -> None:
    """测试后面保留位数为零时不会泄露原值"""
    result = mask_sensitive(
        prefix=2,
        suffix=0,
    )(
        None,
        "info",
        {
            "token": "abcdefgh",
        },
    )

    assert result["token"] == "ab******"


def test_mask_sensitive_recursively_masks_nested_values() -> None:
    """测试递归脱敏嵌套字典、列表和元组"""
    result = mask_sensitive()(
        None,
        "info",
        {
            "request": {
                "password": "12345678",
                "items": [
                    {
                        "api_key": "abcdefgh",
                    }
                ],
                "credentials": (
                    {
                        "secret": "87654321",
                    },
                ),
            },
        },
    )

    request = result["request"]
    assert isinstance(
        request,
        dict,
    )

    items = request["items"]
    assert isinstance(
        items,
        list,
    )

    first_item = items[0]
    assert isinstance(
        first_item,
        dict,
    )

    credentials = request["credentials"]
    assert isinstance(
        credentials,
        tuple,
    )

    first_credential = credentials[0]
    assert isinstance(
        first_credential,
        dict,
    )

    assert request["password"] == "12****78"
    assert first_item["api_key"] == "ab****gh"
    assert first_credential["secret"] == "87****21"


def test_mask_sensitive_masks_all_values_in_sensitive_container() -> None:
    """测试敏感字段容器中的所有叶子值都会被脱敏"""
    result = mask_sensitive()(
        None,
        "info",
        {
            "credentials": (
                "username",
                "password",
            ),
        },
    )

    assert result["credentials"] == (
        "us****me",
        "pa****rd",
    )


def test_mask_sensitive_propagates_sensitive_state_through_containers() -> None:
    """测试敏感状态会跨字典、列表和元组持续传播"""
    result = mask_sensitive()(
        None,
        "info",
        {
            "credentials": {
                "accounts": [
                    (
                        {
                            "username": "operator",
                            "enabled": True,
                            "metadata": None,
                        },
                    ),
                ],
            },
        },
    )

    credentials = result["credentials"]
    assert isinstance(credentials, dict)

    accounts = credentials["accounts"]
    assert isinstance(accounts, list)
    assert isinstance(accounts[0], tuple)

    account = accounts[0][0]
    assert isinstance(account, dict)
    assert account == {
        "username": "op****or",
        "enabled": "********",
        "metadata": None,
    }


def test_mask_sensitive_handles_non_string_values() -> None:
    """测试非字符串敏感值和 None"""
    result = mask_sensitive()(
        None,
        "info",
        {
            "token_count": 123,
            "authorization": False,
            "secret": None,
        },
    )

    assert result["token_count"] == "********"
    assert result["authorization"] == "********"
    assert result["secret"] is None


def test_mask_sensitive_preserves_explicit_status_keys() -> None:
    """测试明确的非敏感状态字段保持可读"""
    result = mask_sensitive()(
        None,
        "info",
        {
            "refresh_token_revoked": True,
            "refresh_token": "abcdefgh",
            "token_count": 1,
        },
    )

    assert result["refresh_token_revoked"] is True
    assert result["refresh_token"] == "ab****gh"
    assert result["token_count"] == "********"


def test_mask_sensitive_does_not_modify_original_event() -> None:
    """测试脱敏处理器不修改原始事件及其嵌套容器"""
    original = {
        "request": {
            "password": "12345678",
            "credentials": [
                (
                    {
                        "username": "operator",
                    },
                ),
            ],
        },
    }

    result = mask_sensitive()(
        None,
        "info",
        original,
    )

    request = result["request"]
    assert isinstance(
        request,
        dict,
    )

    assert request["password"] == "12****78"
    assert request["credentials"][0][0]["username"] == "op****or"
    assert original["request"]["password"] == "12345678"
    assert original["request"]["credentials"][0][0]["username"] == (
        "operator"
    )


@pytest.mark.parametrize(
    (
        "kwargs",
        "message",
    ),
    [
        (
            {
                "mask_char": "",
            },
            "mask_char 不能为空",
        ),
        (
            {
                "mask_char": "**",
            },
            "mask_char 只能包含一个字符",
        ),
        (
            {
                "prefix": -1,
            },
            "prefix 必须大于等于 0",
        ),
        (
            {
                "suffix": -1,
            },
            "suffix 必须大于等于 0",
        ),
    ],
)
def test_mask_sensitive_rejects_invalid_parameters(
        kwargs: dict[str, Any],
        message: str,
) -> None:
    """测试拒绝无效的脱敏参数"""
    with pytest.raises(
            ValueError,
            match=message,
    ):
        mask_sensitive(**kwargs)


def test_sampling_rate_one_keeps_event() -> None:
    """测试采样率为 1 时保留日志"""
    event = {
        "level": "info",
        "event": "普通日志",
    }

    result = sampling(1.0)(
        None,
        "info",
        event,
    )

    assert result is event


def test_sampling_keeps_sampled_event(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试命中采样时保留普通日志"""
    monkeypatch.setattr(
        "datamind.logging.processors.random.random",
        lambda: 0.2,
    )

    event = {
        "level": "info",
        "event": "普通日志",
    }

    result = sampling(0.5)(
        None,
        "info",
        event,
    )

    assert result is event


def test_sampling_drops_unsampled_event(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未命中采样时丢弃普通日志"""
    monkeypatch.setattr(
        "datamind.logging.processors.random.random",
        lambda: 0.8,
    )

    with pytest.raises(
            structlog.DropEvent
    ):
        sampling(0.5)(
            None,
            "info",
            {
                "level": "info",
                "event": "普通日志",
            },
        )


@pytest.mark.parametrize(
    "level",
    [
        "warning",
        "error",
        "critical",
        "fatal",
    ],
)
def test_sampling_always_keeps_important_levels(
        level: str,
) -> None:
    """测试重要级别日志不参与采样"""
    event = {
        "level": level,
        "event": "重要日志",
    }

    result = sampling(0.0)(
        None,
        level,
        event,
    )

    assert result is event


@pytest.mark.parametrize(
    "exception_field",
    [
        "exc_info",
        "exception",
    ],
)
def test_sampling_always_keeps_exception_logs(
        exception_field: str,
) -> None:
    """测试包含异常信息的日志不参与采样"""
    event = {
        "level": "info",
        "event": "异常日志",
        exception_field: True,
    }

    result = sampling(0.0)(
        None,
        "info",
        event,
    )

    assert result is event


@pytest.mark.parametrize(
    "rate",
    [
        -0.1,
        1.1,
    ],
)
def test_sampling_rejects_invalid_rate(
        rate: float,
) -> None:
    """测试拒绝无效采样率"""
    with pytest.raises(
            ValueError,
            match="rate 必须在 0.0 到 1.0 之间",
    ):
        sampling(rate)
