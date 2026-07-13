# datamind/services/outcome.py

"""实验结果回流服务

负责接收业务系统延迟回流的审批、转化和表现结果，
并按照原始请求决策补齐实验关联信息。

核心功能：
  - OutcomeService.submit: 幂等提交实验结果

使用示例：
  from datamind.services.outcome import OutcomeService

  result = await OutcomeService().submit(
      outcome_id="out_0123456789abcdef",
      decision_id="dcs_0123456789abcdef",
      subject_key="customer_10001",
      approved=True,
      converted=True,
  )
"""

from datetime import datetime
from typing import Any

from datamind.db.core import UnitOfWork
from datamind.db.models.decisions import Decision
from datamind.db.models.outcomes import Outcome
from datamind.db.repositories import (
    DecisionRepository,
    OutcomePatch,
    OutcomeRepository,
)


class OutcomeService:
    """实验结果回流服务"""

    async def submit(
            self,
            *,
            outcome_id: str,
            subject_key: str,
            decision_id: str | None = None,
            request_id: str | None = None,
            subject_type: str | None = None,
            approved: bool | None = None,
            converted: bool | None = None,
            defaulted: bool | None = None,
            overdue_days: int | None = None,
            amount: float | None = None,
            label: str | None = None,
            context: dict[str, Any] | None = None,
            outcome_time: datetime | None = None,
    ) -> dict[str, Any]:
        """幂等提交实验结果

        必须提供 decision_id 或 request_id，服务会从原始决策中
        补齐实验、分组、分配和请求关联信息。相同 outcome_id
        再次回流时更新业务结果，不重复创建记录。

        参数：
            outcome_id: 上游结果唯一标识
            subject_key: 结果主体标识
            decision_id: 原始决策 ID（可选）
            request_id: 原始请求 ID（可选）
            subject_type: 结果主体类型（可选）
            approved: 是否审批通过（可选）
            converted: 是否发生转化（可选）
            defaulted: 是否违约（可选）
            overdue_days: 最大逾期天数（可选）
            amount: 结果金额（可选）
            label: 结果标签（可选）
            context: 结果上下文（可选）
            outcome_time: 结果发生时间（可选）

        返回：
            结果记录及本次是否新建

        异常：
            ValueError: 参数为空、原始决策不存在或关联不一致
        """
        normalized_outcome_id = self._require_text(
            "outcome_id",
            outcome_id,
        )
        normalized_subject_key = self._require_text(
            "subject_key",
            subject_key,
        )

        if decision_id is None and request_id is None:
            raise ValueError(
                "decision_id 和 request_id 至少需要提供一个"
            )

        async with UnitOfWork() as uow:
            decision_repo = DecisionRepository(
                uow.session
            )
            outcome_repo = OutcomeRepository(
                uow.session
            )

            decision = await self._resolve_decision(
                repository=decision_repo,
                decision_id=decision_id,
                request_id=request_id,
            )

            self._validate_decision_subject(
                decision=decision,
                subject_key=normalized_subject_key,
            )

            outcome = await outcome_repo.get_outcome(
                normalized_outcome_id
            )
            created = outcome is None

            if outcome is None:
                outcome = outcome_repo.create_outcome(
                    outcome_id=normalized_outcome_id,
                    subject_key=normalized_subject_key,
                    experiment_id=decision.experiment_id,
                    variant_id=decision.variant_id,
                    assignment_id=decision.assignment_id,
                    decision_id=decision.decision_id,
                    request_id=decision.request_id,
                    subject_type=(
                        subject_type
                        or decision.subject_type
                    ),
                    approved=approved,
                    converted=converted,
                    defaulted=defaulted,
                    overdue_days=overdue_days,
                    amount=amount,
                    label=label,
                    context=context,
                    outcome_time=outcome_time,
                )

            else:
                self._validate_existing_outcome(
                    outcome=outcome,
                    decision=decision,
                    subject_key=normalized_subject_key,
                )
                outcome_repo.update_outcome(
                    outcome,
                    OutcomePatch(
                        subject_type=subject_type,
                        approved=approved,
                        converted=converted,
                        defaulted=defaulted,
                        overdue_days=overdue_days,
                        amount=amount,
                        label=label,
                        context=context,
                        outcome_time=outcome_time,
                    ),
                )

            await uow.session.flush()
            await uow.session.refresh(
                outcome
            )

            result: dict[str, Any] = {
                "created": created,
                "outcome": self._to_dict(
                    outcome
                ),
            }

        return result

    @staticmethod
    async def _resolve_decision(
            *,
            repository: DecisionRepository,
            decision_id: str | None,
            request_id: str | None,
    ) -> Decision:
        """查找并校验原始决策"""
        by_decision = (
            await repository.get_by_decision_id(
                decision_id
            )
            if decision_id is not None
            else None
        )
        by_request = (
            await repository.get_decision(
                request_id
            )
            if request_id is not None
            else None
        )

        if decision_id is not None and by_decision is None:
            raise ValueError(
                f"原始决策不存在: {decision_id}"
            )

        if request_id is not None and by_request is None:
            raise ValueError(
                f"原始请求没有决策记录: {request_id}"
            )

        if (
                by_decision is not None
                and by_request is not None
                and by_decision.decision_id
                != by_request.decision_id
        ):
            raise ValueError(
                "decision_id 与 request_id 指向不同决策"
            )

        if by_decision is not None:
            return by_decision

        if by_request is not None:
            return by_request

        raise ValueError(
            "原始决策不存在"
        )

    @staticmethod
    def _validate_decision_subject(
            *,
            decision: Decision,
            subject_key: str,
    ) -> None:
        """校验回流主体与原始决策一致"""
        if (
                decision.subject_key is not None
                and decision.subject_key != subject_key
        ):
            raise ValueError(
                "subject_key 与原始决策不一致"
            )

    @staticmethod
    def _validate_existing_outcome(
            *,
            outcome: Outcome,
            decision: Decision,
            subject_key: str,
    ) -> None:
        """校验幂等更新没有改变结果归属"""
        if outcome.decision_id != decision.decision_id:
            raise ValueError(
                "outcome_id 已关联其他决策"
            )

        if outcome.subject_key != subject_key:
            raise ValueError(
                "outcome_id 已关联其他主体"
            )

    @staticmethod
    def _require_text(
            field_name: str,
            value: str,
    ) -> str:
        """校验必填字符串"""
        normalized = value.strip()

        if normalized == "":
            raise ValueError(
                f"{field_name} 不能为空"
            )

        return normalized

    @staticmethod
    def _to_dict(
            outcome: Outcome,
    ) -> dict[str, Any]:
        """转换结果记录为字典"""
        return {
            "outcome_id": outcome.outcome_id,
            "experiment_id": outcome.experiment_id,
            "variant_id": outcome.variant_id,
            "assignment_id": outcome.assignment_id,
            "decision_id": outcome.decision_id,
            "request_id": outcome.request_id,
            "subject_key": outcome.subject_key,
            "subject_type": outcome.subject_type,
            "approved": outcome.approved,
            "converted": outcome.converted,
            "defaulted": outcome.defaulted,
            "overdue_days": outcome.overdue_days,
            "amount": outcome.amount,
            "label": outcome.label,
            "context": outcome.context,
            "outcome_time": outcome.outcome_time,
            "created_at": outcome.created_at,
            "updated_at": outcome.updated_at,
        }
