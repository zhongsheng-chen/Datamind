"""日志渲染器测试.

验证文本和 JSON 日志的字段输出、内部字段清理和原始事件保护行为。

核心功能：
  - test_text_renderer_outputs_expected_fields:
    验证文本渲染器输出主要字段
  - test_text_renderer_uses_placeholder_for_missing_timestamp:
    验证时间戳缺失时使用占位符
  - test_text_renderer_ignores_empty_context_values:
    验证忽略空上下文字段
  - test_text_renderer_preserves_false_and_zero_values:
    验证保留 False 和 0 等有效值
  - test_text_renderer_removes_processor_meta_fields:
    验证文本渲染器移除处理器内部字段
  - test_text_renderer_does_not_modify_original_event:
    验证文本渲染器不修改原始事件
  - test_json_renderer_outputs_valid_json:
    验证 JSON 渲染器输出有效 JSON
  - test_json_renderer_removes_processor_meta_fields:
    验证 JSON 渲染器移除处理器内部字段
  - test_json_renderer_does_not_modify_original_event:
    验证 JSON 渲染器不修改原始事件
"""

import json
from typing import Any

from datamind.logging.render import (
    json_renderer,
    text_renderer,
)


def test_text_renderer_outputs_expected_fields() -> None:
    """测试文本渲染器输出主要字段."""
    event: dict[str, Any] = {
        "timestamp": "2026-07-22T15:00:00+08:00",
        "level": "info",
        "trace_id": "a1b2c3d4",
        "request_id": "9f8e7d6c",
        "source": "http",
        "user": "admin",
        "ip": "192.168.1.100",
        "hostname": "client",
        "event": "模型注册成功",
        "model_id": "mdl_a1b2c3d4",
    }

    result = text_renderer()(
        None,
        "info",
        event,
    )

    assert result.startswith(
        "2026-07-22T15:00:00+08:00 | INFO"
    )
    assert "trace_id=a1b2c3d4" in result
    assert "request_id=9f8e7d6c" in result
    assert "source=http" in result
    assert "user=admin" in result
    assert "ip=192.168.1.100" in result
    assert "hostname=client" in result
    assert "模型注册成功" in result
    assert "model_id=mdl_a1b2c3d4" in result


def test_text_renderer_uses_placeholder_for_missing_timestamp() -> None:
    """测试时间戳缺失时使用占位符."""
    result = text_renderer()(
        None,
        "warning",
        {
            "level": "warning",
            "event": "时间戳缺失",
        },
    )

    assert result.startswith("- | WARNING")
    assert "时间戳缺失" in result


def test_text_renderer_ignores_empty_context_values() -> None:
    """测试忽略空上下文字段."""
    result = text_renderer()(
        None,
        "info",
        {
            "timestamp": "2026-07-22T15:00:00+08:00",
            "level": "info",
            "trace_id": "",
            "request_id": None,
            "source": "http",
            "event": "测试日志",
        },
    )

    assert "trace_id=" not in result
    assert "request_id=" not in result
    assert "source=http" in result


def test_text_renderer_preserves_false_and_zero_values() -> None:
    """测试保留 False 和 0 等有效值."""
    result = text_renderer()(
        None,
        "info",
        {
            "timestamp": "2026-07-22T15:00:00+08:00",
            "level": "info",
            "event": "测试日志",
            "enabled": False,
            "count": 0,
        },
    )

    assert "enabled=False" in result
    assert "count=0" in result


def test_text_renderer_removes_processor_meta_fields() -> None:
    """测试文本渲染器移除处理器内部字段."""
    result = text_renderer()(
        None,
        "info",
        {
            "timestamp": "2026-07-22T15:00:00+08:00",
            "level": "info",
            "event": "测试日志",
            "_record": object(),
            "_from_structlog": True,
        },
    )

    assert "_record" not in result
    assert "_from_structlog" not in result


def test_text_renderer_does_not_modify_original_event() -> None:
    """测试文本渲染器不修改原始事件."""
    event: dict[str, Any] = {
        "timestamp": "2026-07-22T15:00:00+08:00",
        "level": "info",
        "trace_id": "a1b2c3d4",
        "event": "测试日志",
        "model_id": "mdl_a1b2c3d4",
    }
    original = event.copy()

    text_renderer()(
        None,
        "info",
        event,
    )

    assert event == original


def test_json_renderer_outputs_valid_json() -> None:
    """测试 JSON 渲染器输出有效 JSON."""
    result = json_renderer()(
        None,
        "info",
        {
            "timestamp": "2026-07-22T15:00:00+08:00",
            "level": "info",
            "event": "模型注册成功",
            "model_id": "mdl_a1b2c3d4",
        },
    )

    assert isinstance(result, str)

    event = json.loads(result)

    assert event == {
        "timestamp": "2026-07-22T15:00:00+08:00",
        "level": "info",
        "event": "模型注册成功",
        "model_id": "mdl_a1b2c3d4",
    }


def test_json_renderer_removes_processor_meta_fields() -> None:
    """测试 JSON 渲染器移除处理器内部字段."""
    result = json_renderer()(
        None,
        "info",
        {
            "event": "测试日志",
            "_record": "internal",
            "_from_structlog": True,
        },
    )

    event = json.loads(result)

    assert event == {
        "event": "测试日志",
    }


def test_json_renderer_does_not_modify_original_event() -> None:
    """测试 JSON 渲染器不修改原始事件."""
    event: dict[str, Any] = {
        "event": "测试日志",
        "model_id": "mdl_a1b2c3d4",
        "_from_structlog": True,
    }
    original = event.copy()

    json_renderer()(
        None,
        "info",
        event,
    )

    assert event == original
