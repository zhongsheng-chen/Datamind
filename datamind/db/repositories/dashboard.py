# datamind/db/repositories/dashboard.py

"""管理控制台查询仓储

提供管理控制台各数据页面的记录总数和关键词查询。

核心功能：
  - DashboardRepository.get_counts: 获取控制台页面记录总数
  - DashboardRepository.get_request_trend: 获取 API 调用趋势
  - DashboardRepository.get_variant_counts: 获取实验分组数量
  - DashboardRepository.search_records: 查询控制台页面记录
  - DashboardRepository.search_variants: 查询实验分组

使用示例：
  async with UnitOfWork() as uow:
      counts = await DashboardRepository(
          uow.session
      ).get_counts([
          "models",
          "deployments",
      ])
"""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import (
    func,
    or_,
    select,
)

from datamind.db.models import (
    Audit,
    Decision,
    Deployment,
    Experiment,
    Metadata,
    Request,
    Routing,
    Runtime,
    Variant,
    Version,
)
from datamind.db.repositories.base import BaseRepository


_SECTION_MODELS: dict[str, type[Any]] = {
    "models": Metadata,
    "versions": Version,
    "deployments": Deployment,
    "routings": Routing,
    "runtimes": Runtime,
    "requests": Request,
    "decisions": Decision,
    "experiments": Experiment,
    "audits": Audit,
}

_SECTION_SEARCH_COLUMNS: dict[str, tuple[Any, ...]] = {
    "models": (
        Metadata.model_id,
        Metadata.name,
        Metadata.framework,
        Metadata.model_type,
        Metadata.task_type,
        Metadata.status,
    ),
    "versions": (
        Version.version_id,
        Version.model_id,
        Version.version,
        Version.framework,
        Version.status,
    ),
    "deployments": (
        Deployment.deployment_id,
        Deployment.model_id,
        Deployment.version_id,
        Metadata.name,
        Version.version,
        Deployment.environment,
        Deployment.framework,
        Deployment.rollout_type,
        Deployment.role,
        Deployment.status,
    ),
    "routings": (
        Routing.routing_id,
        Routing.deployment_id,
        Routing.environment,
        Routing.rollout_type,
        Routing.rollout_group,
        Routing.description,
    ),
    "runtimes": (
        Runtime.runtime_id,
        Runtime.deployment_id,
        Runtime.model_id,
        Runtime.version_id,
        Runtime.worker_id,
        Runtime.framework,
        Runtime.status,
    ),
    "requests": (
        Request.request_id,
        Request.model_id,
        Request.source,
        Request.status,
        Request.user,
        Request.ip,
    ),
    "decisions": (
        Decision.decision_id,
        Decision.request_id,
        Decision.model_id,
        Decision.version_id,
        Decision.deployment_id,
        Metadata.name,
        Version.version,
        Decision.source,
        Decision.strategy,
        Decision.subject_key,
        Decision.subject_type,
        Decision.decision,
    ),
    "experiments": (
        Experiment.experiment_id,
        Experiment.model_id,
        Experiment.name,
        Experiment.environment,
        Experiment.status,
    ),
    "audits": (
        Audit.audit_id,
        Audit.action,
        Audit.target_type,
        Audit.target_id,
        Audit.user,
        Audit.source,
        Audit.status,
        Audit.request_id,
        Audit.trace_id,
    ),
}

_LATEST_VERSION = (
    select(
        Version.version
    )
    .where(
        Version.model_id
        == Metadata.model_id
    )
    .order_by(
        Version.created_at.desc()
    )
    .limit(1)
    .correlate(Metadata)
    .scalar_subquery()
)

_VARIANT_COUNT = (
    select(
        func.count()
    )
    .select_from(
        Variant
    )
    .where(
        Variant.experiment_id
        == Experiment.experiment_id
    )
    .correlate(
        Experiment
    )
    .scalar_subquery()
)

