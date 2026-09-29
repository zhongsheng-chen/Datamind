"""实验统一创建流程测试.

验证实验、初始分组和客户映射在同一事务内保存及回滚。

核心功能：
  - test_create_experiment_with_groups:
    验证分组创建和临时标识转换
  - test_create_experiment_rejects_invalid_groups:
    验证分组配置校验
  - test_create_experiment_rejects_invalid_deployment:
    验证部署绑定约束
  - test_create_experiment_rolls_back_invalid_mapping:
    验证映射失败整体回滚
  - test_create_experiment_rolls_back_commit_failure:
    验证提交失败整体回滚
  - test_create_experiment_without_groups:
    验证原有创建接口兼容性
  - test_create_variant_uses_shared_validation:
    验证单独添加分组的共享校验
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.db.core.uow as uow_module
import datamind.services.experiment as module
from datamind.models.errors import (
    InvalidExperimentConfigError,
    InvalidExperimentStateError,
)
from datamind.services.experiment import ExperimentLifecycleService


@pytest.fixture
def creation_context(monkeypatch):
    """配置统一创建流程的仓储和数据库会话替身."""
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    monkeypatch.setitem(
        vars(uow_module),
        "get_session_factory",
        lambda: lambda: session,
    )

    metadata = MagicMock()
    metadata.get_model = AsyncMock(
        return_value=SimpleNamespace(model_id="mdl_test")
    )
    experiments = MagicMock()
    experiments.create_experiment.side_effect = lambda **values: SimpleNamespace(
        **values,
        status="draft",
    )
    experiments.get_experiment = AsyncMock(
        return_value=SimpleNamespace(
            experiment_id="exp_test",
            model_id="mdl_test",
            environment="development",
            status="draft",
            config={"strategy": "hash"},
        )
    )
    variants = MagicMock()
    variants.list_variants = AsyncMock(return_value=[])
    variants.create_variant.side_effect = lambda **values: SimpleNamespace(
        **values,
        status="active",
    )
    deployment = SimpleNamespace(
        model_id="mdl_test",
        environment="development",
        rollout_type="primary",
        role="champion",
        status="active",
    )
    deployments = MagicMock()
    deployments.get_deployment = AsyncMock(return_value=deployment)

    for name, repository in (
            ("MetadataRepository", metadata),
            ("ExperimentRepository", experiments),
            ("VariantRepository", variants),
            ("DeploymentRepository", deployments),
    ):
        monkeypatch.setitem(
            vars(module),
            name,
            lambda _session, repo=repository: repo,
        )

    return SimpleNamespace(
        session=session,
        experiments=experiments,
        variants=variants,
        deployment=deployment,
        deployments=deployments,
    )


def create_payload() -> dict[str, Any]:
    """构造包含两个初始分组的实验参数."""
    return {
        "model_id": "mdl_test",
        "environment": "development",
        "name": "unified-test",
        "bucket_key": "customer_id",
        "groups": [
            {
                "key": "control",
                "name": "control",
                "deployment_id": "dep_control",
                "weight": 0.5,
                "is_control": True,
            },
            {
                "key": "treatment",
                "name": "treatment",
                "deployment_id": "dep_treatment",
                "weight": 0.5,
                "is_control": False,
            },
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy", ["hash", "manual"])
async def test_create_experiment_with_groups(creation_context, strategy):
    """测试分组与实验一并创建并转换客户映射中的临时分组标识."""
    payload = create_payload()
    payload["strategy"] = strategy

    if strategy == "manual":
        payload["manual_assignments"] = {"customer_001": "treatment"}

    result = await ExperimentLifecycleService().create_experiment(**payload)

    assert result["status"] == "draft"
    assert len(result["variants"]) == 2
    assert all(item["status"] == "active" for item in result["variants"])

    if strategy == "manual":
        assert result["config"]["manual_assignments"] == {
            "customer_001": result["variants"][1]["variant_id"],
        }
    else:
        assert "manual_assignments" not in result["config"]

    creation_context.session.commit.assert_awaited_once()
    creation_context.session.rollback.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("key", "control"),
        ("name", "control"),
        ("name", "  "),
        ("deployment_id", "dep_control"),
        ("is_control", True),
        ("weight", 0),
        ("weight", 0.6),
    ],
)
async def test_create_experiment_rejects_invalid_groups(
        creation_context,
        field,
        value,
):
    """测试无效分组配置不能留下部分实验数据."""
    payload = create_payload()
    payload["groups"][1][field] = value

    with pytest.raises(InvalidExperimentConfigError):
        await ExperimentLifecycleService().create_experiment(**payload)

    assert creation_context.variants.create_variant.call_count <= 1
    creation_context.session.commit.assert_not_awaited()
    creation_context.session.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("model_id", "mdl_other"),
        ("environment", "production"),
        ("role", "shadow"),
        ("rollout_type", "shadow"),
        ("status", "inactive"),
    ],
)
async def test_create_experiment_rejects_invalid_deployment(
        creation_context,
        field,
        value,
):
    """测试初始分组不能绑定其他模型、环境、影子或停用部署."""
    setattr(creation_context.deployment, field, value)

    with pytest.raises(InvalidExperimentConfigError):
        await ExperimentLifecycleService().create_experiment(**create_payload())

    creation_context.session.commit.assert_not_awaited()
    creation_context.session.rollback.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "strategy,mapping",
    [
        ("manual", {"customer_001": "missing"}),
        ("manual", {"": "control"}),
        ("hash", {"customer_001": "control"}),
    ],
)
async def test_create_experiment_rolls_back_invalid_mapping(
        creation_context,
        strategy,
        mapping,
):
    """测试客户映射校验失败时回滚已创建的实验和分组."""
    payload = create_payload()
    payload["strategy"] = strategy
    payload["manual_assignments"] = mapping

    with pytest.raises(InvalidExperimentConfigError):
        await ExperimentLifecycleService().create_experiment(**payload)

    assert creation_context.variants.create_variant.call_count == 2
    creation_context.session.commit.assert_not_awaited()
    creation_context.session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_experiment_rolls_back_commit_failure(creation_context):
    """测试事务提交失败时回滚实验及其分组."""
    creation_context.session.commit.side_effect = RuntimeError("commit failed")

    with pytest.raises(RuntimeError, match="commit failed"):
        await ExperimentLifecycleService().create_experiment(**create_payload())

    creation_context.session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_experiment_without_groups(creation_context):
    """测试未传入初始分组时兼容原有创建流程."""
    payload = create_payload()
    payload.pop("groups")
    result = await ExperimentLifecycleService().create_experiment(**payload)

    assert result["status"] == "draft"
    assert "variants" not in result
    creation_context.variants.create_variant.assert_not_called()
    creation_context.session.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "duplicate_name",
        "duplicate_deployment",
        "duplicate_control",
        "overweight",
        "inactive_deployment",
        "running_experiment",
    ],
)
async def test_create_variant_uses_shared_validation(creation_context, scenario):
    """测试单独添加分组复用相同校验且仅提交一次事务."""
    existing = SimpleNamespace(
        variant_id="var_existing",
        name="existing",
        deployment_id="dep_existing",
        weight=0.5,
        is_control=True,
        status="active",
    )
    creation_context.variants.list_variants.return_value = [existing]
    payload = {
        "experiment_id": "exp_test",
        "name": "treatment",
        "deployment_id": "dep_treatment",
        "weight": 0.5,
        "config": {"custom": True},
        "description": "分组说明",
        "created_by": "admin",
    }

    if scenario == "duplicate_name":
        payload["name"] = existing.name
    elif scenario == "duplicate_deployment":
        payload["deployment_id"] = existing.deployment_id
    elif scenario == "duplicate_control":
        payload["is_control"] = True
    elif scenario == "overweight":
        payload["weight"] = 0.6
    elif scenario == "inactive_deployment":
        creation_context.deployment.status = "inactive"
    elif scenario == "running_experiment":
        creation_context.experiments.get_experiment.return_value.status = "running"

    if scenario == "success":
        result = await ExperimentLifecycleService().create_variant(**payload)

        assert result["config"] == {"custom": True}
        arguments = creation_context.variants.create_variant.call_args.kwargs
        assert arguments["description"] == "分组说明"
        assert arguments["created_by"] == "admin"
        creation_context.session.commit.assert_awaited_once()
        creation_context.session.rollback.assert_not_awaited()
    else:
        with pytest.raises((InvalidExperimentConfigError, InvalidExperimentStateError)):
            await ExperimentLifecycleService().create_variant(**payload)

        creation_context.variants.create_variant.assert_not_called()
        creation_context.session.commit.assert_not_awaited()
        creation_context.session.rollback.assert_awaited_once()
