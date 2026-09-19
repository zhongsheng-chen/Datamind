"""模型部署生命周期服务测试

验证部署创建、启用、禁用、运行控制同步和配置校验。

核心功能：
  - test_create_deployment_passes_normalized_values:
    验证创建部署及参数传递
  - test_create_deployment_rejects_missing_model:
    验证模型不存在
  - test_create_deployment_rejects_missing_version:
    验证版本不存在
  - test_create_deployment_rejects_invalid_environment:
    验证非法环境
  - test_create_scoring_deployment_uses_default_threshold:
    验证评分部署保存默认决策阈值
  - test_resolve_threshold_accepts_supported_tasks:
    验证分类和评分决策阈值
  - test_resolve_threshold_rejects_unsupported_task:
    验证拒绝不支持的任务类型
  - test_resolve_threshold_wraps_validation_error:
    验证统一转换阈值校验异常
  - test_enable_deployment_activates_valid_deployment:
    验证启用有效部署
  - test_enable_rejects_missing_deployment:
    验证部署不存在
  - test_enable_rejects_inactive_version:
    验证版本未激活
  - test_disable_sets_runtime_control_unloaded:
    验证禁用并卸载
  - test_disable_creates_runtime_control:
    验证首次禁用创建控制记录
  - test_disable_rejects_running_experiment_reference:
    验证运行中实验引用部署时拒绝禁用
  - test_disable_allows_unreferenced_running_experiment:
    验证其他部署存在运行中实验时仍可禁用
  - test_disable_cascades_to_enabled_routings:
    验证禁用部署时级联禁用已启用路由
  - test_enable_does_not_restore_disabled_routings:
    验证重新启用部署不会自动恢复路由
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock

import pytest

import datamind.services.deployment as deployment_module
from datamind.constants import (
    Environment,
    Framework,
)
from datamind.models.errors import (
    DeploymentError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    InvalidModelStateError,
    ModelNotFoundError,
    VersionNotFoundError,
)
from datamind.services import DeploymentLifecycleService


class FakeUnitOfWork:
    """部署服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_deployment(*, status: str = "inactive") -> SimpleNamespace:
    """创建部署测试对象"""
    return SimpleNamespace(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        environment="production",
        rollout_type="full",
        role="champion",
        threshold=0.5,
        description=None,
        status=status,
    )


