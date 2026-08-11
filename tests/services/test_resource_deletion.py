# tests/services/test_resource_deletion.py

"""资源逻辑删除服务测试

验证部署、路由、实验和实验分组的删除边界与恢复行为。
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.deployment as deployment_module
import datamind.services.experiment as experiment_module
import datamind.services.routing as routing_module
from datamind.models.errors import (
    InvalidDeploymentStateError,
    InvalidExperimentStateError,
)
from datamind.services import (
    DeploymentLifecycleService,
    ExperimentLifecycleService,
    RoutingLifecycleService,
)


class FakeUnitOfWork:
    """服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def install_deployment_repositories(
        monkeypatch: pytest.MonkeyPatch,
        *,
        deployment: object,
        control: object | None = None,
        runtimes: list[object] | None = None,
        routings: list[object] | None = None,
        variants: list[object] | None = None,
) -> MagicMock:
    """安装部署删除服务仓储替身"""
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
    deployment_repo.runtime_repo = runtime_repo
    routing_repo = MagicMock()
    routing_repo.list_enabled_routings = AsyncMock(
        return_value=routings or []
    )
    variant_repo = MagicMock()
    variant_repo.list_variants = AsyncMock(
        return_value=variants or []
    )
    experiment_repo = MagicMock()
    experiment_repo.get_experiment = AsyncMock()
    module_namespace = vars(
        deployment_module
    )

    monkeypatch.setitem(
        module_namespace,
        "UnitOfWork",
        FakeUnitOfWork,
    )
    for name, repository in {
        "DeploymentRepository": deployment_repo,
        "ControlRepository": control_repo,
        "RuntimeRepository": runtime_repo,
        "RoutingRepository": routing_repo,
        "VariantRepository": variant_repo,
        "ExperimentRepository": experiment_repo,
    }.items():
        monkeypatch.setitem(
            module_namespace,
            name,
            lambda _session, value=repository: value,
        )

    return deployment_repo


def create_deployment(
        *,
        status: str = "inactive",
        deleted_at: object | None = None,
) -> SimpleNamespace:
    """创建部署测试对象"""
    return SimpleNamespace(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        status=status,
        deleted_at=deleted_at,
    )


