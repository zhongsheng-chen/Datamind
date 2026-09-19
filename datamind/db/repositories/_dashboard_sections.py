"""管理控制台页面查询配置

定义各控制台页面的模型、查询字段、字段别名和排序规则，
避免仓储与搜索构建逻辑重复维护页面元数据。

核心功能：
  - _SECTION_DEFINITIONS: 控制台页面查询定义

使用示例：
  from datamind.db.repositories._dashboard_sections import (
      _SECTION_DEFINITIONS,
  )

  definition = _SECTION_DEFINITIONS["requests"]
  model = definition.model
  query_fields = definition.query_fields
  order_columns = definition.order_columns
"""

from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Callable,
    Protocol,
)

from sqlalchemy import (
    func,
    select,
)

from datamind.db.models import (
    Attempt,
    Audit,
    Batch,
    Decision,
    Deployment,
    Execution,
    Experiment,
    Metadata,
    Request,
    Role,
    Routing,
    Runtime,
    Shard,
    User,
    Variant,
    Version,
)


_REQUEST_MODEL_NAME = func.coalesce(
    Request.model_name,
    Metadata.name,
)


_SECTION_MODELS: dict[str, type[Any]] = {
    "models": Metadata,
    "versions": Version,
    "deployments": Deployment,
    "routings": Routing,
    "runtimes": Runtime,
    "requests": Request,
    "batches": Batch,
    "attempts": Attempt,
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
    "batches": Batch.batch_id,
    "attempts": Attempt.attempt_id,
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
    INTEGER = "integer"
    DATETIME = "datetime"


@dataclass(
    frozen=True,
    slots=True,
)
class _QueryField:
    """控制台查询字段定义"""

    column: Any
    type: _QueryFieldType


class _NullableColumn(Protocol):
    """支持 SQL 空值判断的字段"""

    def is_(self, other: object) -> Any:
        """构建 IS 条件"""
        ...

    def is_not(self, other: object) -> Any:
        """构建 IS NOT 条件"""
        ...


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


def _integer_field(
        column: Any,
) -> _QueryField:
    """定义整数查询字段"""
    return _QueryField(
        column=column,
        type=_QueryFieldType.INTEGER,
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
        "batch_id": _text_field(Request.batch_id),
        "batch_index": _integer_field(Request.batch_index),
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
    "batches": {
        "batch_id": _text_field(Batch.batch_id),
        "task_id": _text_field(Batch.task_id),
        "model_id": _text_field(Batch.model_id),
        "model_name": _text_field(Batch.model_name),
        "deployment_id": _text_field(Batch.deployment_id),
        "environment": _text_field(Batch.environment),
        "status": _text_field(Batch.status),
        "source": _text_field(Batch.source),
        "user": _text_field(Batch.user),
        "ip": _text_field(Batch.ip),
        "created_at": _time_field(Batch.created_at),
        "updated_at": _time_field(Batch.updated_at),
        "started_at": _time_field(Batch.started_at),
        "finished_at": _time_field(Batch.finished_at),
    },
    "attempts": {
        "attempt_id": _text_field(Attempt.attempt_id),
        "batch_id": _text_field(Attempt.batch_id),
        "task_id": _text_field(Attempt.task_id),
        "status": _text_field(Attempt.status),
        "worker_id": _text_field(Attempt.worker_id),
        "error": _text_field(Attempt.error),
        "created_at": _time_field(Attempt.created_at),
        "updated_at": _time_field(Attempt.updated_at),
        "retry_scheduled_at": _time_field(Attempt.retry_scheduled_at),
        "queued_at": _time_field(Attempt.queued_at),
        "started_at": _time_field(Attempt.started_at),
        "finished_at": _time_field(Attempt.finished_at),
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

def _attempt_shard_task_predicate(
        field: str | None,
        pattern: str,
) -> Any | None:
    """构建执行尝试的分片任务 ID 匹配条件"""
    if field is not None and field != "task_id":
        return None

    return (
        select(Shard.shard_id)
        .where(
            Shard.attempt_id == Attempt.attempt_id,
            Shard.task_id.ilike(
                pattern,
                escape="\\",
            ),
        )
        .exists()
    )


_SECTION_EXTRA_TEXT_PREDICATES: dict[
    str,
    Callable[[str | None, str], Any | None],
] = {
    "attempts": _attempt_shard_task_predicate,
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
        "batch": "batch_id",
        "model": "model_name",
        "version": "model_version",
        "time": "created_at",
    },
    "batches": {
        "id": "batch_id",
        "batch": "batch_id",
        "task": "task_id",
        "model": "model_name",
        "deployment": "deployment_id",
        "time": "created_at",
    },
    "attempts": {
        "id": "attempt_id",
        "batch": "batch_id",
        "task": "task_id",
        "worker": "worker_id",
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
        "batch_id": Request.batch_id,
        "batch_index": Request.batch_index,
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
    "batches": {
        "batch_id": Batch.batch_id,
        "task_id": Batch.task_id,
        "model_id": Batch.model_id,
        "model_name": Batch.model_name,
        "deployment_id": Batch.deployment_id,
        "environment": Batch.environment,
        "status": Batch.status,
        "total_count": Batch.total_count,
        "completed_count": Batch.completed_count,
        "succeeded_count": Batch.succeeded_count,
        "failed_count": Batch.failed_count,
        "attempt_count": Batch.attempt_count,
        "source": Batch.source,
        "user": Batch.user,
        "ip": Batch.ip,
        "created_at": Batch.created_at,
        "started_at": Batch.started_at,
        "finished_at": Batch.finished_at,
    },
    "attempts": {
        "attempt_id": Attempt.attempt_id,
        "batch_id": Attempt.batch_id,
        "task_id": Attempt.task_id,
        "attempt_number": Attempt.attempt_number,
        "status": Attempt.status,
        "worker_id": Attempt.worker_id,
        "created_at": Attempt.created_at,
        "retry_scheduled_at": Attempt.retry_scheduled_at,
        "queued_at": Attempt.queued_at,
        "started_at": Attempt.started_at,
        "finished_at": Attempt.finished_at,
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
    "batches": (
        Batch.created_at.desc(),
        Batch.id.desc(),
    ),
    "attempts": (
        Attempt.created_at.desc(),
        Attempt.id.desc(),
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


@dataclass(
    frozen=True,
    slots=True,
)
class _SectionDefinition:
    """控制台页面查询定义"""

    model: type[Any]
    id_column: Any
    query_fields: dict[str, _QueryField]
    keyword_columns: tuple[Any, ...]
    aliases: dict[str, str]
    sort_columns: dict[str, Any]
    order_columns: tuple[Any, ...]
    deleted_column: _NullableColumn | None = None
    extra_text_predicate: (
        Callable[[str | None, str], Any | None]
        | None
    ) = None


_SECTION_DEFINITIONS: dict[str, _SectionDefinition] = {
    section: _SectionDefinition(
        model=model,
        id_column=_SECTION_ID_COLUMNS[section],
        deleted_column=_SECTION_DELETED_COLUMNS.get(
            section
        ),
        query_fields=_SECTION_QUERY_FIELDS[section],
        keyword_columns=tuple(
            field.column
            for field in _SECTION_QUERY_FIELDS[
                section
            ].values()
            if field.type is _QueryFieldType.TEXT
        ),
        aliases=_SECTION_QUERY_FIELD_ALIASES[section],
        sort_columns=_SECTION_SORT_COLUMNS[section],
        order_columns=_SECTION_ORDER_COLUMNS[section],
        extra_text_predicate=(
            _SECTION_EXTRA_TEXT_PREDICATES.get(
                section
            )
        ),
    )
    for section, model in _SECTION_MODELS.items()
}
