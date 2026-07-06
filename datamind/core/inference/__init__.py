# datamind/core/inference/__init__.py

"""推理模块

提供模型推理的统一接口。

核心功能：
    - Inference: 统一推理接口

使用示例：
    from datamind.core.inference import Inference

    inference = Inference(
        model=model,
        feature_names=["age", "income"]
    )

    prob = inference.predict({"age": 30, "income": 50000})
"""

from datamind.core.inference.inference import Inference

__all__ = ["Inference"]
