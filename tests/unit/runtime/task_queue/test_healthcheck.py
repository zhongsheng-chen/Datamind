"""Celery Worker 健康检查测试.

验证健康检查对节点身份、消费队列和 Broker 异常的判断行为。

核心功能：
  - test_healthcheck_targets_current_container_and_role:
    验证当前容器内消费必需队列的 Worker 通过健康检查
  - test_healthcheck_rejects_other_worker_reply:
    验证其他容器的 Worker 响应不会通过健康检查
  - test_healthcheck_rejects_worker_with_wrong_role_queue:
    验证消费错误角色队列的 Worker 不会通过健康检查
  - test_healthcheck_handles_broker_failure:
    验证 Broker 异常转换为健康检查失败结果
"""

from unittest.mock import MagicMock

import pytest

import datamind.runtime.task_queue.entrypoints.healthcheck as healthcheck_module


def replace_control_method(
        monkeypatch: pytest.MonkeyPatch,
        name: str,
        replacement: object,
) -> None:
    """替换 Celery 控制接口并在测试结束后自动恢复."""
    monkeypatch.setattr(
        healthcheck_module.celery_app.control,
        name,
        replacement,
    )


def test_healthcheck_targets_current_container_and_role(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试当前容器内消费必需队列的 Worker 通过健康检查."""
    monkeypatch.setattr(
        healthcheck_module,
        "get_worker_node_pattern",
        lambda: ("worker-", "@pod-a"),
    )
    monkeypatch.setattr(
        healthcheck_module,
        "get_required_queues",
        lambda: {"prediction.batch"},
    )
    inspector = MagicMock()
    inspector.ping.return_value = {
        "worker-123@pod-a": {"ok": "pong"},
    }
    inspector.active_queues.return_value = {
        "worker-123@pod-a": [{"name": "prediction.batch"}],
    }
    inspect = MagicMock(return_value=inspector)
    replace_control_method(
        monkeypatch,
        "inspect",
        inspect,
    )

    assert healthcheck_module.is_worker_ready()
    inspect.assert_called_once_with(
        timeout=2.0,
    )


def test_healthcheck_rejects_other_worker_reply(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试其他容器的 Worker 响应不会通过健康检查."""
    monkeypatch.setattr(
        healthcheck_module,
        "get_worker_node_pattern",
        lambda: ("worker-", "@pod-a"),
    )
    monkeypatch.setattr(
        healthcheck_module,
        "get_required_queues",
        lambda: {"prediction.batch"},
    )
    inspector = MagicMock()
    inspector.ping.return_value = {
        "worker-456@pod-b": {"ok": "pong"},
    }
    inspector.active_queues.return_value = {
        "worker-456@pod-b": [{"name": "prediction.batch"}],
    }
    replace_control_method(
        monkeypatch,
        "inspect",
        MagicMock(return_value=inspector),
    )

    assert not healthcheck_module.is_worker_ready()


def test_healthcheck_rejects_worker_with_wrong_role_queue(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试消费错误角色队列的 Worker 不会通过健康检查."""
    monkeypatch.setattr(
        healthcheck_module,
        "get_worker_node_pattern",
        lambda: ("worker-", "@pod-a"),
    )
    monkeypatch.setattr(
        healthcheck_module,
        "get_required_queues",
        lambda: {"prediction.batch"},
    )
    inspector = MagicMock()
    inspector.ping.return_value = {
        "worker-123@pod-a": {"ok": "pong"},
    }
    inspector.active_queues.return_value = {
        "worker-123@pod-a": [{"name": "prediction.shadow"}],
    }
    replace_control_method(
        monkeypatch,
        "inspect",
        MagicMock(return_value=inspector),
    )

    assert not healthcheck_module.is_worker_ready()


def test_healthcheck_handles_broker_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Broker 异常转换为健康检查失败结果."""
    monkeypatch.setattr(
        healthcheck_module,
        "get_worker_node_pattern",
        lambda: ("worker-", "@pod-a"),
    )
    monkeypatch.setattr(
        healthcheck_module,
        "get_required_queues",
        lambda: {"prediction.batch"},
    )
    replace_control_method(
        monkeypatch,
        "inspect",
        MagicMock(side_effect=OSError("broker unavailable")),
    )

    assert not healthcheck_module.is_worker_ready()
