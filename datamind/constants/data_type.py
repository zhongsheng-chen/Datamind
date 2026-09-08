"""数据类型枚举

定义特征数据的基本类型，用于数据验证和预处理。

核心功能：
  - DataType: 数据类型字符串枚举
  - SUPPORTED_DATA_TYPES: 支持的数据类型集合

使用示例：
  from datamind.constants.data_type import DataType

  if data_type == DataType.NUMERIC:
      apply_numeric_validation()
  elif data_type == DataType.CATEGORICAL:
      apply_categorical_encoding()
  elif data_type == DataType.BOOLEAN:
      apply_boolean_normalization()
  elif data_type == DataType.ANY:
      skip_type_check()
"""

from enum import Enum
from typing import FrozenSet


class DataType(str, Enum):
    """数据类型字符串枚举

    属性：
        NUMERIC: 数值类型（整数、浮点数）
        CATEGORICAL: 分类类型（字符串、有限枚举值）
        BOOLEAN: 布尔类型（True/False）
        ANY: 任意类型（不进行类型检查）
    """

    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    ANY = "any"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_DATA_TYPES: FrozenSet[str] = frozenset(
    str(data_type)
    for data_type in DataType
)
