"""管理控制台查询仓储

提供管理控制台各数据页面的记录总数、关键词查询、字段化查询和时间范围查询。

核心功能：
  - DashboardRepository.get_counts: 获取控制台页面记录总数
  - DashboardRepository.count_records: 获取查询结果总数
  - DashboardRepository.get_request_metrics: 获取 API 调用核心指标
  - DashboardRepository.get_request_trend: 获取 API 调用趋势
  - DashboardRepository.get_model_request_stats: 获取模型调用统计
  - DashboardRepository.get_execution_details: 获取模型执行关联信息
  - DashboardRepository.get_decision_executions: 获取决策的模型执行
  - DashboardRepository.get_variant_counts: 获取实验分组数量
  - DashboardRepository.get_version_labels: 获取版本对应的模型名称
  - DashboardRepository.get_experiment_labels: 获取实验模型信息
  - DashboardRepository.get_variant_labels: 获取分组实验和模型信息
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

import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import Enum
from typing import Any

from sqlalchemy import (
    and_,
    case,
    func,
    or_,
    select,
)
from datamind.config import get_settings
from datamind.constants.runtime_status import (
    ACTIVE_RUNTIME_STATUSES,
    RuntimeHealthStatus,
)
from datamind.db.models import (
    Audit,
    Decision,
    Deployment,
    Execution,
    Experiment,
    Grant,
    Metadata,
    Request,
    Routing,
    Role,
    Runtime,
    User,
    Variant,
    Version,
)
from datamind.db.repositories.base import BaseRepository
from datamind.runtime.presence import RuntimePresence
from datamind.utils.datetime import get_timezone
from datamind.utils.sorting import parse_sort_specs


_REQUEST_MODEL_NAME = func.coalesce(
    Request.model_name,
    Metadata.name,
)


def _runtime_stale_predicate(
        presence: RuntimePresence,
) -> Any:
    """构建活动实例心跳过期条件。"""
    return or_(
        and_(
            Runtime.status.in_(("starting", "stopping")),
            Runtime.updated_at < presence.stale_at,
        ),
        and_(
            Runtime.status == "running",
            func.coalesce(
                Runtime.last_heartbeat_at,
                Runtime.updated_at,
            ) < presence.stale_at,
        ),
    )


def _runtime_active_predicate(
        presence: RuntimePresence,
) -> Any:
    """构建当前在线运行实例条件。"""
    return and_(
        Runtime.status.in_(ACTIVE_RUNTIME_STATUSES),
        ~_runtime_stale_predicate(presence),
    )


def _runtime_health_status_expression(
        presence: RuntimePresence,
) -> Any:
    """根据最近活动时间构建运行实例健康状态"""
    stale = _runtime_stale_predicate(presence)
    return case(
        (
            stale,
            RuntimeHealthStatus.UNHEALTHY.value,
        ),
        else_=RuntimeHealthStatus.HEALTHY.value,
    )


_SECTION_MODELS: dict[str, type[Any]] = {
    "models": Metadata,
    "versions": Version,
    "deployments": Deployment,
    "routings": Routing,
    "runtimes": Runtime,
    "requests": Request,
    "decisions": Decision,
    "executions": Execution,
    "experiments": Experiment,
    "variants": Variant,
    "audits": Audit,
    "users": User,
    "roles": Role,
}

_SECTION_DELETED_COLUMNS: dict[str, Any] = {
    "models": Metadata.deleted_at,
    "versions": Version.deleted_at,
    "deployments": Deployment.deleted_at,
    "routings": Routing.deleted_at,
    "experiments": Experiment.deleted_at,
    "variants": Variant.deleted_at,
    "users": User.deleted_at,
    "roles": Role.deleted_at,
}

_SECTION_ID_COLUMNS: dict[str, Any] = {
    "models": Metadata.model_id,
    "versions": Version.version_id,
    "deployments": Deployment.deployment_id,
    "routings": Routing.routing_id,
    "runtimes": Runtime.runtime_id,
    "requests": Request.request_id,
    "decisions": Decision.decision_id,
    "executions": Execution.execution_id,
    "experiments": Experiment.experiment_id,
    "variants": Variant.variant_id,
    "audits": Audit.audit_id,
    "users": User.user_id,
    "roles": Role.role_id,
}

class _QueryFieldType(str, Enum):
    """控制台查询字段类型"""

    TEXT = "text"
    DATETIME = "datetime"


@dataclass(
    frozen=True,
    slots=True,
)
class _QueryField:
    """控制台查询字段定义"""

    column: Any
    type: _QueryFieldType


def _text_field(
        column: Any,
) -> _QueryField:
    """定义文本查询字段"""
    return _QueryField(
        column=column,
        type=_QueryFieldType.TEXT,
    )


def _time_field(
        column: Any,
) -> _QueryField:
    """定义时间查询字段"""
    return _QueryField(
        column=column,
        type=_QueryFieldType.DATETIME,
    )


_SECTION_QUERY_FIELDS: dict[str, dict[str, _QueryField]] = {
    "models": {
        "model_id": _text_field(Metadata.model_id),
        "name": _text_field(Metadata.name),
        "display_name": _text_field(Metadata.display_name),
        "framework": _text_field(Metadata.framework),
        "model_type": _text_field(Metadata.model_type),
        "task_type": _text_field(Metadata.task_type),
        "status": _text_field(Metadata.status),
        "created_at": _time_field(Metadata.created_at),
        "updated_at": _time_field(Metadata.updated_at),
        "deleted_at": _time_field(Metadata.deleted_at),
        "restored_at": _time_field(Metadata.restored_at),
        "archived_at": _time_field(Metadata.archived_at),
    },
    "versions": {
        "version_id": _text_field(Version.version_id),
        "model_id": _text_field(Version.model_id),
        "model_name": _text_field(Metadata.name),
        "display_name": _text_field(Metadata.display_name),
        "model_version": _text_field(Version.version),
        "framework": _text_field(Version.framework),
        "status": _text_field(Version.status),
        "created_at": _time_field(Version.created_at),
        "updated_at": _time_field(Version.updated_at),
        "deleted_at": _time_field(Version.deleted_at),
        "restored_at": _time_field(Version.restored_at),
        "archived_at": _time_field(Version.archived_at),
    },
    "deployments": {
        "deployment_id": _text_field(Deployment.deployment_id),
        "model_id": _text_field(Deployment.model_id),
        "version_id": _text_field(Deployment.version_id),
        "model_name": _text_field(Metadata.name),
        "model_version": _text_field(Version.version),
        "environment": _text_field(Deployment.environment),
        "framework": _text_field(Deployment.framework),
        "rollout_type": _text_field(Deployment.rollout_type),
        "role": _text_field(Deployment.role),
        "status": _text_field(Deployment.status),
        "created_at": _time_field(Deployment.created_at),
        "updated_at": _time_field(Deployment.updated_at),
        "effective_from": _time_field(Deployment.effective_from),
        "effective_to": _time_field(Deployment.effective_to),
    },
    "routings": {
        "routing_id": _text_field(Routing.routing_id),
        "name": _text_field(Routing.name),
        "deployment_id": _text_field(Routing.deployment_id),
        "model_id": _text_field(Deployment.model_id),
        "version_id": _text_field(Deployment.version_id),
        "model_name": _text_field(Metadata.name),
        "model_version": _text_field(Version.version),
        "environment": _text_field(Routing.environment),
        "rollout_type": _text_field(Routing.rollout_type),
        "rollout_group": _text_field(Routing.rollout_group),
        "description": _text_field(Routing.description),
        "effective_from": _time_field(Routing.effective_from),
        "effective_to": _time_field(Routing.effective_to),
        "created_at": _time_field(Routing.created_at),
        "updated_at": _time_field(Routing.updated_at),
    },
    "runtimes": {
        "runtime_id": _text_field(Runtime.runtime_id),
        "deployment_id": _text_field(Runtime.deployment_id),
        "model_id": _text_field(Runtime.model_id),
        "version_id": _text_field(Runtime.version_id),
        "model_name": _text_field(Metadata.name),
        "model_version": _text_field(Version.version),
        "role": _text_field(Deployment.role),
        "worker_id": _text_field(Runtime.worker_id),
        "framework": _text_field(Runtime.framework),
        "status": _text_field(Runtime.status),
        "created_at": _time_field(Runtime.created_at),
        "updated_at": _time_field(Runtime.updated_at),
        "loaded_at": _time_field(Runtime.loaded_at),
        "unloaded_at": _time_field(Runtime.unloaded_at),
        "last_heartbeat_at": _time_field(Runtime.last_heartbeat_at),
    },
    "requests": {
        "request_id": _text_field(Request.request_id),
        "model_id": _text_field(Request.model_id),
        "model_name": _text_field(_REQUEST_MODEL_NAME),
        "task_type": _text_field(Metadata.task_type),
        "model_version": _text_field(Version.version),
        "source": _text_field(Request.source),
        "status": _text_field(Request.status),
        "user": _text_field(Request.user),
        "ip": _text_field(Request.ip),
        "created_at": _time_field(Request.created_at),
        "updated_at": _time_field(Request.updated_at),
    },
    "decisions": {
        "decision_id": _text_field(Decision.decision_id),
        "request_id": _text_field(Decision.request_id),
        "experiment_id": _text_field(Decision.experiment_id),
        "model_id": _text_field(Decision.model_id),
        "version_id": _text_field(Decision.version_id),
        "deployment_id": _text_field(Decision.deployment_id),
        "model_name": _text_field(Metadata.name),
        "model_version": _text_field(Version.version),
        "source": _text_field(Decision.source),
        "strategy": _text_field(Decision.strategy),
        "subject_key": _text_field(Decision.subject_key),
        "subject_type": _text_field(Decision.subject_type),
        "decision": _text_field(Decision.decision),
        "created_at": _time_field(Decision.created_at),
        "updated_at": _time_field(Decision.updated_at),
        "decided_at": _time_field(Decision.decided_at),
    },
    "executions": {
        "execution_id": _text_field(Execution.execution_id),
        "decision_id": _text_field(Execution.decision_id),
        "request_id": _text_field(Decision.request_id),
        "model_id": _text_field(Execution.model_id),
        "version_id": _text_field(Execution.version_id),
        "deployment_id": _text_field(Execution.deployment_id),
        "model_name": _text_field(Metadata.name),
        "model_version": _text_field(Version.version),
        "execution_type": _text_field(Execution.execution_type),
        "status": _text_field(Execution.status),
        "error_type": _text_field(Execution.error_type),
        "error": _text_field(Execution.error),
        "created_at": _time_field(Execution.created_at),
        "updated_at": _time_field(Execution.updated_at),
        "started_at": _time_field(Execution.started_at),
        "finished_at": _time_field(Execution.finished_at),
    },
    "experiments": {
        "experiment_id": _text_field(Experiment.experiment_id),
        "model_id": _text_field(Experiment.model_id),
        "name": _text_field(Experiment.name),
        "model_name": _text_field(Metadata.name),
        "environment": _text_field(Experiment.environment),
        "status": _text_field(Experiment.status),
        "created_at": _time_field(Experiment.created_at),
        "updated_at": _time_field(Experiment.updated_at),
        "effective_from": _time_field(Experiment.effective_from),
        "effective_to": _time_field(Experiment.effective_to),
    },
    "variants": {
        "variant_id": _text_field(Variant.variant_id),
        "experiment_id": _text_field(Variant.experiment_id),
        "experiment_name": _text_field(Experiment.name),
        "name": _text_field(Variant.name),
        "deployment_id": _text_field(Variant.deployment_id),
        "model_name": _text_field(Metadata.name),
        "model_version": _text_field(Version.version),
        "status": _text_field(Variant.status),
        "created_at": _time_field(Variant.created_at),
        "updated_at": _time_field(Variant.updated_at),
    },
    "audits": {
        "audit_id": _text_field(Audit.audit_id),
        "action": _text_field(Audit.action),
        "target_type": _text_field(Audit.target_type),
        "target_id": _text_field(Audit.target_id),
        "user": _text_field(Audit.user),
        "source": _text_field(Audit.source),
        "status": _text_field(Audit.status),
        "request_id": _text_field(Audit.request_id),
        "trace_id": _text_field(Audit.trace_id),
        "created_at": _time_field(Audit.created_at),
        "updated_at": _time_field(Audit.updated_at),
        "occurred_at": _time_field(Audit.occurred_at),
    },
    "users": {
        "user_id": _text_field(User.user_id),
        "username": _text_field(User.username),
        "display_name": _text_field(User.display_name),
        "email": _text_field(User.email),
        "status": _text_field(User.status),
        "created_at": _time_field(User.created_at),
        "updated_at": _time_field(User.updated_at),
        "deleted_at": _time_field(User.deleted_at),
        "last_login_at": _time_field(User.last_login_at),
    },
    "roles": {
        "role_id": _text_field(Role.role_id),
        "name": _text_field(Role.name),
        "description": _text_field(Role.description),
        "status": _text_field(Role.status),
        "created_at": _time_field(Role.created_at),
        "updated_at": _time_field(Role.updated_at),
        "deleted_at": _time_field(Role.deleted_at),
    },
}

_SECTION_KEYWORD_COLUMNS: dict[str, tuple[Any, ...]] = {
    section: tuple(
        field.column
        for field in fields.values()
        if field.type is _QueryFieldType.TEXT
    )
    for section, fields in _SECTION_QUERY_FIELDS.items()
}

_SECTION_QUERY_FIELD_ALIASES: dict[str, dict[str, str]] = {
    "models": {
        "id": "model_id",
        "model": "name",
        "time": "updated_at",
    },
    "versions": {
        "id": "version_id",
        "model": "model_name",
        "version": "model_version",
        "time": "updated_at",
    },
    "deployments": {
        "id": "deployment_id",
        "model": "model_name",
        "version": "model_version",
        "time": "updated_at",
    },
    "routings": {
        "id": "routing_id",
        "routing": "name",
        "model": "model_name",
        "version": "model_version",
        "time": "updated_at",
    },
    "runtimes": {
        "id": "runtime_id",
        "model": "model_name",
        "version": "model_version",
        "worker": "worker_id",
        "time": "updated_at",
    },
    "requests": {
        "id": "request_id",
        "model": "model_name",
        "version": "model_version",
        "time": "created_at",
    },
    "decisions": {
        "id": "decision_id",
        "experiment": "experiment_id",
        "model": "model_name",
        "version": "model_version",
        "subject": "subject_key",
        "time": "decided_at",
    },
    "executions": {
        "id": "execution_id",
        "model": "model_name",
        "version": "model_version",
        "type": "execution_type",
        "time": "started_at",
    },
    "experiments": {
        "id": "experiment_id",
        "experiment": "name",
        "model": "model_name",
        "time": "updated_at",
    },
    "variants": {
        "id": "variant_id",
        "variant": "name",
        "experiment": "experiment_name",
        "model": "model_name",
        "version": "model_version",
        "time": "updated_at",
    },
    "audits": {
        "id": "audit_id",
        "time": "occurred_at",
    },
    "users": {
        "id": "user_id",
        "user": "username",
        "time": "updated_at",
    },
    "roles": {
        "id": "role_id",
        "role": "name",
        "time": "updated_at",
    },
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

_VERSION_COUNT = (
    select(
        func.count()
    )
    .select_from(
        Version
    )
    .where(
        Version.model_id
        == Metadata.model_id,
        Version.deleted_at.is_(
            None
        ),
    )
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
        == Experiment.experiment_id,
        Variant.deleted_at.is_(
            None
        ),
    )
    .correlate(
        Experiment
    )
    .scalar_subquery()
)

_EXPERIMENT_MODEL_NAME = (
    select(
        Metadata.name
    )
    .where(
        Metadata.model_id
        == Experiment.model_id
    )
    .correlate(Experiment)
    .scalar_subquery()
)

_SECTION_SORT_COLUMNS: dict[str, dict[str, Any]] = {
    "models": {
        "name": Metadata.name,
        "display_name": Metadata.display_name,
        "model_id": Metadata.model_id,
        "framework": Metadata.framework,
        "model_type": Metadata.model_type,
        "task_type": Metadata.task_type,
        "status": Metadata.status,
        "latest_version": _LATEST_VERSION,
        "version_count": _VERSION_COUNT,
        "updated_at": Metadata.updated_at,
    },
    "versions": {
        "version": Version.version,
        "version_id": Version.version_id,
        "model_name": Metadata.name,
        "display_name": Metadata.display_name,
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
        "name": Routing.name,
        "deployment_id": Routing.deployment_id,
        "model_name": Metadata.name,
        "model_version": Version.version,
        "environment": Routing.environment,
        "rollout_type": Routing.rollout_type,
        "rollout_group": Routing.rollout_group,
        "traffic_ratio": Routing.traffic_ratio,
        "status": Routing.enabled,
        "effective_from": Routing.effective_from,
        "effective_to": Routing.effective_to,
        "updated_at": Routing.updated_at,
    },
    "runtimes": {
        "runtime_id": Runtime.runtime_id,
        "deployment_id": Runtime.deployment_id,
        "model_name": Metadata.name,
        "model_version": Version.version,
        "role": Deployment.role,
        "worker_id": Runtime.worker_id,
        "framework": Runtime.framework,
        "status": Runtime.status,
        "last_heartbeat_at": Runtime.last_heartbeat_at,
        "updated_at": Runtime.updated_at,
    },
    "requests": {
        "request_id": Request.request_id,
        "model_id": Request.model_id,
        "model_name": _REQUEST_MODEL_NAME,
        "model_version": Version.version,
        "payload": Request.payload,
        "prediction": Execution.prediction,
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
        "probability": Execution.probability,
        "score": Execution.score,
        "decision": Decision.decision,
        "decided_at": Decision.decided_at,
    },
    "executions": {
        "execution_id": Execution.execution_id,
        "decision_id": Execution.decision_id,
        "request_id": Decision.request_id,
        "model_name": Metadata.name,
        "model_version": Version.version,
        "deployment_id": Execution.deployment_id,
        "execution_type": Execution.execution_type,
        "status": Execution.status,
        "probability": Execution.probability,
        "score": Execution.score,
        "latency_ms": Execution.latency_ms,
        "started_at": Execution.started_at,
        "finished_at": Execution.finished_at,
    },
    "experiments": {
        "name": Experiment.name,
        "experiment_id": Experiment.experiment_id,
        "model_id": Experiment.model_id,
        "model_name": _EXPERIMENT_MODEL_NAME,
        "environment": Experiment.environment,
        "status": Experiment.status,
        "effective_from": Experiment.effective_from,
        "effective_to": Experiment.effective_to,
        "updated_at": Experiment.updated_at,
        "variant_count": _VARIANT_COUNT,
    },
    "variants": {
        "variant_id": Variant.variant_id,
        "experiment_id": Variant.experiment_id,
        "experiment_name": Experiment.name,
        "name": Variant.name,
        "model_name": Metadata.name,
        "model_version": Version.version,
        "deployment_id": Variant.deployment_id,
        "weight": Variant.weight,
        "is_control": Variant.is_control,
        "status": Variant.status,
        "updated_at": Variant.updated_at,
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
    "users": {
        "user_id": User.user_id,
        "username": User.username,
        "display_name": User.display_name,
        "email": User.email,
        "status": User.status,
        "last_login_at": User.last_login_at,
        "updated_at": User.updated_at,
    },
    "roles": {
        "role_id": Role.role_id,
        "name": Role.name,
        "status": Role.status,
        "updated_at": Role.updated_at,
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
    "executions": (
        Execution.created_at.desc(),
        Execution.id.desc(),
    ),
    "experiments": (
        Experiment.updated_at.desc(),
        Experiment.created_at.desc(),
    ),
    "variants": (
        Variant.updated_at.desc(),
        Variant.created_at.desc(),
    ),
    "audits": (
        Audit.occurred_at.desc(),
        Audit.created_at.desc(),
    ),
    "users": (
        User.updated_at.desc(),
        User.created_at.desc(),
    ),
    "roles": (
        Role.updated_at.desc(),
        Role.created_at.desc(),
    ),
}


def _parse_search_terms(
        *,
        section: str,
        query: str,
) -> tuple[tuple[str | None, str], ...]:
    """解析普通关键词和字段化查询条件"""
    field_query = re.search(
        r"(?:^|\s)[A-Za-z_][A-Za-z0-9_-]*:",
        query,
    ) is not None

    if not field_query:
        return ((None, query),)

    try:
        tokens = shlex.split(
            re.sub(
                (
                    r"(\d{4}[-/]\d{2}[-/]\d{2})\s+"
                    r"(\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?"
                    r"(?:Z|[+-]\d{2}:\d{2})?)"
                ),
                r"\1T\2",
                query,
            )
        )
    except ValueError as error:
        raise ValueError(
            "查询条件中的引号不完整"
        ) from error

    if not tokens:
        return ()

    fields = _SECTION_QUERY_FIELDS[section]
    aliases = _SECTION_QUERY_FIELD_ALIASES[section]
    terms: list[tuple[str | None, str]] = []

    for token in tokens:
        if ":" not in token:
            terms.append((
                None,
                token,
            ))
            continue

        raw_field, value = token.split(
            ":",
            maxsplit=1,
        )
        field = raw_field.lower().replace(
            "-",
            "_",
        )
        field = aliases.get(
            field,
            field,
        )

        if field not in fields:
            supported_fields = ", ".join(
                sorted({
                    *fields,
                    *aliases,
                })
            )
            raise ValueError(
                f"不支持的查询字段: {raw_field}；"
                f"当前页面支持: {supported_fields}"
            )

        if not value:
            raise ValueError(
                f"查询字段 {raw_field} 缺少值"
            )

        terms.append((
            field,
            value,
        ))

    return tuple(terms)


def _parse_query_time(
        value: str,
) -> tuple[datetime, bool]:
    """按控制台本地时区解析查询时间"""
    normalized_value = value.replace(
        "/",
        "-",
    )
    date_only = re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        normalized_value,
    ) is not None
    normalized = (
        f"{normalized_value}T00:00:00"
        if date_only
        else (
            f"{normalized_value[:-1]}+00:00"
            if normalized_value.endswith("Z")
            else normalized_value
        )
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as error:
        raise ValueError(
            f"时间查询值格式无效: {value}"
        ) from error

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=get_timezone(
                get_settings().logging.timezone
            )
        )

    return (
        parsed.astimezone(timezone.utc),
        date_only,
    )


def _build_time_predicate(
        *,
        column: Any,
        value: str,
) -> Any:
    """构建单日或起止时间范围条件"""
    if ".." not in value:
        instant, date_only = _parse_query_time(
            value
        )

        if date_only:
            next_day, _ = _parse_query_time(
                (
                    datetime.fromisoformat(
                        value.replace(
                            "/",
                            "-",
                        )
                    )
                    + timedelta(days=1)
                ).date().isoformat()
            )
            return and_(
                column >= instant,
                column < next_day,
            )

        return column == instant

    raw_start, raw_end = value.split(
        "..",
        maxsplit=1,
    )

    if not raw_start and not raw_end:
        raise ValueError(
            "时间范围不能同时缺少起止时间"
        )

    start = (
        _parse_query_time(raw_start)[0]
        if raw_start
        else None
    )
    end: datetime | None = None
    end_is_exclusive = False

    if raw_end:
        end, end_is_date = _parse_query_time(
            raw_end
        )

        if end_is_date:
            end, _ = _parse_query_time(
                (
                    datetime.fromisoformat(
                        raw_end.replace(
                            "/",
                            "-",
                        )
                    )
                    + timedelta(days=1)
                ).date().isoformat()
            )
            end_is_exclusive = True

    if (
            start is not None
            and end is not None
            and (
                start >= end
                if end_is_exclusive
                else start > end
            )
    ):
        raise ValueError(
            "时间范围的起始时间不能晚于结束时间"
        )

    conditions = []

    if start is not None:
        conditions.append(
            column >= start
        )

    if end is not None:
        conditions.append(
            column < end
            if end_is_exclusive
            else column <= end
        )

    return and_(*conditions)


def _build_search_predicates(
        *,
        section: str,
        query: str,
) -> tuple[Any, ...]:
    """构建字段化查询的 SQL 匹配条件"""
    predicates = []

    for field, value in _parse_search_terms(
            section=section,
            query=query,
    ):
        query_field = (
            _SECTION_QUERY_FIELDS[section][field]
            if field is not None
            else None
        )

        if (
                query_field is not None
                and query_field.type
                is _QueryFieldType.DATETIME
        ):
            predicates.append(
                _build_time_predicate(
                    column=query_field.column,
                    value=value,
                )
            )
            continue

        escaped_value = (
            value
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = (
            f"%{escaped_value}%"
            if query_field is None
            else escaped_value
        )
        columns = (
            _SECTION_KEYWORD_COLUMNS[section]
            if query_field is None
            else (
                query_field.column,
            )
        )
        predicates.append(
            or_(*(
                column.ilike(
                    pattern,
                    escape="\\",
                )
                for column in columns
            ))
        )

    return tuple(predicates)


def _build_record_statement(
        *,
        section: str,
        query: str,
        model_id: str | None = None,
        experiment_id: str | None = None,
        record_ids: Iterable[str] | None = None,
        only_deleted: bool = False,
        presence: RuntimePresence | None = None,
) -> Any:
    """构建控制台记录查询语句"""
    if section not in _SECTION_MODELS:
        raise ValueError(
            f"不支持的控制台页面: {section}"
        )

    model = _SECTION_MODELS[section]
    stmt = select(
        model
    )

    if section == "versions":
        stmt = stmt.outerjoin(
            Metadata,
            Metadata.model_id
            == Version.model_id,
        )
    elif section == "deployments":
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
    elif section == "routings":
        stmt = (
            stmt
            .outerjoin(
                Deployment,
                Deployment.deployment_id
                == Routing.deployment_id,
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
        )
    elif section == "runtimes":
        stmt = (
            stmt
            .outerjoin(
                Deployment,
                Deployment.deployment_id
                == Runtime.deployment_id,
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Runtime.model_id,
            )
            .outerjoin(
                Version,
                Version.version_id
                == Runtime.version_id,
            )
        )
    elif section == "requests":
        stmt = (
            stmt
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
            .outerjoin(
                Execution,
                and_(
                    Execution.decision_id
                    == Decision.decision_id,
                    Execution.execution_type
                    == "primary",
                ),
            )
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
            .outerjoin(
                Execution,
                and_(
                    Execution.decision_id
                    == Decision.decision_id,
                    Execution.execution_type
                    == "primary",
                ),
            )
        )
    elif section == "executions":
        stmt = (
            stmt
            .outerjoin(
                Decision,
                Decision.decision_id
                == Execution.decision_id,
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Execution.model_id,
            )
            .outerjoin(
                Version,
                Version.version_id
                == Execution.version_id,
            )
        )
    elif section == "experiments":
        stmt = stmt.outerjoin(
            Metadata,
            Metadata.model_id
            == Experiment.model_id,
        )
    elif section == "variants":
        stmt = (
            stmt
            .outerjoin(
                Experiment,
                Experiment.experiment_id
                == Variant.experiment_id,
            )
            .outerjoin(
                Deployment,
                Deployment.deployment_id
                == Variant.deployment_id,
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
        )

    if query:
        stmt = stmt.where(
            *_build_search_predicates(
                section=section,
                query=query,
            )
        )

    if section in _SECTION_DELETED_COLUMNS:
        deleted_column = _SECTION_DELETED_COLUMNS[section]
        stmt = stmt.where(
            deleted_column.is_not(None)
            if only_deleted
            else deleted_column.is_(None)
        )

    if section == "runtimes":
        stmt = stmt.where(
            _runtime_active_predicate(
                presence or RuntimePresence.current()
            )
        )

    if model_id is not None:
        if section != "versions":
            raise ValueError(
                "model_id 仅支持模型版本查询"
            )

        stmt = stmt.where(
            Version.model_id == model_id
        )

    if experiment_id is not None:
        if section != "variants":
            raise ValueError(
                "experiment_id 仅支持实验分组查询"
            )

        stmt = stmt.where(
            Variant.experiment_id == experiment_id
        )

    if record_ids is not None:
        stmt = stmt.where(
            _SECTION_ID_COLUMNS[section].in_(
                tuple(record_ids)
            )
        )

    return stmt


class DashboardRepository(BaseRepository):
    """管理控制台查询仓储"""

    async def get_counts(
            self,
            sections: Iterable[str],
            *,
            presence: RuntimePresence | None = None,
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

        count_expressions = []

        for section in selected_sections:
            model = _SECTION_MODELS[section]
            count_stmt = select(
                func.count()
            ).select_from(
                model
            )

            if section in _SECTION_DELETED_COLUMNS:
                count_stmt = count_stmt.where(
                    _SECTION_DELETED_COLUMNS[
                        section
                    ].is_(
                        None
                    )
                )

            if section == "runtimes":
                count_stmt = count_stmt.where(
                    _runtime_active_predicate(
                        presence or RuntimePresence.current()
                    )
                )

            count_expressions.append(
                count_stmt.scalar_subquery().label(
                    section
                )
            )

        stmt = select(
            *count_expressions
        )
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

    async def count_records(
            self,
            *,
            section: str,
            query: str = "",
            model_id: str | None = None,
            experiment_id: str | None = None,
            record_ids: Iterable[str] | None = None,
            only_deleted: bool = False,
            presence: RuntimePresence | None = None,
    ) -> int:
        """获取指定查询条件下的记录总数"""
        stmt = _build_record_statement(
            section=section,
            query=query,
            model_id=model_id,
            experiment_id=experiment_id,
            record_ids=record_ids,
            only_deleted=only_deleted,
            presence=presence,
        )
        count_stmt = select(
            func.count()
        ).select_from(
            stmt
            .order_by(None)
            .distinct()
            .subquery()
        )
        result = await self.session.execute(
            count_stmt
        )

        return int(
            result.scalar_one()
        )

    async def search_records(
            self,
            *,
            section: str,
            query: str,
            limit: int,
            offset: int,
            model_id: str | None = None,
            experiment_id: str | None = None,
            record_ids: Iterable[str] | None = None,
            sort_by: str | None = None,
            sort_order: str = "asc",
            only_deleted: bool = False,
            presence: RuntimePresence | None = None,
    ) -> list[Any]:
        """查询、排序并分页返回指定控制台页面记录"""
        stmt = _build_record_statement(
            section=section,
            query=query,
            model_id=model_id,
            experiment_id=experiment_id,
            record_ids=record_ids,
            only_deleted=only_deleted,
            presence=presence,
        )

        id_column = _SECTION_ID_COLUMNS[section]
        sort_specs = parse_sort_specs(
            sort_by=sort_by,
            sort_order=sort_order,
        )

        if sort_specs:
            sort_columns = _SECTION_SORT_COLUMNS[
                section
            ]
            ordered_columns = []
            sorted_id = False

            for field, direction in sort_specs:
                derived_runtime_sort = (
                    section == "runtimes"
                    and field == "health_status"
                )
                if field not in sort_columns and not derived_runtime_sort:
                    raise ValueError(
                        f"不支持的排序字段: {field}"
                    )

                if derived_runtime_sort:
                    sort_column = _runtime_health_status_expression(
                        presence or RuntimePresence.current()
                    )
                else:
                    sort_column = sort_columns[field]
                sorted_id = sorted_id or sort_column is id_column
                ordered_columns.append((
                    sort_column.asc()
                    if direction == "asc"
                    else sort_column.desc()
                ).nulls_last())

            if not sorted_id:
                ordered_columns.append(id_column.asc())

            order_columns = tuple(ordered_columns)
        else:
            order_columns = (
                *_SECTION_ORDER_COLUMNS[section],
                id_column.asc(),
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

    async def get_version_labels(
            self,
            version_ids: Iterable[str],
    ) -> dict[str, dict[str, str | None]]:
        """获取版本对应的模型名称"""
        identifiers = tuple(
            dict.fromkeys(
                version_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Version.version_id,
                Metadata.name.label(
                    "model_name"
                ),
                Metadata.display_name.label(
                    "display_name"
                ),
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Version.model_id,
            )
            .where(
                Version.version_id.in_(
                    identifiers
                )
            )
        )
        result = await self.session.execute(
            stmt
        )

        return {
            row["version_id"]: {
                "model_name": row["model_name"],
                "display_name": row["display_name"],
            }
            for row in result.mappings().all()
        }

    async def get_user_roles(
            self,
            user_ids: Iterable[str],
    ) -> dict[str, list[str]]:
        """获取用户的有效角色名称"""
        identifiers = tuple(
            dict.fromkeys(
                user_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Grant.user_id,
                Role.name,
            )
            .join(
                Role,
                Role.role_id == Grant.role_id,
            )
            .where(
                Grant.user_id.in_(
                    identifiers
                ),
                Grant.status == "active",
                Role.status == "active",
                Role.deleted_at.is_(
                    None
                ),
            )
            .order_by(
                Role.name.asc()
            )
        )
        result = await self.session.execute(
            stmt
        )
        roles: dict[str, list[str]] = {
            user_id: []
            for user_id in identifiers
        }

        for row in result:
            roles[row.user_id].append(
                row.name
            )

        return roles

    async def get_deployment_labels(
            self,
            deployment_ids: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        """获取部署对应的模型、版本和发布信息"""
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
                Deployment.model_id,
                Deployment.version_id,
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
                Deployment.environment.label(
                    "environment"
                ),
                Deployment.rollout_type.label(
                    "rollout_type"
                ),
                Deployment.role.label(
                    "rollout_group"
                ),
                Deployment.effective_from,
                Deployment.effective_to,
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
                "model_id": row["model_id"],
                "version_id": row["version_id"],
                "model_name": row["model_name"],
                "model_version": row["model_version"],
                "environment": row["environment"],
                "rollout_type": row["rollout_type"],
                "rollout_group": row["rollout_group"],
                "effective_from": row["effective_from"],
                "effective_to": row["effective_to"],
            }
            for row in result.mappings().all()
        }

    async def get_experiment_labels(
            self,
            experiment_ids: Iterable[str],
    ) -> dict[str, dict[str, str | None]]:
        """获取实验对应的模型名称"""
        identifiers = tuple(
            dict.fromkeys(
                experiment_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Experiment.experiment_id,
                Metadata.name.label(
                    "model_name"
                ),
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Experiment.model_id,
            )
            .where(
                Experiment.experiment_id.in_(
                    identifiers
                )
            )
        )
        result = await self.session.execute(
            stmt
        )
        return {
            row["experiment_id"]: {
                "model_name": row[
                    "model_name"
                ],
            }
            for row in result.mappings().all()
        }

    async def get_variant_labels(
            self,
            variant_ids: Iterable[str],
    ) -> dict[str, dict[str, str | None]]:
        """获取分组对应的实验和模型信息"""
        identifiers = tuple(
            dict.fromkeys(
                variant_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Variant.variant_id,
                Experiment.name.label(
                    "experiment_name"
                ),
                Experiment.status.label(
                    "experiment_status"
                ),
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
            )
            .outerjoin(
                Experiment,
                Experiment.experiment_id
                == Variant.experiment_id,
            )
            .outerjoin(
                Deployment,
                Deployment.deployment_id
                == Variant.deployment_id,
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
                Variant.variant_id.in_(
                    identifiers
                )
            )
        )
        result = await self.session.execute(
            stmt
        )

        return {
            row["variant_id"]: {
                "experiment_name": row[
                    "experiment_name"
                ],
                "experiment_status": row[
                    "experiment_status"
                ],
                "model_name": row[
                    "model_name"
                ],
                "model_version": row[
                    "model_version"
                ],
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
                _REQUEST_MODEL_NAME.label(
                    "model_name"
                ),
                Metadata.task_type,
                Version.version.label(
                    "model_version"
                ),
                Decision.deployment_id,
                Decision.decision_id,
                Decision.version_id,
                Execution.prediction,
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
            .outerjoin(
                Execution,
                and_(
                    Execution.decision_id
                    == Decision.decision_id,
                    Execution.execution_type
                    == "primary",
                ),
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
                "task_type": row["task_type"],
                "model_version": row["model_version"],
                "deployment_id": row["deployment_id"],
                "decision_id": row["decision_id"],
                "version_id": row["version_id"],
                "prediction": row["prediction"],
            }
            for row in result.mappings().all()
        }

    async def get_decision_details(
            self,
            decision_ids: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        """获取决策对应的模型和主执行详情"""
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
                Experiment.name.label(
                    "experiment_name"
                ),
                Variant.name.label(
                    "variant_name"
                ),
                Variant.is_control.label(
                    "variant_is_control"
                ),
                Variant.weight.label(
                    "variant_weight"
                ),
                Deployment.role.label(
                    "deployment_role"
                ),
                Deployment.rollout_type.label(
                    "deployment_rollout_type"
                ),
                Execution.routing_id.label(
                    "routing_id"
                ),
                Routing.name.label(
                    "routing_name"
                ),
                Routing.traffic_ratio.label(
                    "routing_weight"
                ),
                Execution.prediction,
                Execution.probability,
                Execution.score,
                Execution.latency_ms,
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
            .outerjoin(
                Experiment,
                Experiment.experiment_id
                == Decision.experiment_id,
            )
            .outerjoin(
                Variant,
                Variant.variant_id
                == Decision.variant_id,
            )
            .outerjoin(
                Deployment,
                Deployment.deployment_id
                == Decision.deployment_id,
            )
            .outerjoin(
                Execution,
                and_(
                    Execution.decision_id
                    == Decision.decision_id,
                    Execution.execution_type
                    == "primary",
                ),
            )
            .outerjoin(
                Routing,
                Routing.routing_id
                == Execution.routing_id,
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
                "experiment_name": row["experiment_name"],
                "variant_name": row["variant_name"],
                "variant_is_control": row["variant_is_control"],
                "variant_weight": row["variant_weight"],
                "deployment_role": row["deployment_role"],
                "deployment_rollout_type": row["deployment_rollout_type"],
                "routing_id": row["routing_id"],
                "routing_name": row["routing_name"],
                "routing_weight": row["routing_weight"],
                "prediction": row["prediction"],
                "probability": row["probability"],
                "score": row["score"],
                "latency_ms": row["latency_ms"],
            }
            for row in result.mappings().all()
        }

    async def get_execution_details(
            self,
            execution_ids: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        """获取模型执行对应的请求和模型信息"""
        identifiers = tuple(
            dict.fromkeys(
                execution_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Execution.execution_id,
                Decision.request_id,
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
                Routing.name.label(
                    "routing_name"
                ),
                Routing.traffic_ratio.label(
                    "routing_weight"
                ),
            )
            .outerjoin(
                Decision,
                Decision.decision_id
                == Execution.decision_id,
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Execution.model_id,
            )
            .outerjoin(
                Version,
                Version.version_id
                == Execution.version_id,
            )
            .outerjoin(
                Routing,
                Routing.routing_id
                == Execution.routing_id,
            )
            .where(
                Execution.execution_id.in_(
                    identifiers
                )
            )
        )
        result = await self.session.execute(
            stmt
        )

        return {
            row["execution_id"]: {
                "request_id": row["request_id"],
                "model_name": row["model_name"],
                "model_version": row["model_version"],
                "routing_name": row["routing_name"],
                "routing_weight": row["routing_weight"],
            }
            for row in result.mappings().all()
        }

    async def get_decision_executions(
            self,
            decision_ids: Iterable[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """获取决策对应的全部主执行和影子执行"""
        identifiers = tuple(
            dict.fromkeys(
                decision_ids
            )
        )

        if not identifiers:
            return {}

        stmt = (
            select(
                Execution,
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
                Routing.name.label(
                    "routing_name"
                ),
                Routing.traffic_ratio.label(
                    "routing_weight"
                ),
            )
            .outerjoin(
                Metadata,
                Metadata.model_id
                == Execution.model_id,
            )
            .outerjoin(
                Version,
                Version.version_id
                == Execution.version_id,
            )
            .outerjoin(
                Routing,
                Routing.routing_id
                == Execution.routing_id,
            )
            .where(
                Execution.decision_id.in_(
                    identifiers
                )
            )
            .order_by(
                Execution.decision_id.asc(),
                Execution.created_at.asc(),
                Execution.id.asc(),
            )
        )
        result = await self.session.execute(
            stmt
        )
        executions: dict[str, list[dict[str, Any]]] = {}

        for (
            execution,
            model_name,
            model_version,
            routing_name,
            routing_weight,
        ) in result.all():
            executions.setdefault(
                execution.decision_id,
                [],
            ).append({
                "execution": execution,
                "model_name": model_name,
                "model_version": model_version,
                "routing_name": routing_name,
                "routing_weight": routing_weight,
            })

        return executions

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
                ),
                Variant.deleted_at.is_(
                    None
                ),
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
            "model_name": Metadata.name,
            "model_version": Version.version,
            "weight": Variant.weight,
            "is_control": Variant.is_control,
            "status": Variant.status,
            "updated_at": Variant.updated_at,
        }
        stmt = (
            select(
                Variant
            )
            .outerjoin(
                Deployment,
                Deployment.deployment_id
                == Variant.deployment_id,
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
                Variant.experiment_id
                == experiment_id,
                Variant.deleted_at.is_(
                    None
                ),
            )
        )

        if query:
            stmt = stmt.where(
                *_build_search_predicates(
                    section="variants",
                    query=query,
                )
            )

        sort_specs = parse_sort_specs(
            sort_by=sort_by,
            sort_order=sort_order,
        )

        if sort_specs:
            order_columns = []
            sorted_id = False
            for field, direction in sort_specs:
                sort_column = sort_columns.get(field)

                if sort_column is None:
                    raise ValueError(
                        f"不支持的排序字段: {field}"
                    )

                sorted_id = (
                    sorted_id
                    or sort_column is Variant.variant_id
                )
                order_columns.append((
                    sort_column.desc()
                    if direction == "desc"
                    else sort_column.asc()
                ).nulls_last())

            if not sorted_id:
                order_columns.append(
                    Variant.variant_id.asc()
                )

            stmt = stmt.order_by(*order_columns)
        else:
            stmt = stmt.order_by(
                Variant.updated_at.desc(),
                Variant.created_at.desc(),
                Variant.variant_id.asc(),
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
            interval: timedelta,
            origin: datetime,
    ) -> list[dict[str, Any]]:
        """按指定时间间隔获取 API 调用量"""
        bucket = func.date_bin(
            interval,
            Request.created_at,
            origin,
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

    async def get_request_metrics(
            self,
            *,
            since: datetime,
            previous_since: datetime,
    ) -> dict[str, Any]:
        """获取当前和上一周期的 API 调用核心指标"""
        current_filter = Request.created_at >= since
        previous_filter = and_(
            Request.created_at >= previous_since,
            Request.created_at < since,
        )
        p95_latency_ms = (
            func.percentile_cont(
                0.95
            )
            .within_group(
                Request.latency_ms
            )
            .filter(
                and_(
                    current_filter,
                    Request.latency_ms.is_not(None),
                )
            )
            .label(
                "p95_latency_ms"
            )
        )
        stmt = select(
            func.count().filter(
                current_filter
            ).label(
                "request_count"
            ),
            func.count().filter(
                and_(
                    current_filter,
                    Request.status == "success",
                )
            ).label(
                "success_count"
            ),
            func.count().filter(
                and_(
                    current_filter,
                    Request.status == "failed",
                )
            ).label(
                "failed_count"
            ),
            func.avg(
                Request.latency_ms
            ).filter(
                and_(
                    current_filter,
                    Request.latency_ms.is_not(None),
                )
            ).label(
                "average_latency_ms"
            ),
            p95_latency_ms,
            func.count().filter(
                previous_filter
            ).label(
                "previous_request_count"
            ),
        )
        result = await self.session.execute(
            stmt
        )
        row = result.mappings().one()

        return {
            "request_count": int(
                row["request_count"]
            ),
            "success_count": int(
                row["success_count"]
            ),
            "failed_count": int(
                row["failed_count"]
            ),
            "average_latency_ms": (
                float(row["average_latency_ms"])
                if row["average_latency_ms"] is not None
                else None
            ),
            "p95_latency_ms": (
                float(row["p95_latency_ms"])
                if row["p95_latency_ms"] is not None
                else None
            ),
            "previous_request_count": int(
                row["previous_request_count"]
            ),
        }

    async def get_model_request_stats(
            self,
            *,
            since: datetime,
    ) -> list[dict[str, Any]]:
        """获取全部模型的最近调用表现和累计调用量"""
        recent_count = func.count(
            Request.request_id
        ).filter(
            Request.created_at >= since
        ).label(
            "recent_count"
        )
        recent_success_count = func.count(
            Request.request_id
        ).filter(
            and_(
                Request.created_at >= since,
                Request.status == "success",
            )
        ).label(
            "recent_success_count"
        )
        average_latency_ms = func.avg(
            Request.latency_ms
        ).filter(
            and_(
                Request.created_at >= since,
                Request.latency_ms.is_not(None),
            )
        ).label(
            "average_latency_ms"
        )
        total_count = func.count(
            Request.request_id
        ).label(
            "total_count"
        )
        recent_total_count = (
            select(
                func.count()
            )
            .select_from(
                Request
            )
            .where(
                Request.created_at >= since
            )
            .correlate(
                None
            )
            .scalar_subquery()
            .label(
                "recent_total_count"
            )
        )
        stmt = (
            select(
                Metadata.model_id,
                Metadata.name.label(
                    "model_name"
                ),
                Metadata.deleted_at,
                recent_count,
                recent_success_count,
                average_latency_ms,
                total_count,
                recent_total_count,
            )
            .select_from(
                Metadata
            )
            .outerjoin(
                Request,
                Request.model_id == Metadata.model_id,
            )
            .group_by(
                Metadata.model_id,
                Metadata.name,
                Metadata.deleted_at,
            )
            .having(
                total_count > 0
            )
            .order_by(
                recent_count.desc(),
                total_count.desc(),
                Metadata.model_id.asc(),
            )
        )
        result = await self.session.execute(
            stmt
        )

        return [
            {
                "model_id": row["model_id"],
                "model_name": row["model_name"],
                "is_deleted": row["deleted_at"] is not None,
                "recent_count": int(
                    row["recent_count"]
                ),
                "recent_success_count": int(
                    row["recent_success_count"]
                ),
                "average_latency_ms": (
                    float(row["average_latency_ms"])
                    if row["average_latency_ms"] is not None
                    else None
                ),
                "total_count": int(
                    row["total_count"]
                ),
                "recent_total_count": int(
                    row["recent_total_count"]
                ),
            }
            for row in result.mappings().all()
        ]
