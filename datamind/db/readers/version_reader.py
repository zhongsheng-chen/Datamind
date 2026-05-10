# datamind/db/reader/version_reader.py

"""模型版本读取器

用于查询模型的具体版本信息。

使用示例：
    reader = VersionReader(session)

    latest = await reader.get_latest_version("mdl_a1b2c3d4")
    version = await reader.get_version("mdl_a1b2c3d4", "1.0.0")
    versions = await reader.list_versions("mdl_a1b2c3d4")
"""

from sqlalchemy import select

from datamind.db.models.versions import Version
from datamind.db.readers.base_reader import BaseReader


class VersionReader(BaseReader):
    """模型版本读取器"""

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

    async def get_version(
        self,
        model_id: str,
        version: str,
    ) -> Version | None:
        """获取指定版本

        参数：
            model_id: 模型 ID
            version: 版本号

        返回：
            版本对象，不存在时返回 None
        """
        stmt = select(Version).where(
            Version.model_id == model_id,
            Version.version == version,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_versions(self, model_id: str) -> list[Version]:
        """列出模型的所有版本列表

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
        return result.scalars().all()