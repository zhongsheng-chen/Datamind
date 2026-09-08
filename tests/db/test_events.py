"""数据库变更事件测试

验证业务模型变更事件的注册、事件记录和 PostgreSQL 通知。

核心功能：
  - test_create_listener_writes_model_event: 验证监听器写入模型事件
  - test_write_event_notifies_postgresql: 验证 PostgreSQL 事件通知
  - test_write_event_skips_notification_for_other_dialects:
    验证其他数据库不发送 PostgreSQL 通知
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import datamind.db.events as events_module


def create_connection(
        *,
        dialect_name: str,
        event_id: int = 10,
) -> MagicMock:
    """创建同步数据库连接替身"""
    connection = MagicMock()
    connection.dialect.name = dialect_name
    result = MagicMock()
    result.scalar_one.return_value = event_id
    connection.execute.return_value = result

    return connection


def test_create_listener_writes_model_event(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证监听器写入模型事件"""
    write_event = MagicMock()
    monkeypatch.setitem(
        vars(events_module),
        "_write_event",
        write_event,
    )
    listener = events_module._create_listener(
        topic="models",
        identifier="model_id",
        action="update",
    )
    connection = create_connection(
        dialect_name="postgresql"
    )

    listener(
        MagicMock(),
        connection,
        SimpleNamespace(
            model_id="mdl_test"
        ),
    )

    write_event.assert_called_once_with(
        connection,
        topic="models",
        resource_id="mdl_test",
        action="update",
    )


def test_write_event_notifies_postgresql() -> None:
    """验证 PostgreSQL 事件通知"""
    connection = create_connection(
        dialect_name="postgresql",
        event_id=20,
    )

    events_module._write_event(
        connection,
        topic="routings",
        resource_id="rtn_test",
        action="insert",
    )

    assert connection.execute.call_count == 2
    notification = connection.execute.call_args_list[
        1
    ]
    assert "pg_notify" in str(
        notification.args[0]
    )
    assert notification.args[1] == {
        "channel": "datamind_console_events",
        "event_id": "20",
    }


def test_write_event_skips_notification_for_other_dialects() -> None:
    """验证其他数据库不发送 PostgreSQL 通知"""
    connection = create_connection(
        dialect_name="sqlite"
    )

    events_module._write_event(
        connection,
        topic="models",
        resource_id="mdl_test",
        action="delete",
    )

    connection.execute.assert_called_once()
