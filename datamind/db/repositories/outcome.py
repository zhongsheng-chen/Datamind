"""实验结果仓储

用于查询与写入实验结果回流数据，
支持 A/B 测试效果评估、模型表现监控和业务指标统计。

核心功能：
  - get_outcome: 获取实验结果
  - list_outcomes: 获取实验结果列表
  - list_experiment_outcomes: 获取实验结果列表
  - list_variant_outcomes: 获取实验分组结果列表
  - list_subject_outcomes: 获取主体结果列表
  - list_request_outcomes: 获取请求结果列表
  - create_outcome: 创建实验结果
  - update_outcome: 更新实验结果

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.outcome import (
      OutcomePatch,
      OutcomeRepository,
  )

  async with UnitOfWork() as uow:
      repo = OutcomeRepository(
          uow.session
      )

      outcome = repo.create_outcome(
          outcome_id="out_0123456789abcdef",
          experiment_id="exp_0123456789abcdef",
          variant_id="var_0123456789abcdef",
          assignment_id="asn_0123456789abcdef",
          decision_id="dcs_0123456789abcdef",
          request_id="req_0123456789abcdef",
          subject_key="customer_10001",
          subject_type="customer",
          approved=True,
          converted=True,
          defaulted=False,
          overdue_days=0,
          amount=10000.0,
          label="good",
          context={
              "source": "loan_core",
          },
      )

      repo.update_outcome(
          outcome,
          OutcomePatch(
              overdue_days=35,
              defaulted=True,
              label="bad",
          ),
      )
"""

from dataclasses import (
    dataclass,
    fields,
)
from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.db.models.outcomes import Outcome
from datamind.db.repositories.base import BaseRepository


@dataclass(slots=True)
class OutcomePatch:
    """实验结果更新结构

    属性：
        experiment_id: 实验 ID
        variant_id: 实验分组 ID
        assignment_id: 实验分配 ID
        decision_id: 请求决策 ID
        request_id: 请求 ID
        subject_key: 结果主体标识
        subject_type: 结果主体类型
        approved: 是否审批通过
        converted: 是否转化
        defaulted: 是否违约或成为坏样本
        overdue_days: 最大逾期天数
        amount: 结果金额
        label: 结果标签
        context: 结果上下文
        outcome_time: 结果发生时间
    """

    experiment_id: str | None = None
    variant_id: str | None = None
    assignment_id: str | None = None
    decision_id: str | None = None
    request_id: str | None = None
    subject_key: str | None = None
    subject_type: str | None = None
    approved: bool | None = None
    converted: bool | None = None
    defaulted: bool | None = None
    overdue_days: int | None = None
    amount: float | None = None
    label: str | None = None
    context: dict | None = None
    outcome_time: datetime | None = None