@pytest.mark.asyncio
async def test_delete_deployment_marks_safe_deployment_deleted(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试删除已停用且已卸载的部署"""
    deployment = create_deployment()
    repository = install_deployment_repositories(
        monkeypatch,
        deployment=deployment,
    )

    result = await DeploymentLifecycleService().delete_deployment(
        deployment_id="dep_test",
        reason="不再使用",
        deleted_by="admin",
    )

    assert result["action"] == "delete_deployment"
    repository.mark_deleted.assert_called_once_with(
        deployment,
        deleted_by="admin",
        deletion_reason="不再使用",
    )


@pytest.mark.asyncio
async def test_delete_deployment_rejects_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝删除启用状态的部署"""
    repository = install_deployment_repositories(
        monkeypatch,
        deployment=create_deployment(
            status="active"
        ),
    )

    with pytest.raises(
        InvalidDeploymentStateError,
        match="请先停用部署",
    ):
        await DeploymentLifecycleService().delete_deployment(
            deployment_id="dep_test"
        )

    repository.mark_deleted.assert_not_called()


@pytest.mark.asyncio
async def test_delete_deployment_rejects_loaded_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试加载期望状态阻止删除部署"""
    repository = install_deployment_repositories(
        monkeypatch,
        deployment=create_deployment(),
        control=SimpleNamespace(
            desired_status="loaded"
        ),
    )

    with pytest.raises(
        InvalidDeploymentStateError,
        match="请重新启用后再停用部署",
    ):
        await DeploymentLifecycleService().delete_deployment(
            deployment_id="dep_test"
        )

    repository.mark_deleted.assert_not_called()


@pytest.mark.asyncio
async def test_delete_deployment_rejects_live_running_runtime(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试仍有近期心跳的运行实例时拒绝删除部署。"""
    runtime = SimpleNamespace(
        runtime_id="rtm_live",
        status="running",
        last_heartbeat_at=datetime.now(timezone.utc),
        context={},
    )
    repository = install_deployment_repositories(
        monkeypatch,
        deployment=create_deployment(),
        control=SimpleNamespace(desired_status="unloaded"),
        runtimes=[runtime],
    )

    with pytest.raises(
        InvalidDeploymentStateError,
        match="rtm_live",
    ):
        await DeploymentLifecycleService().delete_deployment(
            deployment_id="dep_test",
            deleted_by="admin",
        )

    repository.runtime_repo.mark_stopped.assert_not_called()
    repository.mark_deleted.assert_not_called()


@pytest.mark.asyncio
async def test_delete_deployment_finalizes_stale_runtime_after_unload(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试卸载请求后的失联实例不会永久阻塞部署删除。"""
    runtime = SimpleNamespace(
        runtime_id="rtm_stale",
        status="running",
        last_heartbeat_at=(
            datetime.now(timezone.utc)
            - timedelta(minutes=10)
        ),
        context={"worker_id": "worker_stale"},
    )
    repository = install_deployment_repositories(
        monkeypatch,
        deployment=create_deployment(),
        control=SimpleNamespace(desired_status="unloaded"),
        runtimes=[runtime],
    )

    result = await DeploymentLifecycleService().delete_deployment(
        deployment_id="dep_test",
        reason="不再使用",
        deleted_by="admin",
    )

    assert result["finalized_runtime_ids"] == ["rtm_stale"]
    repository.runtime_repo.mark_stopped.assert_called_once_with(
        runtime,
        stopped_by="admin",
        context={
            "worker_id": "worker_stale",
            "reason": "stale_runtime_finalized_on_delete",
        },
    )
    repository.mark_deleted.assert_called_once()


@pytest.mark.asyncio
async def test_restore_deployment_keeps_deployment_inactive(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试恢复部署时调用停用恢复逻辑"""
    deployment = create_deployment(
        deleted_at=object()
    )
    repository = install_deployment_repositories(
        monkeypatch,
        deployment=deployment,
    )
    repository.restore_deployment.side_effect = (
        lambda current, **_kwargs: setattr(
            current,
            "status",
            "inactive",
        )
    )

    result = await DeploymentLifecycleService().restore_deployment(
        deployment_id="dep_test",
        restored_by="admin",
    )

    assert result["status"] == "inactive"
    repository.get_deployment.assert_awaited_once_with(
        "dep_test",
        include_deleted=True,
    )


def install_routing_repository(
        monkeypatch: pytest.MonkeyPatch,
        routing: object,
) -> MagicMock:
    """安装路由服务仓储替身"""
    repository = MagicMock()
    repository.get_routing = AsyncMock(
        return_value=routing
    )
    repository.list_routings = AsyncMock(return_value=[])
    module_namespace = vars(
        routing_module
    )
    monkeypatch.setitem(
        module_namespace,
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        module_namespace,
        "RoutingRepository",
        lambda _session: repository,
    )
    return repository


@pytest.mark.asyncio
async def test_delete_routing_requires_disabled_route(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用路由不能删除"""
    repository = install_routing_repository(
        monkeypatch,
        SimpleNamespace(
            routing_id="rtn_test",
            deployment_id="dep_test",
            enabled=True,
        ),
    )

    with pytest.raises(
        ValueError,
        match="请先禁用路由",
    ):
        await RoutingLifecycleService().delete_routing(
            routing_id="rtn_test"
        )

    repository.mark_deleted.assert_not_called()


@pytest.mark.asyncio
async def test_restore_routing_reads_deleted_record(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试恢复路由包含逻辑删除记录"""
    routing = SimpleNamespace(
        routing_id="rtn_test",
        deployment_id="dep_test",
        enabled=False,
        deleted_at=object(),
    )
    repository = install_routing_repository(
        monkeypatch,
        routing,
    )

    await RoutingLifecycleService().restore_routing(
        routing_id="rtn_test",
        restored_by="admin",
    )

    repository.get_routing.assert_awaited_once_with(
        "rtn_test",
        include_deleted=True,
    )
    repository.restore_routing.assert_called_once_with(
        routing,
        restored_by="admin",
    )


def install_experiment_repositories(
        monkeypatch: pytest.MonkeyPatch,
        *,
        experiment: object,
        variants: list[object],
) -> tuple[MagicMock, MagicMock]:
    """安装实验服务仓储替身"""
    experiment_repo = MagicMock()
    experiment_repo.get_experiment = AsyncMock(
        return_value=experiment
    )
    variant_repo = MagicMock()
    variant_repo.get_variant = AsyncMock(
        return_value=(
            variants[0]
            if variants
            else None
        )
    )
    variant_repo.list_variants = AsyncMock(
        return_value=variants
    )
    module_namespace = vars(
        experiment_module
    )
    monkeypatch.setitem(
        module_namespace,
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        module_namespace,
        "ExperimentRepository",
        lambda _session: experiment_repo,
    )
    monkeypatch.setitem(
        module_namespace,
        "VariantRepository",
        lambda _session: variant_repo,
    )
    monkeypatch.setitem(
        module_namespace,
        "generate_random_id",
        lambda **_kwargs: "del_test",
    )
    return experiment_repo, variant_repo


def create_experiment(
        *,
        status: str = "draft",
        deleted_at: object | None = None,
        deletion_id: str | None = None,
) -> SimpleNamespace:
    """创建实验测试对象"""
    return SimpleNamespace(
        experiment_id="exp_test",
        name="scorecard_test",
        status=status,
        deleted_at=deleted_at,
        deletion_id=deletion_id,
    )


def create_variant(
        *,
        deleted_at: object | None = None,
        deletion_id: str | None = None,
) -> SimpleNamespace:
    """创建实验分组测试对象"""
    return SimpleNamespace(
        variant_id="var_test",
        experiment_id="exp_test",
        name="control",
        deployment_id="dep_test",
        status="active",
        deleted_at=deleted_at,
        deletion_id=deletion_id,
    )


@pytest.mark.asyncio
async def test_delete_experiment_cascades_same_deletion_batch(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试删除实验时同批删除分组"""
    experiment = create_experiment()
    variant = create_variant()
    experiment_repo, variant_repo = install_experiment_repositories(
        monkeypatch,
        experiment=experiment,
        variants=[variant],
    )

    result = await ExperimentLifecycleService().delete_experiment(
        experiment_id="exp_test",
        reason="测试结束",
        deleted_by="admin",
    )

    assert result["deletion_id"] == "del_test"
    variant_call = variant_repo.mark_deleted.call_args.kwargs
    experiment_call = experiment_repo.mark_deleted.call_args.kwargs
    assert variant_call["deletion_id"] == "del_test"
    assert experiment_call["deletion_id"] == "del_test"
    assert variant_call["deleted_at"] == experiment_call["deleted_at"]


@pytest.mark.asyncio
async def test_delete_experiment_rejects_running_experiment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行中实验不能删除"""
    experiment_repo, _ = install_experiment_repositories(
        monkeypatch,
        experiment=create_experiment(
            status="running"
        ),
        variants=[],
    )

    with pytest.raises(
        InvalidExperimentStateError,
        match="当前状态的实验无法删除",
    ):
        await ExperimentLifecycleService().delete_experiment(
            experiment_id="exp_test"
        )

    experiment_repo.mark_deleted.assert_not_called()


@pytest.mark.asyncio
async def test_restore_experiment_restores_same_batch_variants(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试恢复实验时只恢复同批删除分组"""
    current = create_variant(
        deleted_at=object(),
        deletion_id="del_test",
    )
    other = create_variant(
        deleted_at=object(),
        deletion_id="del_other",
    )
    experiment_repo, variant_repo = install_experiment_repositories(
        monkeypatch,
        experiment=create_experiment(
            deleted_at=object(),
            deletion_id="del_test",
        ),
        variants=[current, other],
    )

    result = await ExperimentLifecycleService().restore_experiment(
        experiment_id="exp_test",
        restored_by="admin",
    )

    assert result["variant_count"] == 1
    variant_repo.restore_variant.assert_called_once_with(
        current,
        restored_by="admin",
    )
    experiment_repo.restore_experiment.assert_called_once()


@pytest.mark.asyncio
async def test_delete_variant_requires_draft_experiment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非草稿实验不能单独删除分组"""
    _, variant_repo = install_experiment_repositories(
        monkeypatch,
        experiment=create_experiment(
            status="paused"
        ),
        variants=[create_variant()],
    )

    with pytest.raises(
        InvalidExperimentStateError,
        match="实验启动后不能删除分组",
    ):
        await ExperimentLifecycleService().delete_variant(
            variant_id="var_test"
        )

    variant_repo.mark_deleted.assert_not_called()
