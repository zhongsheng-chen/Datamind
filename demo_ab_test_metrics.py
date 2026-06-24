# demo_ab_test_metrics.py

"""A/B 实验指标 Demo

运行方式：
  python demo_ab_test_metrics.py
"""

from dataclasses import dataclass

from datamind.ab_test.metrics import ABTestMetricEvaluator


@dataclass(slots=True)
class DemoOutcome:
    """Demo 实验结果"""

    experiment_id: str
    variant_id: str
    approved: bool | None = None
    converted: bool | None = None
    defaulted: bool | None = None
    overdue_days: int | None = None
    amount: float | None = None
    label: str | None = None


def main() -> None:
    """运行 A/B 实验指标 Demo"""
    outcomes = [
        DemoOutcome(
            experiment_id="exp_demo_abtest",
            variant_id="var_control",
            approved=True,
            converted=True,
            defaulted=False,
            overdue_days=0,
            amount=10000,
            label="good",
        ),
        DemoOutcome(
            experiment_id="exp_demo_abtest",
            variant_id="var_control",
            approved=True,
            converted=False,
            defaulted=False,
            overdue_days=5,
            amount=8000,
            label="good",
        ),
        DemoOutcome(
            experiment_id="exp_demo_abtest",
            variant_id="var_control",
            approved=False,
            converted=False,
            defaulted=True,
            overdue_days=45,
            amount=5000,
            label="bad",
        ),
        DemoOutcome(
            experiment_id="exp_demo_abtest",
            variant_id="var_treatment",
            approved=True,
            converted=True,
            defaulted=False,
            overdue_days=0,
            amount=12000,
            label="good",
        ),
        DemoOutcome(
            experiment_id="exp_demo_abtest",
            variant_id="var_treatment",
            approved=True,
            converted=True,
            defaulted=False,
            overdue_days=3,
            amount=15000,
            label="good",
        ),
        DemoOutcome(
            experiment_id="exp_demo_abtest",
            variant_id="var_treatment",
            approved=True,
            converted=False,
            defaulted=False,
            overdue_days=10,
            amount=9000,
            label="good",
        ),
    ]

    evaluator = ABTestMetricEvaluator()

    metrics = evaluator.calculate_experiment_metrics(
        experiment_id="exp_demo_abtest",
        outcomes=outcomes,
        baseline_variant_id="var_control",
    )

    print("===== 实验整体信息 =====")
    print(f"experiment_id: {metrics.experiment_id}")
    print(f"total_count: {metrics.total_count}")
    print(f"baseline_variant_id: {metrics.baseline_variant_id}")

    print()
    print("===== 分组指标 =====")

    for variant_id, variant_metrics in metrics.variants.items():
        print(f"[{variant_id}]")
        print(f"  total_count: {variant_metrics.total_count}")
        print(f"  approved_count: {variant_metrics.approved_count}")
        print(f"  converted_count: {variant_metrics.converted_count}")
        print(f"  defaulted_count: {variant_metrics.defaulted_count}")
        print(f"  bad_count: {variant_metrics.bad_count}")
        print(f"  approval_rate: {variant_metrics.approval_rate:.4f}")
        print(f"  conversion_rate: {variant_metrics.conversion_rate:.4f}")
        print(f"  default_rate: {variant_metrics.default_rate:.4f}")
        print(f"  bad_rate: {variant_metrics.bad_rate:.4f}")
        print(f"  average_amount: {variant_metrics.average_amount:.2f}")

    print()
    print("===== Lift 对比 =====")

    for variant_id, comparison_map in metrics.comparisons.items():
        print(f"[{variant_id} vs {metrics.baseline_variant_id}]")

        for metric_name, comparison in comparison_map.items():
            relative_lift = comparison.relative_lift

            if relative_lift is None:
                relative_lift_text = "N/A"
            else:
                relative_lift_text = f"{relative_lift:.4f}"

            print(
                f"  {metric_name}: "
                f"baseline={comparison.baseline_value:.4f}, "
                f"variant={comparison.variant_value:.4f}, "
                f"absolute_lift={comparison.absolute_lift:.4f}, "
                f"relative_lift={relative_lift_text}"
            )

    print()
    print("===== 字典结果 =====")
    print(metrics.to_dict())


if __name__ == "__main__":
    main()