# datamind/models/artifact/__init__.py

"""模型产物模块

负责将模型文件字节流反序列化为 Python 模型对象。

核心功能：
  - ModelArtifactLoader: 模型产物加载器
  - ModelArtifactRegister: 模型产物注册器

使用示例：
  from datamind.models.artifact import ModelArtifactLoader

  model = ModelArtifactLoader.load(
      framework="sklearn",
      data=model_bytes,
  )
"""

import datamind.models.artifact.handlers
from datamind.models.artifact.loader import ModelArtifactLoader
from datamind.models.artifact.register import ModelArtifactRegister

__all__ = [
    "ModelArtifactLoader",
    "ModelArtifactRegister",
]