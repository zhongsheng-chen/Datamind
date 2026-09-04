# datamind/db/repositories/version.py

"""模型版本仓储

提供模型版本的查询、创建、更新和生命周期管理能力。

核心功能：
  - get_version: 获取指定版本
  - get_latest_version: 获取最新版本
  - list_versions: 获取版本列表
  - create_version: 创建版本
  - update_version: 更新版本
  - set_current_artifact: 切换当前制品投影
  - mark_deleted: 标记版本已删除
  - restore_version: 恢复逻辑删除的版本
  - archive_version: 归档版本
  - activate_version: 激活版本
  - deprecate_version: 废弃版本

使用示例：
  from datamind.constants import Framework
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories.version import (
      VersionPatch,
      VersionRepository,
  )

  async with UnitOfWork() as uow:
      repo = VersionRepository(
          uow.session
      )

      new_version = repo.create_version(
          version_id="ver_0123456789abcdef",
          model_id="mdl_0123456789abcdef",
          version="1.0.0",
          framework=Framework.SKLEARN,
          bento_tag="scorecard:abcdefgh",
          model_path=(
              "s3://datamind/models/"
              "mdl_0123456789abcdef/"
              "1.0.0/artifacts/"
              "art_0123456789abcdef/"
              "scorecard.pkl"
          ),
          model_key=(
              "models/"
              "mdl_0123456789abcdef/"
              "1.0.0/artifacts/"
              "art_0123456789abcdef/"
              "scorecard.pkl"
          ),
          current_artifact_id="art_0123456789abcdef",
          artifact_sha256="4f7c2a8d...c91e",
          artifact_digest="9b3e1f6a...72d4",
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

from datamind.constants import Framework
from datamind.db.models.versions import Version
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import VersionStatus
from datamind.models.guard import ModelGuard


@dataclass(slots=True)
class VersionPatch:
    """模型版本更新结构

    注意：
        不允许通过 patch 修改 status 和生命周期字段，
        状态由生命周期方法控制。

    属性：
        version: 版本号
        framework: 框架类型
        bento_tag: BentoML 标签
        model_path: 模型文件原始路径
        model_key: 模型文件存储键
        params: 模型参数
        metrics: 评估指标
        description: 版本说明
    """

    version: str | None = None
    framework: Framework | None = None
    bento_tag: str | None = None
    model_path: str | None = None
    model_key: str | None = None
    params: dict | None = None
    metrics: dict | None = None
    description: str | None = None


class VersionRepository(BaseRepository):
    """模型版本仓储"""

    async def get_version(
            self,
            version_id: str,
    ) -> Version | None:
        """获取指定版本

        参数：
            version_id: 版本 ID

        返回：
            版本对象，不存在时返回 None
        """
        stmt = select(
            Version
        ).where(
            Version.version_id
            == version_id
        )
        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_version_for_update(
            self,
            version_id: str,
    ) -> Version | None:
        """获取并锁定指定模型版本"""
        stmt = select(
            Version
        ).where(
            Version.version_id
            == version_id
        ).with_for_update()
        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def get_latest_version(
            self,
            model_id: str,
    ) -> Version | None:
        """获取最新版本

        参数：
            model_id: 模型 ID

        返回：
            最新版本对象，按创建时间倒序取第一条；
            不存在时返回 None
        """
        stmt = (
            select(
                Version
            )
            .where(
                Version.model_id
                == model_id
            )
            .order_by(
                Version.created_at.desc()
            )
            .limit(
                1
            )
        )
        result = await self.session.execute(
            stmt
        )

        return result.scalar_one_or_none()

    async def list_versions(
            self,
            *,
            model_id: str | None = None,
            version: str | None = None,
            framework: Framework | None = None,
            status: VersionStatus | None = None,
            created_by: str | None = None,
            include_archived: bool = False,
            limit: int | None = None,
            offset: int | None = None,
    ) -> list[Version]:
        """获取版本列表

        参数：
            model_id: 模型 ID（可选）
            version: 版本号（可选）
            framework: 框架类型（可选）
            status: 版本状态（可选）
            created_by: 创建人（可选）
            include_archived: 是否包含归档版本
            limit: 返回数量限制（可选）
            offset: 分页偏移（可选）

        返回：
            版本列表，按创建时间倒序排列

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
            Version
        )

        if model_id is not None:
            stmt = stmt.where(
                Version.model_id
                == model_id
            )

        if version is not None:
            stmt = stmt.where(
                Version.version
                == version
            )

        if framework is not None:
            stmt = stmt.where(
                Version.framework
                == str(
                    framework
                )
            )

        if status is not None:
            stmt = stmt.where(
                Version.status
                == str(
                    status
                )
            )
        elif not include_archived:
            stmt = stmt.where(
                Version.status
                != str(
                    VersionStatus.ARCHIVED
                )
            )

        if created_by is not None:
            stmt = stmt.where(
                Version.created_by
                == created_by
            )

        stmt = stmt.order_by(
            Version.created_at.desc()
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

    def create_version(
            self,
            *,
            version_id: str,
            model_id: str,
            version: str,
            framework: Framework,
            bento_tag: str,
            model_path: str,
            model_key: str,
            current_artifact_id: str,
            artifact_sha256: str,
            artifact_digest: str,
            params: dict | None = None,
            metrics: dict | None = None,
            description: str | None = None,
            created_by: str | None = None,
            artifact_revision: int = 1,
    ) -> Version:
        """创建版本

        新建的版本处于 inactive 状态。

        参数：
            version_id: 版本 ID
            model_id: 模型 ID
            version: 版本号
            framework: 框架类型
            bento_tag: BentoML 标签
            model_path: 模型文件原始路径
            model_key: 模型文件存储键
            params: 模型参数（可选）
            metrics: 评估指标（可选）
            description: 版本说明（可选）
            created_by: 创建人（可选）
            current_artifact_id: 当前制品 ID
            artifact_revision: 当前制品修订号
            artifact_sha256: 当前模型文件 SHA-256
            artifact_digest: 当前模型摘要

        返回：
            创建后的版本对象
        """
        new_version = Version(
            version_id=version_id,
            model_id=model_id,
            version=version,
            framework=str(
                framework
            ),
            status=str(
                VersionStatus.INACTIVE
            ),
            bento_tag=bento_tag,
            model_path=model_path,
            model_key=model_key,
            params=params,
            metrics=metrics,
            current_artifact_id=current_artifact_id,
            artifact_revision=artifact_revision,
            artifact_sha256=artifact_sha256,
            artifact_digest=artifact_digest,
        )

        if description is not None:
            new_version.description = description

        if created_by is not None:
            new_version.created_by = created_by

        self.add(
            new_version
        )

        return new_version

    def update_version(
            self,
            version: Version,
            patch: VersionPatch,
            *,
            updated_by: str | None = None,
    ) -> Version:
        """更新版本

        参数：
            version: 版本对象
            patch: 更新内容
            updated_by: 更新人（可选）

        返回：
            更新后的版本对象
        """
        for field in fields(
                VersionPatch
        ):
            value = getattr(
                patch,
                field.name,
            )

            if value is None:
                continue

            if isinstance(
                    value,
                    Framework,
            ):
                value = str(
                    value
                )

            setattr(
                version,
                field.name,
                value,
            )

        if updated_by is not None:
            version.updated_by = updated_by

        return version

    def archive_version(
            self,
            version: Version,
            *,
            updated_by: str | None = None,
    ) -> Version:
        """归档版本

        仅允许从 inactive 或 deprecated 状态归档。
        archived 为终态，归档后不允许重新激活。

        参数：
            version: 版本对象
            updated_by: 更新人（可选）

        返回：
            归档后的版本对象

        异常：
            InvalidModelStateError: 当前状态不允许归档
        """
        current_status = VersionStatus(
            version.status
        )
        target_status = (
            VersionStatus.ARCHIVED
        )

        ModelGuard.validate_version_transition(
            current=current_status,
            target=target_status,
        )

        if current_status == target_status:
            return version

        version.status = str(
            target_status
        )
        version.archived_at = datetime.now(
            timezone.utc
        )

        if updated_by is not None:
            version.updated_by = updated_by
            version.archived_by = updated_by

        return version

    def mark_deleted(
            self,
            version: Version,
            *,
            deleted_at: datetime | None = None,
            deleted_by: str | None = None,
            deletion_id: str | None = None,
            deletion_reason: str | None = None,
    ) -> Version:
        """标记版本已删除

        记录删除信息并将版本归档。版本已经被删除时原样返回。

        参数：
            version: 模型版本对象
            deleted_at: 删除时间（可选），默认使用当前时间
            deleted_by: 删除人（可选）
            deletion_id: 删除批次 ID（可选）
            deletion_reason: 删除原因（可选）

        返回：
            标记后的模型版本对象
        """
        if getattr(
            version,
            "deleted_at",
            None,
        ) is not None:
            return version

        version.deleted_at = (
            deleted_at
            or datetime.now(timezone.utc)
        )

        if deleted_by is not None:
            version.deleted_by = deleted_by
            version.updated_by = deleted_by

        if deletion_id is not None:
            version.deletion_id = deletion_id

        if deletion_reason is not None:
            version.deletion_reason = deletion_reason

        version.status = str(
            VersionStatus.ARCHIVED
        )
        version.archived_at = version.deleted_at

        if deleted_by is not None:
            version.archived_by = deleted_by

        return version

    @staticmethod
    def set_current_artifact(
            version: Version,
            *,
            artifact_id: str,
            revision: int,
            sha256: str,
            digest: str,
            bento_tag: str,
            model_path: str,
            model_key: str,
            params: dict | None,
            metrics: dict | None,
            description: str | None,
            updated_by: str | None = None,
    ) -> Version:
        """切换当前制品

        将版本切换到指定制品修订，并同步制品位置、
        模型参数、评估指标和版本说明。

        参数：
            version: 模型版本对象
            artifact_id: 制品 ID
            revision: 制品修订号
            sha256: 模型文件 SHA-256
            digest: 模型摘要
            bento_tag: BentoML 标签
            model_path: 模型文件解析路径
            model_key: 模型文件存储键
            params: 模型参数（可选）
            metrics: 评估指标（可选）
            description: 版本说明（可选）
            updated_by: 更新人（可选）

        返回：
            切换后的模型版本对象
        """
        version.current_artifact_id = artifact_id
        version.artifact_revision = revision
        version.artifact_sha256 = sha256
        version.artifact_digest = digest
        version.bento_tag = bento_tag
        version.model_path = model_path
        version.model_key = model_key
        version.params = params
        version.metrics = metrics
        version.description = description

        if updated_by is not None:
            version.updated_by = updated_by

        return version

    @staticmethod
    def restore_version(
            version: Version,
            *,
            restored_by: str | None = None,
    ) -> Version:
        """恢复版本

        将已逻辑删除的版本恢复为 inactive 状态，
        并清除删除和归档信息。版本未被删除时原样返回。

        参数：
            version: 模型版本对象
            restored_by: 恢复人（可选）

        返回：
            恢复后的模型版本对象
        """
        if getattr(version, "deleted_at", None) is None:
            return version

        version.status = str(
            VersionStatus.INACTIVE
        )
        version.deleted_at = None
        version.deleted_by = None
        version.deletion_id = None
        version.deletion_reason = None
        version.archived_at = None
        version.archived_by = None
        version.restored_at = datetime.now(
            timezone.utc
        )

        if restored_by is not None:
            version.restored_by = restored_by
            version.updated_by = restored_by

        return version

    def activate_version(
            self,
            version: Version,
            *,
            updated_by: str | None = None,
    ) -> Version:
        """激活版本

        仅允许从 inactive 状态激活。
        archived 为终态，不能重新激活。

        参数：
            version: 版本对象
            updated_by: 更新人（可选）

        返回：
            激活后的版本对象

        异常：
            InvalidModelStateError: 当前状态不允许激活
        """
        current_status = VersionStatus(
            version.status
        )
        target_status = (
            VersionStatus.ACTIVE
        )

        ModelGuard.validate_version_transition(
            current=current_status,
            target=target_status,
        )

        if current_status == target_status:
            return version

        version.status = str(
            target_status
        )

        if updated_by is not None:
            version.updated_by = updated_by

        return version

    def deprecate_version(
            self,
            version: Version,
            *,
            updated_by: str | None = None,
    ) -> Version:
        """废弃版本

        允许从 active 或 inactive 状态废弃。

        参数：
            version: 版本对象
            updated_by: 更新人（可选）

        返回：
            废弃后的版本对象

        异常：
            InvalidModelStateError: 当前状态不允许废弃
        """
        current_status = VersionStatus(
            version.status
        )
        target_status = (
            VersionStatus.DEPRECATED
        )

        ModelGuard.validate_version_transition(
            current=current_status,
            target=target_status,
        )

        if current_status == target_status:
            return version

        version.status = str(
            target_status
        )

        if updated_by is not None:
            version.updated_by = updated_by

        return version
