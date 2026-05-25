# datamind/db/repositories/experiment.py

"""实验仓储

提供 A/B 实验与灰度策略的查询与管理能力。

核心功能：
  - get_experiment: 获取实验
  - list_running_experiments: 获取运行中实验列表
  - list_experiments: 列出所有实验列表
  - create_experiment: 创建实验
  - update_experiment: 更新实验
  - stop_experiment: 停止实验

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import ExperimentRepository, ExperimentPatch

  async with UnitOfWork() as uow:
      repo = ExperimentRepository(uow.session)

      experiment = await repo.create_experiment(
          experiment_id="exp_a1b2c3d4",
          model_id="mdl_a1b2c3d4",
          name="评分卡A/B测试实验",
          description="测试新策略",
          config={
              "strategy": "consistent",
              "variants": [
                  {"name": "control", "weight": 0.5},
                  {"name": "treatment", "weight": 0.5},
              ],
          },
          created_by="system"
      )
"""

from datetime import datetime, timezone
from dataclasses import dataclass, fields
from sqlalchemy import select

from datamind.db.models.experiments import Experiment
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import ExperimentStatus


@dataclass(slots=True)
class ExperimentPatch:
    """实验更新结构

    属性：
        name: 实验名称
        description: 实验描述
        config: 实验配置
        effective_from: 生效开始时间
        effective_to: 生效结束时间
    """
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class ExperimentRepository(BaseRepository):
    """实验仓储"""

    async def get_experiment(self, experiment_id: str) -> Experiment | None:
        """获取实验

        参数：
            experiment_id: 实验 ID

        返回：
            实验对象，不存在时返回 None
        """
        stmt = select(Experiment).where(Experiment.experiment_id == experiment_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_running_experiments(self, model_id: str) -> list[Experiment]:
        """获取运行中的实验

        参数：
            model_id: 模型 ID

        返回：
            运行中的实验列表
        """
        stmt = select(Experiment).where(
            Experiment.model_id == model_id,
            Experiment.status == "running",
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_experiments(self, model_id: str) -> list[Experiment]:
        """列出所有实验

        参数：
            model_id: 模型 ID

        返回：
            实验列表，按创建时间倒序排列
        """
        stmt = (
            select(Experiment)
            .where(Experiment.model_id == model_id)
            .order_by(Experiment.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_experiment(
        self,
        *,
        experiment_id: str,
        model_id: str,
        name: str | None = None,
        description: str | None = None,
        config: dict | None = None,
        effective_from: datetime | None = None,
        effective_to: datetime | None = None,
        created_by: str | None = None,
    ) -> Experiment:
        """创建实验

        参数：
            experiment_id: 实验 ID
            model_id: 模型 ID
            name: 实验名称（可选）
            description: 实验描述（可选）
            status: 实验状态
            config: 实验配置（可选）
            effective_from: 生效开始时间（可选）
            effective_to: 生效结束时间（可选）
            created_by: 创建人（可选）

        返回：
            创建后的实验对象
        """
        obj = Experiment(
            experiment_id=experiment_id,
            model_id=model_id,
            name=name,
            description=description,
            config=config,
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=created_by,
        )

        self.add(obj)
        return obj

    def update_experiment(self, experiment: Experiment, patch: ExperimentPatch) -> Experiment:
        """更新实验

        参数：
            experiment: 实验对象
            patch: 更新内容

        返回：
            更新后的实验对象
        """
        for field in fields(ExperimentPatch):
            field_name = field.name

            if field_name == "status":
                continue

            value = getattr(patch, field_name)

            if value is None:
                continue

            setattr(experiment, field_name, value)

        experiment.updated_at = datetime.now(timezone.utc)

        return experiment

    def stop_experiment(self, experiment: Experiment, updated_by: str | None = None) -> Experiment:
        """停止实验

        参数：
            experiment: 实验对象
            updated_by: 更新人（可选）

        返回：
            停止后的实验对象
        """
        experiment.status = ExperimentStatus.STOPPED

        if updated_by:
            experiment.updated_by = updated_by

        return experiment

    def pause_experiment(self, experiment: Experiment, updated_by: str | None = None) -> Experiment:
        """暂停实验

        参数：
            experiment: 实验对象
            updated_by: 更新人（可选）

        返回：
            暂停后的实验对象
        """
        experiment.status = ExperimentStatus.PAUSED

        if updated_by:
            experiment.updated_by = updated_by

        return experiment

    def complete_experiment(self, experiment: Experiment, updated_by: str | None = None) -> Experiment:
        """完成实验

        参数：
            experiment: 实验对象
            updated_by: 更新人（可选）

        返回：
            完成后的实验对象
        """
        experiment.status = ExperimentStatus.COMPLETED

        if updated_by:
            experiment.updated_by = updated_by

        return experiment

    def archive_experiment(self, experiment: Experiment, updated_by: str | None = None) -> Experiment:
        """归档实验

        参数：
            experiment: 实验对象
            updated_by: 更新人（可选）

        返回：
            归档后的实验对象
        """
        experiment.status = ExperimentStatus.ARCHIVED

        if updated_by:
            experiment.updated_by = updated_by

        return experiment