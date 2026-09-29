"""请求决策仓储.

用于查询与写入请求决策结果，
支持在线推理、A/B 测试、灰度发布和决策审计。

核心功能：
  - get_decision: 获取请求的决策结果
  - list_decisions: 获取请求决策记录列表
  - list_model_decisions: 获取模型决策记录
  - list_deployment_decisions: 获取部署决策记录
  - list_experiment_decisions: 获取实验决策记录
  - list_variant_decisions: 获取实验分组决策记录
  - create_decision: 创建决策记录

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.decision import DecisionRepository
  from datamind.models.enums import DecisionStrategy

  async with UnitOfWork() as uow:
      repo = DecisionRepository(
          uow.session
      )

      decision = repo.create_decision(
          decision_id="dcs_0123456789abcdef",
          request_id="req_0123456789abcdef",
          model_id="mdl_0123456789abcdef",
          version_id="ver_0123456789abcdef",
          deployment_id="dep_0123456789abcdef",
          experiment_id="exp_0123456789abcdef",
          variant_id="var_0123456789abcdef",
          assignment_id="asn_0123456789abcdef",
          subject_key="customer_10001",
          subject_type="customer",
          source=DecisionStrategy.EXPERIMENT,
          strategy="hash",
          bucket="bucket_0089",
          group="treatment",
          weight=0.5,
          decision="approve",
          context={
              "experiment_id": "exp_0123456789abcdef",
              "group": "treatment",
              ...
          },
      )
"""

from datetime import (
    datetime,
    timezone,
)

from sqlalchemy import select

from datamind.db.models.decisions import Decision
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import DecisionStrategy


