"""路由生命周期与流量约束测试

验证部署路由唯一性、流量分配和启用状态约束。

核心功能：
  - test_duplicate_deployment_routing_is_rejected:
    验证拒绝重复的部署路由
  - test_primary_routing_allocation_over_100_percent_is_rejected:
    验证主路由流量不得超过百分之百
  - test_full_deployment_requires_100_percent_traffic:
    验证全量部署必须分配百分之百流量
  - test_shadow_routing_does_not_use_primary_traffic_budget:
    验证影子路由不占用主路由流量
  - test_inactive_deployment_routing_cannot_be_enabled:
    验证未启用部署的路由不能启用
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from datamind.db.models.deployments import Deployment
from datamind.db.models.routing import Routing
from datamind.services.routing import (
    ensure_deployment_has_no_routing,
    validate_deployment_traffic_ratio,
    validate_routing_allocation,
)


def create_deployment(
        deployment_id: str,
        *,
        model_id: str = "mdl_test",
        rollout_type: str = "canary",
        role: str = "challenger",
) -> Deployment:
    """创建部署测试对象。"""
    return Deployment(
        deployment_id=deployment_id,
        model_id=model_id,
        version_id=f"ver_{deployment_id}",
        environment="development",
        rollout_type=rollout_type,
        role=role,
        framework="sklearn",
        status="active",
    )


def create_routing(
        routing_id: str,
        deployment_id: str,
        traffic_ratio: float,
) -> Routing:
    """创建路由测试对象。"""
    return Routing(
        routing_id=routing_id,
        name=f"{routing_id}-name",
        deployment_id=deployment_id,
        environment="development",
        rollout_type="canary",
        rollout_group="challenger",
        enabled=True,
        traffic_ratio=float(traffic_ratio),
    )


@pytest.mark.asyncio
async def test_duplicate_deployment_routing_is_rejected() -> None:
    """测试一个部署只能维护一条未删除路由"""
    routing_repo = MagicMock()
    routing_repo.list_routings = AsyncMock(
        return_value=[create_routing("rtn_existing", "dep_test", 0.5)]
    )

    with pytest.raises(ValueError, match="已存在路由: rtn_existing"):
        await ensure_deployment_has_no_routing(
            routing_repo=routing_repo,
            deployment_id="dep_test",
        )


@pytest.mark.asyncio
async def test_primary_routing_allocation_over_100_percent_is_rejected(
) -> None:
    """测试同一模型的启用主路由总流量不能超过百分之百"""
    existing_deployment = create_deployment("dep_existing")
    target_deployment = create_deployment("dep_target")
    routing_repo = MagicMock()
    routing_repo.list_enabled_routings = AsyncMock(
        return_value=[
            create_routing("rtn_existing", "dep_existing", 0.8)
        ]
    )
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock(
        return_value=existing_deployment
    )

    with pytest.raises(ValueError, match="达到 110.00%"):
        await validate_routing_allocation(
            routing_repo=routing_repo,
            deployment_repo=deployment_repo,
            deployment=target_deployment,
            traffic_ratio=0.3,
        )


def test_full_deployment_requires_100_percent_traffic() -> None:
    """测试全量发布的路由比例固定为百分之百"""
    deployment = create_deployment(
        "dep_full",
        rollout_type="full",
        role="champion",
    )

    validate_deployment_traffic_ratio(
        deployment=deployment,
        traffic_ratio=1.0,
    )

    with pytest.raises(
            ValueError,
            match="全量发布的流量比例必须为 100%",
    ):
        validate_deployment_traffic_ratio(
            deployment=deployment,
            traffic_ratio=0.5,
        )


@pytest.mark.asyncio
async def test_shadow_routing_does_not_use_primary_traffic_budget() -> None:
    """测试影子路由比例不计入主流量总和"""
    routing_repo = MagicMock()
    routing_repo.list_enabled_routings = AsyncMock()
    deployment_repo = MagicMock()
    deployment_repo.get_deployment = AsyncMock()

    await validate_routing_allocation(
        routing_repo=routing_repo,
        deployment_repo=deployment_repo,
        deployment=create_deployment(
            "dep_shadow",
            rollout_type="shadow",
            role="shadow",
        ),
        traffic_ratio=1.0,
    )

    routing_repo.list_enabled_routings.assert_not_awaited()


@pytest.mark.asyncio
async def test_inactive_deployment_routing_cannot_be_enabled() -> None:
    """测试停用部署不能启用路由"""
    deployment = create_deployment("dep_inactive")
    deployment.status = "inactive"

    with pytest.raises(ValueError, match="只有已启用部署"):
        await validate_routing_allocation(
            routing_repo=MagicMock(),
            deployment_repo=MagicMock(),
            deployment=deployment,
            traffic_ratio=1.0,
        )
