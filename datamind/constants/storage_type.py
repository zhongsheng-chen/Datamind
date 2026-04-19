# datamind/constants/storage_type.py

"""存储类型常量

定义存储后端的类型，用于配置和运行时识别。

核心功能：
  - StorageType: 存储类型常量类
  - SUPPORTED_STORAGE_TYPES: 支持的存储类型集合

使用示例：
  from datamind.constants.storage_type import StorageType, SUPPORTED_STORAGE_TYPES

  if storage_type == StorageType.local:
      use_local_backend()
  elif storage_type == StorageType.minio:
      use_minio_backend()
"""


class StorageType:
    """存储类型常量"""

    local: str = "local"
    minio: str = "minio"


SUPPORTED_STORAGE_TYPES = frozenset({
    StorageType.local,
    StorageType.minio,
})