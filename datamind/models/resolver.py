# datamind/models/resolver.py

"""模型解析器

提供模型和版本的解析能力，支持通过 ID 或名称查找。

核心功能：
  - resolve_model: 解析模型
  - resolve_version: 解析版本

使用示例：
  from datamind.db.repositories import MetadataRepository, VersionRepository
  from datamind.models.resolver import ModelResolver

  resolver = ModelResolver(metadata_repo, version_repo)

  # 解析模型
  model = await resolver.resolve_model(model_id="mdl_0123456789abcdef")
  model = await resolver.resolve_model(name="scorecard")

  # 解析版本
  version = await resolver.resolve_version(
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
  )
  version = await resolver.resolve_version(
      model_id="mdl_0123456789abcdef",
      version="1.0.0",
  )
"""

from datamind.db.repositories import MetadataRepository, VersionRepository
from datamind.models.errors import ModelNotFoundError, VersionNotFoundError


class ModelResolver:
    """模型解析器"""

    def __init__(self, metadata_repo: MetadataRepository, version_repo: VersionRepository):
        """初始化模型解析器

        参数：
            metadata_repo: 模型元数据仓储
            version_repo: 模型版本仓储
        """
        self.metadata_repo = metadata_repo
        self.version_repo = version_repo

    async def resolve_model(
            self,
            *,
            model_id: str | None = None,
            name: str | None = None,
    ):
        """解析模型

        优先按 model_id 查询模型。未找到且提供 name 时，
        再按模型名称查询。

        参数：
            model_id: 模型 ID（可选）
            name: 模型名称（可选）

        返回：
            模型元数据对象

        异常：
            ModelNotFoundError: 模型不存在
        """
        model = None

        if model_id:
            model = await self.metadata_repo.get_model(model_id=model_id)

        if not model and name:
            model = await self.metadata_repo.get_model(name=name)

        if not model:
            model_id = model_id or "未提供"
            name = name or "未提供"

            raise ModelNotFoundError(
                "模型不存在 "
                f"(model_id={model_id}, "
                f"name={name})"
            )

        return model

    async def resolve_version(
            self,
            *,
            model_id: str,
            version_id: str | None = None,
            version: str | None = None,
            include_archived: bool = False,
    ):
        """解析版本

        提供 version_id 时优先按版本 ID 查询，并校验版本是否
        属于指定模型。未提供 version_id 时，再按 model_id 和
        version 查询指定模型的版本。

        参数：
            model_id: 模型 ID
            version_id: 版本 ID（可选）
            version: 版本号（可选）
            include_archived: 按版本号查询时是否包含归档版本

        返回：
            版本对象

        异常：
            VersionNotFoundError: 版本不存在
        """
        if version_id:
            v = await self.version_repo.get_version(version_id)
            if not v or v.model_id != model_id:
                raise VersionNotFoundError(f"版本不存在: {version_id}")
            return v

        if version:
            versions = await self.version_repo.list_versions(
                model_id=model_id,
                include_archived=include_archived,
            )
            v = next((x for x in versions if x.version == version), None)

            if not v:
                raise VersionNotFoundError(
                    f"版本不存在: model_id={model_id}, version={version}"
                )
            return v

        raise VersionNotFoundError(
            f"必须提供 version 或 version_id (model_id={model_id})"
        )
