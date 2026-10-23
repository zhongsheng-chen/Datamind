"""A/B 实验决策与执行指标测试.

验证流量计数、执行状态、缺失值处理与分组比较。

核心功能：
  - test_request_and_subject_counts_are_separate:
    测试重复主体分别计入请求数，但主体与分配去重
  - test_unsuccessful_executions_do_not_contribute_predictions:
    测试终态失败计入成功率分母，预测分布只使用成功执行
  - test_shadow_and_unrelated_executions_are_excluded:
    测试影子与不关联实验决策的执行不污染指标
  - test_invalid_numbers_are_excluded:
    测试无效数值不计入均值或样本数
  - test_no_executions_do_not_produce_comparisons:
    测试只有决策时仍可统计流量，无执行时不生成数值比较
  - test_comparisons_preserve_zero_baseline:
    测试零基准允许绝对差异，相对差异返回 None
  - test_filters_other_experiments_and_handles_missing_subject:
    测试其他实验不计入当前流量，缺失主体不构造伪主体
  - test_invalid_identifiers_are_rejected:
    测试非法实验或基准分组拒绝分析
"""

from types import SimpleNamespace

import pytest

from datamind.ab_test.metrics import ABTestMetricEvaluator


def decision(
        key: str = "d1",
        variant: str = "control",
        subject: str | None = "borrower",
) -> SimpleNamespace:
    """创建请求决策测试对象."""
    return SimpleNamespace(
        decision_id=key, experiment_id="exp", variant_id=variant,
        subject_key=subject, subject_type="borrower", assignment_id="a" + subject if subject else None,
        decision="approve",
    )


def execution(key="d1", **kwargs):
    """创建主执行测试对象."""
    values = dict(decision_id=key, execution_type="primary", status="success",
                  latency_ms=10.0, probability=0.3, score=600.0, prediction={"label": "low"})
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_request_and_subject_counts_are_separate():
    """测试重复主体分别计入请求数，但主体与分配去重."""
    result = ABTestMetricEvaluator().calculate_experiment_metrics(
        experiment_id="exp", decisions=[decision(), decision("d2"), decision("d3", "treatment", "other")],
        executions=[execution(), execution("d2", status="queued"), execution("d3")], baseline_variant_id="control",
    )
    control = result.variants["control"]
    assert result.total_count == 3
    assert control.total_count == 2 and control.subject_count == control.assignment_count == 1
    assert control.traffic_ratio == pytest.approx(2 / 3)
    assert control.queued_count == 1 and control.completed_count == 1
    assert control.success_rate == 1.0
    assert control.prediction_counts == {"low": 1}
    assert result.to_dict()["variants"]["control"]["average_score"] == 600.0


@pytest.mark.parametrize("status", ["failed", "timeout", "cancelled"])
def test_unsuccessful_executions_do_not_contribute_predictions(status):
    """测试终态失败计入成功率分母，预测分布只使用成功执行."""
    result = ABTestMetricEvaluator().calculate_variant_metrics(
        decisions=[decision(), decision("d2")], executions=[execution(), execution("d2", status=status)],
    )["control"]
    assert result.completed_count == 2 and result.success_rate == 0.5
    assert getattr(result, status + "_count") == 1
    assert result.score_count == result.probability_count == 1
    assert result.latency_count == 2


def test_shadow_and_unrelated_executions_are_excluded():
    """测试影子与不关联实验决策的执行不污染指标."""
    result = ABTestMetricEvaluator().calculate_variant_metrics(
        decisions=[decision()], executions=[execution(execution_type="shadow"), execution("other")],
    )["control"]
    assert result.execution_count == 0 and result.total_count == 1
    assert result.success_rate is None and result.average_score is None


@pytest.mark.parametrize("value", [None, True, float("nan"), float("inf")])
def test_invalid_numbers_are_excluded(value):
    """测试无效数值不计入均值或样本数."""
    result = ABTestMetricEvaluator().calculate_variant_metrics(
        decisions=[decision()], executions=[execution(score=value, probability=value, latency_ms=value)],
    )["control"]
    assert result.score_count == result.probability_count == result.latency_count == 0
    assert result.average_score is result.average_probability is result.average_latency_ms is None


def test_no_executions_do_not_produce_comparisons():
    """测试只有决策时仍可统计流量，无执行时不生成数值比较."""
    result = ABTestMetricEvaluator().calculate_experiment_metrics(
        experiment_id="exp", decisions=[decision(), decision("d2", "treatment")], executions=[],
        baseline_variant_id="control",
    )
    assert result.comparisons == {"treatment": {}}


def test_comparisons_preserve_zero_baseline():
    """测试零基准允许绝对差异，相对差异返回 None."""
    result = ABTestMetricEvaluator().calculate_experiment_metrics(
        experiment_id="exp", decisions=[decision(), decision("d2", "treatment")],
        executions=[execution(score=0), execution("d2", score=100)], baseline_variant_id="control",
    )
    value = result.comparisons["treatment"]["average_score"]
    assert value.absolute_lift == 100 and value.relative_lift is None


def test_filters_other_experiments_and_handles_missing_subject():
    """测试其他实验不计入当前流量，缺失主体不构造伪主体."""
    other = decision("other")
    other.experiment_id = "another"
    result = ABTestMetricEvaluator().calculate_experiment_metrics(
        experiment_id="exp", decisions=[decision(subject=None), other], executions=[],
    )
    assert result.total_count == 1
    assert result.variants["control"].subject_count == 0


@pytest.mark.parametrize("experiment_id,baseline", [("", None), ("exp", "missing")])
def test_invalid_identifiers_are_rejected(experiment_id, baseline):
    """测试非法实验或基准分组拒绝分析."""
    with pytest.raises(ValueError):
        ABTestMetricEvaluator().calculate_experiment_metrics(
            experiment_id=experiment_id, decisions=[decision()], executions=[], baseline_variant_id=baseline,
        )
