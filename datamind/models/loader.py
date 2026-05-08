# datamind/models/loader.py

"""模型加载组件

从 BentoML Model Store 加载已注册模型。

核心功能：
  - load: 根据 framework 和 tag 加载模型

使用示例：
  from datamind.models.loader import ModelLoader

  loader = ModelLoader()

  model = loader.load(
      framework="sklearn",
      tag="scorecard:abc123def",
  )
"""

from typing import Any

from datamind.models.backend import BentoBackend


class ModelLoader:
    """模型加载器"""

    def __init__(self):
        self.backend = BentoBackend()

    def load(
        self,
        *,
        framework: str,
        tag: str,
    ) -> Any:
        """加载模型

        参数：
            framework: 模型框架
            tag: BentoML模型标签（格式：name:version）

        返回：
            模型实例
        """
        return self.backend.load(
            framework=framework,
            tag=tag,
        )