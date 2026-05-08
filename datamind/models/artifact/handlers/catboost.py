# datamind/models/artifact/handlers/catboost.py

"""CatBoost 模型加载器

注册 CatBoost 框架的模型加载函数。

使用示例：
  from datamind.models.artifact.register import get_handler

  handler = get_handler("catboost")
  model = handler(model_bytes)
"""

from datamind.constants.framework import Framework
from datamind.models.artifact.io import temp_file
from datamind.models.artifact.register import ModelArtifactRegister


@ModelArtifactRegister.register(Framework.catboost)
def load_catboost(data: bytes):
    """加载 CatBoost 模型

    参数：
        data: 二进制数据

    返回：
        CatBoost 模型实例
    """
    import catboost as cb

    with temp_file(data, ".cbm") as path:
        model = cb.CatBoost()
        model.load_model(path)

        return model