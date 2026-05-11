# datamind/db/reader/version_reader.py

"""模型版本读取器

用于查询模型的具体版本信息。

核心功能：
  - get_version: 获取指定版本信息
  - get_latest_version: 获取最新版本
  - list_versions: 列出所有版本

使用示例：
  from datamind.db.reader.version_reader import VersionReader

  reader = VersionReader(session)

  latest = await reader.get_latest_version("mdl_a1b2c3d4")
  version = await reader.get_version("ver_a1b2c3d4")
  versions = await reader.list_versions("mdl_a1b2c3d4")
"""

from sqlalchemy import select

from datamind.db.models.versions import Version
from datamind.db.readers.base_reader import BaseReader


class VersionReader(BaseReader):
    """模型版本读取器"""

    async def get_version(self, version_id: str) -> Version | None:
        """获取指定版本

        参数：
            version_id: 版本ID

        返回：
            版本对象，不存在时返回 None
        """
        stmt = select(Version).where(Version.version_id == version_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_version(self, model_id: str) -> Version | None:
        """获取最新版本

        参数：
            model_id: 模型ID

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
        """列出所有版本

        参数：
            model_id: 模型ID

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