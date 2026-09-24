"""A/B 实验分析测试.

验证实验与分组分析、基准组解析、指标聚合和告警生成。

核心功能：
  - test_analyze_experiment_aggregates_variants_and_metrics:
    验证实验、分组和指标被汇总为分析结果
  - test_analyze_experiment_rejects_missing_experiment:
    验证实验不存在时拒绝分析
  - test_analyze_variant:
    验证单个实验分组的指标分析
  - test_analyze_experiment_builds_data_quality_warnings:
    验证无效和未知分组结果生成数据质量告警
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from datamind.ab_test.analyzer import ABTestAnalyzer
from datamind.models.enums import AssignmentStrategy


def create_analyzer() -> tuple[ABTestAnalyzer, AsyncMock, AsyncMock, AsyncMock]:
    """创建实验分析器及仓储替身."""
    experiment_repo = AsyncMock()
    variant_repo = AsyncMock()
    outcome_repo = AsyncMock()

    return (
        ABTestAnalyzer(
            experiment_repo=experiment_repo,
            variant_repo=variant_repo,
            outcome_repo=outcome_repo,
        ),
        experiment_repo,
        variant_repo,
        outcome_repo,
    )


def create_experiment(
        **overrides: Any,
) -> SimpleNamespace:
    """创建实验测试对象."""
    values = {
        "experiment_id": "exp_test",
        "model_id": "mdl_test",
        "environment": "production",
        "name": "champion challenger",
        "status": "running",
        "config": {
            "strategy": str(AssignmentStrategy.HASH),
        },
    }
    values.update(overrides)

    return SimpleNamespace(**values)


def create_variant(
        variant_id: str,
        *,
        is_control: bool = False,
        weight: float = 1.0,
        status: str = "active",
        config: object | None = None,
) -> SimpleNamespace:
    """创建实验分组测试对象."""
    return SimpleNamespace(
        variant_id=variant_id,
        experiment_id="exp_test",
        name=variant_id,
        deployment_id=f"dep_{variant_id}",
        environment="production",
        weight=weight,
        is_control=is_control,
        status=status,
        description=None,
        config=(
            {}
            if config is None
            else config
        ),
    )


def create_outcome(
        variant_id: object,
        **overrides: Any,
) -> SimpleNamespace:
    """创建实验结果测试对象."""
    values = {
        "experiment_id": "exp_test",
        "variant_id": variant_id,
        "approved": True,
        "converted": False,
        "defaulted": False,
        "label": None,
        "overdue_days": 0,
        "amount": 100.0,
    }
    values.update(overrides)

    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_analyze_experiment_aggregates_variants_and_metrics() -> None:
    """测试汇总实验、分组和指标."""
    analyzer, experiment_repo, variant_repo, outcome_repo = create_analyzer()
    experiment_repo.get_experiment.return_value = create_experiment()
    control = create_variant(
        "var_control",
        is_control=True,
    )
    variant_repo.list_variants.return_value = [control]
    variant_repo.get_control_variant.return_value = control
    outcome_repo.list_experiment_outcomes.return_value = [
        create_outcome("var_control")
    ]

    result = await analyzer.analyze_experiment(experiment_id="exp_test")

    assert result.experiment_id == "exp_test"
    assert result.baseline_variant_id == "var_control"
    assert result.outcome_count == 1
    assert result.metrics.total_count == 1
    assert result.metrics.variants["var_control"].approval_rate == 1.0


@pytest.mark.asyncio
async def test_analyze_experiment_rejects_missing_experiment() -> None:
    """测试实验不存在时拒绝分析."""
    analyzer, experiment_repo, _, _ = create_analyzer()
    experiment_repo.get_experiment.return_value = None

    with pytest.raises(ValueError, match="实验不存在"):
        await analyzer.analyze_experiment(experiment_id="exp_missing")


@pytest.mark.asyncio
async def test_analyze_experiment_rejects_missing_id() -> None:
    """测试拒绝空实验 ID."""
    analyzer, _, _, _ = create_analyzer()

    with pytest.raises(ValueError, match="实验 ID 不能为空"):
        await analyzer.analyze_experiment(experiment_id="")


@pytest.mark.asyncio
async def test_analyze_experiment_rejects_missing_variants() -> None:
    """测试拒绝没有分组的实验."""
    analyzer, experiment_repo, variant_repo, _ = create_analyzer()
    experiment_repo.get_experiment.return_value = create_experiment()
    variant_repo.list_variants.return_value = []

    with pytest.raises(ValueError, match="实验没有分组"):
        await analyzer.analyze_experiment(experiment_id="exp_test")


@pytest.mark.asyncio
async def test_analyze_experiment_rejects_unknown_baseline() -> None:
    """测试拒绝不存在的基准分组."""
    analyzer, experiment_repo, variant_repo, _ = create_analyzer()
    experiment_repo.get_experiment.return_value = create_experiment()
    variant_repo.list_variants.return_value = [
        create_variant("var_control")
    ]

    with pytest.raises(ValueError, match="基准分组不存在"):
        await analyzer.analyze_experiment(
            experiment_id="exp_test",
            baseline_variant_id="var_missing",
        )


@pytest.mark.asyncio
async def test_analyze_experiment_uses_explicit_baseline() -> None:
    """测试优先使用显式指定的基准分组."""
    analyzer, experiment_repo, variant_repo, outcome_repo = create_analyzer()
    experiment_repo.get_experiment.return_value = create_experiment()
    variants = [
        create_variant("var_control", is_control=True, weight=0.5),
        create_variant("var_treatment", weight=0.5),
    ]
    variant_repo.list_variants.return_value = variants
    outcome_repo.list_experiment_outcomes.return_value = [
        create_outcome("var_control"),
        create_outcome("var_treatment"),
    ]

    result = await analyzer.analyze_experiment(
        experiment_id="exp_test",
        baseline_variant_id="var_treatment",
    )

    assert result.baseline_variant_id == "var_treatment"
    variant_repo.get_control_variant.assert_not_awaited()


@pytest.mark.asyncio
async def test_analyze_experiment_builds_data_quality_warnings() -> None:
    """测试为无效、未知和缺少结果的分组生成告警."""
    analyzer, experiment_repo, variant_repo, outcome_repo = create_analyzer()
    experiment_repo.get_experiment.return_value = create_experiment()
    control = create_variant(
        "var_control",
        is_control=True,
        weight=0.4,
    )
    treatment = create_variant(
        "var_treatment",
        weight=0.4,
    )
    variant_repo.list_variants.return_value = [
        control,
        treatment,
    ]
    variant_repo.get_control_variant.return_value = control
    outcome_repo.list_experiment_outcomes.return_value = [
        create_outcome("var_control"),
        create_outcome("var_unknown"),
        create_outcome(None),
    ]

    result = await analyzer.analyze_experiment(
        experiment_id="exp_test"
    )

    warning_text = "\n".join(result.warnings)
    assert "var_treatment 暂无结果记录" in warning_text
    assert "1 条结果记录缺少有效实验分组 ID" in warning_text
    assert "var_unknown" in warning_text
    assert "权重总和不等于 1" in warning_text


@pytest.mark.asyncio
async def test_analyze_experiment_warns_without_outcomes_or_baseline() -> None:
    """测试实验无结果且无基准分组时生成告警."""
    analyzer, experiment_repo, variant_repo, outcome_repo = create_analyzer()
    experiment_repo.get_experiment.return_value = create_experiment()
    variant_repo.list_variants.return_value = [
        create_variant("var_inactive", status="inactive")
    ]
    variant_repo.get_control_variant.return_value = None
    outcome_repo.list_experiment_outcomes.return_value = []

    result = await analyzer.analyze_experiment(
        experiment_id="exp_test"
    )

    assert "实验暂无结果记录" in result.warnings
    assert "未找到基准分组，未生成 lift 对比" in result.warnings
    assert "实验没有 active 分组" in result.warnings


@pytest.mark.asyncio
async def test_analyze_variant() -> None:
    """测试分析单个实验分组及其指标."""
    analyzer, _, variant_repo, outcome_repo = create_analyzer()
    variant = create_variant(
        "var_treatment",
        config={
            "environment": "testing",
        },
    )
    variant_repo.get_variant.return_value = variant
    outcome_repo.list_variant_outcomes.return_value = [
        create_outcome("var_treatment", converted=True)
    ]

    result = await analyzer.analyze_variant(
        variant_id="var_treatment"
    )

    assert result["variant"]["variant_id"] == "var_treatment"
    assert result["variant"]["environment"] == "testing"
    assert result["outcome_count"] == 1
    metrics = result["metrics"]
    assert isinstance(metrics, dict)
    assert metrics["conversion_rate"] == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("variant_id", "variant", "message"),
    [
        ("", None, "实验分组 ID 不能为空"),
        ("var_missing", None, "实验分组不存在"),
    ],
)
async def test_analyze_variant_rejects_invalid_target(
        variant_id: str,
        variant: object | None,
        message: str,
) -> None:
    """测试拒绝空或不存在的实验分组."""
    analyzer, _, variant_repo, _ = create_analyzer()
    variant_repo.get_variant.return_value = variant

    with pytest.raises(ValueError, match=message):
        await analyzer.analyze_variant(
            variant_id=variant_id
        )


@pytest.mark.asyncio
async def test_analyze_experiment_rejects_invalid_strategy() -> None:
    """测试拒绝不支持的实验分配策略."""
    analyzer, experiment_repo, _, _ = create_analyzer()
    experiment_repo.get_experiment.return_value = create_experiment(
        config={
            "strategy": "random",
        }
    )

    with pytest.raises(ValueError, match="不支持的实验分配策略"):
        await analyzer.analyze_experiment(
            experiment_id="exp_test"
        )
