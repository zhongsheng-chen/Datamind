"""运行时服务接口组件

提供 BentoML 推理服务、请求结构和服务接口异常。

核心功能：
  - DatamindRuntimeService: 多 Worker 模型推理服务
  - ControlRequest: 运行控制请求
  - DeploymentRequest: 部署查询请求
  - PredictRequest: 单条预测请求
  - BatchPredictRequest: 批量预测请求
  - OutcomeFeedbackRequest: 业务结果回流请求
  - ServiceDeploymentNotFoundError: 服务部署不存在
  - ServiceEnvironmentMismatchError: 服务环境不匹配
  - ServiceAuthenticationError: 请求身份认证失败
  - ServiceAuthorizationError: 请求权限不足
  - ServiceAuthenticationUnavailableError: 认证服务不可用

使用示例：
  from datamind.runtime.server import PredictRequest

  request = PredictRequest(
      model_name="scorecard",
      features={
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      },
  )
"""

from importlib import import_module
from typing import Any, Final


_EXPORTS: Final[dict[str, tuple[str, str]]] = {
    "BatchPredictRequest": (
        "datamind.runtime.server.schemas",
        "BatchPredictRequest",
    ),
    "ControlRequest": ("datamind.runtime.server.schemas", "ControlRequest"),
    "DatamindRuntimeService": (
        "datamind.runtime.server.service",
        "DatamindRuntimeService",
    ),
    "DeploymentRequest": (
        "datamind.runtime.server.schemas",
        "DeploymentRequest",
    ),
    "OutcomeFeedbackRequest": (
        "datamind.runtime.server.schemas",
        "OutcomeFeedbackRequest",
    ),
    "PredictRequest": ("datamind.runtime.server.schemas", "PredictRequest"),
    "ServiceDeploymentNotFoundError": (
        "datamind.runtime.server.errors",
        "ServiceDeploymentNotFoundError",
    ),
    "ServiceEnvironmentMismatchError": (
        "datamind.runtime.server.errors",
        "ServiceEnvironmentMismatchError",
    ),
    "ServiceAuthenticationError": (
        "datamind.runtime.server.errors",
        "ServiceAuthenticationError",
    ),
    "ServiceAuthorizationError": (
        "datamind.runtime.server.errors",
        "ServiceAuthorizationError",
    ),
    "ServiceAuthenticationUnavailableError": (
        "datamind.runtime.server.errors",
        "ServiceAuthenticationUnavailableError",
    ),
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
