# datamind/models/artifact/handlers/lightgbm.py

"""LightGBM 模型加载器

注册 LightGBM 框架的模型加载函数。

使用示例：
  from datamind.models.artifact.register import get_handler

  handler = get_handler("lightgbm")
  model = handler(model_bytes)
"""

from datamind.constants.framework import Framework
from datamind.models.artifact.register import ModelArtifactRegister


@ModelArtifactRegister.register(Framework.lightgbm)
def load_lightgbm(data: bytes):
    """加载 LightGBM 模型

    参数：
        data: 二进制数据

    返回：
        LightGBM Booster 实例
    """
    import lightgbm as lgb

    return lgb.Booster(model_str=data.decode("utf-8"))