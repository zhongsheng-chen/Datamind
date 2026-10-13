"""运行时控制服务测试.

验证部署重载、运行状态查询和参数校验。

核心功能：
  - test_reload_requires_existing_control:
    验证重载要求控制记录存在
  - test_reload_requests_new_generation:
    验证重载递增控制代次
  - test_reload_rejects_inactive_deployment:
    验证非活动部署不能重载
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
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.control as control_module
from datamind.db.models.controls import Control
from datamind.db.models.deployments import Deployment
from datamind.db.models.runtimes import Runtime
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


def create_control(
        *,
        desired_status: str = "unloaded",
        generation: int = 1,
) -> Control:
    """创建运行控制测试对象."""
    values: dict[str, Any] = {
        "control_id": "ctl_test",
        "deployment_id": "dep_test",
        "environment": "production",
        "desired_status": desired_status,
        "generation": generation,
        "created_by": "operator",
        "updated_by": "operator",
    }

    return Control(**values)


def create_runtime(
        *,
        status: str = "running",
        worker_id: str = "worker_test",
        applied_generation: int | None = 1,
) -> Runtime:
    """创建运行实例测试对象."""
    values: dict[str, Any] = {
        "runtime_id": f"run_{worker_id}",
        "deployment_id": "dep_test",
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "status": status,
        "worker_id": worker_id,
    }

    if applied_generation is not None:
        values["applied_generation"] = applied_generation

    return Runtime(**values)


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
async def test_reload_rejects_inactive_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非活动部署不能重载."""
    _, control_repo, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="inactive"),
        control=create_control(desired_status="loaded"),
    )

    with pytest.raises(
            InvalidDeploymentStateError,
            match="部署不是启用状态",
    ):
        await RuntimeControlService().reload(
            deployment_id="dep_test"
        )

    control_repo.request_reload.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deployment_status", "desired_status", "runtime_status"),
    [
        ("active", "loaded", "running"),
        ("inactive", "unloaded", "stopped"),
    ],
)
async def test_get_status_returns_deployment_and_runtimes(
        monkeypatch: pytest.MonkeyPatch,
        deployment_status: str,
        desired_status: str,
        runtime_status: str,
) -> None:
    """测试启用和停用部署均可查询运行状态."""
    runtime = create_runtime(
        status=runtime_status,
    )
    configure_service(
        monkeypatch,
        deployment=create_deployment(status=deployment_status),
        control=create_control(desired_status=desired_status),
        runtimes=[runtime],
    )

    result = await RuntimeControlService().get_status(
        deployment_id="dep_test"
    )

    assert result["deployment"]["deployment_id"] == "dep_test"
    assert result["deployment"]["status"] == deployment_status
    assert result["control"]["desired_status"] == desired_status
    assert result["runtimes"][0]["worker_id"] == "worker_test"
    assert result["runtimes"][0]["applied_generation"] == 1


@pytest.mark.parametrize("applied_generation", [7, None])
def test_runtime_serialization_preserves_applied_generation(
        applied_generation: int | None,
) -> None:
    """测试运行实例序列化保留控制代次及其可空语义."""
    result = RuntimeControlService._runtime_to_dict(
        create_runtime(
            applied_generation=applied_generation,
        )
    )

    assert result["applied_generation"] is applied_generation


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("applied_generations", "expected_generations"),
    [
        ((3, 2), [3, 2]),
        ((4, 4), [4, 4]),
    ],
)
async def test_get_status_preserves_worker_applied_generations(
        monkeypatch: pytest.MonkeyPatch,
        applied_generations: tuple[int, int],
        expected_generations: list[int],
) -> None:
    """测试状态响应保留每个 Worker 实际应用的控制代次."""
    runtimes = [
        create_runtime(
            worker_id=f"worker_{index}",
            applied_generation=generation,
        )
        for index, generation in enumerate(
            applied_generations,
            start=1,
        )
    ]
    configure_service(
        monkeypatch,
        deployment=create_deployment(),
        control=create_control(
            desired_status="loaded",
            generation=max(applied_generations),
        ),
        runtimes=runtimes,
    )

    result = await RuntimeControlService().get_status(
        deployment_id="dep_test"
    )

    assert [
        runtime["status"]
        for runtime in result["runtimes"]
    ] == ["running", "running"]
    assert [
        runtime["applied_generation"]
        for runtime in result["runtimes"]
    ] == expected_generations


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
        create_runtime(
            status=status,
            worker_id=f"worker_{status}",
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
    assert all(
        runtime["applied_generation"] == 1
        for runtime in result[0]["runtimes"]
    )


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
