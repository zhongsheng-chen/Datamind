# datamind/core/inference/__init__.py

"""推理模块

提供统一模型推理入口。

核心功能：
  - Inference: 统一模型推理接口

使用示例：
  from datamind.core.inference import Inference

  inference = Inference(
      model=model,
      feature_names=[
          "age",
          "annual_income",
          "debt_to_income_ratio",
          "credit_utilization_ratio",
          "delinquency_count",
      ],
      positive_class=1,
  )

  probability = inference.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

from datamind.core.inference.inference import Inference

__all__ = [
    "Inference",
]
