"""运行时模型服务测试

验证服务生命周期、健康检查和通用安全执行行为。

核心功能：
  - test_apply_response_status_maps_request_error:
    验证请求参数错误映射为 HTTP 400
  - test_apply_response_status_maps_error_types:
    验证错误类型映射为对应 HTTP 状态
  - test_startup_reconciles_and_marks_worker_ready:
    验证 Worker 启动时首次协调并写入就绪标记
  - test_shutdown_stops_models_and_clears_cache:
    验证 Worker 关闭时停止协调器、卸载模型并清理缓存
  - test_health_returns_worker_state:
    验证健康检查返回 Worker 当前状态
  - test_ready_returns_ready_when_database_is_available:
    验证数据库和协调器可用时 Worker 就绪
  - test_ready_returns_unavailable_when_database_fails:
    验证数据库不可用时 Worker 返回未就绪
  - test_execute_secured_applies_status_and_records_audit:
    验证认证执行包装设置状态并记录审计
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError



def test_apply_response_status_maps_request_error(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试请求参数错误映射为 HTTP 400"""
    service_module = runtime_server.load_service_module(
        monkeypatch
    )
    service = runtime_server.create_service(
        service_module
    )
    context = SimpleNamespace(
        response=SimpleNamespace(
            status_code=200
        )
    )

    service._apply_response_status(
        ctx=context,
        response={
            "success": False,
            "error_type": "ValueError",
        },
    )

    assert context.response.status_code == 400