class OutcomeRepository(BaseRepository):
    """实验结果仓储"""

    @staticmethod
    def _validate_pagination(
            *,
            limit: int | None,
            offset: int | None,
    ) -> None:
        """校验分页参数"""
        if (
                limit is not None
                and limit < 0
        ):
            raise ValueError(
                "limit 不能小于 0"
            )

        if (
                offset is not None
                and offset < 0
        ):
            raise ValueError(
                "offset 不能小于 0"
            )

    @staticmethod
    def _validate_overdue_days(
            overdue_days: int | None,
    ) -> None:
        """校验最大逾期天数"""
        if (
                overdue_days is not None
                and overdue_days < 0
        ):
            raise ValueError(
                "overdue_days 不能小于 0"
            )

    @staticmethod
    def _validate_amount(
            amount: float | None,
    ) -> None:
        """校验结果金额"""
        if (
                amount is not None
                and amount < 0
        ):
            raise ValueError(
                "amount 不能小于 0"
            )

    async def get_outcome(
            self,
            outcome_id: str,
    ) -> Outcome | None:
        """获取实验结果

        参数：
            outcome_id: 结果 ID

        返回：
            实验结果对象，不存在时返回 None
        """
        stmt = select(
            Outcome
        ).where(
            Outcome.outcome_id
            == outcome_id
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_outcomes(
            self,
            *,
            outcome_id: str | None = None,
            experiment_id: str | None = None,
            variant_id: str | None = None,
            assignment_id: str | None = None,
            decision_id: str | None = None,
            request_id: str | None = None,
            subject_key: str | None = None,
            subject_type: str | None = None,
            approved: bool | None = None,
            converted: bool | None = None,
            defaulted: bool | None = None,
            label: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Outcome]:
        """获取实验结果列表

        参数：
            outcome_id: 结果 ID（可选）
            experiment_id: 实验 ID（可选）
            variant_id: 实验分组 ID（可选）
            assignment_id: 实验分配 ID（可选）
            decision_id: 请求决策 ID（可选）
            request_id: 请求 ID（可选）
            subject_key: 结果主体标识（可选）
            subject_type: 结果主体类型（可选）
            approved: 是否审批通过（可选）
            converted: 是否转化（可选）
            defaulted: 是否违约或成为坏样本（可选）
            label: 结果标签（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验结果列表，按结果发生时间和创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        stmt = select(
            Outcome
        )

        if outcome_id is not None:
            stmt = stmt.where(
                Outcome.outcome_id
                == outcome_id
            )

        if experiment_id is not None:
            stmt = stmt.where(
                Outcome.experiment_id
                == experiment_id
            )

        if variant_id is not None:
            stmt = stmt.where(
                Outcome.variant_id
                == variant_id
            )

        if assignment_id is not None:
            stmt = stmt.where(
                Outcome.assignment_id
                == assignment_id
            )

        if decision_id is not None:
            stmt = stmt.where(
                Outcome.decision_id
                == decision_id
            )

        if request_id is not None:
            stmt = stmt.where(
                Outcome.request_id
                == request_id
            )

        if subject_key is not None:
            stmt = stmt.where(
                Outcome.subject_key
                == subject_key
            )

        if subject_type is not None:
            stmt = stmt.where(
                Outcome.subject_type
                == subject_type
            )

        if approved is not None:
            stmt = stmt.where(
                Outcome.approved
                == approved
            )

        if converted is not None:
            stmt = stmt.where(
                Outcome.converted
                == converted
            )

        if defaulted is not None:
            stmt = stmt.where(
                Outcome.defaulted
                == defaulted
            )

        if label is not None:
            stmt = stmt.where(
                Outcome.label
                == label
            )

        stmt = stmt.order_by(
            Outcome.outcome_time.desc(),
            Outcome.created_at.desc(),
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

    async def list_experiment_outcomes(
            self,
            experiment_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Outcome]:
        """获取实验结果列表

        参数：
            experiment_id: 实验 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验结果列表，按结果发生时间和创建时间倒序排列
        """
        return await self.list_outcomes(
            experiment_id=experiment_id,
            limit=limit,
            offset=offset,
        )

    async def list_variant_outcomes(
            self,
            variant_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Outcome]:
        """获取实验分组结果列表

        参数：
            variant_id: 实验分组 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验结果列表，按结果发生时间和创建时间倒序排列
        """
        return await self.list_outcomes(
            variant_id=variant_id,
            limit=limit,
            offset=offset,
        )

    async def list_subject_outcomes(
            self,
            subject_key: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Outcome]:
        """获取主体结果列表

        参数：
            subject_key: 结果主体标识
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验结果列表，按结果发生时间和创建时间倒序排列
        """
        return await self.list_outcomes(
            subject_key=subject_key,
            limit=limit,
            offset=offset,
        )

    async def list_request_outcomes(
            self,
            request_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Outcome]:
        """获取请求结果列表

        参数：
            request_id: 请求 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验结果列表，按结果发生时间和创建时间倒序排列
        """
        return await self.list_outcomes(
            request_id=request_id,
            limit=limit,
            offset=offset,
        )

    def create_outcome(
            self,
            *,
            outcome_id: str,
            subject_key: str,
            experiment_id: str | None = None,
            variant_id: str | None = None,
            assignment_id: str | None = None,
            decision_id: str | None = None,
            request_id: str | None = None,
            subject_type: str | None = None,
            approved: bool | None = None,
            converted: bool | None = None,
            defaulted: bool | None = None,
            overdue_days: int | None = None,
            amount: float | None = None,
            label: str | None = None,
            context: dict | None = None,
            outcome_time: datetime | None = None,
    ) -> Outcome:
        """创建实验结果

        参数：
            outcome_id: 结果 ID
            subject_key: 结果主体标识
            experiment_id: 实验 ID（可选）
            variant_id: 实验分组 ID（可选）
            assignment_id: 实验分配 ID（可选）
            decision_id: 请求决策 ID（可选）
            request_id: 请求 ID（可选）
            subject_type: 结果主体类型（可选）
            approved: 是否审批通过（可选）
            converted: 是否转化（可选）
            defaulted: 是否违约或成为坏样本（可选）
            overdue_days: 最大逾期天数（可选）
            amount: 结果金额（可选）
            label: 结果标签（可选）
            context: 结果上下文（可选）
            outcome_time: 结果发生时间（可选）

        返回：
            创建后的实验结果对象

        异常：
            ValueError: overdue_days 或 amount 小于 0
        """
        self._validate_overdue_days(
            overdue_days
        )
        self._validate_amount(
            amount
        )

        new_outcome = Outcome(
            outcome_id=outcome_id,
            subject_key=subject_key,
            context=context,
            outcome_time=(
                outcome_time
                if outcome_time is not None
                else datetime.now(
                    timezone.utc
                )
            ),
        )

        if experiment_id is not None:
            new_outcome.experiment_id = experiment_id

        if variant_id is not None:
            new_outcome.variant_id = variant_id

        if assignment_id is not None:
            new_outcome.assignment_id = assignment_id

        if decision_id is not None:
            new_outcome.decision_id = decision_id

        if request_id is not None:
            new_outcome.request_id = request_id

        if subject_type is not None:
            new_outcome.subject_type = subject_type

        if approved is not None:
            new_outcome.approved = approved

        if converted is not None:
            new_outcome.converted = converted

        if defaulted is not None:
            new_outcome.defaulted = defaulted

        if overdue_days is not None:
            new_outcome.overdue_days = overdue_days

        if amount is not None:
            new_outcome.amount = amount

        if label is not None:
            new_outcome.label = label

        self.add(
            new_outcome
        )

        return new_outcome

    def update_outcome(
            self,
            outcome: Outcome,
            patch: OutcomePatch,
    ) -> Outcome:
        """更新实验结果

        参数：
            outcome: 实验结果对象
            patch: 更新内容

        返回：
            更新后的实验结果对象

        异常：
            ValueError: overdue_days 或 amount 小于 0
        """
        self._validate_overdue_days(
            patch.overdue_days
        )
        self._validate_amount(
            patch.amount
        )

        for field in fields(
                OutcomePatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            setattr(
                outcome,
                field.name,
                value,
            )

        return outcome
