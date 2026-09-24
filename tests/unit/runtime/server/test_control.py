"""运行时部署控制接口测试.

验证部署加载、卸载、状态查询及环境校验行为。

核心功能：
  - test_control_operation_updates_desired_state:
    验证运行控制操作更新期望状态
  - test_control_operation_returns_validation_error:
    验证运行控制校验失败时返回标准错误响应
  - test_unload_returns_deployment_state_error:
    验证卸载启用部署时返回部署状态错误
  - test_status_combines_control_and_local_state:
    验证部署状态查询合并控制、运行记录和本地状态
  - test_validate_service_environment_rejects_invalid_deployment:
    验证服务环境校验拒绝无效部署
  - test_validate_service_environment_accepts_active_deployment:
    验证服务环境校验接受当前环境的活跃部署
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.models.errors import InvalidDeploymentStateError, RuntimeRouteError
from datamind.runtime.server.errors import (
    ServiceDeploymentNotFoundError,
    ServiceEnvironmentMismatchError,
)
from datamind.runtime.server.schemas import (
    ControlRequest,
    DeploymentRequest,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "load",
        "unload",
        "reload",
    ],
)
async def test_control_operation_updates_desired_state(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        action: str,
) -> None:
    """测试运行控制操作更新期望状态."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock()
    controller_method = getattr(service.controller, action)
    controller_method.return_value = {
        "deployment_id": "dep_test",
        "action": action,
    }
    operation = getattr(service, f"_{action}")

    result = await operation(
        request=ControlRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
        operator="alice",
    )

    assert result["success"] is True
    assert result["action"] == action
    controller_method.assert_awaited_once_with(
        deployment_id="dep_test",
        operator="alice",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action",
    [
        "load",
        "unload",
        "reload",
    ],
)
async def test_control_operation_returns_validation_error(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        action: str,
) -> None:
    """测试运行控制校验失败时返回标准错误响应."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock(
        side_effect=RuntimeRouteError("部署不可用")
    )
    operation = getattr(service, f"_{action}")

    result = await operation(
        request=ControlRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
        operator="alice",
    )

    assert result["success"] is False
    assert result["error_type"] == "RuntimeRouteError"
    getattr(service.controller, action).assert_not_awaited()


@pytest.mark.asyncio
async def test_unload_returns_deployment_state_error(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试卸载启用部署时返回部署状态错误."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock()
    service.controller.unload.side_effect = (
        InvalidDeploymentStateError(
            "部署仍处于启用状态，请先禁用部署: dep_test"
        )
    )

    result = await service._unload(
        request=ControlRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
        operator="alice",
    )

    assert result["success"] is False
    assert result["error_type"] == "InvalidDeploymentStateError"


@pytest.mark.asyncio
async def test_status_combines_control_and_local_state(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试部署状态查询合并控制、运行记录和本地状态."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock()
    service.controller.get_status.return_value = {
        "control": {"desired_status": "loaded"},
        "runtimes": [{"worker_id": "worker_test"}],
    }
    service.manager.get_status.return_value = {
        "loaded_in_memory": True,
    }
    service.reconciler.get_applied_generation.return_value = 3

    result = await service._status(
        request=DeploymentRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
    )

    assert result["success"] is True
    assert result["control"] == {
        "desired_status": "loaded"
    }
    assert result["local_generation"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deployment", "error_type"),
    [
        (None, ServiceDeploymentNotFoundError),
        (
            SimpleNamespace(
                environment="production",
                status="active",
            ),
            ServiceEnvironmentMismatchError,
        ),
        (
            SimpleNamespace(
                environment="testing",
                status="inactive",
            ),
            RuntimeRouteError,
        ),
    ],
)
async def test_validate_service_environment_rejects_invalid_deployment(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        deployment: SimpleNamespace | None,
        error_type: type[Exception],
) -> None:
    """测试服务环境校验拒绝无效部署."""
    service_module = runtime_server.load_service_module(monkeypatch)
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=deployment
    )
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        deployment_repo=deployment_repo,
    )

    with pytest.raises(error_type):
        await service_module.DatamindRuntimeService.inner._validate_service_environment(
            deployment_id="dep_test"
        )


@pytest.mark.asyncio
async def test_validate_service_environment_accepts_active_deployment(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试服务环境校验接受当前环境的活跃部署."""
    service_module = runtime_server.load_service_module(monkeypatch)
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=SimpleNamespace(
            environment="testing",
            status="active",
        )
    )
    runtime_server.install_repositories(
        service_module,
        monkeypatch,
        deployment_repo=deployment_repo,
    )

    await service_module.DatamindRuntimeService.inner._validate_service_environment(
        deployment_id="dep_test"
    )

    deployment_repo.get_deployment.assert_awaited_once_with(
        "dep_test"
    )
