"""实验分析器测试.

验证分析直接使用决策与主执行记录，以及实验和基准校验。

核心功能：
  - test_analyze_uses_original_decisions_and_executions:
    测试产生请求后即可分析，不需要额外结果提交
  - test_analyze_empty_experiment:
    测试无决策时返回空指标与提示
  - test_analyze_variant:
    测试单个分组按决策关联主执行
  - test_analyze_rejects_invalid_configuration:
    测试不存在的资源及非法配置被拒绝
  - test_missing_baseline_data_does_not_block_other_groups:
    测试基准无决策时其他分组仍可分析
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from datamind.ab_test.analyzer import ABTestAnalyzer
from tests.unit.ab_test.test_metrics import decision, execution


def analyzer():
    """创建分析器与仓储替身."""
    experiments, variants, decisions, executions = (AsyncMock() for _ in range(4))
    experiments.get_experiment.return_value = SimpleNamespace(
        experiment_id="exp", model_id="model", environment="development", name="demo",
        status="running", config={"strategy": "hash"},
    )
    group = SimpleNamespace(variant_id="control", experiment_id="exp", name="control", deployment_id="dep",
                            weight=1.0, is_control=True, status="active", description=None, config={})
    variants.list_variants.return_value = [group]
    variants.get_control_variant.return_value = group
    variants.get_variant.return_value = group
    decisions.list_experiment_decisions.return_value = [decision()]
    decisions.list_variant_decisions.return_value = [decision()]
    executions.list_experiment_executions.return_value = [execution()]
    return ABTestAnalyzer(experiment_repo=experiments, variant_repo=variants,
                          decision_repo=decisions, execution_repo=executions), experiments, variants, decisions, executions


@pytest.mark.asyncio
async def test_analyze_uses_original_decisions_and_executions():
    """测试产生请求后即可分析，不需要额外结果提交."""
    service, _, _, decisions, executions = analyzer()
    result = await service.analyze_experiment(experiment_id="exp")
    assert result.decision_count == 1
    assert result.metrics.variants["control"].success_rate == 1.0
    assert result.to_dict()["decision_count"] == 1
    decisions.list_experiment_decisions.assert_awaited_once_with("exp")
    executions.list_experiment_executions.assert_awaited_once_with("exp")


@pytest.mark.asyncio
async def test_analyze_empty_experiment():
    """测试无决策时返回空指标与提示."""
    service, _, _, decisions, _ = analyzer()
    decisions.list_experiment_decisions.return_value = []
    result = await service.analyze_experiment(experiment_id="exp")
    assert result.decision_count == 0 and result.metrics.variants == {}
    assert result.warnings


@pytest.mark.asyncio
async def test_analyze_variant():
    """测试单个分组按决策关联主执行."""
    service, *_ = analyzer()
    result = await service.analyze_variant(variant_id="control")
    assert result["decision_count"] == 1
    assert result["metrics"]["average_score"] == 600.0


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["missing_experiment", "no_variants", "invalid_baseline", "invalid_strategy"])
async def test_analyze_rejects_invalid_configuration(case):
    """测试不存在的资源及非法配置被拒绝."""
    service, experiments, variants, *_ = analyzer()
    kwargs = {"experiment_id": "exp"}
    if case == "missing_experiment": experiments.get_experiment.return_value = None
    elif case == "no_variants": variants.list_variants.return_value = []
    elif case == "invalid_baseline": kwargs["baseline_variant_id"] = "other"
    else: experiments.get_experiment.return_value.config = {"strategy": "invalid"}
    with pytest.raises(ValueError):
        await service.analyze_experiment(**kwargs)


@pytest.mark.asyncio
async def test_missing_baseline_data_does_not_block_other_groups():
    """测试基准无决策时其他分组仍可分析."""
    service, _, _, decisions, executions = analyzer()
    decisions.list_experiment_decisions.return_value = [decision("d2", "treatment")]
    executions.list_experiment_executions.return_value = [execution("d2")]
    result = await service.analyze_experiment(experiment_id="exp")
    assert result.baseline_variant_id == "control"
    assert result.metrics.variants["treatment"].total_count == 1
    assert result.metrics.comparisons == {} and result.warnings