@pytest.mark.parametrize(
    ("response", "expected_status"),
    [
        ({"success": True}, 200),
        ({"success": False, "error_type": "ServiceDeploymentNotFoundError"}, 404),
        ({"success": False, "error_type": "ServiceEnvironmentMismatchError"}, 409),
        ({"success": False, "error_type": "RuntimeRouteError"}, 400),
        ({"success": False, "error_type": "TypeError"}, 400),
        ({"success": False, "error_type": "ValueError"}, 400),
        ({"success": False, "error_type": "RuntimeError"}, 500),
        ({"success": False, "error_type": None}, 500),
    ],
)
def test_apply_response_status_maps_error_types(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        response: dict[str, Any],
        expected_status: int,
) -> None:
    """测试错误类型映射为对应 HTTP 状态"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )

    service._apply_response_status(
        ctx=context,
        response=response,
    )

    assert context.response.status_code == expected_status


@pytest.mark.asyncio
async def test_startup_reconciles_and_marks_worker_ready(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Worker 启动时首次协调并写入就绪标记"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    result = MagicMock()
    result.to_dict.return_value = {
        "checked": 1,
    }
    service.reconciler.reconcile_once.return_value = result
    write_marker = MagicMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "_write_worker_ready_marker",
        write_marker,
    )

    await service.startup()

    service.reconciler.reconcile_once.assert_awaited_once()
    service.reconciler.start.assert_awaited_once()
    write_marker.assert_called_once_with(
        worker_id="worker_test",
        environment="testing",
    )


@pytest.mark.asyncio
async def test_startup_keeps_worker_alive_until_database_recovers(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库晚启动时 Worker 进入后台重试而不是退出"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.reconciler.reconcile_once.side_effect = SQLAlchemyError(
        "database unavailable"
    )
    write_marker = MagicMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "_write_worker_ready_marker",
        write_marker,
    )

    await service.startup()

    service.reconciler.reconcile_once.assert_awaited_once()
    service.reconciler.start.assert_awaited_once()
    write_marker.assert_called_once_with(
        worker_id="worker_test",
        environment="testing",
    )


@pytest.mark.asyncio
async def test_startup_keeps_worker_alive_on_native_connection_refusal(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 asyncpg 原生连接拒绝不会终止 Worker"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.reconciler.reconcile_once.side_effect = ConnectionRefusedError(
        "database unavailable"
    )
    write_marker = MagicMock()
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "_write_worker_ready_marker",
        write_marker,
    )

    await service.startup()

    service.reconciler.start.assert_awaited_once()
    write_marker.assert_called_once_with(
        worker_id="worker_test",
        environment="testing",
    )


@pytest.mark.asyncio
async def test_shutdown_stops_models_and_clears_cache(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Worker 关闭时停止协调器、卸载模型并清理缓存"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.manager.registry.all.return_value = [
        SimpleNamespace(deployment_id="dep_1"),
        SimpleNamespace(deployment_id="dep_2"),
    ]
    service.manager.unload.side_effect = [
        None,
        RuntimeError("stop failed"),
    ]
    service_cache = runtime_server.get_service_cache(service)
    service_cache["dep_1"] = object()

    await service.shutdown()

    service.reconciler.stop.assert_awaited_once()
    assert service.manager.unload.await_count == 2
    assert service_cache == {}


def test_health_returns_worker_state(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试健康检查返回 Worker 当前状态"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.manager.registry.__len__.return_value = 2
    runtime_server.get_service_cache(service).update({
        "dep_1": object(),
        "dep_2": object(),
    })

    result = service.health()

    assert result == {
        "status": "ok",
        "worker_id": "worker_test",
        "environment": "testing",
        "reconciler_running": True,
        "runtime_count": 2,
        "service_cache_count": 2,
        "configured_workers": service_module.service_config.workers,
    }


@pytest.mark.asyncio
async def test_ready_returns_ready_when_database_is_available(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试数据库和协调器可用时 Worker 就绪"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "UnitOfWork",
        runtime_server.FakeUnitOfWork,
    )
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )

    result = await service.ready(context)

    assert result["status"] == "ready"
    assert result["database_ready"] is True
    assert context.response.status_code == 200
    assert runtime_server.FakeUnitOfWork.latest is not None
    runtime_server.FakeUnitOfWork.latest.session.execute.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "database_error",
    [
        SQLAlchemyError("database unavailable"),
        ConnectionRefusedError("database unavailable"),
    ],
)
async def test_ready_returns_unavailable_when_database_fails(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        database_error: Exception,
) -> None:
    """测试数据库不可用时 Worker 返回未就绪"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)

    class FailingUnitOfWork(runtime_server.FakeUnitOfWork):
        """数据库查询失败的工作单元"""

        async def __aenter__(self) -> "FailingUnitOfWork":
            self.session.execute.side_effect = database_error
            return self

    runtime_server.patch_server_dependency(
        monkeypatch,
        service_module,
        "UnitOfWork",
        FailingUnitOfWork,
    )
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )

    result = await service.ready(context)

    assert result["status"] == "not_ready"
    assert result["database_ready"] is False
    assert context.response.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("successful", "expected_status", "expected_error"),
    [
        (True, "success", None),
        (False, "failed", "request failed"),
    ],
)
async def test_execute_secured_applies_status_and_records_audit(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        successful: bool,
        expected_status: str,
        expected_error: str | None,
) -> None:
    """测试认证执行包装设置状态并记录审计"""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service.security = runtime_server.SecurityStub()
    context = SimpleNamespace(
        response=SimpleNamespace(status_code=200)
    )
    handler = AsyncMock(return_value={
        "success": successful,
        "error": "request failed" if not successful else None,
        "error_type": "ValueError" if not successful else None,
    })

    result = await service._execute_secured(
        ctx=context,
        permission="runtime.manage",
        request_id="req_test",
        handler=handler,
        audit_action="runtime.load",
        target_type="deployment",
        target_id="dep_test",
    )

    assert result["success"] is successful
    handler.assert_awaited_once()
    runtime_server.get_audit_recorder(service).record.assert_awaited_once_with(
        action="runtime.load",
        target_type="deployment",
        target_id="dep_test",
        status=expected_status,
        error=expected_error,
        after=result if successful else None,
    )
    assert context.response.status_code == (
        200 if successful else 400
    )
