# datamind/models/artifact/handlers/torch.py

"""PyTorch 模型加载器

注册 PyTorch 框架的模型加载函数。

使用示例：
  from datamind.models.artifact.register import get_handler

  handler = get_handler("torch")
  model = handler(model_bytes)
"""

from datamind.constants.framework import Framework
from datamind.models.artifact.register import ModelArtifactRegister


@ModelArtifactRegister.register(Framework.torch)
def load_torch(data: bytes):
    """加载 PyTorch 模型

    参数：
        data: 二进制数据

    返回：
        PyTorch 模型实例
    """
    import torch
    from io import BytesIO

    return torch.load(BytesIO(data), map_location="cpu")