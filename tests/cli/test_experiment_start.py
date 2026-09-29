"""实验启动命令测试.

验证实验启动前对启用分组及其部署的完整性校验。

核心功能：
  - test_validate_rejects_duplicate_deployments:
    验证不同分组不能绑定同一部署
  - test_validate_rejects_inactive_deployment:
    验证实验分组不能绑定未启用部署
  - test_validate_rejects_ineffective_deployment:
    验证实验分组部署必须处于生效时间窗口
  - test_validate_accepts_distinct_active_deployments:
    验证接受不同且可用的分组部署
"""

from datetime import (
    datetime,
    timezone,
)
from typing import Any
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.cli.experiment.start as start_module
from datamind.db.models.deployments import Deployment
from datamind.db.models.experiments import Experiment
from datamind.db.models.variants import Variant
from datamind.models.errors import InvalidExperimentConfigError


CURRENT_TIME = datetime(
    2026,
    8,
    10,
    3,
    0,
    tzinfo=timezone.utc,
)

EARLIER_TIME = datetime(
    2026,
    8,
    10,
    2,
    0,
    tzinfo=timezone.utc,
)

LATER_TIME = datetime(
    2026,
    8,
    10,
    4,
    0,
    tzinfo=timezone.utc,
)


def create_experiment() -> Experiment:
    """创建实验测试对象."""
    return Experiment(
        experiment_id="exp_test",
        model_id="mdl_test",
        environment="development",
    )


def create_variant(
        *,
        variant_id: str,
        deployment_id: str,
) -> Variant:
    """创建实验分组测试对象."""
    return Variant(
        variant_id=variant_id,
        experiment_id="exp_test",
        name=variant_id,
        deployment_id=deployment_id,
        status="active",
    )


def create_deployment(
        *,
        deployment_id: str = "dep_test",
        **overrides: Any,
) -> Deployment:
    """创建部署测试对象."""
    values: dict[str, Any] = {
        "deployment_id": deployment_id,
        "model_id": "mdl_test",
        "version_id": "ver_test",
        "framework": "sklearn",
        "environment": "development",
        "status": "active",
        "effective_from": EARLIER_TIME,
        "effective_to": LATER_TIME,
    }
    values.update(
        overrides
    )

    return Deployment(
        **values
    )


@pytest.mark.asyncio
async def test_validate_rejects_duplicate_deployments() -> None:
    """测试不同分组不能绑定同一部署."""
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock()
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

    with pytest.raises(
            InvalidExperimentConfigError,
            match="必须绑定不同部署",
    ):
        await start_module._validate_active_variant_deployments(
            deployment_repo=deployment_repo,
            experiment=create_experiment(),
            active_variants=variants,
            now=CURRENT_TIME,
        )

    deployment_repo.get_deployment.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_rejects_inactive_deployment() -> None:
    """测试实验分组不能绑定未启用部署."""
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=create_deployment(
            status="inactive"
        )
    )

    with pytest.raises(
            InvalidExperimentConfigError,
            match="部署未启用",
    ):
        await start_module._validate_active_variant_deployments(
            deployment_repo=deployment_repo,
            experiment=create_experiment(),
            active_variants=[
                create_variant(
                    variant_id="var_control",
                    deployment_id="dep_test",
                )
            ],
            now=CURRENT_TIME,
        )


@pytest.mark.asyncio
async def test_validate_rejects_shadow_deployment() -> None:
    """测试实验分组不能绑定影子部署."""
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=create_deployment(
            rollout_type="shadow",
            role="shadow",
        )
    )

    with pytest.raises(
            InvalidExperimentConfigError,
            match="实验分组不能使用影子部署",
    ):
        await start_module._validate_active_variant_deployments(
            deployment_repo=deployment_repo,
            experiment=create_experiment(),
            active_variants=[
                create_variant(
                    variant_id="var_shadow",
                    deployment_id="dep_test",
                )
            ],
            now=CURRENT_TIME,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {
            "effective_from": LATER_TIME,
            "effective_to": None,
        },
        {
            "effective_from": EARLIER_TIME,
            "effective_to": CURRENT_TIME,
        },
    ],
)
async def test_validate_rejects_ineffective_deployment(
        overrides: dict[str, Any],
) -> None:
    """测试实验分组部署必须处于生效时间窗口."""
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=create_deployment(
            **overrides
        )
    )

    with pytest.raises(
            InvalidExperimentConfigError,
            match="不在生效时间内",
    ):
        await start_module._validate_active_variant_deployments(
            deployment_repo=deployment_repo,
            experiment=create_experiment(),
            active_variants=[
                create_variant(
                    variant_id="var_control",
                    deployment_id="dep_test",
                )
            ],
            now=CURRENT_TIME,
        )


@pytest.mark.asyncio
async def test_validate_accepts_distinct_active_deployments() -> None:
    """测试接受不同且可用的分组部署."""
    deployments = {
        "dep_control": create_deployment(
            deployment_id="dep_control"
        ),
        "dep_treatment": create_deployment(
            deployment_id="dep_treatment"
        ),
    }
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        side_effect=deployments.get
    )

    await start_module._validate_active_variant_deployments(
        deployment_repo=deployment_repo,
        experiment=create_experiment(),
        active_variants=[
            create_variant(
                variant_id="var_control",
                deployment_id="dep_control",
            ),
            create_variant(
                variant_id="var_treatment",
                deployment_id="dep_treatment",
            ),
        ],
        now=CURRENT_TIME,
    )

    assert deployment_repo.get_deployment.await_count == 2
