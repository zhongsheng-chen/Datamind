# datamind/core/model/__init__.py

"""模型管理模块

提供模型的全生命周期管理功能，包括模型注册、加载、版本控制等。

模块组成：
  - registry: 模型注册中心，负责模型的注册、状态管理、生产模型管理
  - loader: 模型加载器，负责模型的动态加载和卸载

核心功能：
  - 模型注册：上传模型文件并注册到系统，存储到 BentoML Model Store
  - 模型查询：获取模型详情、列表、历史
  - 模型状态管理：激活、停用、归档
  - 生产模型管理：设置生产模型、版本切换
  - 模型加载管理：动态加载/卸载模型到内存
  - 完整审计：记录所有模型操作到审计日志
  - 链路追踪：完整的 trace_id, span_id, parent_span_id

使用示例：
    from datamind.core.model import get_model_registry, get_model_loader

    # 获取模型注册中心实例
    registry = get_model_registry()

    # 获取模型加载器实例
    loader = get_model_loader()

    # 注册模型
    model_id = registry.register_model(
        model_name="scorecard_v1",
        model_version="1.0.0",
        task_type="scoring",
        model_type="logistic_regression",
        framework="sklearn",
        input_features=["age", "income"],
        output_schema={"score": "float"},
        created_by="admin",
        model_file=open("model.pkl", "rb")
    )

    # 激活模型
    registry.activate_model(model_id, operator="admin")

    # 设置为生产模型
    registry.promote_to_production(model_id, operator="admin")

    # 加载模型到内存
    loader.load_model(model_id, operator="admin")

    # 获取已加载的模型
    model = loader.get_model(model_id)
"""

from datamind.core.model.registry import get_model_registry
from datamind.core.model.loader import get_model_loader

__all__ = [
    'get_model_registry',
    'get_model_loader',
]