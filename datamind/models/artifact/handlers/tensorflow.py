# datamind/models/artifact/handlers/tensorflow.py

"""TensorFlow 模型加载器

注册 TensorFlow 框架的模型加载函数。

使用示例：
  from datamind.models.artifact.register import get_handler

  handler = get_handler("tensorflow")
  model = handler(model_bytes)
"""

from datamind.constants.framework import Framework
from datamind.models.artifact.io import temp_file
from datamind.models.artifact.register import ModelArtifactRegister


@ModelArtifactRegister.register(Framework.tensorflow)
def load_tensorflow(data: bytes):
    """加载 TensorFlow 模型

    参数：
        data: 二进制数据

    返回：
        TensorFlow Keras 模型实例
    """
    import tensorflow as tf

    with temp_file(data, ".keras") as path:
        return tf.keras.models.load_model(path)