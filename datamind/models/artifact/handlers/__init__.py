# datamind/models/artifact/handlers/__init__.py

"""模型加载器实现

注册各框架的模型加载函数。

使用示例：
  from datamind.models.artifact.handlers import sklearn
"""

from datamind.models.artifact.handlers import sklearn
from datamind.models.artifact.handlers import xgboost
from datamind.models.artifact.handlers import lightgbm
from datamind.models.artifact.handlers import catboost

__all__ = [
    "catboost",
    "lightgbm",
    "sklearn",
    "xgboost",
]