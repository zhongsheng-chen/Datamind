"""管理控制台查询仓储.

提供管理控制台记录查询、关联信息补充和调用指标统计能力。

核心功能：
  - get_counts: 获取控制台页面记录总数
  - count_records: 获取查询结果总数
  - search_records: 查询控制台页面记录
  - get_version_labels: 获取版本关联信息
  - get_user_roles: 获取用户角色
  - get_deployment_labels: 获取部署关联信息
  - get_experiment_labels: 获取实验关联信息
  - get_variant_labels: 获取实验分组关联信息
  - get_request_details: 获取 API 调用关联信息
  - get_batch_deployment_stats: 获取批次实际命中部署统计
  - get_attempt_shard_details: 获取执行尝试的分片详情
  - get_decision_details: 获取决策关联信息
  - get_execution_details: 获取模型执行关联信息
  - get_decision_executions: 获取决策的模型执行
  - get_variant_counts: 获取实验分组数量
  - search_variants: 查询实验分组
  - get_request_trend: 获取 API 调用趋势
  - get_request_metrics: 获取 API 调用核心指标
  - get_model_request_stats: 获取模型调用统计

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.dashboard import DashboardRepository

  async with UnitOfWork() as uow:
      repo = DashboardRepository(
          uow.session
      )

      counts = await repo.get_counts([
          "models",
          "deployments",
      ])
"""

from collections.abc import Iterable
from datetime import (
    datetime,
    timedelta,
)
from typing import (
    Any,
    TypedDict,
)

from sqlalchemy import (
    and_,
    func,
    select,
)
from datamind.db.models import (
    Decision,
    Deployment,
    Execution,
    Experiment,
    Grant,
    Metadata,
    Request,
    Routing,
    Role,
    Shard,
    Variant,
    Version,
)
from datamind.db.repositories._dashboard_search import (
    _build_record_statement,
    _build_search_predicates,
    _runtime_active_predicate,
    _runtime_health_status_expression,
)
from datamind.db.repositories._dashboard_sections import (
    _REQUEST_MODEL_NAME,
    _SECTION_DEFINITIONS,
)
from datamind.db.repositories.base import BaseRepository
from datamind.runtime.presence import RuntimePresence
from datamind.utils.sorting import parse_sort_specs


class AttemptShardDetail(TypedDict):
    """执行尝试分片详情."""

    record: Shard
    total_count: int
    completed_count: int
    succeeded_count: int
    failed_count: int


