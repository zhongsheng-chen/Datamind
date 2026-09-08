"""模型元数据仓储

提供模型元数据的查询、创建、更新和生命周期管理能力。

核心功能：
  - get_model: 获取单个模型
  - list_models: 获取模型列表
  - list_active_models: 获取活跃模型列表
  - create_model: 创建模型
  - update_model: 更新模型
  - mark_deleted: 标记模型已删除
  - restore_model: 恢复模型
  - archive_model: 归档模型
  - activate_model: 激活模型

使用示例：
  from datamind.constants import (
      Framework,
      ModelType,
      TaskType,
  )
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.metadata import (
      MetadataPatch,
      MetadataRepository,
  )

  async with UnitOfWork() as uow:
      repo = MetadataRepository(
          uow.session
      )

      model = repo.create_model(
          model_id="mdl_0123456789abcdef",
          name="scorecard",
          model_type=ModelType.LOGISTIC_REGRESSION,
          task_type=TaskType.SCORING,
          framework=Framework.SKLEARN,
          description="基于逻辑回归的信用评分模型",
          created_by="admin",
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

from datamind.constants import (
    Framework,
    ModelType,
    TaskType,
)
from datamind.db.models.metadata import Metadata
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import MetadataStatus
from datamind.models.guard import ModelGuard


@dataclass(slots=True)
class MetadataPatch:
    """模型元数据更新结构

    注意：
        不允许通过 patch 修改 status，
        状态由生命周期方法控制。

    属性：
        name: 模型名称
        display_name: 模型显示名称
        model_type: 模型类型
        task_type: 任务类型
        framework: 框架类型
        description: 模型描述
    """

    name: str | None = None
    display_name: str | None = None
    model_type: ModelType | None = None
    task_type: TaskType | None = None
    framework: Framework | None = None
    description: str | None = None


class MetadataRepository(BaseRepository):
    """模型元数据仓储"""

    async def get_model(
            self,
            *,
            model_id: str | None = None,
            name: str | None = None,
    ) -> Metadata | None:
        """获取单个模型

        参数：
            model_id: 模型 ID（可选）
            name: 模型名称（可选）

        返回：
            模型元数据对象，不存在时返回 None

        异常：
            ValueError: 查询条件为空或同时提供两个查询条件
        """
        normalized_model_id = (
            model_id.strip()
            if model_id is not None
            else None
        )
        normalized_name = (
            name.strip()
            if name is not None
            else None
        )

        if bool(
                normalized_model_id
        ) == bool(
                normalized_name
        ):
            raise ValueError(
                "必须且只能提供 model_id "
                "或 name 其中一个"
            )

        stmt = select(
            Metadata
        )

        if normalized_model_id is not None:
            stmt = stmt.where(
                Metadata.model_id
                == normalized_model_id
            )
        else:
            stmt = stmt.where(
                Metadata.name
                == normalized_name
            )

        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_models(
            self,
            *,
            model_type: ModelType | None = None,
            task_type: TaskType | None = None,
            framework: Framework | None = None,
            status: MetadataStatus | None = None,
            created_by: str | None = None,
            include_archived: bool = False,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Metadata]:
        """获取模型列表

        参数：
            model_type: 模型类型（可选）
            task_type: 任务类型（可选）
            framework: 框架类型（可选）
            status: 模型状态（可选）
            created_by: 创建人（可选）
            include_archived: 是否包含归档模型
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            模型列表，按更新时间和创建时间倒序排列

        异常：
            ValueError: 分页参数小于 0
        """
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

        stmt = select(
            Metadata
        )

        if model_type is not None:
            stmt = stmt.where(
                Metadata.model_type
                == str(
                    model_type
                )
            )

        if task_type is not None:
            stmt = stmt.where(
                Metadata.task_type
                == str(
                    task_type
                )
            )

        if framework is not None:
            stmt = stmt.where(
                Metadata.framework
                == str(
                    framework
                )
            )

        if status is not None:
            stmt = stmt.where(
                Metadata.status
                == str(
                    status
                )
            )
        elif not include_archived:
            stmt = stmt.where(
                Metadata.status
                != str(
                    MetadataStatus.ARCHIVED
                )
            )

        if created_by is not None:
            stmt = stmt.where(
                Metadata.created_by
                == created_by
            )

        stmt = stmt.order_by(
            Metadata.updated_at.desc(),
            Metadata.created_at.desc(),
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

    async def list_active_models(
            self,
            *,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Metadata]:
        """获取活跃模型列表

        参数：
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            活跃模型列表，按更新时间和创建时间倒序排列
        """
        return await self.list_models(
            status=MetadataStatus.ACTIVE,
            limit=limit,
            offset=offset,
        )

    def create_model(
            self,
            *,
            model_id: str,
            name: str,
            model_type: ModelType,
            task_type: TaskType,
            framework: Framework,
            display_name: str | None = None,
            description: str | None = None,
            created_by: str | None = None,
            updated_by: str | None = None,
    ) -> Metadata:
        """创建模型

        新建的模型处于 inactive 状态。

        参数：
            model_id: 模型 ID
            name: 模型机器名称
            display_name: 模型显示名称（可选）
            model_type: 模型类型
            task_type: 任务类型
            framework: 框架类型
            description: 模型描述（可选）
            created_by: 创建人（可选）
            updated_by: 更新人（可选）

        返回：
            创建后的模型元数据对象
        """
        new_model = Metadata(
            model_id=model_id,
            name=name,
            model_type=str(
                model_type
            ),
            task_type=str(
                task_type
            ),
            framework=str(
                framework
            ),
            status=str(
                MetadataStatus.INACTIVE
            ),
        )

        if description is not None:
            new_model.description = description

        if display_name is not None:
            new_model.display_name = display_name

        if created_by is not None:
            new_model.created_by = created_by

        if updated_by is not None:
            new_model.updated_by = updated_by

        self.add(
            new_model
        )

        return new_model

    def update_model(
            self,
            metadata: Metadata,
            patch: MetadataPatch,
            *,
            updated_by: str | None = None,
    ) -> Metadata:
        """更新模型元数据

        参数：
            metadata: 模型元数据对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的模型元数据对象
        """
        for field in fields(
                MetadataPatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            if isinstance(
                    value,
                    (
                        ModelType,
                        TaskType,
                        Framework,
                    ),
            ):
                value = str(
                    value
                )

            setattr(
                metadata,
                field.name,
                value,
            )

        if updated_by is not None:
            metadata.updated_by = updated_by

        return metadata

    def archive_model(
            self,
            metadata: Metadata,
            *,
            updated_by: str | None = None,
    ) -> Metadata:
        """归档模型

        仅允许从 inactive 或 deprecated 状态归档。
        archived 为终态，归档后不允许重新激活。

        参数：
            metadata: 模型元数据对象
            updated_by: 更新人（可选）

        返回：
            归档后的模型元数据对象

        异常：
            InvalidModelStateError: 当前状态不允许归档
        """
        current_status = MetadataStatus(
            metadata.status
        )
        target_status = (
            MetadataStatus.ARCHIVED
        )

        ModelGuard.validate_metadata_transition(
            current=current_status,
            target=target_status,
        )

        if current_status == target_status:
            return metadata

        metadata.status = str(
            target_status
        )
        metadata.archived_at = datetime.now(
            timezone.utc
        )

        if updated_by is not None:
            metadata.updated_by = updated_by
            metadata.archived_by = updated_by

        return metadata

    def mark_deleted(
            self,
            metadata: Metadata,
            *,
            deleted_at: datetime | None = None,
            deleted_by: str | None = None,
            deletion_id: str | None = None,
            deletion_reason: str | None = None,
    ) -> Metadata:
        """标记模型已删除

        记录删除信息并将模型归档。模型已经被删除时原样返回。

        参数：
            metadata: 模型元数据对象
            deleted_at: 删除时间（可选），默认使用当前时间
            deleted_by: 删除人（可选）
            deletion_id: 删除批次 ID（可选）
            deletion_reason: 删除原因（可选）

        返回：
            标记后的模型元数据对象
        """
        if getattr(
            metadata,
            "deleted_at",
            None,
        ) is not None:
            return metadata

        metadata.deleted_at = (
            deleted_at
            or datetime.now(timezone.utc)
        )

        if deleted_by is not None:
            metadata.deleted_by = deleted_by
            metadata.updated_by = deleted_by

        if deletion_id is not None:
            metadata.deletion_id = deletion_id

        if deletion_reason is not None:
            metadata.deletion_reason = deletion_reason

        metadata.status = str(
            MetadataStatus.ARCHIVED
        )
        metadata.archived_at = metadata.deleted_at

        if deleted_by is not None:
            metadata.archived_by = deleted_by

        return metadata

    @staticmethod
    def restore_model(
            metadata: Metadata,
            *,
            restored_by: str | None = None,
    ) -> Metadata:
        """恢复模型

        将已逻辑删除的模型恢复为 inactive 状态，
        并清除删除和归档信息。模型未被删除时原样返回。

        参数：
            metadata: 模型元数据对象
            restored_by: 恢复人（可选）

        返回：
            恢复后的模型元数据对象
        """
        if getattr(metadata, "deleted_at", None) is None:
            return metadata

        metadata.status = str(
            MetadataStatus.INACTIVE
        )
        metadata.deleted_at = None
        metadata.deleted_by = None
        metadata.deletion_id = None
        metadata.deletion_reason = None
        metadata.archived_at = None
        metadata.archived_by = None
        metadata.restored_at = datetime.now(
            timezone.utc
        )

        if restored_by is not None:
            metadata.restored_by = restored_by
            metadata.updated_by = restored_by

        return metadata

    def activate_model(
            self,
            metadata: Metadata,
            *,
            updated_by: str | None = None,
    ) -> Metadata:
        """激活模型

        仅允许从 inactive 状态激活。
        archived 为终态，不能重新激活。

        参数：
            metadata: 模型元数据对象
            updated_by: 更新人（可选）

        返回：
            激活后的模型元数据对象

        异常：
            InvalidModelStateError: 当前状态不允许激活
        """
        current_status = MetadataStatus(
            metadata.status
        )
        target_status = (
            MetadataStatus.ACTIVE
        )

        ModelGuard.validate_metadata_transition(
            current=current_status,
            target=target_status,
        )

        if current_status == target_status:
            return metadata

        metadata.status = str(
            target_status
        )

        if updated_by is not None:
            metadata.updated_by = updated_by

        return metadata
