# datamind/db/repositories/decision.py

"""请求决策仓储

用于查询与写入请求决策结果，支持在线推理、A/B 测试、灰度发布和决策审计。

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
      repo = DecisionRepository(uow.session)

      decision = repo.create_decision(
          decision_id="dcs_a1b2c3d4",
          request_id="req_a1b2c3d4",
          model_id="mdl_a1b2c3d4",
          version_id="ver_a1b2c3d4",
          deployment_id="dep_a1b2c3d4",
          experiment_id="exp_a1b2c3d4",
          variant_id="var_a1b2c3d4",
          customer_id="cus_a1b2c3d4",
          source=DecisionStrategy.EXPERIMENT,
          strategy="hash",
          bucket="bucket_0089",
          group="treatment",
          weight=0.5,
          probability=0.12,
          score=680,
          decision="approve",
          latency_ms=35.6,
          context={"experiment_id": "exp_a1b2c3d4", "group": "treatment"}
      )
"""

from datetime import datetime, timezone

from sqlalchemy import select

from datamind.db.models.decisions import Decision
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import DecisionStrategy


class DecisionRepository(BaseRepository):
    """请求决策仓储"""

    async def get_decision(
        self,
        request_id: str,
    ) -> Decision | None:
        """获取请求的决策结果

        参数：
            request_id: 请求 ID

        返回：
            决策记录对象，不存在时返回 None
        """
        stmt = select(Decision).where(Decision.request_id == request_id)
        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def list_decisions(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
        **filters,
    ) -> list[Decision]:
        """获取请求决策记录列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）
            **filters: 过滤条件
                支持字段：
                    request_id
                    model_id
                    version_id
                    deployment_id
                    experiment_id
                    variant_id
                    customer_id
                    source
                    strategy
                    bucket
                    group
                    decision

        返回：
            决策记录列表，按决策时间倒序排列
        """
        stmt = select(Decision)

        if filters:
            stmt = stmt.filter_by(**filters)

        stmt = stmt.order_by(
            Decision.decided_at.desc(),
            Decision.created_at.desc(),
        )

        if offset is not None:
            stmt = stmt.offset(offset)

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def list_model_decisions(
        self,
        model_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Decision]:
        """获取模型决策记录

        参数：
            model_id: 模型 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            决策记录列表，按决策时间倒序排列
        """
        filters = {
            "model_id": model_id,
        }

        return await self.list_decisions(
            limit=limit,
            offset=offset,
            **filters,
        )

    async def list_deployment_decisions(
        self,
        deployment_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Decision]:
        """获取部署决策记录

        参数：
            deployment_id: 部署 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            决策记录列表，按决策时间倒序排列
        """
        filters = {
            "deployment_id": deployment_id,
        }

        return await self.list_decisions(
            limit=limit,
            offset=offset,
            **filters,
        )

    async def list_experiment_decisions(
        self,
        experiment_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Decision]:
        """获取实验决策记录

        参数：
            experiment_id: 实验 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            决策记录列表，按决策时间倒序排列
        """
        filters = {
            "experiment_id": experiment_id,
        }

        return await self.list_decisions(
            limit=limit,
            offset=offset,
            **filters,
        )

    async def list_variant_decisions(
        self,
        variant_id: str,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[Decision]:
        """获取实验分组决策记录

        参数：
            variant_id: 实验分组 ID
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            决策记录列表，按决策时间倒序排列
        """
        filters = {
            "variant_id": variant_id,
        }

        return await self.list_decisions(
            limit=limit,
            offset=offset,
            **filters,
        )

    def create_decision(
        self,
        *,
        decision_id: str,
        request_id: str,
        model_id: str,
        version_id: str,
        customer_id: str,
        source: DecisionStrategy,
        deployment_id: str | None = None,
        experiment_id: str | None = None,
        variant_id: str | None = None,
        strategy: str | None = None,
        bucket: str | None = None,
        group: str | None = None,
        weight: float | None = None,
        prediction: dict | None = None,
        probability: float | None = None,
        score: float | None = None,
        decision: str | None = None,
        latency_ms: float | None = None,
        context: dict | None = None,
        decided_at: datetime | None = None,
    ) -> Decision:
        """创建决策记录

        参数：
            decision_id: 决策记录 ID
            request_id: 请求 ID
            model_id: 模型 ID
            version_id: 版本 ID
            customer_id: 客户 ID
            source: 决策来源
            deployment_id: 部署 ID（可选）
            experiment_id: 实验 ID（可选）
            variant_id: 实验分组 ID（可选）
            strategy: 分配策略（可选）
            bucket: 分桶标识（可选）
            group: 实验组别（可选）
            weight: 分组权重（可选）
            prediction: 模型预测结果（可选）
            probability: 预测概率（可选）
            score: 评分结果（可选）
            decision: 最终决策结果（可选）
            latency_ms: 决策耗时（可选）
            context: 决策上下文（可选）
            decided_at: 决策时间（可选）

        返回：
            创建后的决策记录对象
        """
        obj = Decision(
            decision_id=decision_id,
            request_id=request_id,
            model_id=model_id,
            version_id=version_id,
            deployment_id=deployment_id,
            experiment_id=experiment_id,
            variant_id=variant_id,
            customer_id=customer_id,
            source=source,
            strategy=strategy,
            bucket=bucket,
            group=group,
            weight=weight,
            prediction=prediction,
            probability=probability,
            score=score,
            decision=decision,
            latency_ms=latency_ms,
            context=context,
            decided_at=decided_at or datetime.now(timezone.utc),
        )

        self.add(obj)

        return obj