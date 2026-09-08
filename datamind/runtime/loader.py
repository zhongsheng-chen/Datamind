"""模型加载组件

负责将统一存储中的模型制品同步至 BentoML Model Store，
并从 BentoML 加载模型对象。

核心功能：
  - load: 同步并加载模型

使用示例：
  from datamind.runtime.loader import ModelLoader

  loader = ModelLoader()

  model = loader.load(
      framework="sklearn",
      bento_tag="scorecard:abc123def",
      model_key=(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/model.pkl"
      ),
  )
"""

from typing import Any

from bentoml.exceptions import BentoMLException, NotFound

from datamind.models.artifact import ModelArtifactLoader
from datamind.runtime.backend import BentoBackend
from datamind.storage import Storage, get_storage


class ModelLoader:
    """模型加载器"""

    def __init__(
            self,
            storage: Storage | None = None,
            backend: BentoBackend | None = None,
    ) -> None:
        """初始化模型加载器

        参数：
            storage: 模型制品存储，默认使用全局存储实例
            backend: BentoML 模型后端，默认使用 BentoBackend
        """
        self._storage = (
            storage
            if storage is not None
            else get_storage()
        )
        self._backend = (
            backend
            if backend is not None
            else BentoBackend()
        )

    def load(
            self,
            *,
            framework: str,
            bento_tag: str,
            model_key: str,
    ) -> Any:
        """同步并加载模型

        参数：
            framework: 模型框架
            bento_tag: BentoML 模型标签
            model_key: 模型制品存储键

        返回：
            模型实例

        异常：
            ValueError: 模型标签或制品存储键为空
        """
        if not bento_tag.strip():
            raise ValueError(
                "bento_tag 不能为空"
            )

        if not model_key.strip():
            raise ValueError(
                "model_key 不能为空"
            )

        try:
            return self._backend.load(
                framework=framework,
                tag=bento_tag,
            )
        except NotFound:
            pass

        data = self._storage.load_by_key(
            model_key
        )
        model = ModelArtifactLoader.load(
            framework=framework,
            data=data,
        )

        try:
            self._backend.save(
                name=bento_tag,
                framework=framework,
                model=model,
                labels={
                    "model_key": model_key,
                },
            )
        except BentoMLException as save_error:
            try:
                return self._backend.load(
                    framework=framework,
                    tag=bento_tag,
                )
            except NotFound:
                raise save_error

        return self._backend.load(
            framework=framework,
            tag=bento_tag,
        )
