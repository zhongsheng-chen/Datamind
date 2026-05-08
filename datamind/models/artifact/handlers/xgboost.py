# datamind/models/artifact/handlers/xgboost.py

"""XGBoost 模型加载器

注册 XGBoost 框架的模型加载函数。

使用示例：
  from datamind.models.artifact.register import get_handler

  handler = get_handler("xgboost")
  model = handler(model_bytes)
"""

from datamind.constants.framework import Framework
from datamind.models.artifact.register import ModelArtifactRegister


@ModelArtifactRegister.register(Framework.xgboost)
def load_xgboost(data: bytes):
    """加载 XGBoost 模型

    参数：
        data: 二进制数据

    返回：
        XGBoost Booster 实例
    """
    import xgboost as xgb

    model = xgb.Booster()
    model.load_model(bytearray(data))

    return model