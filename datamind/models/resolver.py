# datamind/models/resolver.py

"""模型解析器

提供模型和版本的解析能力，支持通过 ID 或名称查找。

核心功能：
  - resolve_model: 解析模型（支持 model_id 或 name）
  - resolve_version: 解析版本（支持 version_id 或 version）

使用示例：
  from datamind.models.resolver import ModelResolver

  resolver = ModelResolver()

  # 解析模型
  model = await resolver.resolve_model(session, model_id="mdl_a1b2c3d4")
  model = await resolver.resolve_model(session, name="scorecard")

  # 解析版本
  version = await resolver.resolve_version(
      session,
      model_id="mdl_a1b2c3d4",
      version_id="ver_a1b2c3d4",
  )
  version = await resolver.resolve_version(
      session,
      model_id="mdl_a1b2c3d4",
      version="1.0.0",
  )
"""

from datamind.db.repositories import MetadataRepository, VersionRepository
from datamind.models.errors import ModelNotFoundError, VersionNotFoundError


class ModelResolver:
    """模型解析器"""

    async def resolve_model(
        self,
        session,
        *,
        model_id: str | None = None,
        name: str | None = None,
    ):
        """解析模型

        参数：
            session: 数据库会话
            model_id: 模型 ID（可选）
            name: 模型名称（可选）

        返回：
            模型元数据对象

        异常：
            ModelNotFoundError: 模型不存在
        """
        repo = MetadataRepository(session)

        if model_id:
            model = await repo.get_model(model_id=model_id)
        elif name:
            model = await repo.get_model(name=name)
        else:
            model = None

        if not model:
            raise ModelNotFoundError("模型不存在")

        return model

    async def resolve_version(
        self,
        session,
        *,
        model_id: str,
        version_id: str | None = None,
        version: str | None = None,
    ):
        """解析版本

        参数：
            session: 数据库会话
            model_id: 模型 ID
            version_id: 版本 ID（可选）
            version: 版本号（可选）

        返回：
            版本对象，如果都未提供则返回 None

        异常：
            VersionNotFoundError: 版本不存在
        """
        repo = VersionRepository(session)

        if version_id:
            v = await repo.get_version(version_id)
            if not v:
                raise VersionNotFoundError(version_id)
            return v

        if version:
            versions = await repo.list_versions(model_id)
            v = next((x for x in versions if x.version == version), None)

            if not v:
                raise VersionNotFoundError(version)

            return v

        return None