"""运行时控制服务测试.

验证部署期望状态控制、运行状态查询和参数校验。

核心功能：
  - test_load_creates_control_and_requests_loaded:
    验证首次加载创建控制记录
  - test_load_updates_existing_control:
    验证加载已有控制记录
  - test_unload_updates_existing_control:
    验证卸载已有控制记录
  - test_unload_creates_control:
    验证首次卸载创建控制记录
  - test_unload_rejects_active_deployment:
    验证启用部署不能卸载
  - test_reload_requires_existing_control:
    验证重载要求控制记录存在
  - test_reload_requests_new_generation:
    验证重载递增控制代次
  - test_load_rejects_inactive_deployment:
    验证非活动部署不能加载
  - test_get_status_returns_deployment_and_runtimes:
    验证运行状态汇总
  - test_list_services_aggregates_runtime_statuses:
    验证服务状态统计
  - test_list_services_rejects_invalid_pagination:
    验证分页参数校验
  - test_validate_control_environment_rejects_mismatch:
    验证环境一致性
  - test_runtime_serialization_preserves_applied_generation:
    测试运行实例序列化保留控制代次及其可空语义
  - test_get_status_preserves_worker_applied_generations:
    测试状态响应保留每个 Worker 实际应用的控制代次
  - test_get_status_rejects_missing_deployment:
    测试查询不存在的部署状态时报错
  - test_list_services_supports_empty_filters:
    测试不传筛选条件时查询全部运行服务
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

import datamind.services.control as control_module
from datamind.constants import Environment
from datamind.db.models.controls import Control
from datamind.db.models.deployments import Deployment
from datamind.models.errors import (
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
)
from datamind.services import RuntimeControlService


class FakeUnitOfWork:
    """运行控制服务测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.flush = AsyncMock()
        self.session.refresh = AsyncMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_deployment(*, status: str = "active") -> Deployment:
    """创建部署测试对象."""
    values: dict[str, Any] = {
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "environment": "production",
        "rollout_type": "full",
        "role": "champion",
        "status": status,
    }

    return Deployment(**values)


def create_control(*, desired_status: str = "unloaded") -> Control:
    """创建运行控制测试对象."""
    values: dict[str, Any] = {
        "control_id": "ctl_test",
        "deployment_id": "dep_test",
        "environment": "production",
        "desired_status": desired_status,
        "generation": 1,
        "created_by": "operator",
        "updated_by": "operator",
    }

    return Control(**values)


def configure_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        deployment: object | None = None,
        control: object | None = None,
        runtimes: list[object] | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock]:
    """配置运行控制服务仓储替身."""
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=deployment
    )
    control_repo = MagicMock()
    control_repo.get_deployment_control = AsyncMock(
        return_value=control
    )
    runtime_repo = MagicMock()
    runtime_repo.list_runtimes = AsyncMock(
        return_value=runtimes or []
    )

    monkeypatch.setitem(
        vars(control_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(control_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(control_module),
        "ControlRepository",
        lambda _session: control_repo,
    )
    monkeypatch.setitem(
        vars(control_module),
        "RuntimeRepository",
        lambda _session: runtime_repo,
    )

    return deployment_repo, control_repo, runtime_repo


@pytest.mark.asyncio
async def test_load_creates_control_and_requests_loaded(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次加载创建控制记录并设置 loaded."""
    deployment = create_deployment()
    control = create_control()
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=deployment,
    )
    control_repo.create_control.return_value = control
    control_repo.set_loaded.return_value = control

    result = await RuntimeControlService().load(
        deployment_id="dep_test",
        operator="operator",
    )

    assert result["action"] == "load"
    assert result["accepted"] is True
    control_repo.create_control.assert_called_once_with(
        control_id=ANY,
        deployment_id="dep_test",
        environment=Environment.PRODUCTION,
        created_by="operator",
    )
    control_repo.set_loaded.assert_called_once_with(
        control,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_load_updates_existing_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试加载已有控制记录并校验部署环境."""
    deployment = create_deployment()
    control = create_control()
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=deployment,
        control=control,
    )
    control_repo.set_loaded.return_value = control

    result = await RuntimeControlService().load(
        deployment_id="dep_test",
        operator="operator",
    )

    assert result["action"] == "load"
    control_repo.create_control.assert_not_called()
    control_repo.set_loaded.assert_called_once_with(
        control,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_load_rejects_missing_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试加载不存在的部署时报错."""
    configure_service(
        monkeypatch
    )

    with pytest.raises(
            DeploymentNotFoundError,
            match="部署不存在",
    ):
        await RuntimeControlService().load(
            deployment_id="dep_missing"
        )


@pytest.mark.asyncio
async def test_unload_updates_existing_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试卸载已有控制记录."""
    control = create_control(desired_status="loaded")
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="inactive"),
        control=control,
    )
    control_repo.set_unloaded.return_value = control

    result = await RuntimeControlService().unload(
        deployment_id="dep_test",
        operator="operator",
    )

    assert result["action"] == "unload"
    control_repo.set_unloaded.assert_called_once_with(
        control,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_unload_creates_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次卸载创建 unloaded 控制记录."""
    control = create_control()
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="inactive"),
    )
    control_repo.create_control.return_value = control

    result = await RuntimeControlService().unload(
        deployment_id="dep_test",
        operator="operator",
    )

    assert result["action"] == "unload"
    control_repo.create_control.assert_called_once_with(
        control_id=ANY,
        deployment_id="dep_test",
        environment=Environment.PRODUCTION,
        created_by="operator",
    )
    control_repo.set_unloaded.assert_not_called()


@pytest.mark.asyncio
async def test_unload_rejects_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用部署不能卸载."""
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="active"),
        control=create_control(desired_status="loaded"),
    )

    with pytest.raises(
            InvalidDeploymentStateError,
            match="部署仍处于启用状态，请先禁用部署",
    ):
        await RuntimeControlService().unload(
            deployment_id="dep_test",
            operator="operator",
        )

    control_repo.set_unloaded.assert_not_called()