_SECTION_SORT_COLUMNS: dict[str, dict[str, Any]] = {
    "models": {
        "name": Metadata.name,
        "model_id": Metadata.model_id,
        "framework": Metadata.framework,
        "model_type": Metadata.model_type,
        "task_type": Metadata.task_type,
        "status": Metadata.status,
        "latest_version": _LATEST_VERSION,
        "versions": _LATEST_VERSION,
        "updated_at": Metadata.updated_at,
    },
    "versions": {
        "version": Version.version,
        "version_id": Version.version_id,
        "model_id": Version.model_id,
        "framework": Version.framework,
        "artifact_revision": Version.artifact_revision,
        "status": Version.status,
        "updated_at": Version.updated_at,
    },
    "deployments": {
        "deployment_id": Deployment.deployment_id,
        "model_name": Metadata.name,
        "model_id": Deployment.model_id,
        "model_version": Version.version,
        "version_id": Deployment.version_id,
        "environment": Deployment.environment,
        "framework": Deployment.framework,
        "rollout_type": Deployment.rollout_type,
        "role": Deployment.role,
        "status": Deployment.status,
        "updated_at": Deployment.updated_at,
    },
    "routings": {
        "routing_id": Routing.routing_id,
        "deployment_id": Routing.deployment_id,
        "environment": Routing.environment,
        "rollout_type": Routing.rollout_type,
        "rollout_group": Routing.rollout_group,
        "traffic_ratio": Routing.traffic_ratio,
        "status": Routing.enabled,
        "updated_at": Routing.updated_at,
    },
    "runtimes": {
        "runtime_id": Runtime.runtime_id,
        "deployment_id": Runtime.deployment_id,
        "worker_id": Runtime.worker_id,
        "framework": Runtime.framework,
        "status": Runtime.status,
        "last_heartbeat_at": Runtime.last_heartbeat_at,
        "updated_at": Runtime.updated_at,
    },
    "requests": {
        "request_id": Request.request_id,
        "model_id": Request.model_id,
        "payload": Request.payload,
        "prediction": Decision.prediction,
        "source": Request.source,
        "status": Request.status,
        "latency_ms": Request.latency_ms,
        "user": Request.user,
        "ip": Request.ip,
        "created_at": Request.created_at,
    },
    "decisions": {
        "decision_id": Decision.decision_id,
        "request_id": Decision.request_id,
        "model_name": Metadata.name,
        "model_version": Version.version,
        "deployment_id": Decision.deployment_id,
        "source": Decision.source,
        "strategy": Decision.strategy,
        "probability": Decision.probability,
        "score": Decision.score,
        "decision": Decision.decision,
        "decided_at": Decision.decided_at,
    },
    "experiments": {
        "name": Experiment.name,
        "experiment_id": Experiment.experiment_id,
        "model_id": Experiment.model_id,
        "environment": Experiment.environment,
        "status": Experiment.status,
        "effective_from": Experiment.effective_from,
        "effective_to": Experiment.effective_to,
        "updated_at": Experiment.updated_at,
        "variant_count": _VARIANT_COUNT,
    },
    "audits": {
        "action": Audit.action,
        "audit_id": Audit.audit_id,
        "target_type": Audit.target_type,
        "target_id": Audit.target_id,
        "user": Audit.user,
        "source": Audit.source,
        "status": Audit.status,
        "occurred_at": Audit.occurred_at,
    },
}

_SECTION_ORDER_COLUMNS: dict[str, tuple[Any, ...]] = {
    "models": (
        Metadata.updated_at.desc(),
        Metadata.created_at.desc(),
    ),
    "versions": (
        Version.created_at.desc(),
    ),
    "deployments": (
        Deployment.updated_at.desc(),
        Deployment.created_at.desc(),
    ),
    "routings": (
        Routing.updated_at.desc(),
        Routing.created_at.desc(),
    ),
    "runtimes": (
        Runtime.updated_at.desc(),
        Runtime.created_at.desc(),
    ),
    "requests": (
        Request.created_at.desc(),
    ),
    "decisions": (
        Decision.decided_at.desc(),
        Decision.created_at.desc(),
    ),
    "experiments": (
        Experiment.updated_at.desc(),
        Experiment.created_at.desc(),
    ),
    "audits": (
        Audit.occurred_at.desc(),
        Audit.created_at.desc(),
    ),
}


