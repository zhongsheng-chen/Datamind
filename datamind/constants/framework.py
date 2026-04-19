# datamind/constants/framework.py

"""框架常量

定义支持的机器学习框架类型，用于模型注册和运行时识别。

核心功能：
  - Framework: 框架类型常量类
  - SUPPORTED_FRAMEWORKS: 支持的框架集合

使用示例：
  from datamind.constants.model_framework import Framework, SUPPORTED_FRAMEWORKS

  if framework in SUPPORTED_FRAMEWORKS:
      load_model(framework, model_path)
"""


class Framework:
    """模型框架常量"""

    sklearn: str = "sklearn"
    xgboost: str = "xgboost"
    lightgbm: str = "lightgbm"
    catboost: str = "catboost"
    torch: str = "torch"
    tensorflow: str = "tensorflow"
    onnx: str = "onnx"


SUPPORTED_FRAMEWORKS = frozenset({
    Framework.sklearn,
    Framework.xgboost,
    Framework.lightgbm,
    Framework.catboost,
    Framework.torch,
    Framework.tensorflow,
    Framework.onnx,
})