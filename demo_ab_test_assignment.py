# demo_ab_test_assignment.py

"""A/B 实验分配 Demo

运行方式：
  python demo_ab_test_assignment.py
"""

from dataclasses import dataclass

from datamind.ab_test.assignment import StableHashAssigner


@dataclass(slots=True)
class DemoVariant:
    """Demo 实验分组"""

    variant_id: str
    name: str
    deployment_id: str
    weight: float


def main() -> None:
    """运行 A/B 实验分配 Demo"""
    assigner = StableHashAssigner()

    variants = [
        DemoVariant(
            variant_id="var_control",
            name="control",
            deployment_id="dep_control",
            weight=0.5,
        ),
        DemoVariant(
            variant_id="var_treatment",
            name="treatment",
            deployment_id="dep_treatment",
            weight=0.5,
        ),
    ]

    experiment_id = "exp_demo_abtest"
    subject_keys = [
        "customer_10001",
        "customer_10002",
        "customer_10003",
        "customer_10004",
        "customer_10005",
    ]

    print("===== A/B 实验分配结果 =====")

    for subject_key in subject_keys:
        result = assigner.assign(
            experiment_id=experiment_id,
            subject_key=subject_key,
            traffic_ratio=0.5,
            variants=variants,
        )

        if result is None:
            print(
                f"{subject_key}: 未进入实验"
            )
            continue

        print(
            f"{subject_key}: "
            f"variant_id={result.variant.variant_id}, "
            f"group={result.variant.name}, "
            f"deployment_id={result.variant.deployment_id}, "
            f"bucket={result.bucket}, "
            f"bucket_value={result.bucket_value:.6f}, "
            f"point={result.point:.6f}"
        )

    print()
    print("===== 稳定性验证 =====")

    subject_key = "customer_10003"

    first_result = assigner.assign(
        experiment_id=experiment_id,
        subject_key=subject_key,
        traffic_ratio=0.5,
        variants=variants,
    )

    second_result = assigner.assign(
        experiment_id=experiment_id,
        subject_key=subject_key,
        traffic_ratio=0.5,
        variants=variants,
    )

    if first_result is None or second_result is None:
        print(f"{subject_key}: 两次都未进入实验")
        return

    print(
        f"{subject_key}: "
        f"第一次={first_result.variant.variant_id}, "
        f"第二次={second_result.variant.variant_id}, "
        f"是否一致={first_result.variant.variant_id == second_result.variant.variant_id}"
    )


if __name__ == "__main__":
    main()