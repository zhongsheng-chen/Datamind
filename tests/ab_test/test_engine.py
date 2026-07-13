# tests/ab_test/test_engine.py

"""A/B 实验执行引擎测试

验证实验分流参数、配置解析、固定分配和并发写入处理。

核心功能：
  - test_engine_rejects_non_finite_traffic_ratio:
    验证拒绝非有限实验曝光比例
  - test_engine_uses_existing_assignment_after_concurrent_insert:
    验证并发写入冲突后返回数据库中的固定分组
  - test_engine_creates_new_assignment:
    验证命中新分组后创建并返回固定分配
  - test_resolve_subject_key:
    验证从直接参数或请求负载解析分桶主体
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.ab_test.engine import ABTestEngine
from datamind.constants import Environment
from datamind.db.models.assignments import Assignment
from datamind.db.models.experiments import Experiment
from datamind.db.models.variants import Variant
from datamind.models.enums import AssignmentStrategy, ExperimentVariantStatus


CURRENT_TIME = datetime(
    2026,
    7,
    30,
    8,
    0,
    tzinfo=timezone.utc,
)


def create_experiment(**config: object) -> Experiment:
    """创建实验测试对象"""
    return Experiment(
        experiment_id="exp_test",
        model_id="mdl_test",
        environment="production",
        status="running",
        config={
            "strategy": str(AssignmentStrategy.HASH),
            **config,
        },
    )


def create_variant(variant_id: str) -> Variant:
    """创建实验分组测试对象"""
    return Variant(
        variant_id=variant_id,
        experiment_id="exp_test",
        name=variant_id,
        deployment_id=f"dep_{variant_id}",
        weight=1.0,
        is_control=False,
        status=str(ExperimentVariantStatus.ACTIVE),
    )


def create_engine() -> tuple[ABTestEngine, AsyncMock, AsyncMock, MagicMock]:
    """创建实验引擎及仓储替身"""
    experiment_repo = AsyncMock()
    variant_repo = AsyncMock()
    assignment_repo = MagicMock()
    assignment_repo.get_subject_assignment = AsyncMock(return_value=None)
    assignment_repo.get_or_create_assignment = AsyncMock()
    assignment_repo.flush = AsyncMock()

    return (
        ABTestEngine(
            experiment_repo=experiment_repo,
            variant_repo=variant_repo,
            assignment_repo=assignment_repo,
        ),
        experiment_repo,
        variant_repo,
        assignment_repo,
    )


@pytest.mark.asyncio
async def test_engine_rejects_non_finite_traffic_ratio() -> None:
    """测试拒绝非有限实验曝光比例"""
    engine, experiment_repo, variant_repo, _ = create_engine()
    experiment_repo.list_running_experiments.return_value = [
        create_experiment(traffic_ratio=float("nan"))
    ]
    variant_repo.list_active_variants.return_value = [
        create_variant("var_new")
    ]

    with pytest.raises(ValueError, match="曝光比例必须是有限数值"):
        await engine.assign(
            model_id="mdl_test",
            environment="production",
            subject_key="customer_10001",
        )


@pytest.mark.asyncio
async def test_engine_uses_existing_assignment_after_concurrent_insert() -> None:
    """测试并发写入冲突后返回数据库中的固定分组"""
    engine, experiment_repo, variant_repo, assignment_repo = create_engine()
    experiment = create_experiment(traffic_ratio=1.0)
    proposed_variant = create_variant("var_new")
    existing_variant = create_variant("var_existing")
    existing_assignment = Assignment(
        assignment_id="asn_existing",
        experiment_id="exp_test",
        variant_id="var_existing",
        subject_key="customer_10001",
        strategy=str(AssignmentStrategy.HASH),
        bucket="bucket_0001",
        weight=1.0,
        context={},
    )

    experiment_repo.list_running_experiments.return_value = [experiment]
    variant_repo.list_active_variants.return_value = [proposed_variant]
    variant_repo.get_variant.return_value = existing_variant
    assignment_repo.get_or_create_assignment.return_value = (
        existing_assignment,
        False,
    )

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
    )

    assert result is not None
    assert result.assignment_id == "asn_existing"
    assert result.variant_id == "var_existing"
    assert result.deployment_id == "dep_var_existing"


@pytest.mark.asyncio
async def test_engine_returns_existing_assignment() -> None:
    """测试优先返回已经存在且有效的固定分配"""
    engine, experiment_repo, variant_repo, assignment_repo = create_engine()
    assignment = Assignment(
        assignment_id="asn_existing",
        experiment_id="exp_test",
        variant_id="var_existing",
        subject_key="customer_10001",
        strategy=str(AssignmentStrategy.HASH),
    )
    experiment_repo.list_running_experiments.return_value = [
        create_experiment()
    ]
    assignment_repo.get_subject_assignment.return_value = assignment
    variant_repo.get_variant.return_value = create_variant(
        "var_existing"
    )

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
    )

    assert result is not None
    assert result.assignment_id == "asn_existing"
    assignment_repo.get_or_create_assignment.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "model_id",
        "environment",
        "subject_key",
        "payload",
        "message",
    ),
    [
        (
            "",
            "production",
            "customer_10001",
            None,
            "模型 ID 不能为空",
        ),
        (
            "mdl_test",
            "",
            "customer_10001",
            None,
            "实验环境不能为空",
        ),
        (
            "mdl_test",
            "production",
            None,
            None,
            "分桶主体不能为空",
        ),
    ],
)
async def test_engine_rejects_missing_arguments(
        model_id: str,
        environment: str,
        subject_key: str | None,
        payload: dict | None,
        message: str,
) -> None:
    """测试拒绝缺少必要参数"""
    engine, _, _, _ = create_engine()

    with pytest.raises(ValueError, match=message):
        await engine.assign(
            model_id=model_id,
            environment=environment,
            subject_key=subject_key,
            payload=payload,
        )


@pytest.mark.asyncio
async def test_engine_rejects_invalid_environment() -> None:
    """测试拒绝不支持的实验环境"""
    engine, _, _, _ = create_engine()

    with pytest.raises(ValueError, match="invalid"):
        await engine.assign(
            model_id="mdl_test",
            environment="invalid",
            subject_key="customer_10001",
        )


@pytest.mark.asyncio
async def test_engine_queries_running_experiments_with_environment_enum() -> None:
    """测试使用环境枚举查询运行中的实验"""
    engine, experiment_repo, _, _ = create_engine()
    experiment_repo.list_running_experiments.return_value = []

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
        now=CURRENT_TIME,
    )

    assert result is None
    experiment_repo.list_running_experiments.assert_awaited_once_with(
        model_id="mdl_test",
        environment=Environment.PRODUCTION,
        now=CURRENT_TIME,
    )


@pytest.mark.asyncio
async def test_engine_rejects_multiple_running_experiments() -> None:
    """测试拒绝同一模型环境存在多个运行实验"""
    engine, experiment_repo, _, _ = create_engine()
    experiment_repo.list_running_experiments.return_value = [
        create_experiment(),
        create_experiment(),
    ]

    with pytest.raises(ValueError, match="存在多个运行中的实验"):
        await engine.assign(
            model_id="mdl_test",
            environment="production",
            subject_key="customer_10001",
        )


@pytest.mark.asyncio
async def test_engine_skips_ineffective_experiment() -> None:
    """测试跳过尚未生效的实验"""
    engine, experiment_repo, _, assignment_repo = create_engine()
    experiment = create_experiment()
    experiment.effective_from = CURRENT_TIME + timedelta(minutes=1)
    experiment_repo.list_running_experiments.return_value = [experiment]

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
        now=CURRENT_TIME,
    )

    assert result is None
    assignment_repo.get_subject_assignment.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_skips_expired_experiment() -> None:
    """测试跳过已经失效的实验"""
    engine, experiment_repo, _, assignment_repo = create_engine()
    experiment = create_experiment()
    experiment.effective_to = CURRENT_TIME
    experiment_repo.list_running_experiments.return_value = [experiment]

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
        now=CURRENT_TIME,
    )

    assert result is None
    assignment_repo.get_subject_assignment.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_skips_unresolved_payload_subject() -> None:
    """测试请求负载中不存在有效分桶主体时跳过实验"""
    engine, experiment_repo, _, assignment_repo = create_engine()
    experiment_repo.list_running_experiments.return_value = [
        create_experiment(bucket_key="customer_id")
    ]

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        payload={
            "customer_id": True,
        },
    )

    assert result is None
    assignment_repo.get_subject_assignment.assert_not_awaited()


@pytest.mark.asyncio
async def test_engine_returns_none_when_assigner_has_no_result() -> None:
    """测试分配器未命中实验曝光时返回 None"""
    engine, experiment_repo, variant_repo, _ = create_engine()
    experiment_repo.list_running_experiments.return_value = [
        create_experiment()
    ]
    variant_repo.list_active_variants.return_value = [
        create_variant("var_new")
    ]
    engine.assigner.assign = MagicMock(
        return_value=None
    )

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
    )

    assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({"traffic_ratio": 0.0}, "实验曝光比例必须大于 0"),
        ({"traffic_ratio": 1.1}, "实验曝光比例不能大于 1"),
        ({"strategy": "random"}, "不支持的实验分配策略"),
    ],
)
async def test_engine_rejects_invalid_experiment_config(
        config: dict[str, object],
        message: str,
) -> None:
    """测试拒绝非法曝光比例或分配策略"""
    engine, experiment_repo, _, _ = create_engine()
    experiment_repo.list_running_experiments.return_value = [
        create_experiment(**config)
    ]

    with pytest.raises(ValueError, match=message):
        await engine.assign(
            model_id="mdl_test",
            environment="production",
            subject_key="customer_10001",
        )


@pytest.mark.asyncio
async def test_engine_rejects_non_mapping_config() -> None:
    """测试拒绝非 JSON 对象的实验配置"""
    engine, experiment_repo, _, _ = create_engine()
    experiment = create_experiment()
    experiment.config = [
        "invalid"
    ]
    experiment_repo.list_running_experiments.return_value = [experiment]

    with pytest.raises(ValueError, match="config 必须是 JSON 对象"):
        await engine.assign(
            model_id="mdl_test",
            environment="production",
            subject_key="customer_10001",
        )


@pytest.mark.asyncio
async def test_engine_creates_new_assignment() -> None:
    """测试命中新分组后创建并返回固定分配"""
    engine, experiment_repo, variant_repo, assignment_repo = create_engine()
    experiment = create_experiment(traffic_ratio=1.0)
    variant = create_variant("var_new")
    assignment = Assignment(
        assignment_id="asn_new",
        experiment_id="exp_test",
        variant_id="var_new",
        subject_key="customer_10001",
        strategy=str(AssignmentStrategy.HASH),
        bucket="bucket_0001",
        weight=1.0,
        context={},
    )
    experiment_repo.list_running_experiments.return_value = [experiment]
    variant_repo.list_active_variants.return_value = [variant]
    assignment_repo.get_or_create_assignment.return_value = (
        assignment,
        True,
    )

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
        now=CURRENT_TIME,
        flush=True,
    )

    assert result is not None
    assert result.assignment_id == "asn_new"
    assert result.variant_id == "var_new"
    assert result.source == "experiment"
    assignment_repo.flush.assert_awaited_once_with()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resolved_variant",
    [
        None,
        create_variant("var_inactive"),
    ],
)
async def test_engine_ignores_unavailable_existing_assignment(
        resolved_variant: Variant | None,
) -> None:
    """测试已有分配对应分组不存在或未启用时不返回结果"""
    engine, experiment_repo, variant_repo, assignment_repo = create_engine()
    experiment_repo.list_running_experiments.return_value = [
        create_experiment()
    ]
    assignment_repo.get_subject_assignment.return_value = Assignment(
        assignment_id="asn_existing",
        experiment_id="exp_test",
        variant_id="var_inactive",
        subject_key="customer_10001",
        strategy=str(AssignmentStrategy.HASH),
    )

    if resolved_variant is not None:
        resolved_variant.status = str(ExperimentVariantStatus.INACTIVE)

    variant_repo.get_variant.return_value = resolved_variant

    result = await engine.assign(
        model_id="mdl_test",
        environment="production",
        subject_key="customer_10001",
    )

    assert result is None


@pytest.mark.parametrize(
    ("subject_key", "payload", "bucket_key", "expected"),
    [
        ("direct", {"customer_id": "payload"}, "customer_id", "direct"),
        (None, {"customer_id": "payload"}, "customer_id", "payload"),
        (None, {"customer_id": 10001}, "customer_id", "10001"),
        (None, {"customer_id": True}, "customer_id", None),
        (None, {"customer_id": 10.5}, "customer_id", None),
        (None, {"customer_id": ""}, "customer_id", None),
        (None, {}, "customer_id", None),
        (None, {"customer_id": "payload"}, None, None),
    ],
)
def test_resolve_subject_key(
        subject_key: str | None,
        payload: dict | None,
        bucket_key: str | None,
        expected: str | None,
) -> None:
    """测试解析直接传入或请求负载中的分桶主体"""
    assert ABTestEngine._resolve_subject_key(
        subject_key=subject_key,
        payload=payload,
        bucket_key=bucket_key,
    ) == expected


@pytest.mark.parametrize(
    ("config", "payload", "expected_id", "expected_name"),
    [
        (
            {
                "manual_variant_id": "var_config",
                "manual_variant_name": "config",
            },
            {
                "manual_variant_id": "var_payload",
                "manual_variant_name": "payload",
            },
            "var_config",
            "config",
        ),
        (
            {},
            {
                "manual_variant_id": "var_payload",
                "manual_variant_name": "payload",
            },
            "var_payload",
            "payload",
        ),
        (
            {
                "manual_variant_id": 100,
                "manual_variant_name": False,
            },
            None,
            None,
            None,
        ),
    ],
)
def test_get_manual_variant_target(
        config: dict,
        payload: dict | None,
        expected_id: str | None,
        expected_name: str | None,
) -> None:
    """测试按配置和请求负载优先级读取手工分组目标"""
    assert ABTestEngine._get_manual_variant_id(
        config=config,
        payload=payload,
        manual_variant_id=None,
    ) == expected_id
    assert ABTestEngine._get_manual_variant_name(
        config=config,
        payload=payload,
        manual_variant_name=None,
    ) == expected_name
