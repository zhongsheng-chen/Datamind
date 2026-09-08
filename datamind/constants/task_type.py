"""模型任务类型枚举

定义模型支持的任务类型，用于模型注册、查询和运行时识别。

核心功能：
  - TaskType: 模型任务类型字符串枚举
  - SUPPORTED_TASK_TYPES: 支持的任务类型集合

使用示例：
  from datamind.constants.task_type import TaskType

  if task_type == TaskType.SCORING:
      return calculate_score(model, features)

  if task_type == TaskType.CLASSIFICATION:
      return predict_class(model, features)
"""

from enum import Enum
from typing import FrozenSet


class TaskType(str, Enum):
    """模型任务类型字符串枚举"""

    SCORING = "scoring"
    CLASSIFICATION = "classification"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_TASK_TYPES: FrozenSet[str] = frozenset(
    str(task_type)
    for task_type in TaskType
)
