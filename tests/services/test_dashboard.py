# tests/services/test_dashboard.py

"""管理控制台查询服务测试

验证控制台数据按权限查询、转换并限制返回数量。

核心功能：
  - test_snapshot_only_queries_authorized_sections: 验证按权限查询数据
  - test_snapshot_serializes_authorized_records: 验证控制台记录转换
  - test_snapshot_rejects_invalid_limit: 验证返回数量限制
  - test_get_section_returns_page: 验证控制台页面分页
  - test_get_model_versions_returns_page: 验证模型版本分页
  - test_get_experiment_variants_returns_page: 验证实验分组分页
  - test_request_item_includes_failure_details: 验证失败调用详情
"""

from datetime import (
    datetime,
    timezone,
)
from types import SimpleNamespace
from unittest.mock import (
    AsyncMock,
    MagicMock,
)

import pytest

import datamind.services.dashboard as dashboard_module
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
        "DashboardRepository": MagicMock(),
        "DeploymentRepository": MagicMock(),
        "RoutingRepository": MagicMock(),
        "RuntimeRepository": MagicMock(),
        "RequestRepository": MagicMock(),
        "DecisionRepository": MagicMock(),
        "ExperimentRepository": MagicMock(),
        "VariantRepository": MagicMock(),
        "AuditRepository": MagicMock(),
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
    repositories["DashboardRepository"].get_counts = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].search_records = AsyncMock(
        return_value=[]
    )
    repositories["DashboardRepository"].get_deployment_labels = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_request_details = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_decision_labels = AsyncMock(
        return_value={}
    )
    repositories["DashboardRepository"].get_request_trend = AsyncMock(
        return_value=[]
    )
    repositories["DashboardRepository"].get_variant_counts = AsyncMock(
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
    ].get_counts.assert_awaited_once_with([
        "models",
        "versions",
        "runtimes",
    ])
    repositories[
        "VersionRepository"
    ].list_versions.assert_not_awaited()
    repositories["RuntimeRepository"].list_runtimes.assert_awaited_once_with(
        limit=10,
    )
    repositories["RequestRepository"].list_requests.assert_not_awaited()
    repositories[
        "DashboardRepository"
    ].get_request_trend.assert_not_awaited()
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
            "experiments": 0,
        "audits": 33,
    }

    result = await DashboardService().snapshot(
        permissions=["*"],
    )

    repositories[
        "VersionRepository"
    ].list_versions.assert_awaited_once_with(
        include_archived=True,
    )

    assert result["sections"]["models"][0] == {
        "model_id": "mdl_test",
        "name": "scorecard",
        "model_type": "logistic_regression",
        "task_type": "scoring",
        "framework": "sklearn",
        "status": "active",
        "latest_version": "1.0.0",
        "versions": [
            {
                "version_id": "ver_test",
                "model_id": "mdl_test",
                "version": "1.0.0",
                "framework": "sklearn",
                "artifact_revision": 2,
                "status": "active",
                "updated_at": "2026-08-05T01:30:00.000Z",
            }
        ],
        "updated_at": "2026-08-05T01:30:00.000Z",
    }
    assert result["sections"]["audits"][0]["action"] == "model.activate"
    assert result["sections"]["routings"][0] == {
        "routing_id": "rtn_test",
        "deployment_id": "dep_test",
        "environment": "production",
        "rollout_type": "canary",
        "rollout_group": "challenger",
        "status": "enabled",
        "traffic_ratio": 0.1,
        "updated_at": "2026-08-05T01:30:00.000Z",
    }
    assert result["sections"]["versions"][0]["version_id"] == "ver_test"
    repositories[
        "DashboardRepository"
    ].get_request_trend.assert_awaited_once()
    assert len(result["request_trend"]) == 24
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
        "experiments": 0,
        "audits": 33,
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
    """测试模型版本分页多取一条判断下一页"""
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
        for index in range(3)
    ]
    repositories[
        "VersionRepository"
    ].list_versions.return_value = versions
    repositories[
        "MetadataRepository"
    ].get_model.return_value = SimpleNamespace(
        name="scorecard"
    )

    result = await DashboardService().get_model_versions(
        model_id="mdl_test",
        page=2,
        page_size=2,
    )

    repositories[
        "VersionRepository"
    ].list_versions.assert_awaited_once_with(
        model_id="mdl_test",
        include_archived=True,
        limit=3,
        offset=2,
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
    assert result["has_previous"] is True
    assert result["has_next"] is True


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
        )
    )
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
        for index in range(1, 3)
    ]

    result = await DashboardService().get_experiment_variants(
        experiment_id="exp_test",
        page_size=1,
    )

    repositories["VariantRepository"].list_variants.assert_awaited_once_with(
        experiment_id="exp_test",
        limit=2,
        offset=0,
    )
    assert result["experiment"] == {
        "experiment_id": "exp_test",
        "name": "credit-policy",
    }
    assert result["items"][0]["group_type"] == "对照组"
    assert result["items"][0]["experiment_id"] == "exp_test"
    assert result["items"][0]["config"] == {
        "group": "group-1"
    }
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
        limit=11,
        offset=0,
        sort_by="weight",
        sort_order="desc",
    )
    repositories["VariantRepository"].list_variants.assert_not_awaited()
    assert result["query"] == "control"
    assert result["sort_by"] == "weight"
    assert result["sort_order"] == "desc"


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
                status="loaded",
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
        "deployments",
        "experiments",
    }

    if uses_dashboard_query:
        repositories[
            "DashboardRepository"
        ].search_records.return_value = [
            record,
            record,
        ]
    else:
        method.return_value = [
            record,
            record,
        ]

    result = await DashboardService().get_section(
        section=section,
        page=2,
        page_size=1,
    )

    expected_arguments = {
        "limit": 2,
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
        repositories[
            "DashboardRepository"
        ].search_records.assert_awaited_once_with(
            section=section,
            query="",
            limit=2,
            offset=1,
            sort_by=None,
            sort_order="asc",
        )
        method.assert_not_awaited()
    else:
        method.assert_awaited_once_with(
            **expected_arguments
        )
    assert result["items"][0][identifier] == getattr(
        record,
        identifier,
    )
    assert result["has_previous"] is True
    assert result["has_next"] is True


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

    result = await DashboardService().get_section(
        section="versions",
        query="  score  ",
    )

    repositories[
        "DashboardRepository"
    ].search_records.assert_awaited_once_with(
        section="versions",
        query="score",
        limit=11,
        offset=0,
        sort_by=None,
        sort_order="asc",
    )
    repositories[
        "VersionRepository"
    ].list_versions.assert_not_awaited()
    assert result["query"] == "score"
    assert result["items"][0]["version_id"] == "ver_test"


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
        limit=11,
        offset=0,
        sort_by="version",
        sort_order="desc",
    )
    repositories[
        "VersionRepository"
    ].list_versions.assert_not_awaited()
    assert result["sort_by"] == "version"
    assert result["sort_order"] == "desc"


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
    assert result["updated_at"] == "2026-08-05T01:30:00.000Z"
    assert "created_at" not in result


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
    assert result["updated_at"] == "2026-08-05T01:30:00.000Z"


