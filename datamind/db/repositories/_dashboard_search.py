"""管理控制台记录搜索

负责解析控制台字段化查询，并根据页面配置构建记录查询语句。

核心功能：
  - _build_record_statement: 构建控制台记录查询语句

使用示例：
  from datamind.db.repositories._dashboard_search import (
      _build_record_statement,
  )

  stmt = _build_record_statement(
      section="requests",
      query="status:success",
  )
"""

import re
import shlex
from collections.abc import Iterable
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from typing import Any

from sqlalchemy import (
    and_,
    case,
    func,
    or_,
    select,
)

from datamind.config import get_logging_config
from datamind.constants.runtime_status import (
    ACTIVE_RUNTIME_STATUSES,
    RuntimeHealthStatus,
)
from datamind.db.models import (
    Decision,
    Deployment,
    Execution,
    Experiment,
    Metadata,
    Request,
    Routing,
    Runtime,
    Variant,
    Version,
)
from datamind.db.repositories._dashboard_sections import (
    _QueryFieldType,
    _SECTION_DEFINITIONS,
)
from datamind.runtime.presence import RuntimePresence
from datamind.utils.datetime import get_timezone


def _runtime_stale_predicate(
        presence: RuntimePresence,
) -> Any:
    """构建活动实例心跳过期条件"""
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
    """构建当前在线运行实例条件"""
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

    definition = _SECTION_DEFINITIONS[section]
    fields = definition.query_fields
    aliases = definition.aliases
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
                get_logging_config().timezone
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
    definition = _SECTION_DEFINITIONS[section]
    predicates = []

    for field, value in _parse_search_terms(
            section=section,
            query=query,
    ):
        query_field = (
            definition.query_fields[field]
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

        if (
                field is not None
                and query_field is not None
                and query_field.type
                is _QueryFieldType.INTEGER
        ):
            if ".." in value:
                bounds = value.split("..")
                if len(bounds) != 2 or not all(bounds):
                    raise ValueError(
                        f"查询字段 {field} 的范围格式应为 起始值..结束值"
                    )
                try:
                    start_value, end_value = (
                        int(bound) for bound in bounds
                    )
                except ValueError as error:
                    raise ValueError(
                        f"查询字段 {field} 的范围只支持整数值"
                    ) from error
                if start_value > end_value:
                    raise ValueError(
                        f"查询字段 {field} 的范围起始值不能大于结束值"
                    )
                predicates.append(
                    query_field.column.between(
                        start_value,
                        end_value,
                    )
                )
                continue
            try:
                integer_value = int(value)
            except ValueError as error:
                raise ValueError(
                    f"查询字段 {field} 只支持整数值"
                ) from error
            predicates.append(
                query_field.column == integer_value
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
            definition.keyword_columns
            if query_field is None
            else (
                query_field.column,
            )
        )
        text_matches = [
            column.ilike(
                pattern,
                escape="\\",
            )
            for column in columns
        ]
        extra_predicate_factory = (
            definition.extra_text_predicate
        )
        if extra_predicate_factory is not None:
            extra_predicate = extra_predicate_factory(
                field,
                pattern,
            )
            if extra_predicate is not None:
                text_matches.append(
                    extra_predicate
                )
        predicates.append(
            or_(*text_matches)
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
    if section not in _SECTION_DEFINITIONS:
        raise ValueError(
            f"不支持的控制台页面: {section}"
        )

    definition = _SECTION_DEFINITIONS[section]
    stmt = select(
        definition.model
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
                Decision.decision_id
                == Request.latest_decision_id,
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

    deleted_column = definition.deleted_column
    if deleted_column is not None:
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
            definition.id_column.in_(
                tuple(record_ids)
            )
        )

    return stmt
