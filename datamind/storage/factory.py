# datamind/storage/factory.py

"""存储后端工厂

根据配置创建对应的存储后端实例。

核心功能：
  - get_backend: 根据配置创建存储后端

使用示例：
  from datamind.config.settings import get_settings
  from datamind.storage.factory import get_backend

  settings = get_settings()
  backend = get_backend(
      settings.storage
  )
"""

from datamind.config.storage import StorageConfig
from datamind.constants import StorageType
from datamind.storage.base import BaseStorageBackend
from datamind.storage.local import LocalStorageBackend
from datamind.storage.minio import MinIOStorageBackend


def get_backend(
    config: StorageConfig,
) -> BaseStorageBackend:
    """创建存储后端实例

    参数：
        config: 存储配置对象

    返回：
        存储后端实例

    异常：
        ValueError: 不支持的存储类型
    """
    if config.type == StorageType.LOCAL:
        return LocalStorageBackend(
            base_dir=config.local.base_dir
        )

    if config.type == StorageType.MINIO:
        return MinIOStorageBackend(
            endpoint=config.minio.endpoint,
            access_key=config.minio.access_key,
            secret_key=config.minio.secret_key,
            bucket=config.minio.bucket,
            secure=config.minio.secure,
            base_prefix=config.minio.base_prefix,
            region=config.minio.region,
        )

    raise ValueError(
        f"不支持的存储类型: {config.type}"
    )
