# datamind/services/dashboard.py

"""管理控制台查询服务

聚合模型、版本、部署、路由、运行状态、API 调用、决策、执行、实验和审计记录，
生成控制台快照和分页查询结果。

核心功能：
  - get_access: 获取控制台数据访问范围
  - snapshot: 获取当前用户可查看的控制台数据
  - get_section: 获取控制台页面分页数据
  - get_model_versions: 获取模型版本分页数据
  - get_experiment_variants: 获取实验分组分页数据

使用示例：
  snapshot = await DashboardService().snapshot(
      permissions=["model.read", "deployment.read"]
  )
"""

from collections.abc import Iterable
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

from datamind.auth.permissions import has_permission
from datamind.constants.identity import (
    BUILTIN_ROLE_NAMES,
    SYSTEM_BOOTSTRAP_ACTOR,
)
from datamind.constants.permissions import (
    SUPPORTED_PERMISSIONS,
)
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    AuditRepository,
    DashboardRepository,
    DecisionRepository,
    DeploymentRepository,
    ExecutionRepository,
    ExperimentRepository,
    MetadataRepository,
    RequestRepository,
    RoutingRepository,
    RoleRepository,
    RuntimeRepository,
    ScorecardRepository,
    UserRepository,
    VariantRepository,
    VersionRepository,
)
from datamind.runtime.presence import RuntimePresence
from datamind.utils.datetime import format_iso_utc
from datamind.utils.sorting import (
    encode_sort_specs,
    parse_sort_specs,
)


_SECTION_PERMISSIONS = {
    "models": "model.read",
    "versions": "model.read",
    "deployments": "deployment.read",
    "routings": "routing.read",
    "runtimes": "runtime.read",
    "requests": "request.read",
    "decisions": "request.read",
    "executions": "request.read",
    "experiments": "experiment.read",
    "variants": "experiment.read",
    "audits": "audit.read",
    "users": "identity.manage",
    "roles": "identity.manage",
}
_RECYCLE_SECTIONS = {
    "models",
    "versions",
    "deployments",
    "routings",
    "experiments",
    "variants",
}

_REQUEST_TREND_PERIODS = {
    "1h": (
        timedelta(hours=1),
        timedelta(minutes=1),
        "1 minute",
    ),
    "24h": (
        timedelta(hours=24),
        timedelta(minutes=5),
        "5 minutes",
    ),
    "7d": (
        timedelta(days=7),
        timedelta(hours=1),
        "1 hour",
    ),
    "30d": (
        timedelta(days=30),
        timedelta(days=1),
        "1 day",
    ),
}
_REQUEST_TREND_ORIGIN = datetime(
    2000,
    1,
    1,
    tzinfo=timezone.utc,
)


def _runtime_activity_at(
        runtime: Any,
) -> datetime | None:
    """返回用于判断运行实例在线状态的最近活动时间"""
    if str(runtime.status) == "running":
        return (
            getattr(runtime, "last_heartbeat_at", None)
            or getattr(runtime, "updated_at", None)
        )

    return getattr(runtime, "updated_at", None)


