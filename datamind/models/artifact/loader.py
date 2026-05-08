# datamind/models/artifact/loader.py

"""模型产物加载器

将模型文件字节流反序列化为 Python 模型对象。

核心功能：
  - load: 加载模型对象

使用示例：
  from datamind.models.artifact.loader import ModelArtifactLoader

  model = ModelArtifactLoader.load(
      framework="sklearn",
      data=model_bytes,
  )
"""

from typing import Any

from datamind.models.artifact.register import get_handler


class ModelArtifactLoader:
    """模型产物加载器"""

    @classmethod
    def load(cls, framework: str, data: bytes) -> Any:
        """加载模型对象

        参数：
            framework: 模型框架
            data: 二进制数据

        返回：
            Python 模型对象

        异常：
            KeyError: 不支持的模型框架
        """
        handler = get_handler(framework)

        return handler(data)