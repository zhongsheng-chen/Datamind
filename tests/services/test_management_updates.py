"""部署相关管理资源更新测试

验证路由、实验和实验分组更新时的参数传递与状态约束。

核心功能：
  - test_update_routing_passes_patch:
    验证路由更新传递变更字段
  - test_update_experiment_only_edits_draft:
    验证仅允许更新草稿实验
  - test_update_variant_checks_sibling_weight:
    验证实验分组更新校验同级权重
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.experiment as experiment_module
import datamind.services.routing as routing_module
from datamind.console.schemas import RoutingUpdateRequest, VariantUpdateRequest
from datamind.services import (
    ExperimentLifecycleService,
    RoutingLifecycleService,
)


class FakeUnitOfWork:
    """服务更新测试工作单元。"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rules_update",
    [
        {},
        {"rules": None},
        {"rules": {
            "match": "all",
            "conditions": [{"field": "features.age", "op": "gte", "value": 30}],
        }},
    ],
    ids=["rules-omitted", "rules-null", "rules-provided"],
)
async def test_update_routing_passes_patch(
        monkeypatch: pytest.MonkeyPatch,
        rules_update: dict,
) -> None:
    """测试路由编辑传递更新字段，并区分规则保留、清空和替换。"""
    original_rules = {
        "match": "all",
        "conditions": [{"field": "features.age", "op": "gte", "value": 18}],
    }
    routing = SimpleNamespace(
        routing_id="rtn_test",
        name="scorecard-route",
        deployment_id="dep_test",
        environment="testing",
        rollout_type="canary",
        rollout_group="challenger",
        traffic_ratio=0.2,
        enabled=False,
        rules=original_rules,
        description=None,
    )
    repository = MagicMock()
    repository.get_routing = AsyncMock(return_value=routing)
    deployment_repository = MagicMock()
    deployment_repository.get_deployment = AsyncMock(
        return_value=SimpleNamespace(
            deployment_id="dep_test",
            model_id="mdl_test",
            environment="testing",
            rollout_type="canary",
            role="challenger",
        )
    )
    monkeypatch.setitem(vars(routing_module), "UnitOfWork", FakeUnitOfWork)
    monkeypatch.setitem(
        vars(routing_module),
        "RoutingRepository",
        lambda _session: repository,
    )
    monkeypatch.setitem(
        vars(routing_module),
        "DeploymentRepository",
        lambda _session: deployment_repository,
    )

    payload = RoutingUpdateRequest.model_validate(rules_update)
    result = await RoutingLifecycleService().update_routing(
        routing_id="rtn_test",
        name="scorecard-route-v2",
        traffic_ratio=0.35,
        description="测试流量",
        updated_by="operator",
        **payload.model_dump(exclude_unset=True),
    )

    expected_rules = rules_update.get("rules", original_rules)
    if "rules" in rules_update:
        assert routing.rules_metadata is None
    assert routing.rules == expected_rules
    assert result["rules"] == expected_rules
    assert result.before is not None
    assert result.after is not None
    if "rules" in rules_update:
        assert result.before["rules"] == original_rules
        assert result.after["rules"] == expected_rules
    else:
        assert "rules" not in result.after

    current, patch = repository.update_routing.call_args.args
    assert current is routing
    assert patch.name == "scorecard-route-v2"
    assert patch.traffic_ratio == 0.35
    assert patch.description == "测试流量"
    assert repository.update_routing.call_args.kwargs == {
        "updated_by": "operator",
    }


@pytest.mark.asyncio
async def test_update_experiment_only_edits_draft(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试草稿实验可更新名称和分流策略。"""
    experiment = SimpleNamespace(
        experiment_id="exp_test",
        model_id="mdl_test",
        environment="testing",
        name="旧实验",
        status="draft",
        config={
            "strategy": "hash",
            "traffic_ratio": 1.0,
            "bucket_key": "subject_key",
        },
        effective_from=None,
        effective_to=None,
    )
    repository = MagicMock()
    repository.get_experiment = AsyncMock(return_value=experiment)
    monkeypatch.setitem(vars(experiment_module), "UnitOfWork", FakeUnitOfWork)
    monkeypatch.setitem(
        vars(experiment_module),
        "ExperimentRepository",
        lambda _session: repository,
    )

    await ExperimentLifecycleService().update_experiment(
        experiment_id="exp_test",
        name="新实验",
        strategy="manual",
        traffic_ratio=0.5,
        updated_by="operator",
    )

    current, patch = repository.update_experiment.call_args.args
    assert current is experiment
    assert patch.name == "新实验"
    assert patch.config == {
        "strategy": "manual",
        "traffic_ratio": 0.5,
        "bucket_key": "subject_key",
    }
    assert repository.update_experiment.call_args.kwargs == {
        "updated_by": "operator",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_update",
    [{}, {"config": None}, {"config": {"group": "treatment"}}],
    ids=["config-omitted", "config-null", "config-provided"],
)
async def test_update_variant_checks_sibling_weight(
        monkeypatch: pytest.MonkeyPatch,
        config_update: dict,
) -> None:
    """测试分组编辑保持实验内活动权重约束。"""
    experiment = SimpleNamespace(
        experiment_id="exp_test",
        status="draft",
    )
    variant = SimpleNamespace(
        variant_id="var_test",
        experiment_id="exp_test",
        name="对照组",
        deployment_id="dep_test",
        weight=0.4,
        is_control=True,
        status="active",
        config={"group": "control"},
    )
    sibling = SimpleNamespace(
        variant_id="var_other",
        experiment_id="exp_test",
        name="实验组",
        deployment_id="dep_other",
        weight=0.3,
        is_control=False,
        status="active",
        config={},
    )
    experiment_repository = MagicMock()
    experiment_repository.get_experiment = AsyncMock(
        return_value=experiment
    )
    variant_repository = MagicMock()
    variant_repository.get_variant = AsyncMock(return_value=variant)
    variant_repository.list_variants = AsyncMock(
        return_value=[variant, sibling]
    )
    monkeypatch.setitem(vars(experiment_module), "UnitOfWork", FakeUnitOfWork)
    monkeypatch.setitem(
        vars(experiment_module),
        "ExperimentRepository",
        lambda _session: experiment_repository,
    )
    monkeypatch.setitem(
        vars(experiment_module),
        "VariantRepository",
        lambda _session: variant_repository,
    )

    payload = VariantUpdateRequest.model_validate(config_update)
    result = await ExperimentLifecycleService().update_variant(
        variant_id="var_test",
        weight=0.6,
        description="调整权重",
        updated_by="operator",
        **payload.model_dump(exclude_unset=True),
    )

    expected_config = config_update.get("config", {"group": "control"})
    assert variant.config == expected_config
    assert result["config"] == expected_config
    assert result.before is not None
    assert result.after is not None
    if "config" in config_update:
        assert result.before["config"] == {"group": "control"}
        assert result.after["config"] == expected_config
    else:
        assert "config" not in result.after

    current, patch = variant_repository.update_variant.call_args.args
    assert current is variant
    assert patch.weight == 0.6
    assert patch.description == "调整权重"
    assert variant_repository.update_variant.call_args.kwargs == {
        "updated_by": "operator",
    }
