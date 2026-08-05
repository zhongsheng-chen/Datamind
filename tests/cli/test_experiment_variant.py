# tests/cli/test_experiment_variant.py

"""实验分组命令测试

验证实验分组新增、更新和启用时的部署唯一性校验。

核心功能：
  - test_add_rejects_variant_deployment:
    验证新增分组拒绝复用已有分组的部署
  - test_update_rejects_other_variant_deployment:
    验证更新分组拒绝复用其他分组的部署
  - test_activate_rejects_other_active_variant:
    验证启用分组拒绝与其他启用分组共用部署
"""

import datamind.cli.experiment.variant.activate as activate_module
import datamind.cli.experiment.variant.add as add_module
import datamind.cli.experiment.variant.update as update_module
from datamind.db.models.variants import Variant


def create_variant(
        *,
        variant_id: str,
        deployment_id: str,
        status: str = "active",
) -> Variant:
    """创建实验分组测试对象"""
    return Variant(
        variant_id=variant_id,
        experiment_id="exp_test",
        name=variant_id,
        deployment_id=deployment_id,
        status=status,
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