class DecisionRepository(BaseRepository):
    """请求决策仓储."""

    async def get_by_decision_id(
            self,
            decision_id: str,
    ) -> Decision | None:
        """按照决策 ID 获取请求决策.

        参数：
            decision_id: 决策 ID

        返回：
            决策记录对象，不存在时返回 None
        """
        stmt = select(
            Decision
        ).where(
            Decision.decision_id
            == decision_id
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    @staticmethod
    def _validate_pagination(
            *,
            limit: int | None,
            offset: int | None,
    ) -> None:
        """校验分页参数."""
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
    def _validate_ratio(
            value: float | None,
            *,
            field_name: str,
    ) -> None:
        """校验取值范围为 0 到 1 的字段."""
        if value is None:
            return

        if (
                value < 0
                or value > 1
        ):
            raise ValueError(
                f"{field_name} 必须在 0 到 1 之间"
            )

    async def get_decision(
            self,
            request_id: str,
    ) -> Decision | None:
        """获取请求最近一次决策结果.

        参数：
            request_id: 请求 ID

        返回：
            最近一次决策记录对象，不存在时返回 None
        """
        stmt = (
            select(Decision)
            .where(
                Decision.request_id
                == request_id
            )
            .order_by(
                Decision.decided_at.desc(),
                Decision.created_at.desc(),
                Decision.id.desc(),
            )
            .limit(1)
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_decisions(
            self,
            *,
            decision_id: str | None = None,
            request_id: str | None = None,
            model_id: str | None = None,
            version_id: str | None = None,
            deployment_id: str | None = None,
            experiment_id: str | None = None,
            variant_id: str | None = None,
            assignment_id: str | None = None,
            subject_key: str | None = None,
            subject_type: str | None = None,
            source: DecisionStrategy | None = None,
            strategy: str | None = None,
            bucket: str | None = None,
            group: str | None = None,
            decision: str | None = None,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Decision]:
        """获取请求决策记录列表.

        参数：
            decision_id: 决策 ID（可选）
            request_id: 请求 ID（可选）
            model_id: 模型 ID（可选）
            version_id: 版本 ID（可选）
            deployment_id: 部署 ID（可选）
            experiment_id: 实验 ID（可选）
            variant_id: 实验分组 ID（可选）
            assignment_id: 实验分配 ID（可选）
            subject_key: 请求主体标识（可选）
            subject_type: 请求主体类型（可选）
            source: 决策来源（可选）
            strategy: 分配策略（可选）
            bucket: 分桶标识（可选）
            group: 实验组别（可选）
            decision: 最终决策结果（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            决策记录列表，按决策时间和创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        stmt = select(
            Decision
        )

        if decision_id is not None:
            stmt = stmt.where(
                Decision.decision_id
                == decision_id
            )

        if request_id is not None:
            stmt = stmt.where(
                Decision.request_id
                == request_id
            )

        if model_id is not None:
            stmt = stmt.where(
                Decision.model_id
                == model_id
            )

        if version_id is not None:
            stmt = stmt.where(
                Decision.version_id
                == version_id
            )

        if deployment_id is not None:
            stmt = stmt.where(
                Decision.deployment_id
                == deployment_id
            )

        if experiment_id is not None:
            stmt = stmt.where(
                Decision.experiment_id
                == experiment_id
            )

        if variant_id is not None:
            stmt = stmt.where(
                Decision.variant_id
                == variant_id
            )

        if assignment_id is not None:
            stmt = stmt.where(
                Decision.assignment_id
                == assignment_id
            )

        if subject_key is not None:
            stmt = stmt.where(
                Decision.subject_key
                == subject_key
            )

        if subject_type is not None:
            stmt = stmt.where(
                Decision.subject_type
                == subject_type
            )

        if source is not None:
            stmt = stmt.where(
                Decision.source
                == str(
                    source
                )
            )

        if strategy is not None:
            stmt = stmt.where(
                Decision.strategy
                == strategy
            )

        if bucket is not None:
            stmt = stmt.where(
                Decision.bucket
                == bucket
            )

        if group is not None:
            stmt = stmt.where(
                Decision.group
                == group
            )

        if decision is not None:
            stmt = stmt.where(
                Decision.decision
                == decision
            )

        stmt = stmt.order_by(
            Decision.decided_at.desc(),
            Decision.created_at.desc(),
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

    async def list_model_decisions(
            self,
            model_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Decision]:
        """获取模型决策记录."""
        return await self.list_decisions(
            model_id=model_id,
            limit=limit,
            offset=offset,
        )

    async def list_deployment_decisions(
            self,
            deployment_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Decision]:
        """获取部署决策记录."""
        return await self.list_decisions(
            deployment_id=deployment_id,
            limit=limit,
            offset=offset,
        )

    async def list_experiment_decisions(
            self,
            experiment_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Decision]:
        """获取实验决策记录."""
        return await self.list_decisions(
            experiment_id=experiment_id,
            limit=limit,
            offset=offset,
        )

    async def list_variant_decisions(
            self,
            variant_id: str,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Decision]:
        """获取实验分组决策记录."""
        return await self.list_decisions(
            variant_id=variant_id,
            limit=limit,
            offset=offset,
        )

    def create_decision(
            self,
            *,
            decision_id: str,
            request_id: str,
            model_id: str,
            version_id: str,
            source: DecisionStrategy,
            deployment_id: str | None = None,
            experiment_id: str | None = None,
            variant_id: str | None = None,
            assignment_id: str | None = None,
            subject_key: str | None = None,
            subject_type: str | None = None,
            strategy: str | None = None,
            bucket: str | None = None,
            group: str | None = None,
            weight: float | None = None,
            decision: str | None = None,
            context: dict | None = None,
            decided_at: datetime | None = None,
    ) -> Decision:
        """创建决策记录.

        参数：
            decision_id: 决策记录 ID
            request_id: 请求 ID
            model_id: 模型 ID
            version_id: 版本 ID
            source: 决策来源
            deployment_id: 部署 ID（可选）
            experiment_id: 实验 ID（可选）
            variant_id: 实验分组 ID（可选）
            assignment_id: 实验分配 ID（可选）
            subject_key: 请求主体标识（可选）
            subject_type: 请求主体类型（可选）
            strategy: 分配策略（可选）
            bucket: 分桶标识（可选）
            group: 实验组别（可选）
            weight: 分组权重（可选）
            decision: 最终决策结果（可选）
            context: 决策上下文（可选）
            decided_at: 决策时间（可选）

        返回：
            创建后的决策记录对象

        异常：
            ValueError: weight 不合法
        """
        self._validate_ratio(
            weight,
            field_name="weight",
        )
        new_decision = Decision(
            decision_id=decision_id,
            request_id=request_id,
            model_id=model_id,
            version_id=version_id,
            source=str(
                source
            ),
            context=context,
            decided_at=(
                decided_at
                if decided_at is not None
                else datetime.now(
                    timezone.utc
                )
            ),
        )

        if deployment_id is not None:
            new_decision.deployment_id = deployment_id

        if experiment_id is not None:
            new_decision.experiment_id = experiment_id

        if variant_id is not None:
            new_decision.variant_id = variant_id

        if assignment_id is not None:
            new_decision.assignment_id = assignment_id

        if subject_key is not None:
            new_decision.subject_key = subject_key

        if subject_type is not None:
            new_decision.subject_type = subject_type

        if strategy is not None:
            new_decision.strategy = strategy

        if bucket is not None:
            new_decision.bucket = bucket

        if group is not None:
            new_decision.group = group

        if weight is not None:
            new_decision.weight = weight

        if decision is not None:
            new_decision.decision = decision

        self.add(
            new_decision
        )

        return new_decision