class DashboardRepository(BaseRepository):
    """管理控制台查询仓储"""

    async def get_counts(
            self,
            sections: Iterable[str],
    ) -> dict[str, int]:
        """获取指定控制台页面的记录总数"""
        selected_sections = tuple(
            dict.fromkeys(
                sections
            )
        )
        unsupported_sections = set(
            selected_sections
        ) - _SECTION_MODELS.keys()

        if unsupported_sections:
            raise ValueError(
                "不支持的控制台页面: "
                + ", ".join(
                    sorted(
                        unsupported_sections
                    )
                )
            )

        if not selected_sections:
            return {}

        stmt = select(*(
            select(
                func.count()
            )
            .select_from(
                _SECTION_MODELS[section]
            )
            .scalar_subquery()
            .label(
                section
            )
            for section in selected_sections
        ))
        result = await self.session.execute(
            stmt
        )
        row = result.mappings().one()

        return {
            section: int(
                row[section]
            )
            for section in selected_sections
        }

    async def search_records(
            self,
            *,
            section: str,
            query: str,
            limit: int,
            offset: int,
            model_id: str | None = None,
            sort_by: str | None = None,
            sort_order: str = "asc",
    ) -> list[Any]:
        """查询、排序并分页返回指定控制台页面记录"""
        if section not in _SECTION_MODELS:
            raise ValueError(
                f"不支持的控制台页面: {section}"
            )

        model = _SECTION_MODELS[section]
        stmt = select(
            model
        )

        if section == "deployments":
            stmt = (
                stmt
                .outerjoin(
                    Metadata,
                    Metadata.model_id
                    == Deployment.model_id,
                )
                .outerjoin(
                    Version,
                    Version.version_id
                    == Deployment.version_id,
                )
            )
        elif section == "requests":
            stmt = stmt.outerjoin(
                Decision,
                Decision.request_id
                == Request.request_id,
            )
        elif section == "decisions":
            stmt = (
                stmt
                .outerjoin(
                    Metadata,
                    Metadata.model_id
                    == Decision.model_id,
                )
                .outerjoin(
                    Version,
                    Version.version_id
                    == Decision.version_id,
                )
            )

        if query:
            escaped_query = (
                query
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped_query}%"
            stmt = stmt.where(
                or_(*(
                    column.ilike(
                        pattern,
                        escape="\\",
                    )
                    for column in _SECTION_SEARCH_COLUMNS[section]
                ))
            )

        if model_id is not None:
            if section != "versions":
                raise ValueError(
                    "model_id 仅支持模型版本查询"
                )

            stmt = stmt.where(
                Version.model_id == model_id
            )

        order_columns = _SECTION_ORDER_COLUMNS[section]

        if sort_by is not None:
            sort_columns = _SECTION_SORT_COLUMNS[
                section
            ]

            if sort_by not in sort_columns:
                raise ValueError(
                    f"不支持的排序字段: {sort_by}"
                )

            sort_column = sort_columns[
                sort_by
            ]

            if sort_order not in {
                "asc",
                "desc",
            }:
                raise ValueError(
                    "sort_order 只支持 asc 或 desc"
                )

            ordered_column = (
                sort_column.asc()
                if sort_order == "asc"
                else sort_column.desc()
            ).nulls_last()
            order_columns = (
                ordered_column,
                *order_columns,
            )

        stmt = stmt.order_by(
            *order_columns
        ).offset(offset).limit(limit)
        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def get_deployment_labels(
            self,
            deployment_ids: Iterable[str],
    ) -> dict[str, dict[str, str | None]]:
        """获取部署对应的模型名称和版本号"""
        identifiers = tuple(
            dict.fromkeys(
                deployment_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Deployment.deployment_id,
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Deployment.model_id,
            )
            .outerjoin(
                Version,
                Version.version_id
                == Deployment.version_id,
            )
            .where(
                Deployment.deployment_id.in_(
                    identifiers
                )
            )
        )
        result = await self.session.execute(
            stmt
        )

        return {
            row["deployment_id"]: {
                "model_name": row["model_name"],
                "model_version": row["model_version"],
            }
            for row in result.mappings().all()
        }

    async def get_request_details(
            self,
            request_ids: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        """获取 API 调用对应的模型和决策详情"""
        identifiers = tuple(
            dict.fromkeys(
                request_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Request.request_id,
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
                Decision.deployment_id,
                Decision.decision_id,
                Decision.prediction,
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Request.model_id,
            )
            .outerjoin(
                Decision,
                Decision.request_id
                == Request.request_id,
            )
            .outerjoin(
                Version,
                Version.version_id
                == Decision.version_id,
            )
            .where(
                Request.request_id.in_(
                    identifiers
                )
            )
        )
        result = await self.session.execute(
            stmt
        )

        return {
            row["request_id"]: {
                "model_name": row["model_name"],
                "model_version": row["model_version"],
                "deployment_id": row["deployment_id"],
                "decision_id": row["decision_id"],
                "prediction": row["prediction"],
            }
            for row in result.mappings().all()
        }

    async def get_decision_labels(
            self,
            decision_ids: Iterable[str],
    ) -> dict[str, dict[str, str | None]]:
        """获取决策对应的模型名称和版本号"""
        identifiers = tuple(
            dict.fromkeys(
                decision_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Decision.decision_id,
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Decision.model_id,
            )
            .outerjoin(
                Version,
                Version.version_id
                == Decision.version_id,
            )
            .where(
                Decision.decision_id.in_(
                    identifiers
                )
            )
        )
        result = await self.session.execute(
            stmt
        )

        return {
            row["decision_id"]: {
                "model_name": row["model_name"],
                "model_version": row["model_version"],
            }
            for row in result.mappings().all()
        }

    async def get_variant_counts(
            self,
            experiment_ids: Iterable[str],
    ) -> dict[str, int]:
        """获取实验对应的分组数量"""
        identifiers = tuple(
            dict.fromkeys(
                experiment_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Variant.experiment_id,
                func.count().label(
                    "variant_count"
                ),
            )
            .where(
                Variant.experiment_id.in_(
                    identifiers
                )
            )
            .group_by(
                Variant.experiment_id
            )
        )
        result = await self.session.execute(
            stmt
        )

        return {
            row["experiment_id"]: int(
                row["variant_count"]
            )
            for row in result.mappings().all()
        }

    async def search_variants(
            self,
            *,
            experiment_id: str,
            query: str,
            limit: int,
            offset: int,
            sort_by: str | None = None,
            sort_order: str = "asc",
    ) -> list[Variant]:
        """查询、排序并分页返回实验分组"""
        sort_columns = {
            "name": Variant.name,
            "variant_id": Variant.variant_id,
            "deployment_id": Variant.deployment_id,
            "weight": Variant.weight,
            "is_control": Variant.is_control,
            "status": Variant.status,
            "updated_at": Variant.updated_at,
        }
        stmt = select(
            Variant
        ).where(
            Variant.experiment_id
            == experiment_id
        )

        if query:
            escaped_query = (
                query
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped_query}%"
            stmt = stmt.where(
                or_(
                    Variant.name.ilike(
                        pattern,
                        escape="\\",
                    ),
                    Variant.variant_id.ilike(
                        pattern,
                        escape="\\",
                    ),
                    Variant.deployment_id.ilike(
                        pattern,
                        escape="\\",
                    ),
                    Variant.status.ilike(
                        pattern,
                        escape="\\",
                    ),
                )
            )

        if sort_by is not None:
            sort_column = sort_columns.get(
                sort_by
            )

            if sort_column is None:
                raise ValueError(
                    f"不支持的排序字段: {sort_by}"
                )

            order_column = (
                sort_column.desc()
                if sort_order == "desc"
                else sort_column.asc()
            )
            stmt = stmt.order_by(
                order_column.nulls_last(),
                Variant.variant_id.asc(),
            )
        else:
            stmt = stmt.order_by(
                Variant.updated_at.desc(),
                Variant.created_at.desc(),
            )

        stmt = stmt.offset(
            offset
        ).limit(
            limit
        )
        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    async def get_request_trend(
            self,
            *,
            since: datetime,
    ) -> list[dict[str, Any]]:
        """按小时获取指定时间后的 API 调用量"""
        bucket = func.date_trunc(
            "hour",
            Request.created_at,
        ).label(
            "bucket"
        )
        request_count = func.count().label(
            "request_count"
        )
        success_count = func.count().filter(
            Request.status == "success"
        ).label(
            "success_count"
        )
        failed_count = func.count().filter(
            Request.status == "failed"
        ).label(
            "failed_count"
        )
        stmt = (
            select(
                bucket,
                request_count,
                success_count,
                failed_count,
            )
            .where(
                Request.created_at >= since
            )
            .group_by(
                bucket
            )
            .order_by(
                bucket
            )
        )
        result = await self.session.execute(
            stmt
        )
        rows = result.mappings().all()

        return [
            {
                "bucket": row[
                    "bucket"
                ],
                "count": int(
                    row[
                        "request_count"
                    ]
                ),
                "success_count": int(
                    row[
                        "success_count"
                    ]
                ),
                "failed_count": int(
                    row[
                        "failed_count"
                    ]
                ),
            }
            for row in rows
        ]
