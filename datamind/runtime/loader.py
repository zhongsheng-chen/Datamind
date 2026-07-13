# datamind/runtime/loader.py

"""模型加载组件

从 BentoML Model Store 加载已注册模型。

核心功能：
  - load: 根据 framework 和 tag 加载模型

使用示例：
  from datamind.runtime.loader import ModelLoader

  loader = ModelLoader()

  model = loader.load(
      framework="sklearn",
      tag="scorecard:abc123def",
  )
"""

from typing import Any

from datamind.models.artifact import ModelArtifactLoader
from datamind.runtime.backend import BentoBackend
from datamind.storage import get_storage


class ModelLoader:
    """模型加载器"""

    def __init__(self):
        self.backend = BentoBackend()
        self.storage = get_storage()

    def load(
            self,
            *,
            framework: str,
            tag: str | None,
            model_key: str | None = None,
    ) -> Any:
        """加载模型

        参数：
            framework: 模型框架
            tag: BentoML 模型标签（可选）
            model_key: 对象存储中的模型制品键（可选）

        返回：
            模型实例
        """
        if model_key is not None:
            data = self.storage.load_by_key(
                model_key
            )

            return ModelArtifactLoader.load(
                framework=framework,
                data=data,
            )

        if tag is None or tag.strip() == "":
            raise ValueError(
                "tag 和 model_key 至少需要提供一个"
            )

        return self.backend.load(
            framework=framework,
            tag=tag,
        )
