"""A/B 实验分配测试.

验证稳定 Hash 分配、手工指定分配和策略分发。

核心功能：
  - test_stable_hash_assignment_is_deterministic:
    验证相同主体稳定命中相同分组
  - test_stable_hash_assignment_result_is_valid:
    验证分桶值、分组位置及上下文有效性
  - test_stable_hash_rejects_non_finite_values:
    验证拒绝非有限曝光比例和分组权重
  - test_stable_hash_rejects_negative_weight:
    验证拒绝负分组权重
  - test_manual_assignment:
    验证按分组 ID、名称和主体映射执行手工分配
  - test_experiment_assigner_dispatches_strategy:
    验证统一分配器按策略选择具体实现
"""

from types import SimpleNamespace

import pytest

from datamind.ab_test.assignment import (
    ExperimentAssigner,
    ManualAssigner,
    StableHashAssigner,
)
from datamind.models.enums import AssignmentStrategy


def create_variants(*weights: float) -> list[SimpleNamespace]:
    """创建实验分组测试对象."""
    return [
        SimpleNamespace(
            variant_id=f"var_{index}",
            name=f"variant_{index}",
            weight=weight,
        )
        for index, weight in enumerate(weights)
    ]


def test_stable_hash_assignment_is_deterministic() -> None:
    """测试相同主体稳定命中相同分组."""
    assigner = StableHashAssigner()
    variants = create_variants(0.5, 0.5)

    first = assigner.assign(
        experiment_id="exp_test",
        subject_key="customer_10001",
        traffic_ratio=1.0,
        variants=variants,
    )
    second = assigner.assign(
        experiment_id="exp_test",
        subject_key="customer_10001",
        traffic_ratio=1.0,
        variants=variants,
    )

    assert first is not None
    assert second is not None
    assert first.variant.variant_id == second.variant.variant_id
    assert first.bucket == second.bucket
    assert first.bucket_value == second.bucket_value
    assert first.point == second.point


def test_stable_hash_assignment_result_is_valid() -> None:
    """测试哈希分配结果包含有效的分桶值和分组位置."""
    result = StableHashAssigner().assign(
        experiment_id="exp_test",
        subject_key="customer_10001",
        traffic_ratio=1.0,
        variants=create_variants(0.5, 0.5),
    )

    assert result is not None
    assert result.bucket_value is not None
    assert result.point is not None
    assert 0.0 <= result.bucket_value < 1.0
    assert 0.0 <= result.point < 1.0
    assert result.context["bucket_value"] == result.bucket_value
    assert result.context["point"] == result.point


@pytest.mark.parametrize(
    ("experiment_id", "subject_key", "message"),
    [
        ("", "customer_10001", "实验 ID 不能为空"),
        ("exp_test", "", "分桶主体不能为空"),
    ],
)
def test_stable_hash_rejects_missing_identifiers(
        experiment_id: str,
        subject_key: str,
        message: str,
) -> None:
    """测试拒绝缺少实验 ID 或分桶主体."""
    with pytest.raises(ValueError, match=message):
        StableHashAssigner().assign(
            experiment_id=experiment_id,
            subject_key=subject_key,
            traffic_ratio=1.0,
            variants=create_variants(1.0),
        )


