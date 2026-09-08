"""存储类型枚举

定义存储后端类型，用于配置解析和运行时识别。

核心功能：
  - StorageType: 存储类型字符串枚举
  - SUPPORTED_STORAGE_TYPES: 支持的存储类型集合

使用示例：
  from datamind.constants.storage_type import StorageType

  if storage_type == StorageType.LOCAL:
      use_local_backend()
  elif storage_type == StorageType.MINIO:
      use_minio_backend()
"""

from enum import Enum
from typing import FrozenSet


class StorageType(str, Enum):
    """存储类型字符串枚举"""

    LOCAL = "local"
    MINIO = "minio"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_STORAGE_TYPES: FrozenSet[str] = frozenset(
    str(storage_type)
    for storage_type in StorageType
)
