# datamind/runtime/__init__.py

"""模型运行时组件

提供模型加载、内存注册、运行状态管理、路由决策和状态协调能力。

核心功能：
  - RuntimeManager: 管理 Worker 内模型加载与卸载
  - RuntimeRegistry: 保存 Worker 内已加载模型
  - RuntimeRouter: 解析实验、灰度和默认部署路由
  - RuntimeReconciler: 协调数据库期望状态与 Worker 实际状态
  - ModelLoader: 从 BentoML Model Store 加载模型

使用示例：
  from datamind.runtime import RuntimeManager

  runtime_model = await RuntimeManager().start(
      "dep_0123456789abcdef"
  )
"""

from importlib import import_module
from typing import Any, Final


_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "BentoBackend": ("datamind.runtime.backend", "BentoBackend"),
    "ControlSnapshot": ("datamind.runtime.reconciler", "ControlSnapshot"),
    "ModelLoader": ("datamind.runtime.loader", "ModelLoader"),
    "ReconcileResult": ("datamind.runtime.reconciler", "ReconcileResult"),
    "RouteResult": ("datamind.runtime.routing", "RouteResult"),
    "RuntimeManager": ("datamind.runtime.manager", "RuntimeManager"),
    "RuntimeModel": ("datamind.runtime.registry", "RuntimeModel"),
    "RuntimeReconciler": ("datamind.runtime.reconciler", "RuntimeReconciler"),
    "RuntimeRegistry": ("datamind.runtime.registry", "RuntimeRegistry"),
    "RuntimeRouter": ("datamind.runtime.routing", "RuntimeRouter"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    """按需加载包级公共对象"""
    export = _EXPORTS.get(name)

    if export is None:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        )

    module_name, attribute_name = export
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回包含延迟公共导出的模块属性列表"""
    return sorted({*globals(), *__all__})
