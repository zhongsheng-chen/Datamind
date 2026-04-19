# datamind/constants/model_type.py

"""模型类型常量

定义支持的机器学习模型类型，用于模型注册、运行时识别和API响应。

核心功能：
  - ModelType: 模型类型常量类
  - SUPPORTED_MODEL_TYPES: 支持的模型类型集合

使用示例：
  from datamind.constants.model_type import ModelType, SUPPORTED_MODEL_TYPES

  if model_type == ModelType.logistic_regression:
      return run_logistic_regression(model)
  elif model_type == ModelType.xgboost:
      return run_xgboost(model)
"""


class ModelType:
    """模型类型常量"""

    # 线性模型
    logistic_regression: str = "logistic_regression"

    # 树模型
    decision_tree: str = "decision_tree"
    random_forest: str = "random_forest"

    # 梯度提升模型
    xgboost: str = "xgboost"
    lightgbm: str = "lightgbm"


SUPPORTED_MODEL_TYPES = frozenset({
    ModelType.logistic_regression,
    ModelType.decision_tree,
    ModelType.random_forest,
    ModelType.xgboost,
    ModelType.lightgbm,
})