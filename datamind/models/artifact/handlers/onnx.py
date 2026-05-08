# datamind/models/artifact/handlers/onnx.py

"""ONNX 模型加载器

注册 ONNX 框架的模型加载函数。

使用示例：
  from datamind.models.artifact.register import get_handler

  handler = get_handler("onnx")
  session = handler(model_bytes)
"""

from datamind.constants.framework import Framework
from datamind.models.artifact.io import temp_file
from datamind.models.artifact.register import ModelArtifactRegister


@ModelArtifactRegister.register(Framework.onnx)
def load_onnx(data: bytes):
    """加载 ONNX 模型

    参数：
        data: 二进制数据

    返回：
        ONNX Runtime InferenceSession 实例
    """
    import onnxruntime as ort

    with temp_file(data, ".onnx") as path:
        return ort.InferenceSession(path)