"""运行时路由器测试.

验证手工部署、实验、灰度路由和默认部署的解析优先级及边界条件。

核心功能：
  - test_resolve_uses_manual_deployment:
    验证使用显式指定的部署
  - test_resolve_uses_ab_test_deployment:
    验证使用 A/B 实验分配的部署
  - test_routing_uses_stable_payload_identifier:
    验证路由使用稳定的请求标识分桶
  - test_routing_context_uses_bucket_value:
    验证路由上下文区分分桶值与流量比例且不包含旧字段
  - test_resolve_uses_first_active_deployment_without_champion:
    验证缺少冠军部署时选择首个启用部署
  - test_resolve_includes_independently_matched_shadow:
    验证路由结果包含独立匹配的影子部署
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.ab_test.engine import ABTestResult
from datamind.db.models.routing import Routing
from datamind.models.enums import DecisionStrategy
from datamind.models.errors import RuntimeRouteError
import datamind.runtime.routing.router as router_module
from datamind.runtime.routing import (
    RouteResult,
    RoutingPlan,
    RuntimeRouter,
)


class FakeUnitOfWork:
    """运行时路由测试工作单元."""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.rollback = AsyncMock()
        FakeUnitOfWork.latest = self

    latest: "FakeUnitOfWork | None" = None

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_deployment(deployment_id: str) -> SimpleNamespace:
    """创建可路由部署测试对象."""
    return SimpleNamespace(
        deployment_id=deployment_id,
        model_id="mdl_test",
        version_id="ver_test",
        framework="sklearn",
        environment="production",
        rollout_type="canary",
        role="challenger",
        status="active",
        effective_from=None,
        effective_to=None,
        threshold=None,
    )


def create_shadow_deployment(
        deployment_id: str,
) -> SimpleNamespace:
    """创建影子部署测试对象."""
    deployment = create_deployment(
        deployment_id
    )
    deployment.rollout_type = "shadow"
    deployment.role = "shadow"
    return deployment


def create_ab_test_result(
        deployment_id: str = "dep_experiment",
) -> ABTestResult:
    """创建 A/B 实验命中结果."""
    return ABTestResult(
        experiment_id="exp_test",
        variant_id="var_test",
        deployment_id=deployment_id,
        assignment_id="asn_test",
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
        subject_type="customer",
        source="experiment",
        strategy="hash",
        bucket="bucket_1000",
        group="challenger",
        weight=0.2,
        experiment=MagicMock(),
        variant=MagicMock(),
        assignment=MagicMock(),
        context={
            "source": "new_assignment",
            "model_id": "mdl_test",
            "experiment_id": "exp_test",
            "variant_id": "var_test",
            "deployment_id": deployment_id,
            "subject_key": "customer_10001",
            "bucket": "bucket_1000",
            "variant_weight": 0.2,
            "traffic_ratio": 0.2,
            "point": 0.4,
        },
    )


def configure_router(
        monkeypatch: pytest.MonkeyPatch,
        *,
        deployment: SimpleNamespace | None = None,
        active_deployments: list[SimpleNamespace] | None = None,
        ab_result: ABTestResult | None = None,
) -> tuple[RuntimeRouter, AsyncMock, AsyncMock, AsyncMock]:
    """配置路由器及仓储替身."""
    deployment_repo = AsyncMock()
    deployment_repo.get_deployment.return_value = deployment
    deployment_repo.list_active_deployments.return_value = (
        active_deployments or []
    )
    routing_repo = AsyncMock()
    routing_repo.list_enabled_routings.return_value = []
    engine = MagicMock()
    engine.assign = AsyncMock(
        return_value=ab_result
    )
    monkeypatch.setitem(
        vars(router_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(router_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(router_module),
        "RoutingRepository",
        lambda _session: routing_repo,
    )
    monkeypatch.setitem(
        vars(router_module),
        "ExperimentRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(router_module),
        "VariantRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(router_module),
        "AssignmentRepository",
        lambda _session: MagicMock(),
    )
    monkeypatch.setitem(
        vars(router_module),
        "ABTestEngine",
        lambda **_kwargs: engine,
    )

    return RuntimeRouter(), deployment_repo, routing_repo, engine.assign


def create_routing(
        routing_id: str,
        deployment_id: str,
        ratio: float,
) -> Routing:
    """创建路由配置测试对象."""
    return Routing(
        routing_id=routing_id,
        name=f"{routing_id}-route",
        deployment_id=deployment_id,
        rollout_type="canary",
        rollout_group="challenger",
        environment="production",
        enabled=True,
        traffic_ratio=float(ratio),
        rules=None,
    )


def test_routing_effective_window_controls_eligibility() -> None:
    """测试路由仅在自身生效区间内参与流量分配."""
    now = datetime(2026, 8, 29, 0, 0, tzinfo=timezone.utc)
    routing = create_routing("rtn_test", "dep_test", 1.0)
    one_minute = timedelta(minutes=1.0)

    routing.effective_from = now - one_minute
    routing.effective_to = now + one_minute
    assert RuntimeRouter._is_effective_routing(routing, now=now)

    routing.effective_from = now + one_minute
    assert not RuntimeRouter._is_effective_routing(routing, now=now)

    routing = create_routing("rtn_test", "dep_test", 1.0)
    routing.effective_to = now
    assert not RuntimeRouter._is_effective_routing(routing, now=now)


async def resolve_routing(
        monkeypatch: pytest.MonkeyPatch,
        *,
        ratio: float,
        routing_ratios: list[float],
        subject_key: str | None = "customer_10001",
        payload: dict[str, object] | None = None,
) -> RouteResult:
    """执行指定哈希点和候选比例的路由解析."""
    router = RuntimeRouter()
    monkeypatch.setattr(
        router,
        "_hash_ratio",
        lambda *_parts: (ratio, "bucket_test"),
    )
    routings = [
        create_routing(f"rtn_{index}", f"dep_{index}", weight)
        for index, weight in enumerate(routing_ratios)
    ]
    deployments = {
        routing.deployment_id: create_deployment(routing.deployment_id)
        for routing in routings
    }
    default_deployment = create_deployment(
        "dep_default"
    )
    default_deployment.role = "champion"
    routing_repo = AsyncMock()
    routing_repo.list_enabled_routings.return_value = routings
    deployment_repo = AsyncMock()
    deployment_repo.get_deployment.side_effect = deployments.get
    deployment_repo.list_active_deployments.return_value = [
        default_deployment
    ]
    monkeypatch.setitem(
        vars(router_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(router_module),
        "RoutingRepository",
        lambda _session: routing_repo,
    )
    monkeypatch.setitem(
        vars(router_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setattr(
        router,
        "_resolve_ab_test",
        AsyncMock(return_value=None),
    )

    plan = await router.resolve(
        model_id="mdl_test",
        subject_key=subject_key,
        subject_type="customer",
        payload=payload,
        environment="production",
        include_shadows=False,
    )

    return plan.primary


@pytest.mark.asyncio
async def test_routing_ratio_preserves_default_traffic(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未进入灰度比例时交给默认部署."""
    result = await resolve_routing(
        monkeypatch,
        ratio=0.5,
        routing_ratios=[0.1],
    )

    assert result.deployment_id == "dep_default"
    assert result.strategy == "fallback"


