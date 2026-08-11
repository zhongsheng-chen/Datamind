# tests/cli/test_experiment_variant.py

"""实验分组命令测试

验证实验分组新增、更新和启用时的配置校验。

核心功能：
  - test_add_rejects_variant_deployment:
    验证新增分组拒绝复用已有分组的部署
  - test_add_rejects_active_weight_sum_above_one:
    验证新增分组拒绝启用权重总和超过 1
  - test_update_rejects_other_variant_deployment:
    验证更新分组拒绝复用其他分组的部署
  - test_activate_rejects_other_active_variant:
    验证启用分组拒绝与其他启用分组共用部署
"""

import pytest

import datamind.cli.experiment.variant.activate as activate_module
import datamind.cli.experiment.variant.add as add_module
import datamind.cli.experiment.variant.update as update_module
from datamind.db.models.experiments import Experiment
from datamind.db.models.variants import Variant
from datamind.models.errors import InvalidExperimentConfigError


def create_variant(
        *,
        variant_id: str,
        deployment_id: str,
        status: str = "active",
        weight: float = 0.5,
) -> Variant:
    """创建实验分组测试对象"""
    return Variant(
        variant_id=variant_id,
        experiment_id="exp_test",
        name=variant_id,
        deployment_id=deployment_id,
        status=status,
        weight=float(
            weight
        ),
    )


def test_add_rejects_variant_deployment() -> None:
    """验证新增分组拒绝复用已有分组的部署"""
    variants = [
        create_variant(
            variant_id="var_control",
            deployment_id="dep_shared",
        ),
        create_variant(
            variant_id="var_inactive",
            deployment_id="dep_inactive",
            status="inactive",
        ),
    ]

    assert add_module._find_variant_by_deployment(
        variants=variants,
        deployment_id="dep_shared",
    ) is variants[0]
    assert add_module._find_variant_by_deployment(
        variants=variants,
        deployment_id="dep_inactive",
    ) is variants[1]
    assert add_module._find_variant_by_deployment(
        variants=variants,
        deployment_id="dep_other",
    ) is None


def test_add_accepts_incomplete_active_weight_sum() -> None:
    """验证草稿阶段允许启用权重总和暂时小于 1"""
    add_module._validate_active_weight_sum(
        experiment=Experiment(
            config={
                "strategy": "hash"
            }
        ),
        variants=[
            create_variant(
                variant_id="var_control",
                deployment_id="dep_control",
                weight=0.4,
            )
        ],
        added_weight=0.5,
    )


def test_add_rejects_active_weight_sum_above_one() -> None:
    """验证新增分组拒绝启用权重总和超过 1"""
    with pytest.raises(
            InvalidExperimentConfigError,
            match="权重之和不能大于 1",
    ):
        add_module._validate_active_weight_sum(
            experiment=Experiment(
                config={
                    "strategy": "hash"
                }
            ),
            variants=[
                create_variant(
                    variant_id="var_control",
                    deployment_id="dep_control",
                    weight=0.6,
                )
            ],
            added_weight=0.5,
        )


def test_add_skips_weight_sum_for_manual_strategy() -> None:
    """验证手动分配策略不限制分组权重总和"""
    add_module._validate_active_weight_sum(
        experiment=Experiment(
            config={
                "strategy": "manual"
            }
        ),
        variants=[
            create_variant(
                variant_id="var_control",
                deployment_id="dep_control",
                weight=0.8,
            )
        ],
        added_weight=0.8,
    )


def test_update_rejects_other_variant_deployment() -> None:
    """验证更新分组拒绝复用其他分组的部署"""
    variants = [
        create_variant(
            variant_id="var_control",
            deployment_id="dep_shared",
        ),
        create_variant(
            variant_id="var_treatment",
            deployment_id="dep_treatment",
        ),
    ]

    assert update_module._find_other_variant_by_deployment(
        variants=variants,
        current_variant_id="var_treatment",
        deployment_id="dep_shared",
    ) is variants[0]
    assert update_module._find_other_variant_by_deployment(
        variants=variants,
        current_variant_id="var_control",
        deployment_id="dep_shared",
    ) is None


def test_activate_rejects_other_active_variant() -> None:
    """验证启用分组拒绝与其他启用分组共用部署"""
    variants = [
        create_variant(
            variant_id="var_control",
            deployment_id="dep_shared",
        ),
        create_variant(
            variant_id="var_treatment",
            deployment_id="dep_shared",
        ),
    ]

    assert activate_module._has_other_active_variant(
        variants=variants,
        current_variant_id="var_treatment",
    )
    assert not activate_module._has_other_active_variant(
        variants=[variants[0]],
        current_variant_id="var_control",
    )
