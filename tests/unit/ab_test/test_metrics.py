"""A/B 实验指标评估测试.

验证分组指标、坏样本识别、金额聚合和基准组 lift 对比。

核心功能：
  - test_metrics_ignore_non_finite_amounts:
    验证 NaN 和无穷金额不会污染汇总指标
  - test_metrics_calculate_counts_and_rates:
    验证审批、转化、违约和金额指标
  - test_metrics_compare_variants:
    验证相对基准组的绝对和相对提升
"""

from types import SimpleNamespace
from typing import Any

import pytest

from datamind.ab_test.metrics import ABTestMetricEvaluator


def create_outcome(
        *,
        experiment_id: str = "exp_test",
        variant_id: object = "var_control",
        approved: object = False,
        converted: object = False,
        defaulted: object = False,
        label: object = None,
        overdue_days: object = None,
        amount: object = None,
        **overrides: Any,
) -> SimpleNamespace:
    """创建实验结果测试对象."""
    values = {
        "experiment_id": experiment_id,
        "variant_id": variant_id,
        "approved": approved,
        "converted": converted,
        "defaulted": defaulted,
        "label": label,
        "overdue_days": overdue_days,
        "amount": amount,
    }
    values.update(overrides)

    return SimpleNamespace(**values)


def test_metrics_ignore_non_finite_amounts() -> None:
    """测试非有限金额不会污染汇总指标."""
    outcomes = [
        SimpleNamespace(
            experiment_id="exp_test",
            variant_id="var_control",
            approved=False,
            converted=False,
            defaulted=False,
            label=None,
            overdue_days=None,
            amount=amount,
        )
        for amount in [100.0, float("nan"), float("inf"), -float("inf")]
    ]

    result = ABTestMetricEvaluator().calculate_experiment_metrics(
        experiment_id="exp_test",
        outcomes=outcomes,
    )
    metrics = result.variants["var_control"]

    assert metrics.amount_count == 1
    assert metrics.total_amount == 100.0
    assert metrics.average_amount == 100.0


def test_metrics_calculate_counts_and_rates() -> None:
    """测试计算分组数量、比例和金额指标."""
    outcomes = [
        create_outcome(
            approved=True,
            converted=True,
            amount=100.0,
        ),
        create_outcome(
            defaulted=True,
            amount="300",
        ),
    ]

    metrics = ABTestMetricEvaluator().calculate_variant_metrics(
        outcomes=outcomes
    )["var_control"]

    assert metrics.total_count == 2
    assert metrics.approved_count == 1
    assert metrics.converted_count == 1
    assert metrics.defaulted_count == 1
    assert metrics.bad_count == 1
    assert metrics.amount_count == 2
    assert metrics.total_amount == 400.0
    assert metrics.average_amount == 200.0
    assert metrics.approval_rate == 0.5
    assert metrics.conversion_rate == 0.5
    assert metrics.default_rate == 0.5
    assert metrics.bad_rate == 0.5


@pytest.mark.parametrize(
    "outcome",
    [
        create_outcome(defaulted=True),
        create_outcome(label="BAD"),
        create_outcome(overdue_days=31),
        create_outcome(overdue_days="31"),
    ],
)
def test_metrics_identify_bad_outcomes(
        outcome: SimpleNamespace,
) -> None:
    """测试通过违约、标签和逾期天数识别坏样本."""
    metrics = ABTestMetricEvaluator().calculate_variant_metrics(
        outcomes=[outcome]
    )["var_control"]

    assert metrics.bad_count == 1
    assert metrics.bad_rate == 1.0


def test_metrics_ignore_invalid_variant_ids() -> None:
    """测试忽略缺少有效分组 ID 的结果记录."""
    metrics = ABTestMetricEvaluator().calculate_variant_metrics(
        outcomes=[
            create_outcome(variant_id=None),
            create_outcome(variant_id=""),
            create_outcome(variant_id=100),
            create_outcome(variant_id="var_control"),
        ]
    )

    assert set(metrics) == {
        "var_control"
    }
    assert metrics["var_control"].total_count == 1


def test_metrics_compare_variants() -> None:
    """测试计算实验分组相对基准组的提升."""
    outcomes = [
        create_outcome(
            variant_id="var_control",
            approved=True,
            amount=100.0,
        ),
        create_outcome(
            variant_id="var_control",
            approved=False,
            amount=100.0,
        ),
        create_outcome(
            variant_id="var_treatment",
            approved=True,
            amount=150.0,
        ),
        create_outcome(
            variant_id="var_treatment",
            approved=True,
            amount=150.0,
        ),
        create_outcome(
            experiment_id="exp_other",
            variant_id="var_other",
            approved=True,
        ),
    ]

    result = ABTestMetricEvaluator().calculate_experiment_metrics(
        experiment_id="exp_test",
        outcomes=outcomes,
        baseline_variant_id="var_control",
    )
    comparison = result.comparisons[
        "var_treatment"
    ]["approval_rate"]

    assert result.total_count == 4
    assert set(result.variants) == {
        "var_control",
        "var_treatment",
    }
    assert comparison.baseline_value == 0.5
    assert comparison.variant_value == 1.0
    assert comparison.absolute_lift == 0.5
    assert comparison.relative_lift == 1.0

    serialized = result.to_dict()
    assert serialized["comparisons"]["var_treatment"][
        "approval_rate"
    ]["relative_lift"] == 1.0


def test_metrics_return_none_relative_lift_for_zero_baseline() -> None:
    """测试基准值为零时不计算相对提升."""
    result = ABTestMetricEvaluator().calculate_experiment_metrics(
        experiment_id="exp_test",
        outcomes=[
            create_outcome(
                variant_id="var_control",
                approved=False,
            ),
            create_outcome(
                variant_id="var_treatment",
                approved=True,
            ),
        ],
        baseline_variant_id="var_control",
    )

    comparison = result.comparisons[
        "var_treatment"
    ]["approval_rate"]
    assert comparison.absolute_lift == 1.0
    assert comparison.relative_lift is None


@pytest.mark.parametrize(
    ("experiment_id", "baseline_variant_id", "message"),
    [
        ("", None, "实验 ID 不能为空"),
        ("exp_test", "var_missing", "基准分组不存在"),
    ],
)
def test_metrics_reject_invalid_experiment_query(
        experiment_id: str,
        baseline_variant_id: str | None,
        message: str,
) -> None:
    """测试拒绝空实验 ID 或不存在的基准分组."""
    with pytest.raises(ValueError, match=message):
        ABTestMetricEvaluator().calculate_experiment_metrics(
            experiment_id=experiment_id,
            outcomes=[
                create_outcome()
            ],
            baseline_variant_id=baseline_variant_id,
        )


def test_metrics_support_custom_bad_sample_rules() -> None:
    """测试自定义坏样本标签和逾期阈值."""
    evaluator = ABTestMetricEvaluator(
        bad_label="reject",
        overdue_bad_threshold=10,
    )
    metrics = evaluator.calculate_variant_metrics(
        outcomes=[
            create_outcome(label="REJECT"),
            create_outcome(overdue_days=11),
            create_outcome(label="bad", overdue_days=10),
        ]
    )["var_control"]

    assert metrics.total_count == 3
    assert metrics.bad_count == 2
