# datamind/constants/logging_rotation.py

"""日志轮转策略常量

定义日志轮转的策略类型和轮转时间。

核心功能：
  - RotationType: 轮转策略常量类
  - RotationWhen: 轮转时间常量类
  - SUPPORTED_ROTATION_TYPES: 支持的轮转策略集合
  - SUPPORTED_ROTATION_WHEN: 支持的轮转时间集合

使用示例：
  from datamind.constants.logging_rotation import RotationType, RotationWhen

  if rotation == RotationType.TIME:
      rotate_by_time()
  elif rotation == RotationType.SIZE:
      rotate_by_size()
"""


class RotationType:
    """轮转策略常量"""

    TIME: str = "time"
    SIZE: str = "size"


class RotationWhen:
    """轮转时间常量"""

    MIDNIGHT: str = "MIDNIGHT"
    HOUR: str = "H"
    MINUTE: str = "M"
    SECOND: str = "S"
    WEEKDAY: str = "W0"


SUPPORTED_ROTATION_TYPES = frozenset({
    RotationType.TIME,
    RotationType.SIZE,
})

SUPPORTED_ROTATION_WHEN = frozenset({
    RotationWhen.MIDNIGHT,
    RotationWhen.HOUR,
    RotationWhen.MINUTE,
    RotationWhen.SECOND,
    RotationWhen.WEEKDAY,
})