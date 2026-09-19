"""模型运行时公共接口

提供模型加载、运行时注册、路由决策、预测执行和状态协调能力。

核心功能：
  - BentoBackend: 管理 BentoML 模型制品
  - ModelLoader: 将模型制品同步至 BentoML 并加载模型
  - RuntimeManager: 管理 Worker 内模型加载与卸载
  - RuntimeRegistry: 保存 Worker 内已加载模型
  - RuntimeRouter: 解析实验、灰度和默认部署路由
  - RuntimeReconciler: 协调数据库期望状态与 Worker 实际状态
  - RuntimePresence: 维护运行时服务在线状态
  - PredictionExecutor: 执行主预测和影子预测

使用示例：
  from datamind.runtime import RuntimeManager

  manager = RuntimeManager()
  runtime_model = await manager.load(
      "dep_0123456789abcdef"
  )
"""

from importlib import import_module
from typing import Any, Final


_EXPORTS_BY_MODULE: Final[dict[str, tuple[str, ...]]] = {
    "backend": ("BentoBackend",),
    "executor": (
        "ExecutionPlan",
        "ExecutionResult",
        "PredictionExecutor",
    ),
    "loader": ("ModelLoader",),
    "manager": ("RuntimeManager",),
    "presence": ("RuntimePresence",),
    "reconciler": (
        "ControlSnapshot",
        "ReconcileResult",
        "RuntimeReconciler",
    ),
    "registry": (
        "RuntimeModel",
        "RuntimeRegistry",
    ),
    "routing": (
        "RouteResult",
        "RoutingPlan",
        "RuntimeRouter",
    ),
    "shadow": ("ShadowTask",),
}

_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    name: (f"{__name__}.{module_name}", name)
    for module_name, names in _EXPORTS_BY_MODULE.items()
    for name in names
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
