"""管理控制台查询服务测试

验证控制台数据按权限查询、转换并限制返回数量。

核心功能：
  - test_identity_sections_require_manage_permission:
    验证身份管理页面权限
  - test_snapshot_only_queries_authorized_sections:
    验证按权限查询数据
  - test_snapshot_serializes_authorized_records:
    验证控制台记录转换
  - test_snapshot_rejects_invalid_limit:
    验证返回数量限制
  - test_get_section_returns_page:
    验证控制台页面分页
  - test_get_model_versions_returns_page:
    验证模型版本分页
  - test_get_version_detail_includes_model_metadata:
    验证版本详情模型信息
  - test_get_experiment_variants_returns_page:
    验证实验分组分页
  - test_request_item_includes_failure_details:
    验证失败调用详情
  - test_decision_item_includes_trace_and_route_details:
    验证决策执行详情
"""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from types import SimpleNamespace
from unittest.mock import (
    ANY,
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.services.dashboard as dashboard_module
from datamind.runtime.presence import RuntimePresence
from datamind.services.dashboard import DashboardService


CURRENT_TIME = datetime(
    2026,
    8,
    5,
    1,
    30,
    tzinfo=timezone.utc,
)


class FakeUnitOfWork:
    """控制台查询测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def install_repositories(
        monkeypatch: pytest.MonkeyPatch,
) -> dict[str, MagicMock]:
    """替换控制台查询仓储"""
    repositories = {
        "MetadataRepository": MagicMock(),
        "VersionRepository": MagicMock(),
        "ScorecardRepository": MagicMock(),
        "DashboardRepository": MagicMock(),
        "DeploymentRepository": MagicMock(),
        "RoutingRepository": MagicMock(),
        "RuntimeRepository": MagicMock(),
        "RequestRepository": MagicMock(),
        "DecisionRepository": MagicMock(),
        "ExecutionRepository": MagicMock(),
        "ExperimentRepository": MagicMock(),
        "VariantRepository": MagicMock(),
        "AuditRepository": MagicMock(),
        "UserRepository": MagicMock(),
        "RoleRepository": MagicMock(),
    }
    repositories["MetadataRepository"].list_models = AsyncMock(
        return_value=[]
    )
    repositories["MetadataRepository"].get_model = AsyncMock(
        return_value=None
    )
    repositories["VersionRepository"].list_versions = AsyncMock(
        return_value=[]
    )
    repositories["VersionRepository"].get_version = AsyncMock(
        return_value=None
    )
    repositories["ScorecardRepository"].get_scorecard = AsyncMock(
        return_value=None
    )
    repositories["DashboardRepository"].get_counts = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].count_records = AsyncMock(
        return_value=3
    )
    repositories["DashboardRepository"].search_records = AsyncMock(
        return_value=[]
    )
    repositories["DashboardRepository"].get_deployment_labels = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_version_labels = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_experiment_labels = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_variant_labels = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_request_details = AsyncMock(
        return_value={}
    )
    repositories[
        "DashboardRepository"
    ].get_batch_deployment_stats = AsyncMock(
        return_value={}
    )
    repositories[
        "DashboardRepository"
    ].get_attempt_shard_details = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_decision_details = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_execution_details = AsyncMock(
        return_value={}
    )
    repositories[
        "DashboardRepository"
    ].get_decision_executions = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_request_trend = AsyncMock(
        return_value=[]
    )
    repositories["DashboardRepository"].get_request_metrics = AsyncMock(
        return_value={
            "request_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "average_latency_ms": None,
            "p95_latency_ms": None,
            "previous_request_count": 0,
        }
    )
    repositories["DashboardRepository"].get_model_request_stats = AsyncMock(
        return_value=[]
    )
    repositories["DashboardRepository"].get_variant_counts = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_user_roles = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].search_variants = AsyncMock(
        return_value=[]
    )
    repositories["DeploymentRepository"].list_deployments = AsyncMock(
        return_value=[]
    )
    repositories["RoutingRepository"].list_routings = AsyncMock(
        return_value=[]
    )
    repositories["RuntimeRepository"].list_runtimes = AsyncMock(
        return_value=[]
    )
    repositories["RequestRepository"].list_requests = AsyncMock(
        return_value=[]
    )
    repositories["DecisionRepository"].list_decisions = AsyncMock(
        return_value=[]
    )
    repositories["ExecutionRepository"].list_executions = AsyncMock(
        return_value=[]
    )
    repositories["ExperimentRepository"].list_experiments = AsyncMock(
        return_value=[]
    )
    repositories["ExperimentRepository"].get_experiment = AsyncMock(
        return_value=None
    )
    repositories["VariantRepository"].list_variants = AsyncMock(
        return_value=[]
    )
    repositories["AuditRepository"].list_audits = AsyncMock(
        return_value=[]
    )
    repositories["UserRepository"].list_users = AsyncMock(
        return_value=[]
    )
    repositories["RoleRepository"].list_roles = AsyncMock(
        return_value=[]
    )

    monkeypatch.setitem(
        vars(dashboard_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )

    for name, repository in repositories.items():
        monkeypatch.setitem(
            vars(dashboard_module),
            name,
            lambda _session, value=repository: value,
        )

    return repositories


@pytest.mark.asyncio
async def test_snapshot_only_queries_authorized_sections(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台只查询当前用户有权查看的数据"""
    repositories = install_repositories(
        monkeypatch
    )

    result = await DashboardService().snapshot(
        permissions=[
            "model.read",
            "runtime.read",
        ],
        limit=10,
    )

    repositories["MetadataRepository"].list_models.assert_awaited_once_with(
        include_archived=True,
        limit=10,
    )
    repositories[
        "DashboardRepository"
    ].get_counts.assert_awaited_once_with(
        [
            "models",
            "versions",
            "runtimes",
        ],
        presence=ANY,
    )
    repositories[
        "VersionRepository"
    ].list_versions.assert_not_awaited()
    repositories["DashboardRepository"].search_records.assert_awaited_once_with(
        section="runtimes",
        query="",
        limit=10,
        offset=0,
        presence=ANY,
    )
    repositories["RuntimeRepository"].list_runtimes.assert_not_awaited()
    repositories["RequestRepository"].list_requests.assert_not_awaited()
    repositories[
        "DashboardRepository"
    ].get_request_trend.assert_not_awaited()
    repositories[
        "DashboardRepository"
    ].get_request_metrics.assert_not_awaited()
    repositories[
        "DashboardRepository"
    ].get_model_request_stats.assert_not_awaited()
    repositories["DeploymentRepository"].list_deployments.assert_not_awaited()
    repositories["RoutingRepository"].list_routings.assert_not_awaited()
    repositories["ExperimentRepository"].list_experiments.assert_not_awaited()
    repositories["AuditRepository"].list_audits.assert_not_awaited()
    assert result["access"]["models"] is True
    assert result["access"]["audits"] is False
    assert set(result["sections"]) == {
        "models",
        "versions",
        "runtimes",
    }


@pytest.mark.asyncio
async def test_snapshot_serializes_authorized_records(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试控制台转换有权查看的最近记录"""
    repositories = install_repositories(
        monkeypatch
    )
    repositories["MetadataRepository"].list_models.return_value = [
        SimpleNamespace(
            model_id="mdl_test",
            name="scorecard",
            model_type="logistic_regression",
            task_type="scoring",
            framework="sklearn",
            status="active",
            updated_at=CURRENT_TIME,
        )
    ]
    repositories[
        "VersionRepository"
    ].list_versions.return_value = [
        SimpleNamespace(
            version_id="ver_test",
            model_id="mdl_test",
            version="1.0.0",
            framework="sklearn",
            artifact_revision=2,
            status="active",
            updated_at=CURRENT_TIME,
        )
    ]
    repositories["AuditRepository"].list_audits.return_value = [
        SimpleNamespace(
            audit_id="aud_test",
            action="model.activate",
            target_type="model",
            target_id="mdl_test",
            source="cli",
            user="alice",
            status="success",
            occurred_at=CURRENT_TIME,
        )
    ]
    repositories["RoutingRepository"].list_routings.return_value = [
        SimpleNamespace(
            routing_id="rtn_test",
            name="scorecard-route",
            deployment_id="dep_test",
            environment="production",
            rollout_type="canary",
            rollout_group="challenger",
            enabled=True,
            traffic_ratio=0.1,
            updated_at=CURRENT_TIME,
        )
    ]
    repositories[
        "DashboardRepository"
    ].get_counts.return_value = {
        "models": 1,
        "versions": 1,
            "deployments": 0,
            "routings": 0,
            "runtimes": 0,
            "requests": 0,
            "decisions": 0,
            "executions": 0,
            "experiments": 0,
            "variants": 0,
            "audits": 33,
            "users": 0,
            "roles": 0,
        }

    result = await DashboardService().snapshot(
        permissions=["*"],
    )

    repositories[
        "VersionRepository"
    ].list_versions.assert_awaited_once_with(
        include_archived=True,
    )

    model_item = result["sections"]["models"][0]
    assert model_item["model_id"] == "mdl_test"
    assert model_item["name"] == "scorecard"
    assert model_item["latest_version"] == "1.0.0"
    assert model_item["description"] is None
    assert model_item["created_at"] is None
    assert model_item["updated_at"] == "2026-08-05T01:30:00.000Z"
    version_item = model_item["versions"][0]
    assert version_item["version_id"] == "ver_test"
    assert version_item["version"] == "1.0.0"
    assert version_item["current_artifact_id"] is None
    assert version_item["artifact_sha256"] is None
    assert version_item["artifact_digest"] is None
    assert version_item["created_at"] is None
    assert version_item["updated_at"] == "2026-08-05T01:30:00.000Z"
    assert result["sections"]["audits"][0]["action"] == "model.activate"
    routing_item = result["sections"]["routings"][0]
    assert routing_item["routing_id"] == "rtn_test"
    assert routing_item["status"] == "enabled"
    assert routing_item["rules"] is None
    assert routing_item["created_at"] is None
    assert routing_item["updated_at"] == "2026-08-05T01:30:00.000Z"
    assert result["sections"]["versions"][0]["version_id"] == "ver_test"
    repositories[
        "DashboardRepository"
    ].get_request_trend.assert_awaited_once()
    trend_call = repositories[
        "DashboardRepository"
    ].get_request_trend.await_args
    assert trend_call is not None
    assert trend_call.kwargs["interval"] == timedelta(
        minutes=5
    )
    assert trend_call.kwargs["origin"] == datetime(
        2000,
        1,
        1,
        tzinfo=timezone.utc,
    )
    repositories[
        "DashboardRepository"
    ].get_request_metrics.assert_awaited_once()
    repositories[
        "DashboardRepository"
    ].get_model_request_stats.assert_awaited_once()
    usage_call = repositories[
        "DashboardRepository"
    ].get_model_request_stats.await_args
    assert usage_call is not None
    assert set(
        usage_call.kwargs
    ) == {
        "since"
    }
    assert len(result["request_trend"]) == 288
    assert result["request_trend_range"] == "24h"
    assert result["request_trend_interval"] == "5 minutes"
    assert all(
        item["count"] == 0
        and item["success_count"] == 0
        and item["failed_count"] == 0
        for item in result["request_trend"]
    )
    assert result["counts"] == {
        "models": 1,
        "versions": 1,
        "deployments": 0,
        "routings": 0,
        "runtimes": 0,
        "requests": 0,
        "decisions": 0,
        "executions": 0,
        "experiments": 0,
        "variants": 0,
        "audits": 33,
        "users": 0,
        "roles": 0,
    }


def test_build_request_trend_preserves_outcomes() -> None:
    """测试 API 调用趋势区分成功和失败次数"""
    result = DashboardService._build_request_trend(
        records=[
            {
                "bucket": CURRENT_TIME,
                "count": 6,
                "success_count": 4,
                "failed_count": 2,
            }
        ],
        start=CURRENT_TIME,
        step=timedelta(minutes=5),
        points=2,
    )

    assert result[0] == {
        "time": "2026-08-05T01:30:00.000Z",
        "count": 6,
        "success_count": 4,
        "failed_count": 2,
    }
    assert result[1]["count"] == 0
    assert result[1]["success_count"] == 0
    assert result[1]["failed_count"] == 0


def test_role_item_marks_builtin_role() -> None:
    """测试控制台角色摘要标识内置角色"""
    role = SimpleNamespace(
        role_id="rol_admin",
        name="administrator",
        description="管理员角色",
        permissions=[
            "*"
        ],
        status="active",
        created_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._role_item(
        role
    )

    assert result["is_builtin"] is True
    assert result["permissions"] == [
        "*"
    ]
    assert "*" not in result[
        "effective_permissions"
    ]
    assert len(result["effective_permissions"]) > 2


def test_identity_sections_require_manage_permission() -> None:
    """测试控制台用户和角色页面仅对身份管理员开放"""
    reader_access = DashboardService.get_access([
        "identity.read"
    ])
    manager_access = DashboardService.get_access([
        "identity.manage"
    ])

    assert reader_access["users"] is False
    assert reader_access["roles"] is False
    assert manager_access["users"] is True
    assert manager_access["roles"] is True


@pytest.mark.parametrize(
    (
        "trend_range",
        "expected_step",
        "expected_interval",
        "expected_points",
    ),
    [
        (
            "1h",
            timedelta(minutes=1),
            "1 minute",
            60,
        ),
        (
            "24h",
            timedelta(minutes=5),
            "5 minutes",
            288,
        ),
        (
            "7d",
            timedelta(hours=1),
            "1 hour",
            168,
        ),
        (
            "30d",
            timedelta(days=1),
            "1 day",
            30,
        ),
    ],
)
def test_resolve_request_trend_period(
        trend_range: str,
        expected_step: timedelta,
        expected_interval: str,
        expected_points: int,
) -> None:
    """测试趋势时间范围映射到固定聚合粒度"""
    start, step, interval, points = (
        DashboardService._resolve_request_trend_period(
            current_time=CURRENT_TIME,
            trend_range=trend_range,
        )
    )

    assert step == expected_step
    assert interval == expected_interval
    assert points == expected_points
    assert start + (points - 1) * step <= CURRENT_TIME
    assert CURRENT_TIME < start + points * step


def test_resolve_request_trend_period_rejects_unknown_range() -> None:
    """测试拒绝不支持的趋势时间范围"""
    with pytest.raises(
            ValueError,
            match="trend_range 只支持",
    ):
        DashboardService._resolve_request_trend_period(
            current_time=CURRENT_TIME,
            trend_range="90d",
        )


def test_build_request_summary_calculates_core_metrics() -> None:
    """测试 API 调用核心指标计算成功率和周期变化"""
    result = DashboardService._build_request_summary({
        "request_count": 1284,
        "success_count": 1267,
        "failed_count": 17,
        "average_latency_ms": 436.25,
        "p95_latency_ms": 612.4,
        "previous_request_count": 1140,
    })

    assert result == {
        "request_count": 1284,
        "success_count": 1267,
        "failed_count": 17,
        "success_rate": pytest.approx(
            1267 / 1284
        ),
        "average_latency_ms": 436.25,
        "p95_latency_ms": 612.4,
        "previous_request_count": 1140,
        "change_rate": pytest.approx(
            (1284 - 1140) / 1140
        ),
    }


def test_build_model_usage_calculates_recent_metrics() -> None:
    """测试模型调用概况计算最近表现和累计调用量"""
    result = DashboardService._build_model_usage([
        {
            "model_id": "mdl_test",
            "model_name": "scorecard",
            "is_deleted": False,
            "recent_count": 8,
            "recent_success_count": 7,
            "recent_total_count": 10,
            "average_latency_ms": 196.315,
            "total_count": 120,
        },
        {
            "model_id": "mdl_idle",
            "model_name": "legacy",
            "is_deleted": True,
            "recent_count": 0,
            "recent_success_count": 0,
            "recent_total_count": 10,
            "average_latency_ms": None,
            "total_count": 24,
        },
    ])

    assert result == [
        {
            "model_id": "mdl_test",
            "model_name": "scorecard",
            "is_deleted": False,
            "recent_count": 8,
            "total_count": 120,
            "success_rate": 0.875,
            "average_latency_ms": 196.315,
            "request_share": 0.8,
        },
        {
            "model_id": "mdl_idle",
            "model_name": "legacy",
            "is_deleted": True,
            "recent_count": 0,
            "total_count": 24,
            "success_rate": None,
            "average_latency_ms": None,
            "request_share": 0.0,
        },
    ]


@pytest.mark.parametrize(
    "limit",
    [
        0,
        101,
    ],
)
@pytest.mark.asyncio
async def test_snapshot_rejects_invalid_limit(
        limit: int,
) -> None:
    """测试控制台拒绝非法返回数量"""
    with pytest.raises(
            ValueError,
            match="limit 必须在 1 到 100 之间",
    ):
        await DashboardService().snapshot(
            permissions=["*"],
            limit=limit,
        )


@pytest.mark.asyncio
async def test_get_model_versions_returns_page(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本分页返回精确总数"""
    repositories = install_repositories(
        monkeypatch
    )
    versions = [
        SimpleNamespace(
            version_id=f"ver_{index}",
            model_id="mdl_test",
            version=f"{index}.0.0",
            framework="sklearn",
            artifact_revision=1,
            status="active",
            updated_at=CURRENT_TIME,
        )
        for index in range(2)
    ]
    repositories[
        "DashboardRepository"
    ].search_records.return_value = versions
    repositories[
        "MetadataRepository"
    ].get_model.return_value = SimpleNamespace(
        name="scorecard"
    )
    repositories[
        "DashboardRepository"
    ].count_records.return_value = 5

    result = await DashboardService().get_model_versions(
        model_id="mdl_test",
        page=2,
        page_size=2,
    )

    repositories[
        "DashboardRepository"
    ].search_records.assert_awaited_once_with(
        section="versions",
        query="",
        model_id="mdl_test",
        limit=2,
        offset=2,
        sort_by=None,
        sort_order="asc",
        only_deleted=False,
    )
    repositories[
        "MetadataRepository"
    ].get_model.assert_awaited_once_with(
        model_id="mdl_test",
    )
    assert result["model"] == {
        "model_id": "mdl_test",
        "name": "scorecard",
    }
    assert [
        item["version_id"]
        for item in result["items"]
    ] == [
        "ver_0",
        "ver_1",
    ]
    assert result["page"] == 2
    assert result["page_size"] == 2
    assert result["total"] == 5
    assert result["total_pages"] == 3
    assert result["has_previous"] is True
    assert result["has_next"] is True


@pytest.mark.asyncio
async def test_get_model_versions_supports_recycle_bin(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型版本分页可以仅返回逻辑删除记录"""
    repositories = install_repositories(monkeypatch)
    repositories["MetadataRepository"].get_model.return_value = (
        SimpleNamespace(name="scorecard")
    )

    result = await DashboardService().get_model_versions(
        model_id="mdl_test",
        deleted=True,
    )

    repositories["DashboardRepository"].count_records.assert_awaited_once_with(
        section="versions",
        query="",
        model_id="mdl_test",
        only_deleted=True,
    )
    repositories["DashboardRepository"].search_records.assert_awaited_once_with(
        section="versions",
        query="",
        model_id="mdl_test",
        limit=10,
        offset=0,
        sort_by=None,
        sort_order="asc",
        only_deleted=True,
    )
    assert result["deleted"] is True


@pytest.mark.asyncio
async def test_get_model_versions_rejects_invalid_page() -> None:
    """测试模型版本分页拒绝非法页码"""
    with pytest.raises(
            ValueError,
            match="page 必须大于等于 1",
    ):
        await DashboardService().get_model_versions(
            model_id="mdl_test",
            page=0,
        )


@pytest.mark.asyncio
async def test_get_experiment_variants_returns_page(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组使用独立分页数据"""
    repositories = install_repositories(
        monkeypatch
    )
    repositories["ExperimentRepository"].get_experiment.return_value = (
        SimpleNamespace(
            experiment_id="exp_test",
            name="credit-policy",
            status="draft",
            config={
                "strategy": "hash",
                "traffic_ratio": 0.25,
            },
        )
    )
    repositories[
        "DashboardRepository"
    ].count_records.return_value = 2
    repositories["VariantRepository"].list_variants.return_value = [
        SimpleNamespace(
            variant_id=f"var_{index}",
            name=f"group-{index}",
            deployment_id=f"dep_{index}",
            weight=0.5,
            is_control=index == 1,
            status="active",
            experiment_id="exp_test",
            config={
                "group": f"group-{index}"
            },
            description=f"group-{index} description",
            created_by="admin",
            updated_by="admin",
            created_at=CURRENT_TIME,
            updated_at=CURRENT_TIME,
        )
        for index in range(1, 2)
    ]

    result = await DashboardService().get_experiment_variants(
        experiment_id="exp_test",
        page_size=1,
    )

    repositories["VariantRepository"].list_variants.assert_awaited_once_with(
        experiment_id="exp_test",
        limit=1,
        offset=0,
    )
    assert result["experiment"] == {
        "experiment_id": "exp_test",
        "name": "credit-policy",
    }
    assert result["items"][0]["group_type"] == "对照组"
    assert result["items"][0]["experiment_id"] == "exp_test"
    assert result["items"][0]["experiment_name"] == "credit-policy"
    assert result["items"][0]["experiment_status"] == "draft"
    assert result["items"][0]["experiment_strategy"] == "hash"
    assert result["items"][0]["experiment_traffic_ratio"] == 0.25
    assert result["items"][0]["config"] == {
        "group": "group-1"
    }
    assert result["total"] == 2
    assert result["total_pages"] == 2
    assert result["has_next"] is True


@pytest.mark.asyncio
async def test_get_experiment_variants_searches_and_sorts(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验分组查询和排序在数据库分页前完成"""
    repositories = install_repositories(
        monkeypatch
    )
    repositories["ExperimentRepository"].get_experiment.return_value = (
        SimpleNamespace(
            experiment_id="exp_test",
            name="credit-policy",
        )
    )

    result = await DashboardService().get_experiment_variants(
        experiment_id="exp_test",
        query="  control  ",
        sort_by="weight",
        sort_order="desc",
    )

    repositories["DashboardRepository"].search_variants.assert_awaited_once_with(
        experiment_id="exp_test",
        query="control",
        limit=10,
        offset=0,
        sort_by="weight",
        sort_order="desc",
    )
    repositories["VariantRepository"].list_variants.assert_not_awaited()
    assert result["query"] == "control"
    assert result["sort_by"] == "weight"
    assert result["sort_order"] == "desc"


@pytest.mark.asyncio
async def test_get_experiment_variants_supports_recycle_bin(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试实验详情中的分组回收站仅查询已删除记录"""
    repositories = install_repositories(monkeypatch)
    repositories["ExperimentRepository"].get_experiment.return_value = (
        SimpleNamespace(
            experiment_id="exp_test",
            name="credit-policy",
            status="draft",
        )
    )
    repositories["DashboardRepository"].count_records.return_value = 1
    repositories["DashboardRepository"].search_records.return_value = [
        SimpleNamespace(
            variant_id="var_deleted",
            experiment_id="exp_test",
            name="treatment",
            deployment_id="dep_test",
            weight=0.5,
            is_control=False,
            status="inactive",
            config={},
            description="已删除分组",
            created_by="admin",
            updated_by="admin",
            deleted_by="admin",
            deletion_reason="实验调整",
            deleted_at=CURRENT_TIME,
            created_at=CURRENT_TIME,
            updated_at=CURRENT_TIME,
        )
    ]

    result = await DashboardService().get_experiment_variants(
        experiment_id="exp_test",
        deleted=True,
    )

    repositories["DashboardRepository"].count_records.assert_awaited_once_with(
        section="variants",
        query="",
        experiment_id="exp_test",
        only_deleted=True,
    )
    repositories["DashboardRepository"].search_records.assert_awaited_once_with(
        section="variants",
        query="",
        experiment_id="exp_test",
        limit=10,
        offset=0,
        sort_by=None,
        sort_order="asc",
        only_deleted=True,
    )
    assert result["deleted"] is True
    assert result["items"][0]["deleted_by"] == "admin"
    assert result["items"][0]["experiment_status"] == "draft"


@pytest.mark.parametrize(
    (
        "section",
        "repository_name",
        "method_name",
        "record",
        "identifier",
    ),
    [
        (
            "models",
            "MetadataRepository",
            "list_models",
            SimpleNamespace(
                model_id="mdl_test",
                name="scorecard",
                model_type="logistic_regression",
                task_type="scoring",
                framework="sklearn",
                status="active",
                updated_at=CURRENT_TIME,
            ),
            "model_id",
        ),
        (
            "versions",
            "VersionRepository",
            "list_versions",
            SimpleNamespace(
                version_id="ver_test",
                model_id="mdl_test",
                version="1.0.0",
                framework="sklearn",
                artifact_revision=1,
                status="active",
                updated_at=CURRENT_TIME,
            ),
            "version_id",
        ),
        (
            "deployments",
            "DeploymentRepository",
            "list_deployments",
            SimpleNamespace(
                deployment_id="dep_test",
                model_id="mdl_test",
                version_id="ver_test",
                environment="production",
                framework="sklearn",
                rollout_type="full",
                role="champion",
                status="active",
                updated_at=CURRENT_TIME,
            ),
            "deployment_id",
        ),
        (
            "routings",
            "RoutingRepository",
            "list_routings",
            SimpleNamespace(
                routing_id="rtn_test",
                name="scorecard-route",
                deployment_id="dep_test",
                environment="production",
                rollout_type="canary",
                rollout_group="challenger",
                enabled=True,
                traffic_ratio=0.1,
                updated_at=CURRENT_TIME,
            ),
            "routing_id",
        ),
        (
            "runtimes",
            "RuntimeRepository",
            "list_runtimes",
            SimpleNamespace(
                runtime_id="rtm_test",
                deployment_id="dep_test",
                worker_id="worker_test",
                framework="sklearn",
                status="running",
                last_heartbeat_at=CURRENT_TIME,
                updated_at=CURRENT_TIME,
            ),
            "runtime_id",
        ),
        (
            "requests",
            "RequestRepository",
            "list_requests",
            SimpleNamespace(
                request_id="req_test",
                model_id="mdl_test",
                source="http",
                status="success",
                error=None,
                payload={
                    "features": {
                        "age": 35
                    }
                },
                latency_ms=18.5,
                user="alice",
                ip="127.0.0.1",
                created_at=CURRENT_TIME,
            ),
            "request_id",
        ),
        (
            "batches",
            "DashboardRepository",
            "search_records",
            SimpleNamespace(
                batch_id="bat_test",
                task_id="tsk_test",
                model_id="mdl_test",
                model_name="scorecard",
                deployment_id=None,
                environment="development",
                status="succeeded",
                payload={"model_name": "scorecard", "instances": []},
                result={"success": True, "predictions": []},
                error=None,
                total_count=1,
                completed_count=1,
                succeeded_count=1,
                failed_count=0,
                attempt_count=1,
                cancel_requested_at=None,
                started_at=CURRENT_TIME,
                finished_at=CURRENT_TIME,
                source="http",
                user="alice",
                ip="127.0.0.1",
                created_at=CURRENT_TIME,
                updated_at=CURRENT_TIME,
            ),
            "batch_id",
        ),
        (
            "attempts",
            "DashboardRepository",
            "search_records",
            SimpleNamespace(
                attempt_id="att_test",
                batch_id="bat_test",
                task_id="tsk_test",
                attempt_number=2,
                status="failed",
                worker_id="worker-1",
                error="temporary error",
                retry_scheduled_at=CURRENT_TIME,
                queued_at=CURRENT_TIME,
                started_at=CURRENT_TIME,
                finished_at=CURRENT_TIME,
                created_at=CURRENT_TIME,
                updated_at=CURRENT_TIME,
            ),
            "attempt_id",
        ),
        (
            "decisions",
            "DecisionRepository",
            "list_decisions",
            SimpleNamespace(
                decision_id="dcs_test",
                request_id="req_test",
                model_id="mdl_test",
                version_id="ver_test",
                deployment_id="dep_test",
                experiment_id=None,
                variant_id=None,
                assignment_id=None,
                subject_key="customer_10001",
                subject_type="customer",
                source="routing",
                strategy="weighted",
                bucket="bucket_1000",
                group=None,
                weight=0.7,
                prediction={
                    "score": 680
                },
                probability=0.25,
                score=680.0,
                decision=None,
                latency_ms=18.5,
                context={
                    "routing_id": "rtn_test"
                },
                decided_at=CURRENT_TIME,
            ),
            "decision_id",
        ),
        (
            "executions",
            "ExecutionRepository",
            "list_executions",
            SimpleNamespace(
                execution_id="exe_test",
                decision_id="dcs_test",
                execution_type="shadow",
                status="success",
                model_id="mdl_test",
                version_id="ver_test",
                deployment_id="dep_test",
                routing_id="rtn_test",
                prediction={
                    "score": 681
                },
                probability=0.24,
                score=681.0,
                latency_ms=12.5,
                error_type=None,
                error=None,
                context={
                    "source": "shadow"
                },
                started_at=CURRENT_TIME,
                finished_at=CURRENT_TIME,
                created_at=CURRENT_TIME,
            ),
            "execution_id",
        ),
        (
            "experiments",
            "ExperimentRepository",
            "list_experiments",
            SimpleNamespace(
                experiment_id="exp_test",
                model_id="mdl_test",
                name="champion",
                environment="production",
                status="running",
                effective_from=CURRENT_TIME,
                effective_to=None,
                updated_at=CURRENT_TIME,
            ),
            "experiment_id",
        ),
        (
            "variants",
            "VariantRepository",
            "list_variants",
            SimpleNamespace(
                variant_id="var_test",
                experiment_id="exp_test",
                name="treatment",
                deployment_id="dep_test",
                weight=0.5,
                is_control=False,
                status="active",
                config={},
                description="实验组",
                created_by="admin",
                updated_by="admin",
                created_at=CURRENT_TIME,
                updated_at=CURRENT_TIME,
            ),
            "variant_id",
        ),
        (
            "audits",
            "AuditRepository",
            "list_audits",
            SimpleNamespace(
                audit_id="aud_test",
                action="model.activate",
                target_type="model",
                target_id="mdl_test",
                user="alice",
                source="cli",
                status="success",
                occurred_at=CURRENT_TIME,
            ),
            "audit_id",
        ),
    ],
)
@pytest.mark.asyncio
async def test_get_section_returns_page(
        monkeypatch: pytest.MonkeyPatch,
        section: str,
        repository_name: str,
        method_name: str,
        record: SimpleNamespace,
        identifier: str,
) -> None:
    """测试所有控制台页面使用统一分页"""
    repositories = install_repositories(
        monkeypatch
    )
    repository = repositories[
        repository_name
    ]
    method = getattr(
        repository,
        method_name,
    )
    uses_dashboard_query = section in {
        "attempts",
        "batches",
        "models",
        "deployments",
        "executions",
        "experiments",
        "versions",
        "variants",
        "runtimes",
    }

    if uses_dashboard_query:
        repositories[
            "DashboardRepository"
        ].search_records.return_value = [
            record,
        ]
        if section == "batches":
            repositories[
                "DashboardRepository"
            ].get_batch_deployment_stats.return_value = {
                record.batch_id: [{
                    "deployment_id": "dep_test",
                    "execution_type": "primary",
                    "model_name": "scorecard",
                    "model_version": "1.0.0",
                    "execution_count": 1,
                }],
            }
    else:
        method.return_value = [
            record,
        ]

    result = await DashboardService().get_section(
        section=section,
        page=2,
        page_size=1,
    )

    expected_arguments = {
        "limit": 1,
        "offset": 1,
    }

    if section in {
        "models",
        "versions",
    }:
        expected_arguments[
            "include_archived"
        ] = True

    if uses_dashboard_query:
        expected_dashboard_arguments = {
            "section": section,
            "query": "",
            "limit": 1,
            "offset": 1,
            "sort_by": None,
            "sort_order": "asc",
        }
        if section == "versions":
            expected_dashboard_arguments["only_deleted"] = False
        if section == "runtimes":
            expected_dashboard_arguments["presence"] = ANY
        repositories[
            "DashboardRepository"
        ].search_records.assert_awaited_once_with(
            **expected_dashboard_arguments
        )
        if repository_name != "DashboardRepository":
            method.assert_not_awaited()
    else:
        method.assert_awaited_once_with(
            **expected_arguments
        )
    assert result["items"][0][identifier] == getattr(
        record,
        identifier,
    )
    if section == "batches":
        assert result["items"][0]["deployments"] == [{
            "deployment_id": "dep_test",
            "execution_type": "primary",
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "execution_count": 1,
        }]
    assert result["has_previous"] is True
    assert result["has_next"] is True
    assert result["total"] == 3
    assert result["total_pages"] == 3


@pytest.mark.asyncio
async def test_get_section_searches_by_keyword(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试页面查询使用规范化关键词和统一分页"""
    repositories = install_repositories(
        monkeypatch
    )
    record = SimpleNamespace(
        version_id="ver_test",
        model_id="mdl_test",
        version="1.0.0",
        framework="sklearn",
        artifact_revision=1,
        status="active",
        updated_at=CURRENT_TIME,
    )
    repositories[
        "DashboardRepository"
    ].search_records.return_value = [
        record
    ]
    repositories[
        "DashboardRepository"
    ].get_version_labels.return_value = {
        "ver_test": {
            "model_name": "scorecard",
            "display_name": "信用评分卡模型",
        }
    }
    repositories[
        "DashboardRepository"
    ].count_records.return_value = 1

    result = await DashboardService().get_section(
        section="versions",
        query="  score  ",
    )

    repositories[
        "DashboardRepository"
    ].search_records.assert_awaited_once_with(
        section="versions",
        query="score",
        limit=10,
        offset=0,
        sort_by=None,
        sort_order="asc",
        only_deleted=False,
    )
    repositories[
        "VersionRepository"
    ].list_versions.assert_not_awaited()
    assert result["query"] == "score"
    assert result["items"][0]["version_id"] == "ver_test"
    assert result["items"][0]["model_name"] == "scorecard"
    assert result["items"][0]["display_name"] == "信用评分卡模型"
    assert result["total"] == 1
    assert result["total_pages"] == 1

    repositories[
        "DashboardRepository"
    ].get_version_labels.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_section_returns_deleted_versions(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试全局版本回收站仅返回已逻辑删除版本"""
    repositories = install_repositories(
        monkeypatch
    )
    record = SimpleNamespace(
        version_id="ver_deleted",
        model_id="mdl_test",
        version="1.0.0",
        framework="sklearn",
        artifact_revision=1,
        status="archived",
        deleted_by="admin",
        deletion_reason="不再使用",
        deleted_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )
    dashboard_repo = repositories[
        "DashboardRepository"
    ]
    dashboard_repo.count_records.return_value = 1
    dashboard_repo.search_records.return_value = [
        record
    ]
    dashboard_repo.get_version_labels.return_value = {
        "ver_deleted": {
            "model_name": "scorecard",
            "display_name": "信用评分卡模型",
        }
    }

    result = await DashboardService().get_section(
        section="versions",
        deleted=True,
    )

    dashboard_repo.count_records.assert_awaited_once_with(
        section="versions",
        query="",
        only_deleted=True,
    )
    dashboard_repo.search_records.assert_awaited_once_with(
        section="versions",
        query="",
        limit=10,
        offset=0,
        sort_by=None,
        sort_order="asc",
        only_deleted=True,
    )
    assert result["deleted"] is True
    assert result["items"][0]["deleted_by"] == "admin"
    assert result["items"][0]["model_name"] == "scorecard"


@pytest.mark.asyncio
async def test_get_section_returns_deleted_models(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型回收站仅返回整体逻辑删除的模型"""
    repositories = install_repositories(monkeypatch)
    record = SimpleNamespace(
        model_id="mdl_deleted",
        name="scorecard",
        display_name="信用评分卡模型",
        model_type="logistic_regression",
        task_type="scoring",
        framework="sklearn",
        status="archived",
        description="已删除模型",
        deleted_by="admin",
        deletion_reason="停止维护",
        deleted_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )
    dashboard_repo = repositories["DashboardRepository"]
    dashboard_repo.count_records.return_value = 1
    dashboard_repo.search_records.return_value = [record]

    result = await DashboardService().get_section(
        section="models",
        deleted=True,
    )

    dashboard_repo.count_records.assert_awaited_once_with(
        section="models",
        query="",
        only_deleted=True,
    )
    dashboard_repo.search_records.assert_awaited_once_with(
        section="models",
        query="",
        limit=10,
        offset=0,
        sort_by=None,
        sort_order="asc",
        only_deleted=True,
    )
    assert result["deleted"] is True
    assert result["items"][0]["model_id"] == "mdl_deleted"
    assert result["items"][0]["deleted_by"] == "admin"
    assert result["items"][0]["deletion_reason"] == "停止维护"


@pytest.mark.asyncio
async def test_get_version_detail_includes_model_metadata(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试版本详情通过模型仓储补齐模型信息"""
    repositories = install_repositories(
        monkeypatch
    )
    repositories[
        "VersionRepository"
    ].get_version.return_value = SimpleNamespace(
        version_id="ver_test",
        model_id="mdl_test",
        version="1.0.0",
        framework="sklearn",
        artifact_revision=2,
        status="active",
        current_artifact_id="art_test",
        artifact_sha256="sha256_test",
        artifact_digest="digest_test",
        bento_tag="scorecard:test",
        model_key="models/scorecard/1.0.0/model.pkl",
        description="版本说明",
        created_by="admin",
        updated_by="admin",
        created_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )
    repositories[
        "MetadataRepository"
    ].get_model.return_value = SimpleNamespace(
        model_id="mdl_test",
        name="scorecard",
        display_name="信用评分卡模型",
        model_type="logistic_regression",
        task_type="scoring",
    )
    repositories["ScorecardRepository"].get_scorecard.return_value = (
        SimpleNamespace(
            scorecard_id="scr_test",
            details_version=1,
            details={"variable_count": 8},
        )
    )

    result = await DashboardService().get_version_detail(
        version_id="ver_test"
    )

    repositories[
        "VersionRepository"
    ].get_version.assert_awaited_once_with(
        "ver_test"
    )
    repositories[
        "MetadataRepository"
    ].get_model.assert_awaited_once_with(
        model_id="mdl_test"
    )
    assert result is not None
    assert result["model_name"] == "scorecard"
    assert result["display_name"] == "信用评分卡模型"
    assert result["model_type"] == "logistic_regression"
    assert result["scorecard"] == {
        "scorecard_id": "scr_test",
        "details_version": 1,
        "details": {"variable_count": 8},
    }
    assert result["task_type"] == "scoring"
    assert result["version"] == "1.0.0"
    assert result["artifact_revision"] == 2


@pytest.mark.asyncio
async def test_get_section_filters_selected_records(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试页面查询可限定为待导出的已选记录"""
    repositories = install_repositories(
        monkeypatch
    )
    record = SimpleNamespace(
        version_id="ver_test",
        model_id="mdl_test",
        version="1.0.0",
        framework="sklearn",
        artifact_revision=1,
        status="active",
        updated_at=CURRENT_TIME,
    )
    record_ids = (
        "ver_test",
    )
    repositories[
        "DashboardRepository"
    ].search_records.return_value = [
        record
    ]
    repositories[
        "DashboardRepository"
    ].count_records.return_value = 1

    result = await DashboardService().get_section(
        section="versions",
        record_ids=record_ids,
    )

    repositories[
        "DashboardRepository"
    ].count_records.assert_awaited_once_with(
        section="versions",
        query="",
        record_ids=record_ids,
        only_deleted=False,
    )
    repositories[
        "DashboardRepository"
    ].search_records.assert_awaited_once_with(
        section="versions",
        query="",
        record_ids=record_ids,
        limit=10,
        offset=0,
        sort_by=None,
        sort_order="asc",
        only_deleted=False,
    )
    repositories[
        "VersionRepository"
    ].list_versions.assert_not_awaited()
    assert result["total"] == 1
    assert result["items"][0][
        "version_id"
    ] == "ver_test"


@pytest.mark.asyncio
async def test_get_section_sorts_before_pagination(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试页面排序由数据库查询在分页前完成"""
    repositories = install_repositories(
        monkeypatch
    )
    record = SimpleNamespace(
        version_id="ver_test",
        model_id="mdl_test",
        version="1.0.0",
        framework="sklearn",
        artifact_revision=1,
        status="active",
        updated_at=CURRENT_TIME,
    )
    repositories[
        "DashboardRepository"
    ].search_records.return_value = [
        record
    ]
    repositories[
        "DashboardRepository"
    ].count_records.return_value = 1

    result = await DashboardService().get_section(
        section="versions",
        sort_by="version",
        sort_order="desc",
    )

    repositories[
        "DashboardRepository"
    ].search_records.assert_awaited_once_with(
        section="versions",
        query="",
        limit=10,
        offset=0,
        sort_by="version",
        sort_order="desc",
        only_deleted=False,
    )
    repositories[
        "VersionRepository"
    ].list_versions.assert_not_awaited()
    assert result["sort_by"] == "version"
    assert result["sort_order"] == "desc"


@pytest.mark.asyncio
async def test_get_section_normalizes_multiple_sort_fields(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试页面查询规范化多字段排序参数"""
    repositories = install_repositories(monkeypatch)
    repositories["DashboardRepository"].count_records.return_value = 0

    result = await DashboardService().get_section(
        section="deployments",
        sort_by=" status, updated_at ",
        sort_order="asc, DESC",
    )

    repositories[
        "DashboardRepository"
    ].search_records.assert_awaited_once_with(
        section="deployments",
        query="",
        limit=10,
        offset=0,
        sort_by="status,updated_at",
        sort_order="asc,desc",
    )
    assert result["sort_by"] == "status,updated_at"
    assert result["sort_order"] == "asc,desc"


def test_deployment_item_includes_model_labels() -> None:
    """测试部署摘要包含模型名称和版本号"""
    deployment = SimpleNamespace(
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        environment="production",
        framework="sklearn",
        rollout_type="canary",
        role="challenger",
        status="active",
        threshold=0.5,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._deployment_item(
        deployment,
        labels={
            "model_name": "scorecard",
            "model_version": "1.0.0",
        },
    )

    assert result["model_name"] == "scorecard"
    assert result["model_version"] == "1.0.0"
    assert result["rollout_type"] == "canary"
    assert result["role"] == "challenger"
    assert result["threshold"] == 0.5
    assert result["updated_at"] == "2026-08-05T01:30:00.000Z"
    assert result["created_at"] is None


def test_routing_item_uses_current_deployment_release_values() -> None:
    """测试路由摘要以关联部署的当前发布信息为准"""
    routing = SimpleNamespace(
        routing_id="rtn_test",
        name="scorecard-route",
        deployment_id="dep_test",
        environment="production",
        rollout_type="full",
        rollout_group="champion",
        enabled=True,
        traffic_ratio=1.0,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._routing_item(
        routing,
        labels={
            "model_id": "mdl_test",
            "version_id": "ver_test",
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "environment": "testing",
            "rollout_type": "canary",
            "rollout_group": "challenger",
        },
    )

    assert result["model_id"] == "mdl_test"
    assert result["version_id"] == "ver_test"
    assert result["environment"] == "testing"
    assert result["rollout_type"] == "canary"
    assert result["rollout_group"] == "challenger"


def test_runtime_item_includes_deployment_labels() -> None:
    """测试运行实例摘要包含模型和部署角色"""
    runtime = SimpleNamespace(
        runtime_id="rtm_test",
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        worker_id="worker_test",
        framework="sklearn",
        status="running",
        last_heartbeat_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._runtime_item(
        runtime,
        labels={
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "rollout_group": "challenger",
        },
        presence=RuntimePresence(
            stale_at=CURRENT_TIME - timedelta(seconds=1),
        ),
    )

    assert result["model_name"] == "scorecard"
    assert result["model_version"] == "1.0.0"
    assert result["role"] == "challenger"
    assert result["status"] == "running"
    assert result["health_status"] == "healthy"


def test_runtime_item_reports_unhealthy_worker() -> None:
    """测试过期心跳仅影响健康状态并格式化 Worker 名称"""
    runtime = SimpleNamespace(
        runtime_id="rtm_stale",
        deployment_id="dep_test",
        model_id="mdl_test",
        version_id="ver_test",
        worker_id="LAPTOP-TEST-5884",
        framework="sklearn",
        status="running",
        last_heartbeat_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._runtime_item(
        runtime,
        presence=RuntimePresence(
            stale_at=CURRENT_TIME + timedelta(seconds=1),
        ),
    )

    assert result["status"] == "running"
    assert result["health_status"] == "unhealthy"
    assert result["worker_id"] == "LAPTOP-TEST-5884"


def test_experiment_item_includes_variant_count() -> None:
    """测试实验摘要包含分组数量和更新时间"""
    experiment = SimpleNamespace(
        experiment_id="exp_test",
        model_id="mdl_test",
        name="credit-policy",
        environment="production",
        status="running",
        effective_from=CURRENT_TIME,
        effective_to=None,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._experiment_item(
        experiment,
        variant_count=2,
    )

    assert result["variant_count"] == 2
    assert "model_version" not in result
    assert result["updated_at"] == "2026-08-05T01:30:00.000Z"


def test_variant_item_includes_experiment_and_model_labels() -> None:
    """测试分组摘要包含实验名称和部署模型版本"""
    variant = SimpleNamespace(
        variant_id="var_test",
        experiment_id="exp_test",
        name="treatment",
        deployment_id="dep_test",
        weight=0.5,
        is_control=False,
        status="active",
        config={},
        description="实验组",
        created_by="admin",
        updated_by="admin",
        created_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._variant_item(
        variant,
        labels={
            "experiment_name": "credit-policy",
            "experiment_config": {
                "strategy": "hash",
                "traffic_ratio": 0.3,
            },
            "model_name": "scorecard",
            "model_version": "2.0.0",
        },
    )

    assert result["experiment_name"] == "credit-policy"
    assert result["experiment_strategy"] == "hash"
    assert result["experiment_traffic_ratio"] == 0.3
    assert result["model_name"] == "scorecard"
    assert result["model_version"] == "2.0.0"


def test_variant_item_does_not_invent_experiment_allocation() -> None:
    """测试实验分流配置缺失时不伪造默认值"""
    variant = SimpleNamespace(
        variant_id="var_test",
        experiment_id="exp_test",
        name="control",
        deployment_id="dep_test",
        weight=1.0,
        is_control=True,
        status="active",
        config={},
        description=None,
        created_by="admin",
        updated_by="admin",
        created_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )

    result = DashboardService._variant_item(variant, labels={})

    assert result["experiment_strategy"] is None
    assert result["experiment_traffic_ratio"] is None


def test_request_item_includes_model_and_decision_details() -> None:
    """测试 API 调用摘要包含模型、决策和预测详情"""
    prediction = {
        "task_type": "scoring",
        "score": 680,
        "features": {"age": {"value": 35, "points": 680}},
    }
    request = SimpleNamespace(
        request_id="req_test",
        batch_id="bat_test",
        batch_index=0,
        model_id="mdl_test",
        payload={
            "features": {
                "age": 35
            }
        },
        response={
            "success": True,
            **prediction,
            "request_id": "req_test",
        },
        source="http",
        status="success",
        error=None,
        latency_ms=18.5,
        user="alice",
        ip="127.0.0.1",
        created_at=CURRENT_TIME,
    )

    result = DashboardService._request_item(
        request,
        details={
            "model_name": "scorecard",
            "task_type": "scoring",
            "model_version": "1.0.0",
            "deployment_id": "dep_test",
            "decision_id": "dcs_test",
            "prediction": prediction,
            "version_id": "ver_test",
        },
    )

    assert result["payload"] is request.payload
    assert result["batch_id"] == "bat_test"
    assert result["batch_index"] == 0
    assert result["prediction"] is prediction
    assert result["response"] is request.response
    assert result["version_id"] == "ver_test"
    assert result["model_name"] == "scorecard"
    assert result["task_type"] == "scoring"
    assert result["model_version"] == "1.0.0"
    assert result["deployment_id"] == "dep_test"
    assert result["decision_id"] == "dcs_test"
    assert result["error"] is None


def test_request_item_includes_failure_details() -> None:
    """测试失败 API 调用包含错误和请求中的部署 ID"""
    request = SimpleNamespace(
        request_id="req_failed",
        model_id=None,
        model_name="missing-model",
        payload={
            "model_name": "missing-model",
            "deployment_id": "dep_test",
            "features": {
                "age": 35
            },
        },
        response={
            "success": False,
            "error": "部署不存在: dep_test",
        },
        source="http",
        status="failed",
        error="部署不存在: dep_test",
        latency_ms=12.5,
        user="alice",
        ip="127.0.0.1",
        created_at=CURRENT_TIME,
    )

    result = DashboardService._request_item(
        request
    )

    assert result["error"] == "部署不存在: dep_test"
    assert result["response"] == {
        "success": False,
        "error": "部署不存在: dep_test",
    }
    assert result["deployment_id"] == "dep_test"
    assert result["model_id"] is None
    assert result["model_name"] == "missing-model"
    assert result["prediction"] is None


def test_batch_item_includes_progress_and_payload() -> None:
    """测试批次摘要包含进度、请求负载和执行结果"""
    batch = SimpleNamespace(
        batch_id="bat_test",
        task_id="tsk_test",
        model_id="mdl_test",
        model_name="scorecard",
        deployment_id=None,
        environment="development",
        status="partially_succeeded",
        payload={"model_name": "scorecard", "instances": [{"features": {}}]},
        result={"success": False, "predictions": []},
        error=None,
        total_count=2,
        completed_count=2,
        succeeded_count=1,
        failed_count=1,
        attempt_count=2,
        cancel_requested_at=None,
        started_at=CURRENT_TIME,
        finished_at=CURRENT_TIME,
        source="http",
        user="alice",
        ip="127.0.0.1",
        created_at=CURRENT_TIME,
        updated_at=CURRENT_TIME,
    )

    deployments = [{
        "deployment_id": "dep_primary",
        "execution_type": "primary",
        "model_name": "scorecard",
        "model_version": "1.0.0",
        "execution_count": 2,
    }, {
        "deployment_id": "dep_shadow",
        "execution_type": "shadow",
        "model_name": "scorecard",
        "model_version": "2.0.0",
        "execution_count": 2,
    }]
    result = DashboardService._batch_item(
        batch,
        deployments=deployments,
    )

    assert result["batch_id"] == "bat_test"
    assert result["status"] == "partially_succeeded"
    assert result["total_count"] == 2
    assert result["succeeded_count"] == 1
    assert result["failed_count"] == 1
    assert result["attempt_count"] == 2
    assert result["retry_count"] == 1
    assert result["deployments"] == deployments
    assert result["payload"] is batch.payload
    assert result["result"] is batch.result


def test_decision_item_includes_trace_and_route_details() -> None:
    """测试决策摘要包含追踪、预测、路由和模型执行信息"""
    prediction = {"probability": 0.25, "score": 680}
    shadow_prediction = {"score": 675}
    decision = SimpleNamespace(
        decision_id="dcs_test",
        request_id="req_test",
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        experiment_id="exp_test",
        variant_id=None,
        assignment_id=None,
        subject_key="customer_10001",
        subject_type="customer",
        source="routing",
        strategy="weighted",
        bucket="bucket_1000",
        group=None,
        weight=0.7,
        decision=None,
        context={
            "routing_id": "rtn_test"
        },
        decided_at=CURRENT_TIME,
    )

    result = DashboardService._decision_item(
        decision,
        details={
            "model_name": "scorecard",
            "model_version": "1.0.0",
            "experiment_name": "credit-policy",
            "variant_name": "treatment",
            "variant_is_control": False,
            "variant_weight": 0.5,
            "deployment_role": "challenger",
            "deployment_rollout_type": "canary",
            "routing_id": "rtn_test",
            "routing_name": "scorecard-route",
            "routing_weight": 0.9,
            "prediction": prediction,
            "probability": 0.25,
            "score": 680.0,
            "latency_ms": 18.5,
        },
        executions=[
            {
                "execution": SimpleNamespace(
                    execution_id="exe_shadow",
                    decision_id="dcs_test",
                    execution_type="shadow",
                    status="success",
                    model_id="mdl_test",
                    version_id="ver_shadow",
                    deployment_id="dep_shadow",
                    routing_id="rtn_shadow",
                    prediction=shadow_prediction,
                    probability=0.27,
                    score=675.0,
                    latency_ms=12.5,
                    error_type=None,
                    error=None,
                    context={
                        "source": "shadow"
                    },
                    started_at=CURRENT_TIME,
                    finished_at=CURRENT_TIME,
                    created_at=CURRENT_TIME,
                ),
                "model_name": "scorecard",
                "model_version": "2.0.0",
                "routing_name": "scorecard-shadow-route",
                "routing_weight": 1.0,
            }
        ],
    )

    assert result["decision_id"] == "dcs_test"
    assert result["request_id"] == "req_test"
    assert result["model_name"] == "scorecard"
    assert result["model_version"] == "1.0.0"
    assert result["experiment_id"] == "exp_test"
    assert result["experiment_name"] == "credit-policy"
    assert result["variant_name"] == "treatment"
    assert result["variant_is_control"] is False
    assert result["variant_weight"] == 0.5
    assert result["deployment_role"] == "challenger"
    assert result["routing_id"] == "rtn_test"
    assert result["routing_name"] == "scorecard-route"
    assert result["routing_weight"] == 0.9
    assert result["prediction"] is prediction
    assert result["context"] == {
        "routing_id": "rtn_test"
    }
    assert result["executions"][0]["execution_id"] == "exe_shadow"
    assert result["executions"][0]["request_id"] == "req_test"
    assert result["executions"][0]["execution_type"] == "shadow"
    assert result["executions"][0]["model_version"] == "2.0.0"
    assert result["executions"][0]["routing_name"] == "scorecard-shadow-route"
    assert result["executions"][0]["routing_weight"] == 1.0
    assert result["executions"][0]["score"] == 675.0
    assert result["executions"][0]["prediction"] is shadow_prediction
    assert result["decided_at"] == "2026-08-05T01:30:00.000Z"