@pytest.mark.asyncio
async def test_routing_ratio_selects_candidate(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试进入灰度比例时命中候选部署."""
    result = await resolve_routing(
        monkeypatch,
        ratio=0.05,
        routing_ratios=[0.1],
    )

    assert result is not None
    assert result.deployment_id == "dep_0"
    assert result.weight == 0.1


@pytest.mark.asyncio
async def test_routing_context_uses_bucket_value(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由上下文使用分桶值字段且不再输出旧字段."""
    result = await resolve_routing(
        monkeypatch,
        ratio=0.05,
        routing_ratios=[0.1],
    )

    assert result is not None
    assert result.context["bucket_value"] == 0.05
    assert result.context["traffic_ratio"] == 0.1
    assert "ratio" not in result.context


@pytest.mark.asyncio
async def test_routing_rejects_total_ratio_above_one(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝启用路由总占比超过 1."""
    with pytest.raises(RuntimeRouteError, match="总和不能大于 1"):
        await resolve_routing(
            monkeypatch,
            ratio=0.2,
            routing_ratios=[0.6, 0.6],
        )


@pytest.mark.parametrize(
    (
        "payload",
        "expected",
    ),
    [
        (
            {"customer_id": 10001},
            "10001",
        ),
        (
            {
                "customer_id": {"value": 10001},
                "order_id": 20001,
            },
            "20001",
        ),
        (
            {"customer_id": [10001]},
            None,
        ),
    ],
)
@pytest.mark.asyncio
async def test_routing_uses_stable_payload_identifier(
        monkeypatch: pytest.MonkeyPatch,
        payload: dict[str, object],
        expected: str | None,
) -> None:
    """测试稳定路由键使用首个有效标量标识."""
    result = await resolve_routing(
        monkeypatch,
        ratio=0.05,
        routing_ratios=[0.1],
        subject_key=None,
        payload=payload,
    )

    assert result.subject_key == expected


def test_route_result_converts_to_dict() -> None:
    """测试路由结果完整转换为字典."""
    result = RouteResult(
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        framework="sklearn",
        environment="production",
        source="manual",
        strategy="manual",
        subject_key="customer_10001",
        context={"reason": "manual_deployment"},
    )

    assert result.to_dict() == {
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "deployment_id": "dep_test",
        "framework": "sklearn",
        "environment": "production",
        "source": "manual",
        "strategy": "manual",
        "experiment_id": None,
        "variant_id": None,
        "assignment_id": None,
        "routing_id": None,
        "subject_key": "customer_10001",
        "subject_type": None,
        "bucket": None,
        "group": None,
        "weight": None,
        "context": {"reason": "manual_deployment"},
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_id", "environment", "message"),
    [
        ("", "production", "模型 ID 不能为空"),
        ("mdl_test", "", "部署环境不能为空"),
    ],
)
async def test_resolve_rejects_missing_required_parameter(
        model_id: str,
        environment: str,
        message: str,
) -> None:
    """测试路由解析拒绝空模型或环境."""
    with pytest.raises(
            RuntimeRouteError,
            match=message,
    ):
        await RuntimeRouter().resolve(
            model_id=model_id,
            environment=environment,
        )


@pytest.mark.asyncio
async def test_resolve_uses_manual_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试显式部署通过校验后直接命中."""
    deployment = create_deployment("dep_manual")
    router, deployment_repo, _, engine_assign = configure_router(
        monkeypatch,
        deployment=deployment,
    )

    plan = await router.resolve(
        model_id="mdl_test",
        environment="production",
        deployment_id="dep_manual",
        subject_key="customer_10001",
        subject_type="customer",
    )
    result = plan.primary

    deployment_repo.get_deployment.assert_awaited_once_with(
        "dep_manual"
    )
    engine_assign.assert_not_awaited()
    assert result.deployment_id == "dep_manual"
    assert result.source == str(DecisionStrategy.MANUAL)
    assert result.strategy == "manual"
    assert result.context["reason"] == "manual_deployment"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deployment", "message"),
    [
        (None, "部署不存在"),
        (
            SimpleNamespace(**{
                **vars(create_deployment("dep_manual")),
                "model_id": "mdl_other",
            }),
            "部署所属模型与请求模型不一致",
        ),
        (
            SimpleNamespace(**{
                **vars(create_deployment("dep_manual")),
                "status": "inactive",
            }),
            "部署不可用",
        ),
        (
            create_shadow_deployment(
                "dep_manual"
            ),
            "影子部署不能作为主预测目标",
        ),
    ],
)
async def test_resolve_rejects_invalid_manual_deployment(
        monkeypatch: pytest.MonkeyPatch,
        deployment: SimpleNamespace | None,
        message: str,
) -> None:
    """测试显式部署拒绝不存在、模型不符或不可用状态."""
    router, _, _, _ = configure_router(
        monkeypatch,
        deployment=deployment,
    )

    with pytest.raises(
            RuntimeRouteError,
            match=message,
    ):
        await router.resolve(
            model_id="mdl_test",
            environment="production",
            deployment_id="dep_manual",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary",
    [
        "future",
        "expired",
    ],
)
async def test_resolve_rejects_ineffective_manual_deployment(
        monkeypatch: pytest.MonkeyPatch,
        boundary: str,
) -> None:
    """测试显式部署拒绝尚未生效或已经失效的部署."""
    now = datetime.now(timezone.utc)
    deployment = create_deployment("dep_manual")

    if boundary == "future":
        deployment.effective_from = now + timedelta(minutes=1)
    else:
        deployment.effective_to = now

    router, _, _, _ = configure_router(
        monkeypatch,
        deployment=deployment,
    )

    with pytest.raises(
            RuntimeRouteError,
            match="部署不可用",
    ):
        await router.resolve(
            model_id="mdl_test",
            environment="production",
            deployment_id="dep_manual",
            now=now,
        )


@pytest.mark.asyncio
async def test_resolve_uses_ab_test_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 A/B 实验命中可用部署."""
    deployment = create_deployment("dep_experiment")
    router, _, _, engine_assign = configure_router(
        monkeypatch,
        deployment=deployment,
        ab_result=create_ab_test_result(),
    )

    plan = await router.resolve(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
        subject_type="customer",
        payload={"age": 35},
    )
    result = plan.primary

    engine_assign.assert_awaited_once()
    assert result.deployment_id == "dep_experiment"
    assert result.source == str(DecisionStrategy.EXPERIMENT)
    assert result.experiment_id == "exp_test"
    assert result.variant_id == "var_test"
    assert result.context == {
        "traffic_ratio": 0.2,
        "point": 0.4,
        "assignment_source": "new_assignment",
    }


@pytest.mark.asyncio
async def test_resolve_wraps_ab_test_assignment_error(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 A/B 实验参数错误转换为路由错误."""
    router, _, _, engine_assign = configure_router(
        monkeypatch
    )
    engine_assign.side_effect = ValueError("实验配置非法")

    with pytest.raises(
            RuntimeRouteError,
            match="A/B 实验分配失败",
    ):
        await router.resolve(
            model_id="mdl_test",
            environment="production",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_reason",
    [
        "missing",
        "model",
        "status",
    ],
)
async def test_invalid_ab_test_deployment_falls_back(
        monkeypatch: pytest.MonkeyPatch,
        invalid_reason: str,
) -> None:
    """测试实验部署失效时回滚分配并回退默认部署."""
    experiment_deployment = create_deployment("dep_experiment")

    if invalid_reason == "model":
        experiment_deployment.model_id = "mdl_other"
    elif invalid_reason == "status":
        experiment_deployment.status = "inactive"

    default_deployment = create_deployment("dep_default")
    default_deployment.role = "champion"
    router, deployment_repo, _, _ = configure_router(
        monkeypatch,
        active_deployments=[default_deployment],
        ab_result=create_ab_test_result(),
    )
    deployment_repo.get_deployment.return_value = (
        None
        if invalid_reason == "missing"
        else experiment_deployment
    )

    plan = await router.resolve(
        model_id="mdl_test",
        environment="production",
        include_shadows=False,
    )
    result = plan.primary

    assert result.deployment_id == "dep_default"
    assert FakeUnitOfWork.latest is not None
    FakeUnitOfWork.latest.session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_uses_first_active_deployment_without_champion(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试没有主部署时使用首个可用部署."""
    deployment = create_deployment("dep_first")
    deployment.role = "challenger"
    router, _, _, _ = configure_router(
        monkeypatch,
        active_deployments=[deployment],
    )

    plan = await router.resolve(
        model_id="mdl_test",
        environment="production",
    )
    result = plan.primary

    assert result.deployment_id == "dep_first"
    assert result.context["reason"] == "first_active_deployment"


@pytest.mark.asyncio
async def test_resolve_rejects_missing_available_deployment(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试没有实验、路由和默认部署时抛出路由错误."""
    router, _, _, _ = configure_router(monkeypatch)

    with pytest.raises(
            RuntimeRouteError,
            match="没有可用部署",
    ):
        await router.resolve(
            model_id="mdl_test",
            environment="production",
        )


@pytest.mark.asyncio
async def test_resolve_skips_shadow_routing_for_primary_result(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试影子路由不参与主路由流量分配."""
    primary = create_deployment(
        "dep_primary"
    )
    shadow = create_shadow_deployment(
        "dep_shadow"
    )
    router, deployment_repo, routing_repo, _ = configure_router(
        monkeypatch,
    )
    shadow_routing = create_routing(
        "rtn_0",
        "dep_shadow",
        1.0,
    )
    shadow_routing.rollout_type = "full"
    shadow_routing.rollout_group = "champion"
    primary_routing = create_routing(
        "rtn_1",
        "dep_primary",
        1.0,
    )
    routing_repo.list_enabled_routings.return_value = [
        shadow_routing,
        primary_routing,
    ]
    deployments = {
        "dep_primary": primary,
        "dep_shadow": shadow,
    }
    deployment_repo.get_deployment.side_effect = (
        deployments.get
    )
    monkeypatch.setattr(
        router,
        "_hash_ratio",
        lambda *_parts: (0.5, "bucket_test"),
    )

    plan = await router.resolve(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
    )
    result = plan.primary

    assert result.deployment_id == "dep_primary"
    assert result.source == str(
        DecisionStrategy.ROUTING
    )


@pytest.mark.asyncio
async def test_resolve_includes_independently_matched_shadow(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试路由计划包含独立命中的影子部署."""
    router, deployment_repo, routing_repo, _ = configure_router(
        monkeypatch,
    )
    primary = RouteResult(
        model_id="mdl_test",
        version_id="ver_primary",
        deployment_id="dep_primary",
        framework="sklearn",
        environment="production",
        source="deployment",
        strategy="fallback",
    )
    shadow = create_shadow_deployment(
        "dep_shadow"
    )
    shadow.version_id = "ver_shadow"
    routing = create_routing(
        "rtn_shadow",
        "dep_shadow",
        1.0,
    )
    routing.rollout_type = "full"
    routing.rollout_group = "champion"
    routing_repo.list_enabled_routings.return_value = [
        routing
    ]
    deployment_repo.get_deployment.return_value = shadow
    resolve = AsyncMock(
        return_value=primary
    )
    monkeypatch.setattr(
        router,
        "_resolve_primary",
        resolve,
    )

    plan = await router.resolve(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
        subject_type="customer",
        payload={"age": 35},
    )

    assert isinstance(plan, RoutingPlan)
    assert plan.primary is primary
    assert len(plan.shadows) == 1
    shadow_result = plan.shadows[0]
    assert shadow_result.deployment_id == "dep_shadow"
    assert shadow_result.version_id == "ver_shadow"
    assert shadow_result.source == str(
        DecisionStrategy.SHADOW
    )
    assert shadow_result.routing_id == "rtn_shadow"
    assert 0 <= shadow_result.context["bucket_value"] < 1
    assert "ratio" not in shadow_result.context
    assert shadow_result.subject_key == "customer_10001"
    assert shadow_result.context["rollout_type"] == "shadow"
    assert shadow_result.context["rollout_group"] == "shadow"


@pytest.mark.asyncio
async def test_resolve_can_disable_shadow_resolution(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试配置关闭时不查询影子路由."""
    router, _, routing_repo, _ = configure_router(
        monkeypatch,
    )
    primary = RouteResult(
        model_id="mdl_test",
        version_id="ver_primary",
        deployment_id="dep_primary",
        framework="sklearn",
        environment="production",
        source="deployment",
        strategy="fallback",
    )
    monkeypatch.setattr(
        router,
        "_resolve_primary",
        AsyncMock(return_value=primary),
    )

    plan = await router.resolve(
        model_id="mdl_test",
        environment="production",
        include_shadows=False,
    )

    assert plan == RoutingPlan(
        primary=primary
    )
    routing_repo.list_enabled_routings.assert_not_awaited()
