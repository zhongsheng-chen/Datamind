"""实验仓储

提供 A/B 实验与灰度策略的查询、创建、更新和生命周期管理能力。

核心功能：
  - get_experiment: 获取实验
  - get_running_experiment: 获取指定模型和环境下的运行中实验
  - list_experiments: 获取实验列表
  - list_running_experiments: 获取运行中实验列表
  - create_experiment: 创建实验
  - update_experiment: 更新实验
  - start_experiment: 启动实验
  - stop_experiment: 停止实验
  - pause_experiment: 暂停实验
  - complete_experiment: 完成实验
  - archive_experiment: 归档实验
  - mark_deleted: 逻辑删除实验
  - restore_experiment: 恢复实验

使用示例：
  from datamind.constants import Environment
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.experiment import (
      ExperimentPatch,
      ExperimentRepository,
  )

  async with UnitOfWork() as uow:
      repo = ExperimentRepository(
          uow.session
      )

      experiment = repo.create_experiment(
          experiment_id="exp_0123456789abcdef",
          model_id="mdl_0123456789abcdef",
          environment=Environment.DEVELOPMENT,
          name="评分卡 A/B 测试实验",
          description="测试新策略",
          config={
              "strategy": "hash",
              "traffic_ratio": 1.0,
              "bucket_key": "customer_id",
          },
          created_by="system",
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
from typing import Any

from sqlalchemy import (
    or_,
    select,
)
from sqlalchemy.sql import Select

from datamind.constants import Environment
from datamind.db.models.experiments import Experiment
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import ExperimentStatus
from datamind.models.guard import ModelGuard


@dataclass(slots=True)
class ExperimentPatch:
    """实验更新结构

    注意：
        不允许通过 patch 修改 status，
        实验状态由生命周期方法控制。

    属性：
        environment: 实验环境
        name: 实验名称
        description: 实验描述
        config: 实验配置
        effective_from: 生效时间
        effective_to: 失效时间
    """

    environment: Environment | None = None
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None


class ExperimentRepository(BaseRepository):
    """实验仓储"""

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
    def _apply_effective_window(
            stmt: Select[Any],
            *,
            now: datetime | None,
    ) -> Select[Any]:
        """应用实验生效时间窗口条件"""
        if now is None:
            return stmt

        return stmt.where(
            or_(
                Experiment.effective_from.is_(
                    None
                ),
                Experiment.effective_from
                <= now,
            ),
            or_(
                Experiment.effective_to.is_(
                    None
                ),
                Experiment.effective_to
                > now,
            ),
        )

    @staticmethod
    def _transition_experiment(
            experiment: Experiment,
            *,
            target_status: ExperimentStatus,
            updated_by: str | None,
    ) -> Experiment:
        """执行实验状态迁移"""
        current_status = ExperimentStatus(
            experiment.status
        )

        if current_status == target_status:
            return experiment

        ModelGuard.validate_experiment_transition(
            current=current_status,
            target=target_status,
        )

        experiment.status = str(
            target_status
        )

        if updated_by is not None:
            experiment.updated_by = updated_by

        return experiment

    async def get_experiment(
            self,
            experiment_id: str,
            *,
            include_deleted: bool = False,
    ) -> Experiment | None:
        """获取实验

        参数：
            experiment_id: 实验 ID
            include_deleted: 是否包含逻辑删除记录

        返回：
            实验对象，不存在时返回 None
        """
        stmt = select(
            Experiment
        ).where(
            Experiment.experiment_id
            == experiment_id
        )

        if not include_deleted:
            stmt = stmt.where(
                Experiment.deleted_at.is_(
                    None
                )
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_running_experiment(
            self,
            *,
            model_id: str,
            environment: Environment,
            exclude_experiment_id: str | None = None,
            now: datetime | None = None,
    ) -> Experiment | None:
        """获取指定模型和环境下的运行中实验

        参数：
            model_id: 模型 ID
            environment: 实验环境
            exclude_experiment_id: 需要排除的实验 ID（可选）
            now: 当前时间，传入后校验实验生效时间窗口（可选）

        返回：
            运行中的实验对象，不存在时返回 None

        说明：
            如果历史数据中存在多个运行中实验，
            返回创建时间最新的一条。
        """
        stmt = select(
            Experiment
        ).where(
            Experiment.model_id
            == model_id,
            Experiment.environment
            == str(
                environment
            ),
            Experiment.status
            == str(
                ExperimentStatus.RUNNING
            ),
            Experiment.deleted_at.is_(
                None
            ),
        )

        if exclude_experiment_id is not None:
            stmt = stmt.where(
                Experiment.experiment_id
                != exclude_experiment_id
            )

        stmt = self._apply_effective_window(
            stmt,
            now=now,
        ).order_by(
            Experiment.created_at.desc()
        )

        result = await self.session.execute(
            stmt
        )

        return result.scalars().first()

    async def list_experiments(
            self,
            *,
            experiment_id: str | None = None,
            model_id: str | None = None,
            environment: Environment | None = None,
            name: str | None = None,
            status: ExperimentStatus | None = None,
            created_by: str | None = None,
            include_deleted: bool = False,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Experiment]:
        """获取实验列表

        参数：
            experiment_id: 实验 ID（可选）
            model_id: 模型 ID（可选）
            environment: 实验环境（可选）
            name: 实验名称（可选）
            status: 实验状态（可选）
            created_by: 创建人（可选）
            include_deleted: 是否包含逻辑删除记录
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            实验列表，按创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        stmt = select(
            Experiment
        )

        if not include_deleted:
            stmt = stmt.where(
                Experiment.deleted_at.is_(
                    None
                )
            )

        if experiment_id is not None:
            stmt = stmt.where(
                Experiment.experiment_id
                == experiment_id
            )

        if model_id is not None:
            stmt = stmt.where(
                Experiment.model_id
                == model_id
            )

        if environment is not None:
            stmt = stmt.where(
                Experiment.environment
                == str(
                    environment
                )
            )

        if name is not None:
            stmt = stmt.where(
                Experiment.name
                == name
            )

        if status is not None:
            stmt = stmt.where(
                Experiment.status
                == str(
                    status
                )
            )

        if created_by is not None:
            stmt = stmt.where(
                Experiment.created_by
                == created_by
            )

        stmt = stmt.order_by(
            Experiment.created_at.desc()
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

    async def list_running_experiments(
            self,
            model_id: str,
            *,
            environment: Environment | None = None,
            limit: int | None = None,
            offset: int | None = None,
            now: datetime | None = None,
    ) -> list[Experiment]:
        """获取运行中的实验

        参数：
            model_id: 模型 ID
            environment: 实验环境（可选）
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）
            now: 当前时间，传入后校验实验生效时间窗口（可选）

        返回：
            运行中的实验列表，按创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
        self._validate_pagination(
            limit=limit,
            offset=offset,
        )

        stmt = select(
            Experiment
        ).where(
            Experiment.model_id
            == model_id,
            Experiment.status
            == str(
                ExperimentStatus.RUNNING
            ),
            Experiment.deleted_at.is_(
                None
            ),
        )

        if environment is not None:
            stmt = stmt.where(
                Experiment.environment
                == str(
                    environment
                )
            )

        stmt = self._apply_effective_window(
            stmt,
            now=now,
        ).order_by(
            Experiment.created_at.desc()
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

    def create_experiment(
            self,
            *,
            experiment_id: str,
            model_id: str,
            environment: Environment,
            name: str | None = None,
            description: str | None = None,
            config: dict | None = None,
            effective_from: datetime | None = None,
            effective_to: datetime | None = None,
            created_by: str | None = None,
    ) -> Experiment:
        """创建实验

        新建的实验处于 draft 状态。

        参数：
            experiment_id: 实验 ID
            model_id: 模型 ID
            environment: 实验环境
            name: 实验名称（可选）
            description: 实验描述（可选）
            config: 实验配置（可选）
            effective_from: 生效时间（可选）
            effective_to: 失效时间（可选）
            created_by: 创建人（可选）

        返回：
            创建后的实验对象
        """
        new_experiment = Experiment(
            experiment_id=experiment_id,
            model_id=model_id,
            environment=environment.value,
            status=str(
                ExperimentStatus.DRAFT
            ),
            config=config,
        )

        if name is not None:
            new_experiment.name = name

        if description is not None:
            new_experiment.description = description

        if effective_from is not None:
            new_experiment.effective_from = (
                effective_from
            )

        if effective_to is not None:
            new_experiment.effective_to = effective_to

        if created_by is not None:
            new_experiment.created_by = created_by

        self.add(
            new_experiment
        )

        return new_experiment

    def update_experiment(
            self,
            experiment: Experiment,
            patch: ExperimentPatch,
            *,
            updated_by: str | None = None,
    ) -> Experiment:
        """更新实验

        参数：
            experiment: 实验对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的实验对象
        """
        for field in fields(
                ExperimentPatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            if isinstance(
                    value,
                    Environment,
            ):
                value = str(
                    value
                )

            setattr(
                experiment,
                field.name,
                value,
            )

        if updated_by is not None:
            experiment.updated_by = updated_by

        return experiment

    def start_experiment(
            self,
            experiment: Experiment,
            *,
            updated_by: str | None = None,
    ) -> Experiment:
        """启动实验

        未配置生效时间时，使用实验启动时间。
        """
        current_status = ExperimentStatus(
            experiment.status
        )

        if current_status == ExperimentStatus.RUNNING:
            return experiment

        started_experiment = self._transition_experiment(
            experiment,
            target_status=(
                ExperimentStatus.RUNNING
            ),
            updated_by=updated_by,
        )
        effective_from: Any = (
            started_experiment.effective_from
        )

        if effective_from is None:
            started_experiment.effective_from = (
                datetime.now(
                    timezone.utc
                )
            )

        return started_experiment

    def stop_experiment(
            self,
            experiment: Experiment,
            *,
            updated_by: str | None = None,
    ) -> Experiment:
        """停止实验"""
        return self._transition_experiment(
            experiment,
            target_status=(
                ExperimentStatus.STOPPED
            ),
            updated_by=updated_by,
        )

    def pause_experiment(
            self,
            experiment: Experiment,
            *,
            updated_by: str | None = None,
    ) -> Experiment:
        """暂停实验"""
        return self._transition_experiment(
            experiment,
            target_status=(
                ExperimentStatus.PAUSED
            ),
            updated_by=updated_by,
        )

    def complete_experiment(
            self,
            experiment: Experiment,
            *,
            updated_by: str | None = None,
    ) -> Experiment:
        """完成实验"""
        return self._transition_experiment(
            experiment,
            target_status=(
                ExperimentStatus.COMPLETED
            ),
            updated_by=updated_by,
        )

    def archive_experiment(
            self,
            experiment: Experiment,
            *,
            updated_by: str | None = None,
    ) -> Experiment:
        """归档实验"""
        return self._transition_experiment(
            experiment,
            target_status=(
                ExperimentStatus.ARCHIVED
            ),
            updated_by=updated_by,
        )

    @staticmethod
    def mark_deleted(
            experiment: Experiment,
            *,
            deletion_id: str,
            deleted_at: datetime | None = None,
            deleted_by: str | None = None,
            deletion_reason: str | None = None,
    ) -> Experiment:
        """逻辑删除实验"""
        experiment.deleted_at = (
            deleted_at
            if deleted_at is not None
            else datetime.now(
                timezone.utc
            )
        )
        experiment.deleted_by = deleted_by
        experiment.deletion_id = deletion_id
        experiment.deletion_reason = deletion_reason
        experiment.updated_by = deleted_by

        return experiment

    @staticmethod
    def restore_experiment(
            experiment: Experiment,
            *,
            restored_by: str | None = None,
    ) -> Experiment:
        """恢复逻辑删除的实验"""
        experiment.deleted_at = None
        experiment.deleted_by = None
        experiment.deletion_id = None
        experiment.deletion_reason = None
        experiment.updated_by = restored_by

        return experiment
