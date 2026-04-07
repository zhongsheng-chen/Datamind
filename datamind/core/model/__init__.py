# datamind/core/model/__init__.py

"""模型管理模块

提供模型注册、加载、推理等核心功能，是模型部署平台的核心模块。

核心功能：
  - 模型注册：将训练好的模型注册到 BentoML Model Store
  - 模型加载：从 BentoML Model Store 加载模型到内存
  - 模型推理：执行模型预测，返回结果
  - 模型管理：激活/停用/归档/提升生产模型
  - 模型预热：避免首次推理冷启动延迟

模块组成：
  - ModelRegistry: 模型注册中心，负责模型的注册、版本管理和状态管理
  - ModelLoader: 模型加载器，负责模型的动态加载、卸载和缓存管理
  - ModelInference: 模型推理引擎，负责执行模型预测（待实现）
  - ScorecardEngine: 评分卡计算引擎（待实现）
  - FraudEngine: 反欺诈检测引擎（待实现）

使用场景：
  - 模型上线：注册新模型 -> 激活 -> 提升为生产模型
  - 模型推理：获取模型 -> 执行预测 -> 返回结果
  - A/B测试：同时加载多个模型，根据流量分配进行推理

使用示例：
    from datamind.core.model import get_model_registry, get_model_loader

    # 获取实例
    registry = get_model_registry()
    loader = get_model_loader()

    # 注册模型
    model_id = registry.register_model(
        model_name="credit_scorecard",
        model_version="1.0.0",
        task_type="scoring",
        model_type="logistic_regression",
        framework="sklearn",
        input_features=["age", "income", "debt"],
        output_schema={"score": "float", "feature_scores": "dict"},
        created_by="admin",
        model_file=open("model.pkl", "rb")
    )

    # 激活模型
    registry.activate_model(model_id, operator="admin")

    # 提升为生产模型
    registry.promote_to_production(model_id, operator="admin")

    # 加载模型
    loader.load_model(model_id)

    # 预热模型
    loader.warm_up_model(model_id)

    # 获取模型实例进行推理
    model = loader.get_model(model_id)
    result = model.predict(features)
"""

from datamind.core.model.registry import ModelRegistry, get_model_registry
from datamind.core.model.loader import ModelLoader, get_model_loader

__all__ = [
    'ModelRegistry',
    'get_model_registry',
    'ModelLoader',
    'get_model_loader',
]