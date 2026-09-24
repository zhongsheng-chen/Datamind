"""运行时状态协调器测试.

验证控制状态加载、模型状态收敛、失败隔离、心跳和后台循环生命周期。

核心功能：
  - test_reconciler_binds_service_identity:
    验证协调器绑定服务实例标识
  - test_reconcile_result_records_actions:
    验证协调结果记录各类操作
  - test_reconcile_result_rejects_unknown_action:
    验证协调结果拒绝未知操作
  - test_reconciler_rejects_invalid_configuration:
    验证协调器拒绝无效配置
  - test_reconcile_loads_missing_deployment:
    验证协调器加载缺失部署
  - test_reconcile_uses_default_operator:
    验证协调器使用默认操作人
  - test_reconcile_initializes_loaded_generation:
    验证协调器初始化已加载代次
  - test_reconcile_restarts_changed_generation:
    验证协调器重启已变更代次
  - test_reconcile_keeps_same_generation:
    验证协调器保留相同代次
  - test_reconcile_unloads_loaded_deployment:
    验证协调器卸载已加载部署
  - test_reconcile_keeps_unloaded_deployment:
    验证协调器保留已卸载部署状态
  - test_reconcile_isolates_control_failure:
    验证单个控制状态失败相互隔离
  - test_reconcile_rejects_control_from_other_environment:
    验证拒绝其他环境的控制状态
  - test_reconcile_rejects_invalid_control_status:
    验证拒绝无效控制状态
  - test_reconcile_heartbeats_loaded_runtime:
    验证协调器更新已加载运行实例心跳
  - test_heartbeat_skips_missing_and_unloaded_runtime:
    验证心跳跳过缺失和已卸载实例
  - test_heartbeat_failure_does_not_fail_reconciliation:
    验证心跳失败不影响协调过程
  - test_reconciler_start_and_stop_are_idempotent:
    验证协调器启停操作具有幂等性
"""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
from sqlalchemy.exc import SQLAlchemyError

import datamind.runtime.reconciler as reconciler_module
from datamind.constants import Environment
from datamind.models.enums import RuntimeControlStatus
from datamind.models.errors import BackendError
from datamind.runtime.reconciler import (
    ReconcileResult,
    RuntimeReconciler,
)


class FakeUnitOfWork:
    """运行时协调器测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_control(
        *,
        deployment_id: str = "dep_test",
        environment: str = "production",
        desired_status: object = "loaded",
        generation: int = 1,
        updated_by: str | None = "operator",
) -> SimpleNamespace:
    """创建运行控制记录."""
    return SimpleNamespace(
        deployment_id=deployment_id,
        environment=environment,
        desired_status=desired_status,
        generation=generation,
        updated_by=updated_by,
    )


def configure_reconciler(
        monkeypatch: pytest.MonkeyPatch,
        *,
        controls: list[SimpleNamespace] | None = None,
        local_loaded: bool = False,
) -> tuple[RuntimeReconciler, Any, MagicMock, MagicMock]:
    """配置运行时协调器及仓储替身."""
    manager: Any = MagicMock()
    manager.worker_id = "worker_test"
    manager.registry.__contains__.return_value = (
        local_loaded
    )
    manager.load = AsyncMock()
    manager.reload = AsyncMock()
    manager.unload = AsyncMock()
    control_repo = MagicMock()
    control_repo.list_controls = AsyncMock(
        return_value=controls or []
    )
    runtime_repo = MagicMock()
    runtime_repo.get_deployment_runtime = AsyncMock(
        return_value=None
    )
    runtime_repo.set_applied_generation = AsyncMock()
    runtime_repo.mark_stale_runtimes_failed = AsyncMock(
        return_value=[]
    )
    monkeypatch.setitem(
        vars(reconciler_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(reconciler_module),
        "ControlRepository",
        lambda _session: control_repo,
    )
    monkeypatch.setitem(
        vars(reconciler_module),
        "RuntimeRepository",
        lambda _session: runtime_repo,
    )

    reconciler = RuntimeReconciler(
        manager=manager,
        environment="production",
        interval_seconds=0.01,
        heartbeat_interval_seconds=30.0,
    )

    return reconciler, manager, control_repo, runtime_repo


def test_reconciler_binds_service_identity(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试协调器日志绑定调用方传入的实例标识."""
    manager = MagicMock()
    manager.worker_id = "worker_test"
    monkeypatch.setenv("DATAMIND_SERVICE_INSTANCE_ID", "unrelated-instance")
    reconciler = RuntimeReconciler(
        manager=manager,
        environment="testing",
        service_instance_id="service-test",
    )

    context = structlog.get_context(reconciler._logger)
    assert context["service_instance_id"] == "service-test"
    assert context["worker_id"] == "worker_test"
    assert context["pid"] == reconciler_module.os.getpid()


