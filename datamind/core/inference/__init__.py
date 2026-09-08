"""推理模块

提供统一模型推理入口。

核心功能：
  - Inference: 统一模型推理接口

使用示例：
  from datamind.core.inference import Inference

  inference = Inference(
      model=trained_model,
      feature_names=[
          "age",
          "employment_type",
      ],
  )

  probability = inference.predict({
      "age": 35,
      "employment_type": "salaried",
  })
"""

from datamind.core.inference.inference import Inference

__all__ = [
    "Inference",
]
