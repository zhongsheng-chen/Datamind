# datamind/models/backend.py

"""BentoML 模型后端

负责模型的保存与加载，仅封装 BentoML 框架差异。

核心功能：
  - save: 保存模型到 BentoML Model Store
  - load: 从 BentoML Model Store 加载模型

使用示例：
  from datamind.models.backend import BentoBackend

  backend = BentoBackend()

  backend.save(
      name="my_model",
      framework="sklearn",
      model=model
  )

  loaded_model = backend.load(
      framework="sklearn",
      tag="my_model:latest"
  )
"""

from typing import Any
import bentoml


FRAMEWORK_TO_BENTOML = {
    "sklearn": bentoml.sklearn,
    "xgboost": bentoml.xgboost,
    "lightgbm": bentoml.lightgbm,
    "catboost": bentoml.catboost,
    "torch": bentoml.pytorch,
    "pytorch": bentoml.pytorch,
    "tensorflow": bentoml.tensorflow,
    "onnx": bentoml.onnx,
}


class BentoBackend:
    """BentoML 模型后端"""

    @staticmethod
    def _get_backend(framework: str):
        """获取框架对应的 BentoML 后端

        参数：
            framework: 模型框架

        返回：
            BentoML 后端模块

        异常：
            KeyError: 不支持的框架
        """
        try:
            return FRAMEWORK_TO_BENTOML[framework]
        except KeyError:
            raise KeyError(
                f"不支持的框架: {framework}, 支持: {list(FRAMEWORK_TO_BENTOML.keys())}"
            )

    def save(self, *, name: str, framework: str, model: Any, **kwargs) -> Any:
        """保存模型到 BentoML Model Store

        参数：
            name: 模型名称
            framework: 模型框架（sklearn/xgboost/lightgbm 等）
            model: 模型实例

        返回：
            保存的模型对象
        """
        backend = self._get_backend(framework)
        return backend.save_model(name=name, model=model, **kwargs)

    def load(self, *, framework: str, tag: str) -> Any:
        """从 BentoML Model Store 加载模型

        参数：
            framework: 模型框架
            tag: 模型标签（格式：模型名:版本）

        返回：
            加载的模型实例
        """
        backend = self._get_backend(framework)
        return backend.load_model(tag)