def test_reconcile_result_records_actions() -> None:
    """测试协调结果记录各类动作."""
    result = ReconcileResult(
        checked=4
    )

    for action in (
            "loaded",
            "unloaded",
            "reloaded",
            "unchanged",
    ):
        result.record(action)

    assert result.to_dict() == {
        "checked": 4,
        "loaded": 1,
        "unloaded": 1,
        "reloaded": 1,
        "unchanged": 1,
        "failed": 0,
    }


def test_reconcile_result_rejects_unknown_action() -> None:
    """测试协调结果拒绝未知动作."""
    with pytest.raises(
            ValueError,
            match="未知协调动作",
    ):
        ReconcileResult().record("invalid")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"environment": ""}, "environment 不能为空"),
        ({"interval_seconds": 0}, "interval_seconds 必须大于 0"),
        (
            {"heartbeat_interval_seconds": 0},
            "heartbeat_interval_seconds 必须大于 0",
        ),
        ({"operator": ""}, "operator 不能为空"),
    ],
)
def test_reconciler_rejects_invalid_configuration(
        kwargs: dict[str, Any],
        message: str,
) -> None:
    """测试协调器拒绝非法配置."""
    manager: Any = MagicMock(worker_id="worker_test")
    values: dict[str, Any] = {
        "manager": manager,
        "environment": "production",
    }
    values.update(kwargs)

    with pytest.raises(
            ValueError,
            match=message,
    ):
        RuntimeReconciler(**values)


@pytest.mark.asyncio
async def test_reconcile_loads_missing_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试协调器加载本地缺失的部署."""
    reconciler, manager, control_repo, runtime_repo = configure_reconciler(
        monkeypatch,
        controls=[create_control()],
    )

    result = await reconciler.reconcile_once()

    control_repo.list_controls.assert_awaited_once_with(
        environment=Environment.PRODUCTION
    )
    manager.load.assert_awaited_once_with(
        deployment_id="dep_test",
        operator="operator",
    )
    assert result.to_dict() == {
        "checked": 1,
        "loaded": 1,
        "unloaded": 0,
        "reloaded": 0,
        "unchanged": 0,
        "failed": 0,
    }
    assert reconciler.get_applied_generation("dep_test") == 1
    runtime_repo.set_applied_generation.assert_awaited_once_with(
        deployment_id="dep_test",
        worker_id="worker_test",
        generation=1,
    )


@pytest.mark.asyncio
async def test_reconcile_uses_default_operator(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制记录未提供更新人时使用默认操作人."""
    reconciler, manager, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control(updated_by=None)],
    )

    await reconciler.reconcile_once()

    manager.load.assert_awaited_once_with(
        deployment_id="dep_test",
        operator="system",
    )


@pytest.mark.asyncio
async def test_reconcile_initializes_loaded_generation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已加载部署初始化本地控制版本."""
    reconciler, manager, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control(generation=2)],
        local_loaded=True,
    )

    result = await reconciler.reconcile_once()

    assert result.unchanged == 1
    assert reconciler.get_applied_generation("dep_test") == 2
    manager.reload.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_restarts_changed_generation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制版本变化时重新加载部署."""
    control = create_control(generation=1)
    reconciler, manager, control_repo, _ = configure_reconciler(
        monkeypatch,
        controls=[control],
        local_loaded=True,
    )
    await reconciler.reconcile_once()
    control.generation = 2
    control_repo.list_controls.return_value = [control]

    result = await reconciler.reconcile_once()

    manager.reload.assert_awaited_once_with(
        deployment_id="dep_test",
        operator="operator",
    )
    assert result.reloaded == 1
    assert reconciler.get_applied_generation("dep_test") == 2


@pytest.mark.asyncio
async def test_reconcile_keeps_same_generation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制版本未变化时不执行运行操作."""
    reconciler, manager, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control()],
        local_loaded=True,
    )

    await reconciler.reconcile_once()
    result = await reconciler.reconcile_once()

    assert result.unchanged == 1
    manager.load.assert_not_awaited()
    manager.reload.assert_not_awaited()
    manager.unload.assert_not_awaited()


@pytest.mark.asyncio
async def test_reconcile_unloads_loaded_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试协调器卸载本地已加载部署."""
    reconciler, manager, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control(desired_status="unloaded")],
        local_loaded=True,
    )

    result = await reconciler.reconcile_once()

    manager.unload.assert_awaited_once_with(
        deployment_id="dep_test",
        operator="operator",
    )
    assert result.unloaded == 1
    assert reconciler.get_applied_generation("dep_test") == 1


