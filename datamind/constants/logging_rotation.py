# datamind/constants/logging_rotation.py

"""日志轮转枚举

定义日志轮转的策略类型和轮转时间。

核心功能：
  - RotationType: 日志轮转策略字符串枚举
  - RotationWhen: 日志轮转时间字符串枚举
  - SUPPORTED_ROTATION_TYPES: 支持的轮转策略集合
  - SUPPORTED_ROTATION_WHEN: 支持的轮转时间集合

使用示例：
  from datamind.constants.logging_rotation import (
      RotationType,
      RotationWhen,
  )

  if rotation == RotationType.TIME:
      rotate_by_time()
  elif rotation == RotationType.SIZE:
      rotate_by_size()

  if rotation_when == RotationWhen.MIDNIGHT:
      rotate_at_midnight()
"""

from enum import Enum
from typing import FrozenSet


class RotationType(str, Enum):
    """日志轮转策略字符串枚举"""

    TIME = "time"
    SIZE = "size"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


class RotationWhen(str, Enum):
    """日志轮转时间字符串枚举"""

    MIDNIGHT = "MIDNIGHT"
    HOUR = "H"
    MINUTE = "M"
    SECOND = "S"

    MONDAY = "W0"
    TUESDAY = "W1"
    WEDNESDAY = "W2"
    THURSDAY = "W3"
    FRIDAY = "W4"
    SATURDAY = "W5"
    SUNDAY = "W6"

    def __str__(self) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_ROTATION_TYPES: FrozenSet[str] = frozenset(
    str(rotation_type)
    for rotation_type in RotationType
)

SUPPORTED_ROTATION_WHEN: FrozenSet[str] = frozenset(
    str(rotation_when)
    for rotation_when in RotationWhen
)
