"""模型执行仓储

提供模型执行记录的创建、查询和状态迁移能力。

核心功能：
  - get_execution: 获取模型执行记录
  - list_executions: 获取模型执行记录列表
  - create_execution: 创建模型执行记录
  - mark_running: 标记模型执行开始
  - mark_success: 标记模型执行成功
  - mark_failed: 标记模型执行未成功
  - reset_for_retry: 重置影子模型执行状态
"""

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.db.models.executions import Execution
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import (
    ExecutionStatus,
    ExecutionType,
)


TERMINAL_EXECUTION_STATUSES = frozenset({
    ExecutionStatus.SUCCESS,
    ExecutionStatus.FAILED,
    ExecutionStatus.TIMEOUT,
    ExecutionStatus.CANCELLED,
})
FAILED_EXECUTION_STATUSES = frozenset({
    ExecutionStatus.FAILED,
    ExecutionStatus.TIMEOUT,
    ExecutionStatus.CANCELLED,
})


class ExecutionRepository(BaseRepository):
    """模型执行仓储"""

    async def get_execution(
            self,
            execution_id: str,
    ) -> Execution | None:
        """按照执行 ID 获取模型执行记录"""
        stmt = select(
            Execution
        ).where(
            Execution.execution_id
            == execution_id
        )
        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_executions(
            self,
            *,
            decision_id: str | None = None,
            deployment_id: str | None = None,
            execution_type: ExecutionType | None = None,
            status: ExecutionStatus | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Execution]:
        """获取模型执行记录列表"""
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )
        stmt = select(
            Execution
        )

        if decision_id is not None:
            stmt = stmt.where(
                Execution.decision_id
                == decision_id
            )

        if deployment_id is not None:
            stmt = stmt.where(
                Execution.deployment_id
                == deployment_id
            )

        if execution_type is not None:
            stmt = stmt.where(
                Execution.execution_type
                == str(
                    execution_type
                )
            )

        if status is not None:
            stmt = stmt.where(
                Execution.status
                == str(
                    status
                )
            )

        stmt = stmt.order_by(
            Execution.created_at.asc(),
            Execution.id.asc(),
        )

        if offset is not None:
            stmt = stmt.offset(
                offset
            )

        if limit is not None:
            stmt = stmt.limit(
                limit
            )

        result = await self.session.execute(
            stmt
        )

        return list(
            result.scalars().all()
        )

    def create_execution(
            self,
            *,
            execution_id: str,
            decision_id: str,
            execution_type: ExecutionType,
            status: ExecutionStatus,
            model_id: str,
            version_id: str,
            deployment_id: str | None,
            routing_id: str | None = None,
            prediction: dict | None = None,
            probability: float | None = None,
            score: float | None = None,
            latency_ms: float | None = None,
            error_type: str | None = None,
            error: str | None = None,
            context: dict | None = None,
            started_at: datetime | None = None,
            finished_at: datetime | None = None,
    ) -> Execution:
        """创建模型执行记录"""
        self._validate_probability(
            probability
        )
        self._validate_latency_ms(
            latency_ms
        )

        if (
                status in TERMINAL_EXECUTION_STATUSES
                and finished_at is None
        ):
            finished_at = datetime.now(
                timezone.utc
            )

        new_execution = Execution(
            execution_id=execution_id,
            decision_id=decision_id,
            execution_type=str(
                execution_type
            ),
            status=str(
                status
            ),
            model_id=model_id,
            version_id=version_id,
        )

        if deployment_id is not None:
            new_execution.deployment_id = deployment_id

        if routing_id is not None:
            new_execution.routing_id = routing_id

        if prediction is not None:
            new_execution.prediction = prediction

        if probability is not None:
            new_execution.probability = probability

        if score is not None:
            new_execution.score = score

        if latency_ms is not None:
            new_execution.latency_ms = latency_ms

        if error_type is not None:
            new_execution.error_type = error_type

        if error is not None:
            new_execution.error = error

        if context is not None:
            new_execution.context = context

        if started_at is not None:
            new_execution.started_at = started_at

        if finished_at is not None:
            new_execution.finished_at = finished_at

        self.add(
            new_execution
        )

        return new_execution

    @staticmethod
    def mark_running(
            execution: Execution,
            *,
            started_at: datetime | None = None,
    ) -> Execution:
        """标记模型执行开始"""
        current_status = ExecutionStatus(
            execution.status
        )

        if current_status != ExecutionStatus.QUEUED:
            raise ValueError(
                "只有 queued 状态的模型执行可以开始"
            )

        execution.status = str(
            ExecutionStatus.RUNNING
        )
        execution.started_at = (
            started_at
            if started_at is not None
            else datetime.now(
                timezone.utc
            )
        )

        return execution

    def mark_success(
            self,
            execution: Execution,
            *,
            prediction: dict,
            probability: float | None = None,
            score: float | None = None,
            latency_ms: float | None = None,
            finished_at: datetime | None = None,
    ) -> Execution:
        """标记模型执行成功"""
        self._require_running(
            execution
        )
        self._validate_probability(
            probability
        )
        self._validate_latency_ms(
            latency_ms
        )
        execution.status = str(
            ExecutionStatus.SUCCESS
        )
        execution.prediction = prediction
        execution.error_type = None
        execution.error = None
        execution.finished_at = (
            finished_at
            if finished_at is not None
            else datetime.now(
                timezone.utc
            )
        )

        if probability is not None:
            execution.probability = probability

        if score is not None:
            execution.score = score

        if latency_ms is not None:
            execution.latency_ms = latency_ms

        return execution

    def mark_failed(
            self,
            execution: Execution,
            *,
            status: ExecutionStatus,
            error: str,
            error_type: str | None = None,
            latency_ms: float | None = None,
            finished_at: datetime | None = None,
    ) -> Execution:
        """标记模型执行未成功"""
        if status not in FAILED_EXECUTION_STATUSES:
            raise ValueError(
                "模型执行失败状态无效"
            )

        current_status = ExecutionStatus(
            execution.status
        )

        if current_status not in {
            ExecutionStatus.QUEUED,
            ExecutionStatus.RUNNING,
        }:
            raise ValueError(
                "只有 queued 或 running 状态的模型执行可以结束"
            )

        self._validate_latency_ms(
            latency_ms
        )
        execution.status = str(
            status
        )
        execution.error = error
        execution.finished_at = (
            finished_at
            if finished_at is not None
            else datetime.now(
                timezone.utc
            )
        )

        if error_type is not None:
            execution.error_type = error_type

        if latency_ms is not None:
            execution.latency_ms = latency_ms

        return execution

    @staticmethod
    def reset_for_retry(execution: Execution) -> Execution:
        """重置未成功的影子执行以便重试

        参数：
            execution: 模型执行记录

        返回：
            重新进入 queued 状态的模型执行记录

        异常：
            ValueError: 执行不是影子执行或当前状态不允许重试
        """
        execution_type = ExecutionType(
            execution.execution_type
        )

        if execution_type != ExecutionType.SHADOW:
            raise ValueError(
                "只有影子模型执行可以重试"
            )

        current_status = ExecutionStatus(
            execution.status
        )

        if current_status not in FAILED_EXECUTION_STATUSES:
            raise ValueError(
                "只有未成功的影子模型执行可以重试"
            )

        execution.status = str(ExecutionStatus.QUEUED)
        execution.prediction = None
        execution.probability = None
        execution.score = None
        execution.latency_ms = None
        execution.error_type = None
        execution.error = None
        execution.started_at = None
        execution.finished_at = None
        return execution

    @staticmethod
    def _require_running(
            execution: Execution,
    ) -> None:
        """校验模型执行处于 running 状态"""
        if ExecutionStatus(
                execution.status
        ) != ExecutionStatus.RUNNING:
            raise ValueError(
                "只有 running 状态的模型执行可以成功结束"
            )

    @staticmethod
    def _validate_probability(
            probability: float | None,
    ) -> None:
        """校验预测概率"""
        if (
                probability is not None
                and not 0 <= probability <= 1
        ):
            raise ValueError(
                "probability 必须在 0 到 1 之间"
            )

    @staticmethod
    def _validate_latency_ms(
            latency_ms: float | None,
    ) -> None:
        """校验执行耗时"""
        if (
                latency_ms is not None
                and latency_ms < 0
        ):
            raise ValueError(
                "latency_ms 不能小于 0"
            )

    @staticmethod
    def _validate_pagination(
            *,
            limit: int | None,
            offset: int | None,
    ) -> None:
        """校验分页参数"""
        if limit is not None and limit < 0:
            raise ValueError(
                "limit 不能小于 0"
            )

        if offset is not None and offset < 0:
            raise ValueError(
                "offset 不能小于 0"
            )