@pytest.mark.asyncio
async def test_reconcile_keeps_unloaded_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试本地未加载部署保持卸载状态."""
    reconciler, manager, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control(desired_status="unloaded")],
    )

    result = await reconciler.reconcile_once()

    assert result.unchanged == 1
    manager.unload.assert_not_awaited()
    assert reconciler.get_applied_generations() == {
        "dep_test": 1,
    }


@pytest.mark.asyncio
async def test_reconcile_isolates_control_failure(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试单个部署加载失败计入失败结果."""
    reconciler, manager, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control()],
    )
    manager.load.side_effect = BackendError("load failed")

    result = await reconciler.reconcile_once()

    assert result.failed == 1
    assert reconciler.get_applied_generation("dep_test") is None


@pytest.mark.asyncio
async def test_reconcile_rejects_control_from_other_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试其他环境控制记录被计入失败结果."""
    reconciler, _, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control(environment="staging")],
    )

    result = await reconciler.reconcile_once()

    assert result.failed == 1
    assert result.loaded == 0


@pytest.mark.asyncio
async def test_reconcile_rejects_invalid_control_status(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试读取控制记录时拒绝非法状态."""
    reconciler, _, _, _ = configure_reconciler(
        monkeypatch,
        controls=[create_control(desired_status="invalid")],
    )

    with pytest.raises(ValueError):
        await reconciler.reconcile_once()


@pytest.mark.asyncio
async def test_reconcile_heartbeats_loaded_runtime(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试到达心跳间隔后更新已加载运行记录."""
    reconciler, _, _, runtime_repo = configure_reconciler(
        monkeypatch,
        controls=[create_control(
            desired_status=RuntimeControlStatus.LOADED
        )],
        local_loaded=True,
    )
    runtime = SimpleNamespace(
        status="running"
    )
    runtime_repo.get_deployment_runtime.return_value = runtime
    monkeypatch.setattr(
        reconciler_module.time,
        "monotonic",
        lambda: 100.0,
    )

    await reconciler.reconcile_once()
    await reconciler.reconcile_once()

    runtime_repo.heartbeat.assert_called_once_with(
        runtime
    )
    runtime_repo.mark_stale_runtimes_failed.assert_awaited_once()
    cleanup_arguments = (
        runtime_repo.mark_stale_runtimes_failed.await_args
    )
    assert cleanup_arguments is not None
    assert cleanup_arguments.kwargs["environment"] == "production"
    assert cleanup_arguments.kwargs["exclude_worker_id"] == "worker_test"
    assert cleanup_arguments.kwargs["stale_before"].tzinfo is not None


@pytest.mark.asyncio
async def test_heartbeat_skips_missing_and_unloaded_runtime(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试心跳跳过缺失和非加载状态的运行记录."""
    controls = [
        create_control(deployment_id="dep_missing"),
        create_control(deployment_id="dep_unloaded"),
    ]
    reconciler, manager, _, runtime_repo = configure_reconciler(
        monkeypatch,
        controls=controls,
        local_loaded=True,
    )
    manager.registry.__contains__.return_value = True
    runtime_repo.get_deployment_runtime.side_effect = [
        None,
        SimpleNamespace(status="stopped"),
    ]

    await reconciler.reconcile_once()

    runtime_repo.heartbeat.assert_not_called()


@pytest.mark.asyncio
async def test_heartbeat_failure_does_not_fail_reconciliation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试心跳数据库错误不影响状态协调结果."""
    reconciler, _, _, runtime_repo = configure_reconciler(
        monkeypatch,
        controls=[create_control()],
        local_loaded=True,
    )
    runtime_repo.get_deployment_runtime.side_effect = SQLAlchemyError(
        "database unavailable"
    )

    result = await reconciler.reconcile_once()

    assert result.unchanged == 1
    assert result.failed == 0


@pytest.mark.asyncio
async def test_reconciler_start_and_stop_are_idempotent(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试后台协调循环可幂等启动和停止."""
    reconciler, _, _, _ = configure_reconciler(
        monkeypatch
    )
    reconcile_once = AsyncMock(
        return_value=ReconcileResult()
    )
    monkeypatch.setattr(
        reconciler,
        "reconcile_once",
        reconcile_once,
    )

    await reconciler.stop()
    await reconciler.start()
    await reconciler.start()
    await asyncio.sleep(0)

    assert reconciler.is_running is True

    await reconciler.stop()

    assert reconciler.is_running is False