def configure_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        deployment: object | None = None,
        model_status: str = "active",
        version_status: str = "active",
        task_type: str = "classification",
        model_exists: bool = True,
        version_exists: bool = True,
        control: object | None = None,
        running_experiment: object | None = None,
        referenced_variants: list[object] | None = None,
        routings: list[object] | None = None,
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """配置部署服务依赖替身"""
    model = (
        SimpleNamespace(
            model_id="mdl_test",
            status=model_status,
            task_type=task_type,
            framework="sklearn",
        )
        if model_exists
        else None
    )
    version = (
        SimpleNamespace(
            version_id="ver_test",
            model_id="mdl_test",
            status=version_status,
        )
        if version_exists
        else None
    )
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=deployment
    )
    deployment_repo.create_deployment.return_value = (
        deployment or create_deployment()
    )
    resolver = MagicMock()
    resolver.resolve_model = AsyncMock(
        return_value=model
    )
    resolver.resolve_version = AsyncMock(
        return_value=version
    )

    if not model_exists:
        resolver.resolve_model.side_effect = (
            ModelNotFoundError(
                "模型不存在: mdl_test"
            )
        )

    if not version_exists:
        resolver.resolve_version.side_effect = (
            VersionNotFoundError(
                "版本不存在: ver_test"
            )
        )
    control_repo = MagicMock()
    control_repo.get_deployment_control = AsyncMock(
        return_value=control
    )
    control_repo.create_control.return_value = SimpleNamespace(
        desired_status="unloaded",
        generation=1,
    )
    experiment_repo = MagicMock()
    experiment_repo.get_running_experiment = AsyncMock(
        return_value=running_experiment
    )
    variant_repo = MagicMock()
    variant_repo.list_variants = AsyncMock(
        return_value=(
            referenced_variants
            if referenced_variants is not None
            else []
        )
    )
    routing_repo = MagicMock()
    routing_repo.list_routings = AsyncMock(
        return_value=(routings if routings is not None else [])
    )

    def disable_routing(
            routing: Any,
            *,
            updated_by: str | None = None,
    ) -> Any:
        routing.enabled = False
        if updated_by is not None:
            routing.updated_by = updated_by
        return routing

    routing_repo.disable_routing.side_effect = disable_routing

    monkeypatch.setitem(
        vars(deployment_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "MetadataRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "VersionRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "ControlRepository",
        lambda _session: control_repo,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "ExperimentRepository",
        lambda _session: experiment_repo,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "VariantRepository",
        lambda _session: variant_repo,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "RoutingRepository",
        lambda _session: routing_repo,
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "ModelResolver",
        lambda **_kwargs: resolver,
    )

    return (
        deployment_repo,
        control_repo,
        resolver,
        experiment_repo,
    )


@pytest.mark.asyncio
async def test_create_deployment_passes_normalized_values(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建部署并向仓储传递规范化参数"""
    deployment_repo, _, resolver, _ = configure_service(
        monkeypatch,
    )

    result = await DeploymentLifecycleService().create_deployment(
        model_id="mdl_test",
        version_id="ver_test",
        environment="production",
        threshold=0.5,
        description="分类部署",
        deployed_by="operator",
    )

    assert result["deployment_id"] == "dep_test"
    resolver.resolve_model.assert_awaited_once_with(
        model_id="mdl_test",
        name=None,
    )
    deployment_repo.create_deployment.assert_called_once_with(
        deployment_id=ANY,
        model_id="mdl_test",
        version_id="ver_test",
        framework=Framework.SKLEARN,
        environment=Environment.PRODUCTION,
        rollout_type="full",
        role="champion",
        threshold=0.5,
        description="分类部署",
        deployed_by="operator",
    )


@pytest.mark.asyncio
async def test_create_shadow_deployment_passes_normalized_values(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试创建影子部署并传递规范化发布参数"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
    )

    await DeploymentLifecycleService().create_deployment(
        model_id="mdl_test",
        version_id="ver_test",
        environment="production",
        rollout_type=" SHADOW ",
        role=" SHADOW ",
    )

    call = deployment_repo.create_deployment.call_args
    assert call is not None
    assert call.kwargs["rollout_type"] == "shadow"
    assert call.kwargs["role"] == "shadow"
    assert call.kwargs["threshold"] is None


@pytest.mark.asyncio
async def test_create_scoring_deployment_uses_default_threshold(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试评分部署保存默认决策阈值"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        task_type="scoring",
    )

    await DeploymentLifecycleService().create_deployment(
        model_id="mdl_test",
        version_id="ver_test",
        environment="production",
    )

    call = deployment_repo.create_deployment.call_args
    assert call is not None
    assert call.kwargs["threshold"] == 600.0


@pytest.mark.parametrize(
    ("rollout_type", "role", "message"),
    [
        (
            "shadow",
            "champion",
            "影子发布必须使用 shadow 部署角色",
        ),
        (
            "full",
            "shadow",
            "shadow 部署角色只能用于影子发布",
        ),
        (
            "full",
            "challenger",
            "全量发布必须使用 champion 部署角色",
        ),
        (
            "unknown",
            "champion",
            "不支持的发布方式",
        ),
        (
            "full",
            "unknown",
            "不支持的部署角色",
        ),
    ],
)
def test_validate_release_mode_rejects_invalid_combinations(
        rollout_type: str,
        role: str,
        message: str,
) -> None:
    """测试拒绝不合法的发布方式和部署角色组合"""
    with pytest.raises(
            DeploymentError,
            match=message,
    ):
        DeploymentLifecycleService.validate_release_mode(
            rollout_type=rollout_type,
            role=role,
        )


@pytest.mark.asyncio
async def test_create_deployment_rejects_missing_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型不存在时拒绝创建部署"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        model_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型不存在"):
        await DeploymentLifecycleService().create_deployment(
            model_id="mdl_test"
        )

    deployment_repo.create_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_create_deployment_rejects_missing_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本不存在时拒绝创建部署"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        version_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型版本不存在"):
        await DeploymentLifecycleService().create_deployment(
            model_id="mdl_test",
            version_id="ver_test",
        )

    deployment_repo.create_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_create_deployment_rejects_invalid_environment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝未知部署环境"""
    deployment_repo, _, _, _ = configure_service(monkeypatch)

    with pytest.raises(ValueError, match="not a valid Environment"):
        await DeploymentLifecycleService().create_deployment(
            model_id="mdl_test",
            version_id="ver_test",
            environment="unknown",
        )

    deployment_repo.create_deployment.assert_not_called()


@pytest.mark.parametrize(
    ("task_type", "threshold"),
    [
        ("classification", 0.5),
        ("scoring", 650.0),
    ],
)
def test_resolve_threshold_accepts_supported_tasks(
        task_type: str,
        threshold: float,
) -> None:
    """测试接受合法的分类和评分决策阈值"""
    result = DeploymentLifecycleService._resolve_threshold(
        task_type=task_type,
        threshold=threshold,
    )

    assert result is not None


def test_resolve_threshold_rejects_unsupported_task() -> None:
    """测试有配置时拒绝未知任务类型"""
    with pytest.raises(DeploymentError, match="不支持的任务类型"):
        DeploymentLifecycleService._resolve_threshold(
            task_type="unknown",
            threshold=1.0,
        )


def test_resolve_threshold_wraps_validation_error() -> None:
    """测试将配置模型校验异常转换为部署异常"""
    with pytest.raises(DeploymentError, match="配置校验失败"):
        DeploymentLifecycleService._resolve_threshold(
            task_type="classification",
            threshold=2.0,
        )


@pytest.mark.asyncio
async def test_enable_deployment_activates_valid_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用满足条件的部署"""
    deployment = create_deployment()
    deployment_repo, control_repo, _, _ = configure_service(
        monkeypatch,
        deployment=deployment,
    )

    result = await DeploymentLifecycleService().enable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    assert result["deployment_id"] == "dep_test"
    deployment_repo.activate_deployment.assert_called_once_with(
        deployment,
        updated_by="operator",
    )
    control_repo.create_control.assert_called_once_with(
        control_id=ANY,
        deployment_id="dep_test",
        environment=Environment.PRODUCTION,
        created_by="operator",
    )
    control_repo.set_loaded.assert_called_once_with(
        control_repo.create_control.return_value,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_enable_deployment_reuses_runtime_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重新启用部署时复用运行控制记录"""
    control = SimpleNamespace(
        desired_status="unloaded",
        generation=2,
    )
    _, control_repo, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(),
        control=control,
    )

    await DeploymentLifecycleService().enable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    control_repo.create_control.assert_not_called()
    control_repo.set_loaded.assert_called_once_with(
        control,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_enable_rejects_missing_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用不存在的部署时报错"""
    deployment_repo, _, _, _ = configure_service(monkeypatch)

    with pytest.raises(DeploymentNotFoundError, match="部署不存在"):
        await DeploymentLifecycleService().enable_deployment(
            deployment_id="dep_missing"
        )

    deployment_repo.activate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_enable_rejects_inactive_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试非活动版本不能启用部署"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(),
        version_status="inactive",
    )

    with pytest.raises(InvalidModelStateError, match="版本未激活"):
        await DeploymentLifecycleService().enable_deployment(
            deployment_id="dep_test"
        )

    deployment_repo.activate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_enable_rejects_missing_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型不存在时拒绝启用部署"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(),
        model_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型不存在"):
        await DeploymentLifecycleService().enable_deployment(
            deployment_id="dep_test"
        )

    deployment_repo.activate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_disable_sets_runtime_control_unloaded(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试禁用部署同步请求 Worker 卸载模型"""
    deployment = create_deployment(status="active")
    control = SimpleNamespace(
        desired_status="loaded",
        generation=1,
    )
    deployment_repo, control_repo, _, experiment_repo = configure_service(
        monkeypatch,
        deployment=deployment,
        control=control,
    )

    await DeploymentLifecycleService().disable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    deployment_repo.deactivate_deployment.assert_called_once_with(
        deployment,
        updated_by="operator",
    )
    experiment_repo.get_running_experiment.assert_awaited_once_with(
        model_id="mdl_test",
        environment=Environment.PRODUCTION,
    )
    control_repo.set_unloaded.assert_called_once_with(
        control,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_disable_creates_runtime_control(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试首次禁用部署时创建 unloaded 控制记录"""
    deployment = create_deployment(status="active")
    _, control_repo, _, _ = configure_service(
        monkeypatch,
        deployment=deployment,
    )

    await DeploymentLifecycleService().disable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    control_repo.create_control.assert_called_once_with(
        control_id=ANY,
        deployment_id="dep_test",
        environment=Environment.PRODUCTION,
        created_by="operator",
    )
    control_repo.set_unloaded.assert_not_called()


@pytest.mark.asyncio
async def test_disable_rejects_running_experiment_reference(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行中实验引用部署时拒绝禁用"""
    deployment = create_deployment(
        status="active"
    )
    running_experiment = SimpleNamespace(
        experiment_id="exp_running"
    )
    deployment_repo, control_repo, _, experiment_repo = configure_service(
        monkeypatch,
        deployment=deployment,
        running_experiment=running_experiment,
        referenced_variants=[
            SimpleNamespace(
                variant_id="var_active"
            )
        ],
    )

    with pytest.raises(
            InvalidDeploymentStateError,
            match="部署正在被运行中的实验引用",
    ):
        await DeploymentLifecycleService().disable_deployment(
            deployment_id="dep_test",
            updated_by="operator",
        )

    experiment_repo.get_running_experiment.assert_awaited_once_with(
        model_id="mdl_test",
        environment=Environment.PRODUCTION,
    )
    deployment_repo.deactivate_deployment.assert_not_called()
    control_repo.get_deployment_control.assert_not_awaited()


@pytest.mark.asyncio
async def test_disable_allows_unreferenced_running_experiment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试运行中实验未引用当前部署时允许禁用"""
    deployment = create_deployment(
        status="active"
    )
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        deployment=deployment,
        running_experiment=SimpleNamespace(
            experiment_id="exp_running"
        ),
        referenced_variants=[],
    )

    await DeploymentLifecycleService().disable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    deployment_repo.deactivate_deployment.assert_called_once_with(
        deployment,
        updated_by="operator",
    )


@pytest.mark.asyncio
async def test_disable_cascades_to_enabled_routings(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试禁用部署时级联禁用已启用路由"""
    routings = [
        SimpleNamespace(
            routing_id="rtn_first",
            enabled=True,
            updated_by=None,
        ),
        SimpleNamespace(
            routing_id="rtn_second",
            enabled=True,
            updated_by=None,
        ),
    ]
    configure_service(
        monkeypatch,
        deployment=create_deployment(status="active"),
        routings=routings,
    )

    result = await DeploymentLifecycleService().disable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    assert result["disabled_routing_ids"] == [
        "rtn_first",
        "rtn_second",
    ]
    assert all(not routing.enabled for routing in routings)
    assert all(
        routing.updated_by == "operator"
        for routing in routings
    )


@pytest.mark.asyncio
async def test_enable_does_not_restore_disabled_routings(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试重新启用部署不会自动恢复路由"""
    routing = SimpleNamespace(
        routing_id="rtn_disabled",
        enabled=False,
        updated_by="operator",
    )
    configure_service(
        monkeypatch,
        deployment=create_deployment(),
        routings=[routing],
    )

    await DeploymentLifecycleService().enable_deployment(
        deployment_id="dep_test",
        updated_by="operator",
    )

    assert routing.enabled is False


@pytest.mark.asyncio
async def test_disable_rejects_missing_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试禁用不存在的部署时报错"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch
    )

    with pytest.raises(DeploymentNotFoundError, match="部署不存在"):
        await DeploymentLifecycleService().disable_deployment(
            deployment_id="dep_missing"
        )

    deployment_repo.deactivate_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_update_deployment_normalizes_release_values(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试仅允许编辑停用部署并规范化发布参数"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(),
    )
    routing = SimpleNamespace(
        routing_id="rtn_test",
        deployment_id="dep_test",
    )
    routing_repo = MagicMock()
    routing_repo.list_routings = AsyncMock(
        return_value=[routing]
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "RoutingRepository",
        lambda _session: routing_repo,
    )

    await DeploymentLifecycleService().update_deployment(
        deployment_id="dep_test",
        environment="testing",
        rollout_type=" CANARY ",
        role=" CHALLENGER ",
        description="灰度验证",
        updated_by="operator",
    )

    deployment_repo.update_deployment.assert_called_once()
    deployment, patch = deployment_repo.update_deployment.call_args.args
    assert deployment.deployment_id == "dep_test"
    assert patch.environment.value == "testing"
    assert patch.rollout_type == "canary"
    assert patch.role == "challenger"
    assert patch.description == "灰度验证"
    assert deployment_repo.update_deployment.call_args.kwargs == {
        "updated_by": "operator",
    }
    routing_repo.list_routings.assert_awaited_once_with(
        deployment_id="dep_test",
        include_deleted=True,
    )
    routing_repo.update_routing.assert_called_once()
    synced_routing, routing_patch = (
        routing_repo.update_routing.call_args.args
    )
    assert synced_routing is routing
    assert routing_patch.environment.value == "testing"
    assert routing_patch.rollout_type == "canary"
    assert routing_patch.rollout_group == "challenger"
    assert routing_repo.update_routing.call_args.kwargs == {
        "updated_by": "operator",
    }


@pytest.mark.asyncio
async def test_update_deployment_to_full_sets_routing_to_100_percent(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试切换为全量发布时同步固定现有路由比例"""
    deployment = create_deployment()
    deployment.rollout_type = "canary"
    deployment.role = "challenger"
    configure_service(
        monkeypatch,
        deployment=deployment,
    )
    routing = SimpleNamespace(
        routing_id="rtn_test",
        deployment_id="dep_test",
    )
    routing_repo = MagicMock()
    routing_repo.list_routings = AsyncMock(
        return_value=[routing]
    )
    monkeypatch.setitem(
        vars(deployment_module),
        "RoutingRepository",
        lambda _session: routing_repo,
    )

    await DeploymentLifecycleService().update_deployment(
        deployment_id="dep_test",
        rollout_type="full",
        role="champion",
        updated_by="operator",
    )

    _, routing_patch = routing_repo.update_routing.call_args.args
    assert routing_patch.rollout_type == "full"
    assert routing_patch.rollout_group == "champion"
    assert routing_patch.traffic_ratio == 1.0


@pytest.mark.asyncio
async def test_update_deployment_rejects_active_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试启用状态部署必须先停用再编辑"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="active"),
    )

    with pytest.raises(
            InvalidDeploymentStateError,
            match="请先停用部署",
    ):
        await DeploymentLifecycleService().update_deployment(
            deployment_id="dep_test",
            description="不可直接修改",
        )

    deployment_repo.update_deployment.assert_not_called()


@pytest.mark.asyncio
async def test_disable_rejects_missing_model(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型不存在时拒绝禁用部署"""
    deployment_repo, _, _, _ = configure_service(
        monkeypatch,
        deployment=create_deployment(status="active"),
        model_exists=False,
    )

    with pytest.raises(DeploymentError, match="模型不存在"):
        await DeploymentLifecycleService().disable_deployment(
            deployment_id="dep_test"
        )

    deployment_repo.deactivate_deployment.assert_not_called()
