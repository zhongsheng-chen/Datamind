# datamind/services/dashboard.py

"""管理控制台查询服务

聚合模型、版本、部署、路由、运行状态、API 调用、决策、实验和审计记录，
生成只读控制台快照。

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
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    AuditRepository,
    DashboardRepository,
    DecisionRepository,
    DeploymentRepository,
    ExperimentRepository,
    MetadataRepository,
    RequestRepository,
    RoutingRepository,
    RuntimeRepository,
    VariantRepository,
    VersionRepository,
)
from datamind.utils.datetime import format_iso_utc


_SECTION_PERMISSIONS = {
    "models": "model.read",
    "versions": "model.read",
    "deployments": "deployment.read",
    "routings": "routing.read",
    "runtimes": "runtime.read",
    "requests": "request.read",
    "decisions": "request.read",
    "experiments": "experiment.read",
    "audits": "audit.read",
}


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
        trend_start = (
            current_time.replace(
                minute=0,
                second=0,
                microsecond=0,
            )
            - timedelta(
                hours=23
            )
        )
        request_trend: list[dict[str, Any]] = []

        async with UnitOfWork() as uow:
            dashboard_repo = DashboardRepository(
                uow.session
            )
            counts = await dashboard_repo.get_counts(
                visible_sections
            )

            if access["requests"]:
                trend_records = await dashboard_repo.get_request_trend(
                    since=trend_start,
                )
                request_trend = self._build_request_trend(
                    records=trend_records,
                    start=trend_start,
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
                visible_model_ids = {
                    model.model_id
                    for model in models
                }

                for version in versions:
                    if version.model_id not in visible_model_ids:
                        continue

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
                    )
                    for model in models
                ]

            if access["versions"]:
                sections["versions"] = [
                    self._version_item(
                        version
                    )
                    for version in versions[:limit]
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
                sections["routings"] = [
                    self._routing_item(
                        routing
                    )
                    for routing in routings
                ]

            if access["runtimes"]:
                runtimes = await RuntimeRepository(
                    uow.session
                ).list_runtimes(
                    limit=limit,
                )
                sections["runtimes"] = [
                    self._runtime_item(runtime)
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
                decision_labels = (
                    await dashboard_repo.get_decision_labels(
                        decision.decision_id
                        for decision in decisions
                    )
                )
                sections["decisions"] = [
                    self._decision_item(
                        decision,
                        labels=decision_labels.get(
                            decision.decision_id
                        ),
                    )
                    for decision in decisions
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
                sections["experiments"] = [
                    self._experiment_item(
                        experiment,
                        variant_count=variant_counts.get(
                            experiment.experiment_id,
                            0,
                        ),
                    )
                    for experiment in experiments
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

        return {
            "generated_at": format_iso_utc(
                current_time
            ),
            "limit": limit,
            "access": access,
            "counts": counts,
            "request_trend": request_trend,
            "sections": sections,
        }

    async def get_model_versions(
            self,
            *,
            model_id: str,
            page: int = 1,
            page_size: int = 10,
            query: str = "",
            sort_by: str | None = None,
            sort_order: str = "asc",
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
        limit = page_size + 1
        offset = (page - 1) * page_size

        async with UnitOfWork() as uow:
            model = await MetadataRepository(
                uow.session
            ).get_model(
                model_id=model_id,
            )
            if (
                    normalized_query
                    or normalized_sort_by is not None
            ):
                versions = await DashboardRepository(
                    uow.session
                ).search_records(
                    section="versions",
                    query=normalized_query,
                    model_id=model_id,
                    limit=limit,
                    offset=offset,
                    sort_by=normalized_sort_by,
                    sort_order=normalized_sort_order,
                )
            else:
                versions = await VersionRepository(
                    uow.session
                ).list_versions(
                    model_id=model_id,
                    include_archived=True,
                    limit=limit,
                    offset=offset,
                )

        has_next = len(versions) > page_size

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
                    version
                )
                for version in versions[:page_size]
            ],
            "page": page,
            "page_size": page_size,
            "query": normalized_query,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "has_previous": page > 1,
            "has_next": has_next,
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
        limit = page_size + 1
        offset = (page - 1) * page_size

        async with UnitOfWork() as uow:
            experiment = await ExperimentRepository(
                uow.session
            ).get_experiment(
                experiment_id
            )

            if experiment is None:
                raise ValueError(
                    f"实验不存在: {experiment_id}"
                )

            if (
                    normalized_query
                    or normalized_sort_by is not None
            ):
                variants = await DashboardRepository(
                    uow.session
                ).search_variants(
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

        return {
            "experiment": {
                "experiment_id": experiment.experiment_id,
                "name": experiment.name,
            },
            "items": [
                self._variant_item(
                    variant
                )
                for variant in variants[:page_size]
            ],
            "page": page,
            "page_size": page_size,
            "query": normalized_query,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "has_previous": page > 1,
            "has_next": len(variants) > page_size,
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
    ) -> dict[str, Any]:
        """获取控制台页面分页数据"""
        if section not in _SECTION_PERMISSIONS:
            raise ValueError(
                f"不支持的控制台页面: {section}"
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
        limit = page_size + 1
        offset = (page - 1) * page_size

        async with UnitOfWork() as uow:
            dashboard_repo = DashboardRepository(
                uow.session
            )

            if (
                    normalized_query
                    or normalized_sort_by is not None
                    or section in {
                        "deployments",
                        "experiments",
                    }
            ):
                records = await dashboard_repo.search_records(
                    section=section,
                    query=normalized_query,
                    limit=limit,
                    offset=offset,
                    sort_by=normalized_sort_by,
                    sort_order=normalized_sort_order,
                )
            else:
                records = await self._list_section_records(
                    uow.session,
                    section=section,
                    limit=limit,
                    offset=offset,
                )

            if section == "models":
                page_records = records[:page_size]
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
                visible_model_ids = {
                    model.model_id
                    for model in page_records
                }

                for version in versions:
                    if version.model_id not in visible_model_ids:
                        continue

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
                    )
                    for model in page_records
                ]
            elif section == "versions":
                items = [
                    self._version_item(
                        version
                    )
                    for version in records[:page_size]
                ]
            elif section == "deployments":
                page_records = records[:page_size]
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
                items = [
                    self._routing_item(
                        routing
                    )
                    for routing in records[:page_size]
                ]
            elif section == "runtimes":
                items = [
                    self._runtime_item(
                        runtime
                    )
                    for runtime in records[:page_size]
                ]
            elif section == "requests":
                page_records = records[:page_size]
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
                page_records = records[:page_size]
                decision_labels = (
                    await dashboard_repo.get_decision_labels(
                        decision.decision_id
                        for decision in page_records
                    )
                )
                items = [
                    self._decision_item(
                        decision,
                        labels=decision_labels.get(
                            decision.decision_id
                        ),
                    )
                    for decision in page_records
                ]
            elif section == "experiments":
                page_records = records[:page_size]
                variant_counts = (
                    await dashboard_repo.get_variant_counts(
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
                    )
                    for experiment in page_records
                ]
            else:
                items = [
                    self._audit_item(
                        audit
                    )
                    for audit in records[:page_size]
                ]

        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "query": normalized_query,
            "sort_by": normalized_sort_by,
            "sort_order": normalized_sort_order,
            "has_previous": page > 1,
            "has_next": len(records) > page_size,
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
            "experiments": ExperimentRepository(
                session
            ).list_experiments,
            "audits": AuditRepository(
                session
            ).list_audits,
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
    def _normalize_sort(
            *,
            sort_by: str | None,
            sort_order: str,
    ) -> tuple[str | None, str]:
        """规范化控制台排序参数"""
        normalized_sort_by = (
            sort_by.strip()
            if sort_by is not None
            else None
        )
        normalized_sort_by = normalized_sort_by or None
        normalized_sort_order = sort_order.strip().lower()

        if normalized_sort_order not in {
            "asc",
            "desc",
        }:
            raise ValueError(
                "sort_order 只支持 asc 或 desc"
            )

        return (
            normalized_sort_by,
            normalized_sort_order,
        )

    @staticmethod
    def _build_request_trend(
            *,
            records: Iterable[dict[str, Any]],
            start: datetime,
    ) -> list[dict[str, Any]]:
        """补齐最近 24 小时的 API 调用趋势"""
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

        for hour in range(24):
            current = start + timedelta(
                hours=hour
            )
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
    def _model_item(
            model: Any,
            *,
            versions: Iterable[Any],
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
            "model_type": model.model_type,
            "task_type": model.task_type,
            "framework": model.framework,
            "status": model.status,
            "latest_version": (
                version_items[0]["version"]
                if version_items
                else None
            ),
            "versions": version_items,
            "updated_at": format_iso_utc(
                model.updated_at
            ),
        }

    @staticmethod
    def _version_item(
            version: Any,
    ) -> dict[str, Any]:
        """转换模型版本摘要"""
        return {
            "version_id": version.version_id,
            "model_id": version.model_id,
            "version": version.version,
            "framework": version.framework,
            "artifact_revision": version.artifact_revision,
            "status": version.status,
            "updated_at": format_iso_utc(
                version.updated_at
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
            "updated_at": format_iso_utc(
                deployment.updated_at
            ),
        }

    @staticmethod
    def _routing_item(
            routing: Any,
    ) -> dict[str, Any]:
        """转换路由摘要"""
        return {
            "routing_id": routing.routing_id,
            "deployment_id": routing.deployment_id,
            "environment": routing.environment,
            "rollout_type": routing.rollout_type,
            "rollout_group": routing.rollout_group,
            "status": (
                "enabled"
                if bool(
                    routing.enabled
                )
                else "disabled"
            ),
            "traffic_ratio": routing.traffic_ratio,
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

        return {
            "request_id": request.request_id,
            "model_id": request.model_id,
            "model_name": request_details.get(
                "model_name"
            ),
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
            labels: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """转换决策记录摘要"""
        decision_labels = labels or {}

        return {
            "decision_id": decision.decision_id,
            "request_id": decision.request_id,
            "model_id": decision.model_id,
            "model_name": decision_labels.get(
                "model_name"
            ),
            "version_id": decision.version_id,
            "model_version": decision_labels.get(
                "model_version"
            ),
            "deployment_id": decision.deployment_id,
            "experiment_id": decision.experiment_id,
            "variant_id": decision.variant_id,
            "assignment_id": decision.assignment_id,
            "subject_key": decision.subject_key,
            "subject_type": decision.subject_type,
            "source": decision.source,
            "strategy": decision.strategy,
            "bucket": decision.bucket,
            "group": decision.group,
            "weight": decision.weight,
            "prediction": decision.prediction,
            "probability": decision.probability,
            "score": decision.score,
            "decision": decision.decision,
            "latency_ms": decision.latency_ms,
            "context": decision.context,
            "decided_at": format_iso_utc(
                decision.decided_at
            ),
        }

    @staticmethod
    def _runtime_item(
            runtime: Any,
    ) -> dict[str, Any]:
        """转换运行状态摘要"""
        return {
            "runtime_id": runtime.runtime_id,
            "deployment_id": runtime.deployment_id,
            "worker_id": runtime.worker_id,
            "framework": runtime.framework,
            "status": runtime.status,
            "last_heartbeat_at": format_iso_utc(
                runtime.last_heartbeat_at
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
    ) -> dict[str, Any]:
        """转换实验摘要"""
        return {
            "experiment_id": experiment.experiment_id,
            "model_id": experiment.model_id,
            "name": experiment.name,
            "environment": experiment.environment,
            "status": experiment.status,
            "effective_from": format_iso_utc(
                experiment.effective_from
            ),
            "effective_to": format_iso_utc(
                experiment.effective_to
            ),
            "updated_at": format_iso_utc(
                experiment.updated_at
            ),
            "variant_count": variant_count,
        }

    @staticmethod
    def _variant_item(
            variant: Any,
    ) -> dict[str, Any]:
        """转换实验分组摘要"""
        return {
            "variant_id": variant.variant_id,
            "experiment_id": variant.experiment_id,
            "name": variant.name,
            "deployment_id": variant.deployment_id,
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
            "occurred_at": format_iso_utc(
                audit.occurred_at
            ),
        }