class DashboardRepository(BaseRepository):
    """管理控制台查询仓储."""

    async def get_counts(
            self,
            sections: Iterable[str],
            *,
            presence: RuntimePresence | None = None,
    ) -> dict[str, int]:
        """获取指定控制台页面的记录总数.

        参数：
            sections: 控制台页面名称集合
            presence: 运行实例在线状态判定参数（可选）

        返回：
            页面名称与记录总数的映射

        异常：
            ValueError: 包含不支持的控制台页面
        """
        selected_sections = tuple(
            dict.fromkeys(
                sections
            )
        )
        unsupported_sections = set(
            selected_sections
        ) - _SECTION_DEFINITIONS.keys()

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
            definition = _SECTION_DEFINITIONS[section]
            count_stmt = select(
                func.count()
            ).select_from(
                definition.model
            )

            deleted_column = definition.deleted_column
            if deleted_column is not None:
                count_stmt = count_stmt.where(
                    deleted_column.is_(
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
        """获取指定查询条件下的记录总数.

        参数：
            section: 控制台页面名称
            query: 关键词或字段化查询表达式
            model_id: 模型 ID（可选）
            experiment_id: 实验 ID（可选）
            record_ids: 记录 ID 集合（可选）
            only_deleted: 是否只统计逻辑删除记录
            presence: 运行实例在线状态判定参数（可选）

        返回：
            符合条件的记录总数

        异常：
            ValueError: 页面或查询条件不受支持
        """
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
        """查询、排序并分页返回指定控制台页面记录.

        参数：
            section: 控制台页面名称
            query: 关键词或字段化查询表达式
            limit: 返回数量限制
            offset: 分页偏移
            model_id: 模型 ID（可选）
            experiment_id: 实验 ID（可选）
            record_ids: 记录 ID 集合（可选）
            sort_by: 排序字段表达式（可选）
            sort_order: 默认排序方向
            only_deleted: 是否只查询逻辑删除记录
            presence: 运行实例在线状态判定参数（可选）

        返回：
            符合条件的控制台记录列表

        异常：
            ValueError: 页面、查询条件或排序字段不受支持
        """
        stmt = _build_record_statement(
            section=section,
            query=query,
            model_id=model_id,
            experiment_id=experiment_id,
            record_ids=record_ids,
            only_deleted=only_deleted,
            presence=presence,
        )

        definition = _SECTION_DEFINITIONS[section]
        id_column = definition.id_column
        sort_specs = parse_sort_specs(
            sort_by=sort_by,
            sort_order=sort_order,
        )

        if sort_specs:
            sort_columns = definition.sort_columns
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
                *definition.order_columns,
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
        """获取版本关联信息.

        参数：
            version_ids: 版本 ID 集合

        返回：
            版本 ID 与模型名称、显示名称的映射
        """
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
        """获取用户的有效角色名称.

        参数：
            user_ids: 用户 ID 集合

        返回：
            用户 ID 与有效角色名称列表的映射
        """
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
        """获取部署关联信息.

        参数：
            deployment_ids: 部署 ID 集合

        返回：
            部署 ID 与模型、版本和发布信息的映射
        """
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
        """获取实验关联信息.

        参数：
            experiment_ids: 实验 ID 集合

        返回：
            实验 ID 与模型名称的映射
        """
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
    ) -> dict[str, dict[str, Any]]:
        """获取实验分组关联信息.

        参数：
            variant_ids: 分组 ID 集合

        返回：
            分组 ID 与实验、模型及版本信息的映射
        """
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
                Experiment.config.label(
                    "experiment_config"
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
                "experiment_config": row[
                    "experiment_config"
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
        """获取 API 调用关联信息.

        参数：
            request_ids: 请求 ID 集合

        返回：
            请求 ID 与模型、版本、决策及预测信息的映射
        """
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

    async def get_batch_deployment_stats(
            self,
            batch_ids: Iterable[str],
    ) -> dict[str, list[dict[str, Any]]]:
        """获取批次实际命中的部署统计.

        参数：
            batch_ids: 批次 ID 集合

        返回：
            批次 ID 与主执行、影子执行命中部署统计的映射
        """
        identifiers = tuple(
            dict.fromkeys(
                batch_ids
            )
        )

        if not identifiers:
            return {}

        execution_count = func.count(
            Execution.execution_id
        ).label("execution_count")
        stmt = (
            select(
                Request.batch_id,
                Execution.deployment_id,
                Execution.execution_type,
                Metadata.name.label(
                    "model_name"
                ),
                Version.version.label(
                    "model_version"
                ),
                execution_count,
            )
            .join(
                Decision,
                Decision.decision_id
                == Request.latest_decision_id,
            )
            .join(
                Execution,
                Execution.decision_id
                == Decision.decision_id,
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
            .where(
                Request.batch_id.in_(
                    identifiers
                ),
                Execution.deployment_id.is_not(None),
            )
            .group_by(
                Request.batch_id,
                Execution.deployment_id,
                Execution.execution_type,
                Metadata.name,
                Version.version,
            )
            .order_by(
                Request.batch_id.asc(),
                Execution.execution_type.asc(),
                Execution.deployment_id.asc(),
            )
        )
        result = await self.session.execute(stmt)
        deployments: dict[str, list[dict[str, Any]]] = {}

        for row in result.mappings().all():
            deployments.setdefault(
                row["batch_id"],
                [],
            ).append({
                "deployment_id": row["deployment_id"],
                "execution_type": row["execution_type"],
                "model_name": row["model_name"],
                "model_version": row["model_version"],
                "execution_count": row["execution_count"],
            })

        return deployments

    async def get_attempt_shard_details(
            self,
            attempt_ids: Iterable[str],
    ) -> dict[str, list[AttemptShardDetail]]:
        """获取执行尝试的分片及处理进度.

        参数：
            attempt_ids: 执行尝试 ID 集合

        返回：
            执行尝试 ID 与分片及其处理进度列表的映射
        """
        identifiers = tuple(
            dict.fromkeys(
                attempt_ids
            )
        )

        if not identifiers:
            return {}

        completed_count = func.count(
            Request.request_id
        ).filter(
            Request.status.in_((
                "success",
                "failed",
            ))
        ).label(
            "completed_count"
        )
        succeeded_count = func.count(
            Request.request_id
        ).filter(
            Request.status == "success"
        ).label(
            "succeeded_count"
        )
        failed_count = func.count(
            Request.request_id
        ).filter(
            Request.status == "failed"
        ).label(
            "failed_count"
        )
        stmt = (
            select(
                Shard,
                completed_count,
                succeeded_count,
                failed_count,
            )
            .outerjoin(
                Request,
                and_(
                    Request.batch_id == Shard.batch_id,
                    Request.batch_index >= Shard.start_index,
                    Request.batch_index < Shard.end_index,
                ),
            )
            .where(
                Shard.attempt_id.in_(
                    identifiers
                )
            )
            .group_by(
                Shard.id
            )
            .order_by(
                Shard.attempt_id,
                Shard.start_index,
            )
        )
        result = await self.session.execute(
            stmt
        )
        details: dict[str, list[AttemptShardDetail]] = {}

        for (
            shard,
            completed,
            succeeded,
            failed,
        ) in result.all():
            details.setdefault(
                shard.attempt_id,
                [],
            ).append({
                "record": shard,
                "total_count": shard.end_index - shard.start_index,
                "completed_count": int(completed),
                "succeeded_count": int(succeeded),
                "failed_count": int(failed),
            })

        return details

    async def get_decision_details(
            self,
            decision_ids: Iterable[str],
    ) -> dict[str, dict[str, Any]]:
        """获取决策关联信息.

        参数：
            decision_ids: 决策 ID 集合

        返回：
            决策 ID 与模型、实验、部署、路由及主执行信息的映射
        """
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
        """获取模型执行关联信息.

        参数：
            execution_ids: 执行 ID 集合

        返回：
            执行 ID 与请求、模型、版本及路由信息的映射
        """
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
        """获取决策对应的全部主执行和影子执行.

        参数：
            decision_ids: 决策 ID 集合

        返回：
            决策 ID 与模型执行信息列表的映射
        """
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
        """获取实验对应的分组数量.

        参数：
            experiment_ids: 实验 ID 集合

        返回：
            实验 ID 与未删除分组数量的映射
        """
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
        """查询、排序并分页返回实验分组.

        参数：
            experiment_id: 实验 ID
            query: 关键词或字段化查询表达式
            limit: 返回数量限制
            offset: 分页偏移
            sort_by: 排序字段表达式（可选）
            sort_order: 默认排序方向

        返回：
            符合条件的实验分组列表

        异常：
            ValueError: 查询条件或排序字段不受支持
        """
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
        """按指定时间间隔获取 API 调用趋势.

        参数：
            since: 统计起始时间
            interval: 时间分桶间隔
            origin: 时间分桶基准点

        返回：
            各时间分桶的调用量、成功量和失败量列表
        """
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
        """获取当前和上一周期的 API 调用核心指标.

        参数：
            since: 当前统计周期起始时间
            previous_since: 上一统计周期起始时间

        返回：
            调用量、成功量、失败量、耗时及上一周期调用量
        """
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
        """获取全部模型的最近调用表现和累计调用量.

        参数：
            since: 最近调用统计起始时间

        返回：
            各模型的近期调用指标和历史累计调用量列表
        """
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