@pytest.mark.asyncio
async def test_reload_requires_existing_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重载要求运行控制记录存在."""
    configure_service(
        monkeypatch,
        deployment=create_deployment(),
    )

    with pytest.raises(RuntimeError, match="请先停用后重新启用部署"):
        await RuntimeControlService().reload(
            deployment_id="dep_test"
        )


@pytest.mark.asyncio
async def test_reload_requests_new_generation(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重载已有 loaded 控制记录."""
    control = create_control(desired_status="loaded")
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(),
        control=control,
    )
    control_repo.request_reload.return_value = control

    result = await RuntimeControlService().reload(
        deployment_id="dep_test",
        operator="operator",
    )

    assert result["action"] == "reload"
    assert result["accepted"] is True
    control_repo.request_reload.assert_called_once_with(
        control,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_load_rejects_inactive_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非活动部署不能加载."""
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="inactive"),
    )

    with pytest.raises(
            InvalidDeploymentStateError,
            match="部署不是启用状态",
    ):
        await RuntimeControlService().load(
            deployment_id="dep_test"
        )

    control_repo.create_control.assert_not_called()


@pytest.mark.asyncio
async def test_get_status_returns_deployment_and_runtimes(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试查询部署、控制记录和 Worker 运行状态."""
    runtime = SimpleNamespace(
        runtime_id="run_test",
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        status="running",
        worker_id="worker_test",
        loaded_at=None,
        unloaded_at=None,
        last_heartbeat_at=None,
        error=None,
        context=None,
    )
    configure_service(
        monkeypatch,
        deployment=create_deployment(),
        control=create_control(desired_status="loaded"),
        runtimes=[runtime],
    )

    result = await RuntimeControlService().get_status(
        deployment_id="dep_test"
    )

    assert result["deployment"]["deployment_id"] == "dep_test"
    assert result["control"]["desired_status"] == "loaded"
    assert result["runtimes"][0]["worker_id"] == "worker_test"


@pytest.mark.asyncio
async def test_get_status_rejects_missing_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试查询不存在的部署状态时报错."""
    configure_service(
        monkeypatch
    )

    with pytest.raises(
            DeploymentNotFoundError,
            match="部署不存在",
    ):
        await RuntimeControlService().get_status(
            deployment_id="dep_missing"
        )


@pytest.mark.asyncio
async def test_list_services_aggregates_runtime_statuses(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试按部署汇总 Worker 运行状态."""
    now = datetime.now(timezone.utc)
    control = create_control(desired_status="loaded")
    control.updated_at = now
    runtimes = [
        SimpleNamespace(
            runtime_id=f"run_{status}",
            deployment_id="dep_test",
            model_id="mdl_test",
            version_id="ver_test",
            framework="sklearn",
            status=status,
            worker_id=f"worker_{status}",
            loaded_at=None,
            unloaded_at=None,
            last_heartbeat_at=None,
            error=None,
            context=None,
        )
        for status in (
            "starting",
            "running",
            "stopping",
            "stopped",
            "failed",
            "unknown",
        )
    ]
    _, control_repo, _ = configure_service(
        monkeypatch,
        runtimes=runtimes,
    )
    control_repo.list_controls = AsyncMock(return_value=[control])

    result = await RuntimeControlService().list_services(
        environment="production",
        desired_status="loaded",
    )

    assert result[0]["worker_count"] == 4
    assert result[0]["runtime_count"] == 6
    assert result[0]["starting_count"] == 1
    assert result[0]["running_count"] == 1
    assert result[0]["stopping_count"] == 1
    assert result[0]["failed_count"] == 1
    assert result[0]["stopped_count"] == 1


@pytest.mark.asyncio
async def test_list_services_supports_empty_filters(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试不传筛选条件时查询全部运行服务."""
    _, control_repo, _ = configure_service(
        monkeypatch
    )
    control_repo.list_controls = AsyncMock(
        return_value=[]
    )

    result = await RuntimeControlService().list_services()

    assert result == []
    control_repo.list_controls.assert_awaited_once_with(
        limit=None,
        offset=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"limit": 0}, "limit 必须大于 0"),
        ({"offset": -1}, "offset 不能小于 0"),
    ],
)
async def test_list_services_rejects_invalid_pagination(
        kwargs: dict[str, int],
        message: str,
) -> None:
    """测试拒绝非法分页参数."""
    with pytest.raises(ValueError, match=message):
        await RuntimeControlService().list_services(**kwargs)


def test_validate_control_environment_rejects_mismatch() -> None:
    """测试拒绝控制记录与部署环境不一致."""
    control = create_control()
    control.environment = "testing"

    with pytest.raises(RuntimeError, match="环境与部署环境不一致"):
        RuntimeControlService._validate_control_environment(
            control=control,
            deployment=create_deployment(),
        )