class DashboardService:
    """管理控制台查询服务"""

    @staticmethod
    def get_access(
            permissions: Iterable[str],
    ) -> dict[str, bool]:
        """获取当前用户的控制台数据访问范围"""
        granted = tuple(
            permissions
        )

        return {
            section: has_permission(
                granted_permissions=granted,
                required_permission=permission,
            )
            for section, permission in _SECTION_PERMISSIONS.items()
        }

    async def snapshot(
            self,
            *,
            permissions: Iterable[str],
            limit: int = 20,
            trend_range: str = "24h",
    ) -> dict[str, Any]:
        """获取当前用户可查看的控制台数据"""
        if limit <= 0 or limit > 100:
            raise ValueError(
                "limit 必须在 1 到 100 之间"
            )

        access = self.get_access(
            permissions
        )
        visible_sections = [
            section
            for section, allowed in access.items()
            if allowed
        ]
        sections: dict[str, list[dict[str, Any]]] = {}
        versions: list[Any] = []
        current_time = datetime.now(
            timezone.utc
        )
        runtime_presence = RuntimePresence.current(
            current_time=current_time
        )
        period_start = current_time - timedelta(
            hours=24
        )
        (
            trend_start,
            trend_step,
            trend_interval,
            trend_points,
        ) = self._resolve_request_trend_period(
            current_time=current_time,
            trend_range=trend_range,
        )
        request_trend: list[dict[str, Any]] = []
        request_summary: dict[str, Any] | None = None
        model_usage: list[dict[str, Any]] = []

        async with UnitOfWork() as uow:
            dashboard_repo = DashboardRepository(
                uow.session
            )
            counts = await dashboard_repo.get_counts(
                visible_sections,
                presence=runtime_presence,
            )

            if access["requests"]:
                request_metrics = await dashboard_repo.get_request_metrics(
                    since=period_start,
                    previous_since=(
                        period_start - timedelta(
                            hours=24
                        )
                    ),
                )
                request_summary = self._build_request_summary(
                    request_metrics
                )
                trend_records = await dashboard_repo.get_request_trend(
                    since=trend_start,
                    interval=trend_step,
                    origin=_REQUEST_TREND_ORIGIN,
                )
                request_trend = self._build_request_trend(
                    records=trend_records,
                    start=trend_start,
                    step=trend_step,
                    points=trend_points,
                )
                usage_records = (
                    await dashboard_repo.get_model_request_stats(
                        since=period_start,
                    )
                )
                model_usage = self._build_model_usage(
                    usage_records
                )

            if access["models"]:
                models = await MetadataRepository(
                    uow.session
                ).list_models(
                    include_archived=True,
                    limit=limit,
                )
                versions = (
                    await VersionRepository(
                        uow.session
                    ).list_versions(
                        include_archived=True,
                    )
                    if models
                    else []
                )
                versions_by_model: dict[str, list[Any]] = {}
                version_counts: dict[str, int] = {}
                visible_model_ids = {
                    model.model_id
                    for model in models
                }

                for version in versions:
                    if version.model_id not in visible_model_ids:
                        continue

                    version_counts[version.model_id] = (
                        version_counts.get(
                            version.model_id,
                            0,
                        )
                        + 1
                    )

                    model_versions = versions_by_model.setdefault(
                        version.model_id,
                        [],
                    )

                    if len(model_versions) < 10:
                        model_versions.append(
                            version
                        )

                sections["models"] = [
                    self._model_item(
                        model,
                        versions=versions_by_model.get(
                            model.model_id,
                            [],
                        ),
                        version_count=version_counts.get(
                            model.model_id,
                            0,
                        ),
                    )
                    for model in models
                ]

            if access["versions"]:
                version_page = versions[:limit]
                version_labels = (
                    await dashboard_repo.get_version_labels(
                        version.version_id
                        for version in version_page
                    )
                )
                sections["versions"] = [
                    self._version_item(
                        version,
                        labels=version_labels.get(
                            version.version_id
                        ),
                    )
                    for version in version_page
                ]

            if access["deployments"]:
                deployments = await DeploymentRepository(
                    uow.session
                ).list_deployments(
                    limit=limit,
                )
                deployment_labels = (
                    await dashboard_repo.get_deployment_labels(
                        deployment.deployment_id
                        for deployment in deployments
                    )
                )
                sections["deployments"] = [
                    self._deployment_item(
                        deployment,
                        labels=deployment_labels.get(
                            deployment.deployment_id
                        ),
                    )
                    for deployment in deployments
                ]

            if access["routings"]:
                routings = await RoutingRepository(
                    uow.session
                ).list_routings(
                    limit=limit,
                )
                routing_labels = (
                    await dashboard_repo.get_deployment_labels(
                        routing.deployment_id
                        for routing in routings
                    )
                )
                sections["routings"] = [
                    self._routing_item(
                        routing,
                        labels=routing_labels.get(
                            routing.deployment_id
                        ),
                    )
                    for routing in routings
                ]

            if access["runtimes"]:
                runtimes = await dashboard_repo.search_records(
                    section="runtimes",
                    query="",
                    limit=limit,
                    offset=0,
                    presence=runtime_presence,
                )
                runtime_labels = (
                    await dashboard_repo.get_deployment_labels(
                        runtime.deployment_id
                        for runtime in runtimes
                    )
                )
                sections["runtimes"] = [
                    self._runtime_item(
                        runtime,
                        labels=runtime_labels.get(
                            runtime.deployment_id
                        ),
                        presence=runtime_presence,
                    )
                    for runtime in runtimes
                ]

            if access["requests"]:
                requests = await RequestRepository(
                    uow.session
                ).list_requests(
                    limit=limit,
                )
                request_details = (
                    await dashboard_repo.get_request_details(
                        request.request_id
                        for request in requests
                    )
                )
                sections["requests"] = [
                    self._request_item(
                        request,
                        details=request_details.get(
                            request.request_id
                        ),
                    )
                    for request in requests
                ]

            if access["decisions"]:
                decisions = await DecisionRepository(
                    uow.session
                ).list_decisions(
                    limit=limit,
                )
                decision_details = (
                    await dashboard_repo.get_decision_details(
                        decision.decision_id
                        for decision in decisions
                    )
                )
                decision_executions = (
                    await dashboard_repo.get_decision_executions(
                        decision.decision_id
                        for decision in decisions
                    )
                )
                sections["decisions"] = [
                    self._decision_item(
                        decision,
                        details=decision_details.get(
                            decision.decision_id
                        ),
                        executions=decision_executions.get(
                            decision.decision_id,
                            [],
                        ),
                    )
                    for decision in decisions
                ]

            if access["executions"]:
                executions = await dashboard_repo.search_records(
                    section="executions",
                    query="",
                    limit=limit,
                    offset=0,
                )
                execution_details = (
                    await dashboard_repo.get_execution_details(
                        execution.execution_id
                        for execution in executions
                    )
                )
                sections["executions"] = [
                    self._execution_item(
                        execution,
                        details=execution_details.get(
                            execution.execution_id
                        ),
                    )
                    for execution in executions
                ]

            if access["experiments"]:
                experiments = await ExperimentRepository(
                    uow.session
                ).list_experiments(
                    limit=limit,
                )
                variant_counts = (
                    await dashboard_repo.get_variant_counts(
                        experiment.experiment_id
                        for experiment in experiments
                    )
                )
                experiment_labels = (
                    await dashboard_repo.get_experiment_labels(
                        experiment.experiment_id
                        for experiment in experiments
                    )
                )
                sections["experiments"] = [
                    self._experiment_item(
                        experiment,
                        variant_count=variant_counts.get(
                            experiment.experiment_id,
                            0,
                        ),
                        labels=experiment_labels.get(
                            experiment.experiment_id
                        ),
                    )
                    for experiment in experiments
                ]

            if access["variants"]:
                variants = await VariantRepository(
                    uow.session
                ).list_variants(
                    limit=limit,
                )
                variant_labels = (
                    await dashboard_repo.get_variant_labels(
                        variant.variant_id
                        for variant in variants
                    )
                )
                sections["variants"] = [
                    self._variant_item(
                        variant,
                        labels=variant_labels.get(
                            variant.variant_id
                        ),
                    )
                    for variant in variants
                ]

            if access["audits"]:
                audits = await AuditRepository(
                    uow.session
                ).list_audits(
                    limit=limit,
                )
                sections["audits"] = [
                    self._audit_item(audit)
                    for audit in audits
                ]

            if access["users"]:
                users = await UserRepository(
                    uow.session
                ).list_users(
                    limit=limit,
                )
                user_roles = await dashboard_repo.get_user_roles(
                    user.user_id
                    for user in users
                )
                sections["users"] = [
                    self._user_item(
                        user,
                        roles=user_roles.get(
                            user.user_id,
                            [],
                        ),
                    )
                    for user in users
                    if user.deleted_at is None
                ]

            if access["roles"]:
                roles = await RoleRepository(
                    uow.session
                ).list_roles(
                    limit=limit,
                )
                sections["roles"] = [
                    self._role_item(role)
                    for role in roles
                    if role.deleted_at is None
                ]

        return {
            "generated_at": format_iso_utc(
                current_time
            ),
            "limit": limit,
            "access": access,
            "counts": counts,
            "request_summary": request_summary,
            "request_trend": request_trend,
            "request_trend_range": trend_range,
            "request_trend_interval": trend_interval,
            "model_usage": model_usage,
            "sections": sections,
        }

    async def get_model_detail(
            self,
            *,
            model_id: str,
    ) -> dict[str, Any] | None:
        """获取模型详情"""
        if not model_id:
            raise ValueError(
                "model_id 不能为空"
            )

        async with UnitOfWork() as uow:
            model = await MetadataRepository(
                uow.session
            ).get_model(
                model_id=model_id
            )

            if model is None:
                return None

            versions = await VersionRepository(
                uow.session
            ).list_versions(
                model_id=model_id,
                include_archived=True,
            )

        return self._model_item(
            model,
            versions=versions,
            version_count=len(versions),
        )

    async def get_version_detail(
            self,
            *,
            version_id: str,
    ) -> dict[str, Any] | None:
        """获取模型版本详情"""
        if not version_id:
            raise ValueError(
                "version_id 不能为空"
            )

        async with UnitOfWork() as uow:
            version = await VersionRepository(
                uow.session
            ).get_version(
                version_id
            )

            if version is None:
                return None

            model = await MetadataRepository(
                uow.session
            ).get_model(
                model_id=version.model_id
            )
            scorecard = None
            if getattr(model, "task_type", None) == "scoring":
                scorecard = await ScorecardRepository(
                    uow.session
                ).get_scorecard(version_id)

        labels = {
            "model_name": getattr(
                model,
                "name",
                None,
            ),
            "display_name": getattr(
                model,
                "display_name",
                None,
            ),
            "model_type": getattr(
                model,
                "model_type",
                None,
            ),
            "task_type": getattr(
                model,
                "task_type",
                None,
            ),
        }
        item = self._version_item(
            version,
            labels=labels,
        )
        if scorecard is not None:
            item["scorecard"] = {
                "scorecard_id": scorecard.scorecard_id,
                "details_version": scorecard.details_version,
                "details": scorecard.details,
            }
        return item

    async def get_model_versions(
            self,
            *,
            model_id: str,
            page: int = 1,
            page_size: int = 10,
            query: str = "",
            sort_by: str | None = None,
            sort_order: str = "asc",
            record_ids: Iterable[str] | None = None,
            deleted: bool = False,
    ) -> dict[str, Any]:
        """获取模型版本分页数据"""
        if not model_id:
            raise ValueError(
                "model_id 不能为空"
            )

        if page < 1:
            raise ValueError(
                "page 必须大于等于 1"
            )

        if page_size < 1 or page_size > 100:
            raise ValueError(
                "page_size 必须在 1 到 100 之间"
            )

        normalized_query = self._normalize_query(
            query
        )
        normalized_sort_by, normalized_sort_order = self._normalize_sort(
            sort_by=sort_by,
            sort_order=sort_order,
        )
        normalized_record_ids = self._normalize_record_ids(
            record_ids
        )
        selection_arguments = (
            {
                "record_ids": normalized_record_ids,
            }
            if normalized_record_ids is not None
            else {}
        )
        limit = page_size
        offset = (page - 1) * page_size

        async with UnitOfWork() as uow:
            dashboard_repo = DashboardRepository(
                uow.session
            )
            model = await MetadataRepository(
                uow.session
            ).get_model(
                model_id=model_id,
            )
            total = await dashboard_repo.count_records(
                section="versions",
                query=normalized_query,
                model_id=model_id,
                only_deleted=deleted,
                **selection_arguments,
            )
            versions = await dashboard_repo.search_records(
                section="versions",
                query=normalized_query,
                model_id=model_id,
                limit=limit,
                offset=offset,
                sort_by=normalized_sort_by,
                sort_order=normalized_sort_order,
                only_deleted=deleted,
                **selection_arguments,
            )

        total_pages = max(
            1,
            (total + page_size - 1) // page_size,
        )

        return {
            "model": {
                "model_id": model_id,
                "name": (
                    model.name
                    if model is not None
                    else model_id
                ),
            },
            "items": [
                self._version_item(
                    version,
                    labels={
                        "model_name": (
                            model.name
                            if model is not None
                            else None
                        ),
                    },
                )
                for version in versions
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "query": normalized_query,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "deleted": deleted,
            "has_previous": page > 1,
            "has_next": page < total_pages,
        }

    async def get_experiment_variants(
            self,
            *,
            experiment_id: str,
            page: int = 1,
            page_size: int = 10,
            query: str = "",
            sort_by: str | None = None,
            sort_order: str = "asc",
            record_ids: Iterable[str] | None = None,
            deleted: bool = False,
    ) -> dict[str, Any]:
        """获取实验分组分页数据"""
        if not experiment_id:
            raise ValueError(
                "experiment_id 不能为空"
            )

        if page < 1:
            raise ValueError(
                "page 必须大于等于 1"
            )

        if page_size < 1 or page_size > 100:
            raise ValueError(
                "page_size 必须在 1 到 100 之间"
            )

        normalized_query = self._normalize_query(
            query
        )
        normalized_sort_by, normalized_sort_order = self._normalize_sort(
            sort_by=sort_by,
            sort_order=sort_order,
        )
        normalized_record_ids = self._normalize_record_ids(
            record_ids
        )
        selection_arguments = (
            {
                "record_ids": normalized_record_ids,
            }
            if normalized_record_ids is not None
            else {}
        )
        limit = page_size
        offset = (page - 1) * page_size

        async with UnitOfWork() as uow:
            dashboard_repo = DashboardRepository(
                uow.session
            )
            experiment = await ExperimentRepository(
                uow.session
            ).get_experiment(
                experiment_id
            )

            if experiment is None:
                raise ValueError(
                    f"实验不存在: {experiment_id}"
                )

            total = await dashboard_repo.count_records(
                section="variants",
                query=normalized_query,
                experiment_id=experiment_id,
                **({"only_deleted": True} if deleted else {}),
                **selection_arguments,
            )

            if deleted or normalized_record_ids is not None:
                variants = await dashboard_repo.search_records(
                    section="variants",
                    query=normalized_query,
                    experiment_id=experiment_id,
                    limit=limit,
                    offset=offset,
                    sort_by=normalized_sort_by,
                    sort_order=normalized_sort_order,
                    **({"only_deleted": True} if deleted else {}),
                    **selection_arguments,
                )
            elif normalized_query or normalized_sort_by is not None:
                variants = await dashboard_repo.search_variants(
                    experiment_id=experiment_id,
                    query=normalized_query,
                    limit=limit,
                    offset=offset,
                    sort_by=normalized_sort_by,
                    sort_order=normalized_sort_order,
                )
            else:
                variants = await VariantRepository(
                    uow.session
                ).list_variants(
                    experiment_id=experiment_id,
                    limit=limit,
                    offset=offset,
                )

            deployment_labels = (
                await dashboard_repo.get_deployment_labels(
                    variant.deployment_id
                    for variant in variants
                )
            )
            variant_labels = {
                variant.variant_id: {
                    **deployment_labels.get(
                        variant.deployment_id,
                        {},
                    ),
                    "experiment_name": experiment.name,
                    "experiment_status": experiment.status,
                }
                for variant in variants
            }

        total_pages = max(
            1,
            (total + page_size - 1) // page_size,
        )

        return {
            "experiment": {
                "experiment_id": experiment.experiment_id,
                "name": experiment.name,
            },
            "items": [
                self._variant_item(
                    variant,
                    labels=variant_labels.get(
                        variant.variant_id
                    ),
                )
                for variant in variants
            ],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "query": normalized_query,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "deleted": deleted,
            "has_previous": page > 1,
            "has_next": page < total_pages,
        }

    async def get_section(
            self,
            *,
            section: str,
            page: int = 1,
            page_size: int = 10,
            query: str = "",
            sort_by: str | None = None,
            sort_order: str = "asc",
            record_ids: Iterable[str] | None = None,
            deleted: bool = False,
    ) -> dict[str, Any]:
        """获取控制台页面分页数据"""
        if section not in _SECTION_PERMISSIONS:
            raise ValueError(
                f"不支持的控制台页面: {section}"
            )

        if deleted and section not in _RECYCLE_SECTIONS:
            raise ValueError(
                "deleted 仅支持可回收资源页面"
            )

        if page < 1:
            raise ValueError(
                "page 必须大于等于 1"
            )

        if page_size < 1 or page_size > 100:
            raise ValueError(
                "page_size 必须在 1 到 100 之间"
            )

        normalized_query = self._normalize_query(
            query
        )
        normalized_sort_by, normalized_sort_order = self._normalize_sort(
            sort_by=sort_by,
            sort_order=sort_order,
        )
        normalized_record_ids = self._normalize_record_ids(
            record_ids
        )
        selection_arguments = (
            {
                "record_ids": normalized_record_ids,
            }
            if normalized_record_ids is not None
            else {}
        )
        deletion_arguments = (
            {
                "only_deleted": deleted,
            }
            if section == "versions" or deleted
            else {}
        )
        runtime_presence = (
            RuntimePresence.current()
            if section == "runtimes"
            else None
        )
        runtime_arguments = (
            {"presence": runtime_presence}
            if runtime_presence is not None
            else {}
        )
        limit = page_size
        offset = (page - 1) * page_size

        async with UnitOfWork() as uow:
            dashboard_repo = DashboardRepository(
                uow.session
            )
            total = await dashboard_repo.count_records(
                section=section,
                query=normalized_query,
                **selection_arguments,
                **deletion_arguments,
                **runtime_arguments,
            )

            if (
                    normalized_query
                    or normalized_sort_by is not None
                    or normalized_record_ids is not None
                    or deleted
                    or section in {
                        "models",
                        "deployments",
                        "executions",
                        "experiments",
                        "versions",
                        "variants",
                        "users",
                        "roles",
                        "runtimes",
                    }
            ):
                records = await dashboard_repo.search_records(
                    section=section,
                    query=normalized_query,
                    limit=limit,
                    offset=offset,
                    sort_by=normalized_sort_by,
                    sort_order=normalized_sort_order,
                    **selection_arguments,
                    **deletion_arguments,
                    **runtime_arguments,
                )
            else:
                records = await self._list_section_records(
                    uow.session,
                    section=section,
                    limit=limit,
                    offset=offset,
                )

            if section == "models":
                page_records = records
                versions = (
                    await VersionRepository(
                        uow.session
                    ).list_versions(
                        include_archived=True,
                    )
                    if page_records
                    else []
                )
                versions_by_model: dict[str, list[Any]] = {}
                version_counts: dict[str, int] = {}
                visible_model_ids = {
                    model.model_id
                    for model in page_records
                }

                for version in versions:
                    if version.model_id not in visible_model_ids:
                        continue

                    version_counts[version.model_id] = (
                        version_counts.get(
                            version.model_id,
                            0,
                        )
                        + 1
                    )
                    model_versions = versions_by_model.setdefault(
                        version.model_id,
                        [],
                    )

                    if len(model_versions) < 10:
                        model_versions.append(
                            version
                        )

                items = [
                    self._model_item(
                        model,
                        versions=versions_by_model.get(
                            model.model_id,
                            [],
                        ),
                        version_count=version_counts.get(
                            model.model_id,
                            0,
                        ),
                    )
                    for model in page_records
                ]
            elif section == "versions":
                page_records = records
                version_labels = (
                    await dashboard_repo.get_version_labels(
                        version.version_id
                        for version in page_records
                    )
                )
                items = [
                    self._version_item(
                        version,
                        labels=version_labels.get(
                            version.version_id
                        ),
                    )
                    for version in page_records
                ]
            elif section == "deployments":
                page_records = records
                deployment_labels = (
                    await dashboard_repo.get_deployment_labels(
                        deployment.deployment_id
                        for deployment in page_records
                    )
                )
                items = [
                    self._deployment_item(
                        deployment,
                        labels=deployment_labels.get(
                            deployment.deployment_id
                        ),
                    )
                    for deployment in page_records
                ]
            elif section == "routings":
                page_records = records
                routing_labels = (
                    await dashboard_repo.get_deployment_labels(
                        routing.deployment_id
                        for routing in page_records
                    )
                )
                items = [
                    self._routing_item(
                        routing,
                        labels=routing_labels.get(
                            routing.deployment_id
                        ),
                    )
                    for routing in page_records
                ]
            elif section == "runtimes":
                page_records = records
                if runtime_presence is None:
                    raise RuntimeError(
                        "运行实例在线状态尚未初始化"
                    )
                runtime_labels = (
                    await dashboard_repo.get_deployment_labels(
                        runtime.deployment_id
                        for runtime in page_records
                    )
                )
                items = [
                    self._runtime_item(
                        runtime,
                        labels=runtime_labels.get(
                            runtime.deployment_id
                        ),
                        presence=runtime_presence,
                    )
                    for runtime in page_records
                ]
            elif section == "requests":
                page_records = records
                request_details = (
                    await dashboard_repo.get_request_details(
                        request.request_id
                        for request in page_records
                    )
                )
                items = [
                    self._request_item(
                        request,
                        details=request_details.get(
                            request.request_id
                        ),
                    )
                    for request in page_records
                ]
            elif section == "decisions":
                page_records = records
                decision_details = (
                    await dashboard_repo.get_decision_details(
                        decision.decision_id
                        for decision in page_records
                    )
                )
                decision_executions = (
                    await dashboard_repo.get_decision_executions(
                        decision.decision_id
                        for decision in page_records
                    )
                )
                items = [
                    self._decision_item(
                        decision,
                        details=decision_details.get(
                            decision.decision_id
                        ),
                        executions=decision_executions.get(
                            decision.decision_id,
                            [],
                        ),
                    )
                    for decision in page_records
                ]
            elif section == "executions":
                page_records = records
                execution_details = (
                    await dashboard_repo.get_execution_details(
                        execution.execution_id
                        for execution in page_records
                    )
                )
                items = [
                    self._execution_item(
                        execution,
                        details=execution_details.get(
                            execution.execution_id
                        ),
                    )
                    for execution in page_records
                ]
            elif section == "experiments":
                page_records = records
                variant_counts = (
                    await dashboard_repo.get_variant_counts(
                        experiment.experiment_id
                        for experiment in page_records
                    )
                )
                experiment_labels = (
                    await dashboard_repo.get_experiment_labels(
                        experiment.experiment_id
                        for experiment in page_records
                    )
                )
                items = [
                    self._experiment_item(
                        experiment,
                        variant_count=variant_counts.get(
                            experiment.experiment_id,
                            0,
                        ),
                        labels=experiment_labels.get(
                            experiment.experiment_id
                        ),
                    )
                    for experiment in page_records
                ]
            elif section == "variants":
                page_records = records
                variant_labels = (
                    await dashboard_repo.get_variant_labels(
                        variant.variant_id
                        for variant in page_records
                    )
                )
                items = [
                    self._variant_item(
                        variant,
                        labels=variant_labels.get(
                            variant.variant_id
                        ),
                    )
                    for variant in page_records
                ]
            elif section == "users":
                page_records = records
                user_roles = await dashboard_repo.get_user_roles(
                    user.user_id
                    for user in page_records
                )
                items = [
                    self._user_item(
                        user,
                        roles=user_roles.get(
                            user.user_id,
                            [],
                        ),
                    )
                    for user in page_records
                ]
            elif section == "roles":
                items = [
                    self._role_item(role)
                    for role in records
                ]
            else:
                items = [
                    self._audit_item(
                        audit
                    )
                    for audit in records
                ]

        total_pages = max(
            1,
            (total + page_size - 1) // page_size,
        )

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "query": normalized_query,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "deleted": deleted,
            "has_previous": page > 1,
            "has_next": page < total_pages,
        }

    @staticmethod
    async def _list_section_records(
            session: Any,
            *,
            section: str,
            limit: int,
            offset: int,
    ) -> list[Any]:
        """获取未使用关键词筛选的页面记录"""
        if section == "models":
            return await MetadataRepository(
                session
            ).list_models(
                include_archived=True,
                limit=limit,
                offset=offset,
            )

        if section == "versions":
            return await VersionRepository(
                session
            ).list_versions(
                include_archived=True,
                limit=limit,
                offset=offset,
            )

        repository_methods = {
            "deployments": DeploymentRepository(
                session
            ).list_deployments,
            "routings": RoutingRepository(
                session
            ).list_routings,
            "runtimes": RuntimeRepository(
                session
            ).list_runtimes,
            "requests": RequestRepository(
                session
            ).list_requests,
            "decisions": DecisionRepository(
                session
            ).list_decisions,
            "executions": ExecutionRepository(
                session
            ).list_executions,
            "experiments": ExperimentRepository(
                session
            ).list_experiments,
            "variants": VariantRepository(
                session
            ).list_variants,
            "audits": AuditRepository(
                session
            ).list_audits,
            "users": UserRepository(
                session
            ).list_users,
            "roles": RoleRepository(
                session
            ).list_roles,
        }

        return await repository_methods[section](
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _normalize_query(
            query: str,
    ) -> str:
        """规范化控制台查询关键词"""
        normalized_query = query.strip()

        if len(normalized_query) > 100:
            raise ValueError(
                "query 不能超过 100 个字符"
            )

        return normalized_query

    @staticmethod
    def _normalize_record_ids(
            record_ids: Iterable[str] | None,
    ) -> tuple[str, ...] | None:
        """规范化待导出的记录 ID"""
        if record_ids is None:
            return None

        identifiers = tuple(
            dict.fromkeys(
                record_ids
            )
        )

        if not identifiers:
            raise ValueError(
                "record_ids 不能为空"
            )

        if len(identifiers) > 10_000:
            raise ValueError(
                "record_ids 不能超过 10000 个"
            )

        if any(
                not identifier
                or len(identifier) > 128
                for identifier in identifiers
        ):
            raise ValueError(
                "record_ids 包含无效记录 ID"
            )

        return identifiers

    @staticmethod
    def _normalize_sort(
            *,
            sort_by: str | None,
            sort_order: str,
    ) -> tuple[str | None, str]:
        """规范化控制台排序参数"""
        return encode_sort_specs(
            parse_sort_specs(
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )

    @staticmethod
    def _resolve_request_trend_period(
            *,
            current_time: datetime,
            trend_range: str,
    ) -> tuple[datetime, timedelta, str, int]:
        """解析 API 调用趋势的时间范围和聚合粒度"""
        try:
            duration, step, interval = (
                _REQUEST_TREND_PERIODS[
                    trend_range
                ]
            )
        except KeyError as exc:
            raise ValueError(
                "trend_range 只支持 "
                "1h、24h、7d 或 30d"
            ) from exc

        elapsed = (
            current_time
            - _REQUEST_TREND_ORIGIN
        )
        completed_steps = elapsed // step
        current_bucket = (
            _REQUEST_TREND_ORIGIN
            + completed_steps * step
        )
        points = duration // step
        start = current_bucket - (
            points - 1
        ) * step

        return (
            start,
            step,
            interval,
            points,
        )

    @staticmethod
    def _build_request_trend(
            *,
            records: Iterable[dict[str, Any]],
            start: datetime,
            step: timedelta,
            points: int,
    ) -> list[dict[str, Any]]:
        """按指定粒度补齐 API 调用趋势"""
        counts: dict[datetime, dict[str, int]] = {}

        for record in records:
            bucket = record.get(
                "bucket"
            )

            if not isinstance(
                    bucket,
                    datetime,
            ):
                continue

            normalized_bucket = (
                bucket.replace(
                    tzinfo=timezone.utc
                )
                if bucket.tzinfo is None
                else bucket.astimezone(
                    timezone.utc
                )
            )
            counts[normalized_bucket] = {
                "count": int(
                    record.get(
                        "count",
                        0,
                    )
                ),
                "success_count": int(
                    record.get(
                        "success_count",
                        0,
                    )
                ),
                "failed_count": int(
                    record.get(
                        "failed_count",
                        0,
                    )
                ),
            }

        trend: list[dict[str, Any]] = []

        for index in range(points):
            current = start + index * step
            bucket_counts = counts.get(
                current,
                {
                    "count": 0,
                    "success_count": 0,
                    "failed_count": 0,
                },
            )
            trend.append({
                "time": format_iso_utc(
                    current
                ),
                **bucket_counts,
            })

        return trend

    @staticmethod
    def _build_model_usage(
            records: Iterable[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """构建模型调用概况"""
        usage: list[dict[str, Any]] = []

        for record in records:
            recent_count = int(
                record.get(
                    "recent_count",
                    0,
                )
            )
            recent_success_count = int(
                record.get(
                    "recent_success_count",
                    0,
                )
            )
            recent_total_count = int(
                record.get(
                    "recent_total_count",
                    0,
                )
            )

            usage.append({
                "model_id": record["model_id"],
                "model_name": record.get(
                    "model_name"
                ),
                "recent_count": recent_count,
                "total_count": int(
                    record.get(
                        "total_count",
                        0,
                    )
                ),
                "success_rate": (
                    recent_success_count / recent_count
                    if recent_count > 0
                    else None
                ),
                "average_latency_ms": record.get(
                    "average_latency_ms"
                ),
                "request_share": (
                    recent_count / recent_total_count
                    if recent_total_count > 0
                    else None
                ),
            })

        return usage

    @staticmethod
    def _build_request_summary(
            metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """构建 API 调用核心指标"""
        request_count = int(
            metrics.get(
                "request_count",
                0,
            )
        )
        success_count = int(
            metrics.get(
                "success_count",
                0,
            )
        )
        previous_request_count = int(
            metrics.get(
                "previous_request_count",
                0,
            )
        )

        return {
            "request_count": request_count,
            "success_count": success_count,
            "failed_count": int(
                metrics.get(
                    "failed_count",
                    0,
                )
            ),
            "success_rate": (
                success_count / request_count
                if request_count > 0
                else None
            ),
            "average_latency_ms": metrics.get(
                "average_latency_ms"
            ),
            "p95_latency_ms": metrics.get(
                "p95_latency_ms"
            ),
            "previous_request_count": previous_request_count,
            "change_rate": (
                (
                    request_count
                    - previous_request_count
                ) / previous_request_count
                if previous_request_count > 0
                else None
            ),
        }

    @staticmethod
    def _model_item(
            model: Any,
            *,
            versions: Iterable[Any],
            version_count: int,
    ) -> dict[str, Any]:
        """转换模型摘要"""
        version_items = [
            DashboardService._version_item(
                version
            )
            for version in versions
        ]

        return {
            "model_id": model.model_id,
            "name": model.name,
            "display_name": getattr(
                model,
                "display_name",
                None,
            ),
            "model_type": model.model_type,
            "task_type": model.task_type,
            "framework": model.framework,
            "status": model.status,
            "description": getattr(
                model,
                "description",
                None,
            ),
            "created_by": getattr(
                model,
                "created_by",
                None,
            ),
            "updated_by": getattr(
                model,
                "updated_by",
                None,
            ),
            **DashboardService._deletion_fields(model),
            "latest_version": (
                version_items[0]["version"]
                if version_items
                else None
            ),
            "version_count": version_count,
            "versions": version_items,
            "created_at": format_iso_utc(
                getattr(
                    model,
                    "created_at",
                    None,
                )
            ),
            "updated_at": format_iso_utc(
                model.updated_at
            ),
        }

    @staticmethod
    def _version_item(
            version: Any,
            *,
            labels: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """转换模型版本摘要"""
        version_labels = labels or {}

        return {
            "version_id": version.version_id,
            "model_id": version.model_id,
            "model_name": version_labels.get(
                "model_name"
            ),
            "display_name": version_labels.get(
                "display_name"
            ),
            "model_type": version_labels.get(
                "model_type"
            ),
            "task_type": version_labels.get(
                "task_type"
            ),
            "version": version.version,
            "framework": version.framework,
            "artifact_revision": version.artifact_revision,
            "status": version.status,
            "current_artifact_id": getattr(
                version,
                "current_artifact_id",
                None,
            ),
            "artifact_sha256": getattr(
                version,
                "artifact_sha256",
                None,
            ),
            "artifact_digest": getattr(
                version,
                "artifact_digest",
                None,
            ),
            "bento_tag": getattr(
                version,
                "bento_tag",
                None,
            ),
            "model_key": getattr(
                version,
                "model_key",
                None,
            ),
            "description": getattr(
                version,
                "description",
                None,
            ),
            "created_by": getattr(
                version,
                "created_by",
                None,
            ),
            "updated_by": getattr(
                version,
                "updated_by",
                None,
            ),
            "deleted_by": getattr(
                version,
                "deleted_by",
                None,
            ),
            "deletion_reason": getattr(
                version,
                "deletion_reason",
                None,
            ),
            "deleted_at": format_iso_utc(
                getattr(
                    version,
                    "deleted_at",
                    None,
                )
            ),
            "created_at": format_iso_utc(
                getattr(
                    version,
                    "created_at",
                    None,
                )
            ),
            "updated_at": format_iso_utc(
                version.updated_at
            ),
        }

    @staticmethod
    def _deletion_fields(record: Any) -> dict[str, Any]:
        """转换逻辑删除审计字段"""
        return {
            "deleted_by": getattr(record, "deleted_by", None),
            "deletion_reason": getattr(
                record,
                "deletion_reason",
                None,
            ),
            "deleted_at": format_iso_utc(
                getattr(record, "deleted_at", None)
            ),
        }

    @staticmethod
    def _deployment_item(
            deployment: Any,
            *,
            labels: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """转换部署摘要"""
        deployment_labels = labels or {}

        return {
            "deployment_id": deployment.deployment_id,
            "model_name": deployment_labels.get(
                "model_name"
            ),
            "model_id": deployment.model_id,
            "model_version": deployment_labels.get(
                "model_version"
            ),
            "version_id": deployment.version_id,
            "environment": deployment.environment,
            "framework": deployment.framework,
            "rollout_type": deployment.rollout_type,
            "role": deployment.role,
            "status": deployment.status,
            "config": getattr(
                deployment,
                "config",
                None,
            ),
            "description": getattr(
                deployment,
                "description",
                None,
            ),
            "deployed_by": getattr(
                deployment,
                "deployed_by",
                None,
            ),
            "effective_from": format_iso_utc(
                getattr(
                    deployment,
                    "effective_from",
                    None,
                )
            ),
            "effective_to": format_iso_utc(
                getattr(
                    deployment,
                    "effective_to",
                    None,
                )
            ),
            **DashboardService._deletion_fields(deployment),
            "created_at": format_iso_utc(
                getattr(
                    deployment,
                    "created_at",
                    None,
                )
            ),
            "updated_at": format_iso_utc(
                deployment.updated_at
            ),
        }

    @staticmethod
    def _routing_item(
            routing: Any,
            *,
            labels: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """转换路由摘要"""
        routing_labels = labels or {}

        return {
            "routing_id": routing.routing_id,
            "name": routing.name,
            "deployment_id": routing.deployment_id,
            "model_id": routing_labels.get(
                "model_id"
            ),
            "version_id": routing_labels.get(
                "version_id"
            ),
            "model_name": routing_labels.get(
                "model_name"
            ),
            "model_version": routing_labels.get(
                "model_version"
            ),
            "environment": (
                routing_labels.get("environment")
                or routing.environment
            ),
            "rollout_type": (
                routing_labels.get("rollout_type")
                or routing.rollout_type
            ),
            "rollout_group": (
                routing_labels.get("rollout_group")
                or routing.rollout_group
            ),
            "status": (
                "enabled"
                if bool(
                    routing.enabled
                )
                else "disabled"
            ),
            "traffic_ratio": routing.traffic_ratio,
            "effective_from": format_iso_utc(
                getattr(routing, "effective_from", None)
            ),
            "effective_to": format_iso_utc(
                getattr(routing, "effective_to", None)
            ),
            "rules": getattr(
                routing,
                "rules",
                None,
            ),
            "description": getattr(
                routing,
                "description",
                None,
            ),
            "created_by": getattr(
                routing,
                "created_by",
                None,
            ),
            "updated_by": getattr(
                routing,
                "updated_by",
                None,
            ),
            **DashboardService._deletion_fields(routing),
            "created_at": format_iso_utc(
                getattr(
                    routing,
                    "created_at",
                    None,
                )
            ),
            "updated_at": format_iso_utc(
                routing.updated_at
            ),
        }

    @staticmethod
    def _request_item(
            request: Any,
            *,
            details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """转换 API 调用摘要"""
        request_details = details or {}
        payload = request.payload
        model_name = (
            request_details.get(
                "model_name"
            )
            or getattr(
                request,
                "model_name",
                None,
            )
        )
        deployment_id = request_details.get(
            "deployment_id"
        )

        if (
                deployment_id is None
                and isinstance(
                    payload,
                    dict,
                )
        ):
            deployment_id = payload.get(
                "deployment_id"
            )

        if (
                model_name is None
                and isinstance(
                    payload,
                    dict,
                )
        ):
            model_name = payload.get(
                "model_name"
            )

        return {
            "request_id": request.request_id,
            "model_id": request.model_id,
            "model_name": model_name,
            "model_version": request_details.get(
                "model_version"
            ),
            "deployment_id": deployment_id,
            "decision_id": request_details.get(
                "decision_id"
            ),
            "payload": payload,
            "response": getattr(
                request,
                "response",
                None,
            ),
            "prediction": request_details.get(
                "prediction"
            ),
            "source": request.source,
            "status": request.status,
            "error": request.error,
            "latency_ms": request.latency_ms,
            "user": request.user,
            "ip": request.ip,
            "created_at": format_iso_utc(
                request.created_at
            ),
        }

    @staticmethod
    def _decision_item(
            decision: Any,
            *,
            details: dict[str, Any] | None = None,
            executions: Iterable[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        """转换决策记录摘要"""
        decision_details = details or {}
        decision_context = decision.context or {}

        return {
            "decision_id": decision.decision_id,
            "request_id": decision.request_id,
            "model_id": decision.model_id,
            "model_name": decision_details.get(
                "model_name"
            ),
            "version_id": decision.version_id,
            "model_version": decision_details.get(
                "model_version"
            ),
            "deployment_id": decision.deployment_id,
            "experiment_id": decision.experiment_id,
            "experiment_name": decision_details.get(
                "experiment_name"
            ),
            "variant_id": decision.variant_id,
            "variant_name": decision_details.get(
                "variant_name"
            ),
            "variant_is_control": decision_details.get(
                "variant_is_control"
            ),
            "variant_weight": decision_details.get(
                "variant_weight"
            ),
            "assignment_id": decision.assignment_id,
            "subject_key": decision.subject_key,
            "subject_type": decision.subject_type,
            "source": decision.source,
            "strategy": decision.strategy,
            "bucket": decision.bucket,
            "group": decision.group,
            "weight": decision.weight,
            "deployment_role": decision_details.get(
                "deployment_role"
            ),
            "deployment_rollout_type": decision_details.get(
                "deployment_rollout_type"
            ),
            "routing_id": (
                decision_details.get("routing_id")
                or decision_context.get("routing_id")
            ),
            "routing_name": decision_details.get(
                "routing_name"
            ),
            "routing_weight": decision_details.get(
                "routing_weight"
            ),
            "prediction": decision_details.get(
                "prediction"
            ),
            "probability": decision_details.get(
                "probability"
            ),
            "score": decision_details.get(
                "score"
            ),
            "decision": decision.decision,
            "latency_ms": decision_details.get(
                "latency_ms"
            ),
            "context": decision.context,
            "executions": [
                DashboardService._execution_item(
                    item["execution"],
                    details=item,
                    request_id=decision.request_id,
                )
                for item in executions
            ],
            "decided_at": format_iso_utc(
                decision.decided_at
            ),
        }

    @staticmethod
    def _execution_item(
            execution: Any,
            *,
            details: dict[str, Any] | None = None,
            request_id: str | None = None,
    ) -> dict[str, Any]:
        """转换模型执行记录摘要"""
        execution_details = details or {}

        return {
            "execution_id": execution.execution_id,
            "decision_id": execution.decision_id,
            "request_id": (
                request_id
                if request_id is not None
                else execution_details.get(
                    "request_id"
                )
            ),
            "execution_type": execution.execution_type,
            "status": execution.status,
            "model_id": execution.model_id,
            "model_name": execution_details.get(
                "model_name"
            ),
            "version_id": execution.version_id,
            "model_version": execution_details.get(
                "model_version"
            ),
            "deployment_id": execution.deployment_id,
            "routing_id": execution.routing_id,
            "routing_name": execution_details.get(
                "routing_name"
            ),
            "routing_weight": execution_details.get(
                "routing_weight"
            ),
            "prediction": execution.prediction,
            "probability": execution.probability,
            "score": execution.score,
            "latency_ms": execution.latency_ms,
            "error_type": execution.error_type,
            "error": execution.error,
            "context": execution.context,
            "started_at": format_iso_utc(
                execution.started_at
            ),
            "finished_at": format_iso_utc(
                execution.finished_at
            ),
            "created_at": format_iso_utc(
                execution.created_at
            ),
        }

    @staticmethod
    def _runtime_item(
            runtime: Any,
            *,
            labels: dict[str, str | None] | None = None,
            presence: RuntimePresence,
    ) -> dict[str, Any]:
        """转换运行状态摘要"""
        runtime_labels = labels or {}
        status = str(runtime.status)
        health_status = presence.health_status(
            status=status,
            activity_at=_runtime_activity_at(runtime),
        )

        return {
            "runtime_id": runtime.runtime_id,
            "deployment_id": runtime.deployment_id,
            "worker_id": runtime.worker_id,
            "framework": runtime.framework,
            "status": status,
            "health_status": str(health_status),
            "model_id": getattr(
                runtime,
                "model_id",
                None,
            ),
            "model_name": runtime_labels.get(
                "model_name"
            ),
            "version_id": getattr(
                runtime,
                "version_id",
                None,
            ),
            "model_version": runtime_labels.get(
                "model_version"
            ),
            "role": runtime_labels.get(
                "rollout_group"
            ),
            "loaded_at": format_iso_utc(
                getattr(
                    runtime,
                    "loaded_at",
                    None,
                )
            ),
            "unloaded_at": format_iso_utc(
                getattr(
                    runtime,
                    "unloaded_at",
                    None,
                )
            ),
            "started_by": getattr(
                runtime,
                "started_by",
                None,
            ),
            "stopped_by": getattr(
                runtime,
                "stopped_by",
                None,
            ),
            "error": getattr(
                runtime,
                "error",
                None,
            ),
            "context": getattr(
                runtime,
                "context",
                None,
            ),
            "applied_generation": getattr(
                runtime,
                "applied_generation",
                None,
            ),
            "last_heartbeat_at": format_iso_utc(
                runtime.last_heartbeat_at
            ),
            "created_at": format_iso_utc(
                getattr(
                    runtime,
                    "created_at",
                    None,
                )
            ),
            "updated_at": format_iso_utc(
                runtime.updated_at
            ),
        }

    @staticmethod
    def _experiment_item(
            experiment: Any,
            *,
            variant_count: int = 0,
            labels: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """转换实验摘要"""
        experiment_labels = labels or {}

        return {
            "experiment_id": experiment.experiment_id,
            "model_id": experiment.model_id,
            "model_name": experiment_labels.get(
                "model_name"
            ),
            "name": experiment.name,
            "environment": experiment.environment,
            "status": experiment.status,
            "description": getattr(
                experiment,
                "description",
                None,
            ),
            "config": getattr(
                experiment,
                "config",
                None,
            ),
            "created_by": getattr(
                experiment,
                "created_by",
                None,
            ),
            "updated_by": getattr(
                experiment,
                "updated_by",
                None,
            ),
            "effective_from": format_iso_utc(
                experiment.effective_from
            ),
            "effective_to": format_iso_utc(
                experiment.effective_to
            ),
            **DashboardService._deletion_fields(experiment),
            "created_at": format_iso_utc(
                getattr(
                    experiment,
                    "created_at",
                    None,
                )
            ),
            "updated_at": format_iso_utc(
                experiment.updated_at
            ),
            "variant_count": variant_count,
        }

    @staticmethod
    def _variant_item(
            variant: Any,
            *,
            labels: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """转换实验分组摘要"""
        variant_labels = labels or {}

        return {
            "variant_id": variant.variant_id,
            "experiment_id": variant.experiment_id,
            "experiment_name": variant_labels.get(
                "experiment_name"
            ),
            "experiment_status": variant_labels.get(
                "experiment_status"
            ),
            "name": variant.name,
            "deployment_id": variant.deployment_id,
            "model_name": variant_labels.get(
                "model_name"
            ),
            "model_version": variant_labels.get(
                "model_version"
            ),
            "weight": variant.weight,
            "is_control": variant.is_control,
            "group_type": (
                "对照组"
                if bool(
                    variant.is_control
                )
                else "实验组"
            ),
            "status": variant.status,
            "config": variant.config,
            "description": variant.description,
            "created_by": variant.created_by,
            "updated_by": variant.updated_by,
            **DashboardService._deletion_fields(variant),
            "created_at": format_iso_utc(
                variant.created_at
            ),
            "updated_at": format_iso_utc(
                variant.updated_at
            ),
        }

    @staticmethod
    def _audit_item(
            audit: Any,
    ) -> dict[str, Any]:
        """转换审计摘要"""
        return {
            "audit_id": audit.audit_id,
            "action": audit.action,
            "target_type": audit.target_type,
            "target_id": audit.target_id,
            "source": audit.source,
            "user": audit.user,
            "status": audit.status,
            "resource": getattr(
                audit,
                "resource",
                None,
            ),
            "operation": getattr(
                audit,
                "operation",
                None,
            ),
            "trace_id": getattr(
                audit,
                "trace_id",
                None,
            ),
            "request_id": getattr(
                audit,
                "request_id",
                None,
            ),
            "ip": getattr(
                audit,
                "ip",
                None,
            ),
            "hostname": getattr(
                audit,
                "hostname",
                None,
            ),
            "error": getattr(
                audit,
                "error",
                None,
            ),
            "before": getattr(
                audit,
                "before",
                None,
            ),
            "after": getattr(
                audit,
                "after",
                None,
            ),
            "context": getattr(
                audit,
                "context",
                None,
            ),
            "occurred_at": format_iso_utc(
                audit.occurred_at
            ),
        }

    @staticmethod
    def _user_item(
            user: Any,
            *,
            roles: Iterable[str],
    ) -> dict[str, Any]:
        """转换用户摘要"""
        return {
            "user_id": user.user_id,
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "status": user.status,
            "is_builtin": (
                user.created_by
                == SYSTEM_BOOTSTRAP_ACTOR
            ),
            "roles": list(roles),
            "last_login_at": format_iso_utc(
                user.last_login_at
            ),
            "created_at": format_iso_utc(
                user.created_at
            ),
            "updated_at": format_iso_utc(
                user.updated_at
            ),
        }

    @staticmethod
    def _role_item(
            role: Any,
    ) -> dict[str, Any]:
        """转换角色摘要"""
        permissions = role.permissions
        permission_items = (
            list(permissions)
            if isinstance(permissions, list)
            else []
        )
        effective_permissions = (
            sorted(SUPPORTED_PERMISSIONS)
            if "*" in permission_items
            else permission_items
        )

        return {
            "role_id": role.role_id,
            "name": role.name,
            "description": role.description,
            "is_builtin": (
                role.name in BUILTIN_ROLE_NAMES
            ),
            "permissions": permission_items,
            "effective_permissions": effective_permissions,
            "status": role.status,
            "created_at": format_iso_utc(
                role.created_at
            ),
            "updated_at": format_iso_utc(
                role.updated_at
            ),
        }
