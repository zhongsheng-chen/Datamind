# datamind/db/repositories/version.py

"""模型版本访问器

提供模型版本的查询、创建、更新与写入能力。

核心功能：
  - get_version: 获取指定版本
  - get_latest_version: 获取最新版本
  - list_versions: 获取版本列表
  - create_version: 创建版本
  - update_version: 更新版本
  - archive_version: 归档版本
  - activate_version: 激活版本
  - deprecate_version: 废弃版本

使用示例：
  from datamind.db.core import UnitOfWork
  from datamind.db.repositories import VersionRepository

  async with UnitOfWork() as uow:
      repo = VersionRepository(uow.session)

      version = await repo.create_version(
          version_id="ver_xxx",
          model_id="mdl_xxx",
          version="1.0.0",
          framework="sklearn",
          status="active",
          bento_tag="scorecard:abc",
          model_path="s3://xxx",
          storage_key="models/xxx"
      )
"""

from datetime import datetime, timezone
from dataclasses import dataclass, fields
from sqlalchemy import select

from datamind.db.models.versions import Version
from datamind.db.repositories.base import BaseRepository
from datamind.models.enums import VersionStatus


@dataclass(slots=True)
class VersionPatch:
    """模型版本更新结构

    注意：
        不允许通过 patch 修改 status（由生命周期方法控制）

    属性：
        version: 版本号
        framework: 框架类型
        bento_tag: BentoML 标签
        model_path: 模型路径
        storage_key: 存储键
        params: 模型参数
        metrics: 评估指标
        description: 版本描述
        deleted_at: 删除时间
        deleted_by: 删除人
        archived_at: 归档时间
        archived_by: 归档人
        updated_by: 更新人
    """
    version: str | None = None
    framework: str | None = None
    bento_tag: str | None = None
    model_path: str | None = None
    storage_key: str | None = None
    params: dict | None = None
    metrics: dict | None = None
    description: str | None = None
    deleted_at: str | None = None
    deleted_by: str | None = None
    archived_at: str | None = None
    archived_by: str | None = None
    updated_by: str | None = None


class VersionRepository(BaseRepository):
    """模型版本访问器"""

    async def get_version(self, version_id: str) -> Version | None:
        """获取指定版本

        参数：
            version_id: 版本 ID

        返回：
            版本对象，不存在时返回 None
        """
        stmt = select(Version).where(Version.version_id == version_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_version(self, model_id: str) -> Version | None:
        """获取最新版本

        参数：
            model_id: 模型 ID

        返回：
            最新版本对象，按创建时间倒序取第一条，不存在时返回 None
        """
        stmt = (
            select(Version)
            .where(Version.model_id == model_id)
            .order_by(Version.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(self, model_id: str) -> list[Version]:
        """获取版本列表

        参数：
            model_id: 模型 ID

        返回：
            版本列表，按创建时间倒序排列
        """
        stmt = (
            select(Version)
            .where(Version.model_id == model_id)
            .order_by(Version.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def create_version(
        self,
        *,
        version_id: str,
        model_id: str,
        version: str,
        framework: str,
        bento_tag: str,
        model_path: str,
        storage_key: str,
        params: dict | None = None,
        metrics: dict | None = None,
        description: str | None = None,
        created_by: str | None = None,
    ) -> Version:
        """创建版本

        参数：
            version_id: 版本 ID
            model_id: 模型 ID
            version: 版本号
            framework: 框架类型
            bento_tag: BentoML 标签
            model_path: 模型路径
            storage_key: 存储键
            params: 模型参数（可选）
            metrics: 评估指标（可选）
            description: 版本描述（可选）
            created_by: 创建人（可选）

        返回：
            创建后的版本对象
        """
        obj = Version(
            version_id=version_id,
            model_id=model_id,
            version=version,
            framework=framework,
            bento_tag=bento_tag,
            model_path=model_path,
            storage_key=storage_key,
            params=params,
            metrics=metrics,
            description=description,
            created_by=created_by,
        )

        self.add(obj)
        return obj

    def update_version(
        self,
        version: Version,
        patch: VersionPatch,
        *,
        updated_by: str | None = None) -> Version:
        """更新版本

        参数：
            version: 版本对象
            patch: 更新内容

        返回：
            更新后的版本对象
        """
        for field in fields(VersionPatch):
            field_name = field.name

            if field_name == "status":
                continue

            value = getattr(patch, field_name)

            if value is None:
                continue

            setattr(version, field_name, value)

        if updated_by:
            version.updated_by = updated_by

        version.updated_at = datetime.now(timezone.utc)

        return version

    def archive_version(
        self,
        version: Version,
        *,
        archived_by: str | None = None
    ) -> Version:
        """归档版本

        参数：
            version: 版本对象
            archived_by: 归档人（可选）

        返回：
            归档后的版本对象
        """
        version.status = VersionStatus.ARCHIVED

        if archived_by:
            version.archived_by = archived_by

        return version

    def activate_version(
        self,
        version: Version,
        *,
        updated_by: str | None = None
    ) -> Version:
        """激活版本

        参数：
            version: 版本对象
            updated_by: 更新人（可选）

        返回：
            激活后的版本对象
        """
        version.status = VersionStatus.ACTIVE

        if updated_by:
            version.updated_by = updated_by

        return version

    def deprecate_version(
        self,
        version: Version,
        updated_by: str | None = None
    ) -> Version:
        """标记版本废弃

        参数：
            version: 版本对象
            updated_by: 更新人（可选）

        返回：
            废弃后的版本对象
        """
        version.status = VersionStatus.DEPRECATED

        if updated_by:
            version.updated_by = updated_by

        return version