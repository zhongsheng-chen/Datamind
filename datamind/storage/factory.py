# datamind/storage/factory.py

"""存储后端工厂

根据配置创建对应的存储后端实例。

核心功能：
  - get_backend: 根据配置创建存储后端

特性：
  - 配置驱动：根据 type 自动选择后端
  - 参数传递：自动从配置对象提取所需参数
"""

from datamind.config.storage import StorageConfig
from datamind.storage.local import LocalStorageBackend
from datamind.storage.minio import MinIOStorageBackend


def get_backend(config: StorageConfig) -> LocalStorageBackend | MinIOStorageBackend:
    """创建存储后端实例

    参数：
        config: 存储配置对象

    返回：
        存储后端实例

    异常：
        ValueError: 不支持的存储类型
    """
    if config.type == "local":
        return LocalStorageBackend(base_dir=config.local.base_dir)

    if config.type == "minio":
        return MinIOStorageBackend(
            endpoint=config.minio.endpoint,
            access_key=config.minio.access_key,
            secret_key=config.minio.secret_key,
            bucket=config.minio.bucket,
            secure=config.minio.secure,
            region=config.minio.region,
        )

    raise ValueError(f"不支持的存储类型: {config.type}")