# datamind/constants/framework.py

"""框架枚举

定义支持的机器学习框架类型，用于模型注册和运行时识别。

核心功能：
  - Framework: 机器学习框架字符串枚举
  - SUPPORTED_FRAMEWORKS: 支持的框架集合

使用示例：
  from datamind.constants.framework import Framework

  if framework == Framework.SKLEARN:
      load_sklearn_model(model_path)
  elif framework == Framework.XGBOOST:
      load_xgboost_model(model_path)
"""

from enum import Enum
from typing import FrozenSet


class Framework(str, Enum):
    """机器学习框架字符串枚举"""

    SKLEARN = "sklearn"
    XGBOOST = "xgboost"
    LIGHTGBM = "lightgbm"
    CATBOOST = "catboost"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


SUPPORTED_FRAMEWORKS: FrozenSet[str] = frozenset(
    str(framework)
    for framework in Framework
)
