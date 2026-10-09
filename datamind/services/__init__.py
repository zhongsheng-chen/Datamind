"""业务服务模块.

提供系统初始化、身份管理、模型管理、资源生命周期管理、
运行控制和控制台查询服务。

核心功能：
  - InitializationService: 系统初始化服务
  - IdentityService: 身份管理服务
  - ModelRegistrationService: 模型注册服务
  - ModelCatalogService: 模型目录管理服务
  - ModelDeletionService: 模型删除、恢复和制品清理服务
  - ModelLifecycleService: 模型生命周期管理服务
  - DeploymentLifecycleService: 模型部署生命周期服务
  - RoutingLifecycleService: 路由生命周期服务
  - ExperimentLifecycleService: 实验生命周期服务
  - BatchLifecycleService: 批次生命周期服务
  - RuntimeControlService: 部署重载与运行状态查询服务
  - DashboardService: 管理控制台查询服务

使用示例：
  from datamind.services import (
      InitializationService,
      IdentityService,
      ModelRegistrationService,
      ModelCatalogService,
      ModelDeletionService,
      ModelLifecycleService,
      DeploymentLifecycleService,
      RoutingLifecycleService,
      ExperimentLifecycleService,
      BatchLifecycleService,
      RuntimeControlService,
      DashboardService,
  )
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datamind.services.batch import BatchLifecycleService
    from datamind.services.catalog import ModelCatalogService
    from datamind.services.control import RuntimeControlService
    from datamind.services.dashboard import DashboardService
    from datamind.services.deletion import ModelDeletionService
    from datamind.services.deployment import DeploymentLifecycleService
    from datamind.services.experiment import ExperimentLifecycleService
    from datamind.services.identity import IdentityService
    from datamind.services.initialization import InitializationService
    from datamind.services.lifecycle import ModelLifecycleService
    from datamind.services.registration import ModelRegistrationService
    from datamind.services.routing import RoutingLifecycleService

__all__ = [
    "InitializationService",
    "IdentityService",
    "ModelRegistrationService",
    "ModelCatalogService",
    "ModelDeletionService",
    "ModelLifecycleService",
    "DeploymentLifecycleService",
    "RoutingLifecycleService",
    "ExperimentLifecycleService",
    "BatchLifecycleService",
    "RuntimeControlService",
    "DashboardService",
]


_SERVICE_MODULES = {
    "InitializationService": "initialization",
    "IdentityService": "identity",
    "ModelRegistrationService": "registration",
    "ModelCatalogService": "catalog",
    "ModelDeletionService": "deletion",
    "ModelLifecycleService": "lifecycle",
    "DeploymentLifecycleService": "deployment",
    "RoutingLifecycleService": "routing",
    "ExperimentLifecycleService": "experiment",
    "BatchLifecycleService": "batch",
    "RuntimeControlService": "control",
    "DashboardService": "dashboard",
}


def __getattr__(name: str) -> Any:
    """按需加载业务服务，避免包导入触发运行时基础设施配置."""
    module_name = _SERVICE_MODULES.get(name)

    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(
        import_module(f"{__name__}.{module_name}"),
        name,
    )
    globals()[name] = value
    return value
