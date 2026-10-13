"""运行时部署控制接口测试.

验证部署重载、状态查询及环境校验行为。

核心功能：
  - test_runtime_service_exposes_only_supported_admin_routes:
    验证预测服务不再公开直接加载和卸载接口
  - test_reload_returns_controller_result:
    验证重载请求返回控制服务结果
  - test_reload_returns_validation_error:
    验证重载校验失败时返回标准错误响应
  - test_status_combines_control_and_local_state:
    验证部署状态查询合并控制、运行记录和本地状态
  - test_validate_service_environment_rejects_invalid_deployment:
    验证服务环境校验拒绝无效部署
  - test_validate_service_environment_accepts_current_environment:
    验证服务环境校验不限制部署状态
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.runtime.server.errors import (
    ServiceDeploymentNotFoundError,
    ServiceEnvironmentMismatchError,
)
from datamind.runtime.server.schemas import (
    ControlRequest,
    DeploymentRequest,
)


def test_runtime_service_exposes_only_supported_admin_routes(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试预测服务只公开保留的运行管理接口."""
    service_module = runtime_server.load_service_module(monkeypatch)

    admin_routes = {
        api.route
        for api in service_module.DatamindRuntimeService.apis.values()
        if api.route.startswith("/admin/")
    }

    assert admin_routes == {
        "/admin/reload",
        "/admin/services",
        "/admin/status",
    }


@pytest.mark.asyncio
async def test_reload_returns_controller_result(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重载请求返回控制服务结果."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock()
    service.controller.reload.return_value = {
        "deployment_id": "dep_test",
        "action": "reload",
    }

    result = await service._reload(
        request=ControlRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
        operator="alice",
    )

    assert result["success"] is True
    assert result["action"] == "reload"
    service.controller.reload.assert_awaited_once_with(
        deployment_id="dep_test",
        operator="alice",
    )


@pytest.mark.asyncio
async def test_reload_returns_validation_error(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重载校验失败时返回标准错误响应."""
    service_module = runtime_server.load_service_module(monkeypatch)
    service = runtime_server.create_service(service_module)
    service._validate_service_environment = AsyncMock(
        side_effect=ServiceEnvironmentMismatchError(
            "部署环境与当前服务环境不一致"
        )
    )
    result = await service._reload(
        request=ControlRequest(
            deployment_id="dep_test"
        ),
        request_id="req_test",
        operator="alice",
    )

    assert result["success"] is False
    assert result["error_type"] == "ServiceEnvironmentMismatchError"
    service.controller.reload.assert_not_awaited()


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
        "control": {
            "desired_status": "loaded",
            "generation": 4,
        },
        "runtimes": [
            {
                "worker_id": "worker_one",
                "status": "running",
                "applied_generation": 4,
            },
            {
                "worker_id": "worker_two",
                "status": "running",
                "applied_generation": 3,
            },
        ],
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
        "desired_status": "loaded",
        "generation": 4,
    }
    assert result["runtimes"] == [
        {
            "worker_id": "worker_one",
            "status": "running",
            "applied_generation": 4,
        },
        {
            "worker_id": "worker_two",
            "status": "running",
            "applied_generation": 3,
        },
    ]
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
@pytest.mark.parametrize("status", ["active", "inactive"])
async def test_validate_service_environment_accepts_current_environment(
        runtime_server: Any,
        monkeypatch: pytest.MonkeyPatch,
        status: str,
) -> None:
    """测试服务环境校验不限制当前环境部署的状态."""
    service_module = runtime_server.load_service_module(monkeypatch)
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=SimpleNamespace(
            environment="testing",
            status=status,
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