def test_request_item_includes_model_and_decision_details() -> None:
    """测试 API 调用摘要包含模型、决策和预测详情"""
    request = SimpleNamespace(
        request_id="req_test",
        model_id="mdl_test",
        payload={
            "features": {
                "age": 35
            }
        },
        response={
            "success": True,
            "score": 680,
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
            "model_version": "1.0.0",
            "deployment_id": "dep_test",
            "decision_id": "dcs_test",
            "prediction": {
                "score": 680
            },
        },
    )

    assert result["payload"] == {
        "features": {
            "age": 35
        }
    }
    assert result["prediction"] == {
        "score": 680
    }
    assert result["response"] == {
        "success": True,
        "score": 680,
    }
    assert result["model_name"] == "scorecard"
    assert result["model_version"] == "1.0.0"
    assert result["deployment_id"] == "dep_test"
    assert result["decision_id"] == "dcs_test"
    assert result["error"] is None


def test_request_item_includes_failure_details() -> None:
    """测试失败 API 调用包含错误和请求中的部署 ID"""
    request = SimpleNamespace(
        request_id="req_failed",
        model_id="mdl_not_exists",
        payload={
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
    assert result["prediction"] is None


def test_decision_item_includes_trace_and_route_details() -> None:
    """测试决策摘要包含追踪、预测和路由信息"""
    decision = SimpleNamespace(
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
            "probability": 0.25,
            "score": 680,
        },
        probability=0.25,
        score=680.0,
        decision=None,
        latency_ms=18.5,
        context={
            "routing_id": "rtn_test"
        },
        decided_at=CURRENT_TIME,
    )

    result = DashboardService._decision_item(
        decision,
        labels={
            "model_name": "scorecard",
            "model_version": "1.0.0",
        },
    )

    assert result["decision_id"] == "dcs_test"
    assert result["request_id"] == "req_test"
    assert result["model_name"] == "scorecard"
    assert result["model_version"] == "1.0.0"
    assert result["prediction"] == {
        "probability": 0.25,
        "score": 680,
    }
    assert result["context"] == {
        "routing_id": "rtn_test"
    }
    assert result["decided_at"] == "2026-08-05T01:30:00.000Z"