@pytest.mark.parametrize(
    ("traffic_ratio", "message"),
    [
        (0.0, "实验曝光比例必须大于 0"),
        (-0.1, "实验曝光比例必须大于 0"),
        (1.1, "实验曝光比例不能大于 1"),
    ],
)
def test_stable_hash_rejects_invalid_traffic_ratio(
        traffic_ratio: float,
        message: str,
) -> None:
    """测试拒绝越界的实验曝光比例."""
    with pytest.raises(ValueError, match=message):
        StableHashAssigner().assign(
            experiment_id="exp_test",
            subject_key="customer_10001",
            traffic_ratio=traffic_ratio,
            variants=create_variants(1.0),
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_stable_hash_rejects_non_finite_values(value: float) -> None:
    """测试拒绝非有限曝光比例和分组权重."""
    assigner = StableHashAssigner()

    with pytest.raises(ValueError, match="曝光比例必须是有限数值"):
        assigner.assign(
            experiment_id="exp_test",
            subject_key="customer_10001",
            traffic_ratio=value,
            variants=create_variants(1.0),
        )

    with pytest.raises(ValueError, match="权重必须是有限数值"):
        assigner.assign(
            experiment_id="exp_test",
            subject_key="customer_10001",
            traffic_ratio=1.0,
            variants=create_variants(value, 1.0),
        )


def test_stable_hash_rejects_negative_weight() -> None:
    """测试拒绝负分组权重."""
    with pytest.raises(ValueError, match="权重不能小于 0"):
        StableHashAssigner().assign(
            experiment_id="exp_test",
            subject_key="customer_10001",
            traffic_ratio=1.0,
            variants=create_variants(-0.1, 1.1),
        )


@pytest.mark.parametrize(
    ("weights", "message"),
    [
        ((0.0, 0.0), "实验没有可用 Variant"),
        ((0.4, 0.5), "实验 Variant 权重总和必须等于 1"),
    ],
)
def test_stable_hash_rejects_invalid_active_weights(
        weights: tuple[float, ...],
        message: str,
) -> None:
    """测试拒绝无可用分组或权重总和非法."""
    with pytest.raises(ValueError, match=message):
        StableHashAssigner().assign(
            experiment_id="exp_test",
            subject_key="customer_10001",
            traffic_ratio=1.0,
            variants=create_variants(*weights),
        )


def test_stable_hash_returns_none_outside_exposure() -> None:
    """测试主体未进入实验曝光比例时返回 None."""
    subject_key = next(
        f"customer_{index}"
        for index in range(1000)
        if StableHashAssigner.exposure_value(
            experiment_id="exp_test",
            subject_key=f"customer_{index}",
        ) >= 0.5
    )

    result = StableHashAssigner().assign(
        experiment_id="exp_test",
        subject_key=subject_key,
        traffic_ratio=0.5,
        variants=create_variants(1.0),
    )

    assert result is None


@pytest.mark.parametrize(
    ("target_field", "target"),
    [
        ("manual_variant_id", "var_1"),
        ("manual_variant_name", "variant_1"),
    ],
)
def test_manual_assignment(
        target_field: str,
        target: str,
) -> None:
    """测试按分组 ID 或名称执行手工分配."""
    assigner = ManualAssigner()
    result = assigner.assign(
        experiment_id="exp_test",
        subject_key="customer_10001",
        variants=create_variants(0.5, 0.5),
        manual_variant_id=(
            target
            if target_field == "manual_variant_id"
            else None
        ),
        manual_variant_name=(
            target
            if target_field == "manual_variant_name"
            else None
        ),
    )

    assert result is not None
    assert result.variant.variant_id == "var_1"
    assert result.context["manual_target"] == target
    assert "traffic_ratio" not in result.context
    assert result.bucket is None
    assert result.bucket_value is None
    assert result.point is None
    assert not {"bucket", "bucket_value", "point"} & result.context.keys()
    assert result.context["strategy"] == str(AssignmentStrategy.MANUAL)


@pytest.mark.parametrize(
    "mapping_value",
    [
        "var_1",
        {"variant_id": "var_1"},
        {"variant_name": "variant_1"},
        {"name": "variant_1"},
    ],
)
def test_manual_assignment_uses_subject_mapping(
        mapping_value: object,
) -> None:
    """测试从主体映射中解析手工指定分组."""
    result = ManualAssigner().assign(
        experiment_id="exp_test",
        subject_key="customer_10001",
        variants=create_variants(0.5, 0.5),
        manual_assignments={
            "customer_10001": mapping_value,
        },
    )

    assert result is not None
    assert result.variant.variant_id == "var_1"


def test_manual_assignment_returns_none_without_target() -> None:
    """测试未提供有效手工目标时返回 None."""
    result = ManualAssigner().assign(
        experiment_id="exp_test",
        subject_key="customer_10001",
        variants=create_variants(1.0),
        manual_assignments={
            "customer_10001": 100,
        },
    )

    assert result is None


@pytest.mark.parametrize(
    ("experiment_id", "subject_key", "weights", "message"),
    [
        ("", "customer_10001", (1.0,), "实验 ID 不能为空"),
        ("exp_test", "", (1.0,), "分桶主体不能为空"),
        ("exp_test", "customer_10001", (0.0,), "实验没有可用 Variant"),
    ],
)
def test_manual_assignment_rejects_invalid_request(
        experiment_id: str,
        subject_key: str,
        weights: tuple[float, ...],
        message: str,
) -> None:
    """测试手工分配拒绝缺少标识或无可用分组."""
    with pytest.raises(ValueError, match=message):
        ManualAssigner().assign(
            experiment_id=experiment_id,
            subject_key=subject_key,
            variants=create_variants(*weights),
            manual_variant_id="var_0",
        )


@pytest.mark.parametrize(
    "manual_assignments",
    [
        {
            "customer_other": "var_0",
        },
        {
            "customer_10001": {},
        },
    ],
)
def test_manual_assignment_returns_none_for_invalid_mapping(
        manual_assignments: dict[str, object],
) -> None:
    """测试主体映射缺失或不含目标字段时返回 None."""
    result = ManualAssigner().assign(
        experiment_id="exp_test",
        subject_key="customer_10001",
        variants=create_variants(1.0),
        manual_assignments=manual_assignments,
    )

    assert result is None


def test_manual_assignment_rejects_unavailable_target() -> None:
    """测试拒绝不存在或权重为零的手工目标."""
    with pytest.raises(
            ValueError,
            match="手工指定 Variant 不存在或不可用",
    ):
        ManualAssigner().assign(
            experiment_id="exp_test",
            subject_key="customer_10001",
            variants=create_variants(1.0, 0.0),
            manual_variant_id="var_1",
        )


@pytest.mark.parametrize(
    "strategy",
    [
        AssignmentStrategy.HASH,
        AssignmentStrategy.MANUAL,
    ],
)
def test_experiment_assigner_dispatches_strategy(
        strategy: AssignmentStrategy,
) -> None:
    """测试统一分配器按策略执行分配."""
    result = ExperimentAssigner().assign(
        strategy=strategy,
        experiment_id="exp_test",
        subject_key="customer_10001",
        variants=create_variants(1.0),
        manual_variant_id="var_0",
    )

    assert result is not None
    assert result.context["strategy"] == str(strategy)


def test_experiment_assigner_rejects_unknown_strategy() -> None:
    """测试统一分配器拒绝未知策略."""
    with pytest.raises(ValueError, match="不支持的实验分配策略"):
        ExperimentAssigner().assign(
            strategy="random",
            experiment_id="exp_test",
            subject_key="customer_10001",
            variants=create_variants(1.0),
        )
