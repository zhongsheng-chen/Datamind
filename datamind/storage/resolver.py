# datamind/storage/resolver.py

"""存储路径解析器

根据存储类型将存储键解析为完整路径。

核心功能：
  - resolve: 解析存储键为完整路径

使用示例：
  from datamind.storage.resolver import StorageResolver

  resolver = StorageResolver()
  path = resolver.resolve("models/mdl_001/1.0.0/model.pkl")
"""

from pathlib import Path

from datamind.config.settings import get_settings
from datamind.constants import StorageType


class StorageResolver:
    """存储路径解析器"""

    def __init__(self):
        self.settings = get_settings()

    def resolve(self, key: str) -> str:
        """解析存储键为完整路径

        参数：
            key: 存储键

        返回：
            完整路径

        异常：
            ValueError: 不支持的存储类型
        """
        storage_type = self.settings.storage.type

        if storage_type == StorageType.local:
            return self._resolve_local(key)

        if storage_type == StorageType.minio:
            return self._resolve_minio(key)

        raise ValueError(f"不支持的存储类型: {storage_type}")

    def _resolve_local(self, key: str) -> str:
        """解析本地存储路径

        参数：
            key: 存储键

        返回：
            本地文件系统绝对路径
        """
        base_dir = Path(self.settings.storage.local.base_dir)
        path = base_dir / key

        return str(path.resolve())

    def _resolve_minio(self, key: str) -> str:
        """解析 MinIO 存储路径

        参数：
            key: 存储键

        返回：
            S3 兼容路径
        """
        cfg = self.settings.storage.minio

        return f"s3://{cfg.base_prefix}/{key}"