# datamind/models/artifact.py

"""模型产物加载器

将模型文件字节流加载为 Python 模型对象。

核心功能：
  - load: 加载模型对象

使用示例：
  from datamind.models.artifact import ModelArtifact

  model = ModelArtifact.load(
      framework="sklearn",
      data=model_bytes
  )
"""

import os
import tempfile

from typing import Any, Callable, Dict

from datamind.constants.framework import Framework


def _normalize(framework: str) -> str:
    """规范化框架名称

    参数：
        framework: 框架名称

    返回：
        规范化后的框架名称（小写、去空格）
    """
    return framework.strip().lower()


def _temp_file(data: bytes, suffix: str):
    """创建临时文件

    参数：
        data: 文件数据
        suffix: 文件后缀

    返回：
        临时文件路径
    """
    fd, path = tempfile.mkstemp(suffix=suffix)

    with os.fdopen(fd, "wb") as f:
        f.write(data)

    return path


class ModelArtifact:
    """模型产物加载器"""

    _registry: Dict[str, Callable[[bytes], Any]] = {}

    @classmethod
    def register(cls, framework: str):
        """注册加载器

        参数：
            framework: 模型框架
        """

        def decorator(func: Callable[[bytes], Any]):
            cls._registry[_normalize(framework)] = func
            return func

        return decorator

    @classmethod
    def load(cls, framework: str, data: bytes) -> Any:
        """加载模型对象

        参数：
            framework: 模型框架
            data: 模型文件二进制数据

        返回：
            模型对象

        异常：
            KeyError: 不支持的框架
        """
        framework = _normalize(framework)

        if framework not in cls._registry:
            raise KeyError(f"不支持的框架: {framework}")

        return cls._registry[framework](data)


@ModelArtifact.register(Framework.sklearn)
def _sklearn(data: bytes):
    import joblib
    from io import BytesIO

    return joblib.load(BytesIO(data))


@ModelArtifact.register(Framework.xgboost)
def _xgboost(data: bytes):
    import xgboost as xgb

    model = xgb.Booster()
    model.load_model(bytearray(data))
    return model


@ModelArtifact.register(Framework.lightgbm)
def _lightgbm(data: bytes):
    import lightgbm as lgb

    return lgb.Booster(model_str=data.decode("utf-8"))


@ModelArtifact.register(Framework.torch)
def _torch(data: bytes):
    import torch
    from io import BytesIO

    return torch.load(BytesIO(data), map_location="cpu")


@ModelArtifact.register(Framework.tensorflow)
def _tensorflow(data: bytes):
    import tensorflow as tf

    path = _temp_file(data, ".keras")
    return tf.keras.models.load_model(path)


@ModelArtifact.register(Framework.onnx)
def _onnx(data: bytes):
    import onnxruntime as ort

    path = _temp_file(data, ".onnx")
    return ort.InferenceSession(path)


@ModelArtifact.register(Framework.catboost)
def _catboost(data: bytes):
    import catboost as cb

    path = _temp_file(data, ".cbm")
    model = cb.CatBoost()
    model.load_model(path)
    return model