# datamind/constants/model_type.py

"""模型类型枚举

定义支持的机器学习模型类型，用于模型注册、运行时识别和 API 响应。

核心功能：
  - ModelType: 模型类型字符串枚举
  - SUPPORTED_MODEL_TYPES: 支持的模型类型集合
  - SUPPORTED_MODEL_TYPES_BY_FRAMEWORK: 各框架支持的模型类型

使用示例：
  from datamind.constants.model_type import ModelType

  if model_type == ModelType.LOGISTIC_REGRESSION:
      return run_logistic_regression(model)
  elif model_type == ModelType.XGBOOST:
      return run_xgboost(model)
"""

from enum import Enum
from typing import (
    FrozenSet,
    Mapping,
)


class ModelType(str, Enum):
    """机器学习模型类型字符串枚举"""

    # 线性模型
    LOGISTIC_REGRESSION = "logistic_regression"

    # 树模型
    DECISION_TREE = "decision_tree"
    RANDOM_FOREST = "random_forest"

    # 梯度提升模型
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_MODEL_TYPES: FrozenSet[str] = frozenset(
    str(model_type)
    for model_type in ModelType
)


SUPPORTED_MODEL_TYPES_BY_FRAMEWORK: Mapping[str, FrozenSet[str]] = {
    "sklearn": frozenset({
        ModelType.LOGISTIC_REGRESSION.value,
        ModelType.DECISION_TREE.value,
        ModelType.RANDOM_FOREST.value,
    }),
    "xgboost": frozenset({ModelType.XGBOOST.value}),
    "lightgbm": frozenset({ModelType.LIGHTGBM.value}),
    "catboost": frozenset({ModelType.CATBOOST.value}),
}
