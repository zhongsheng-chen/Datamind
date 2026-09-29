"""模型推理核心模块.

提供统一模型推理入口和模型能力定义。

核心功能：
  - Inference: 统一模型推理接口
  - ModelCapability: 模型能力标记

使用示例：
  from datamind.core import Inference, ModelCapability

  inference = Inference(model=trained_model)
  capabilities = inference.get_capabilities()

  if capabilities & ModelCapability.PREDICT_PROBA:
      probability = inference.predict(features)
"""

from datamind.core.capability import ModelCapability
from datamind.core.inference import Inference

__all__ = [
    "Inference",
    "ModelCapability",
]
