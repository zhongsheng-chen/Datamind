# datamind/models/artifact/handlers/sklearn.py

"""Sklearn 模型加载器

注册 Sklearn 框架的模型加载函数。

使用示例：
  from datamind.models.artifact.register import get_handler

  handler = get_handler("sklearn")
  model = handler(model_bytes)
"""

from datamind.constants.framework import Framework
from datamind.models.artifact.register import ModelArtifactRegister


@ModelArtifactRegister.register(Framework.sklearn)
def load_sklearn(data: bytes):
    """加载 Sklearn 模型

    参数：
        data: 二进制数据

    返回：
        Sklearn 模型实例
    """
    import joblib
    from io import BytesIO

    return joblib.load(BytesIO(data))