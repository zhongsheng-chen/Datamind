# datamind/services/__init__.py

"""业务服务模块

提供模型注册、删除恢复与制品清理、模型生命周期管理、
模型部署管理、部署运行期望状态控制和系统初始化服务。

核心功能：
  - InitializationService: 系统初始化服务
  - IdentityService: 身份管理服务
  - ModelRegistrationService: 模型注册服务
  - ModelDeletionService: 模型删除、恢复和制品清理服务
  - ModelLifecycleService: 模型生命周期管理服务
  - DeploymentLifecycleService: 模型部署生命周期服务
  - RuntimeControlService: 部署运行期望状态控制服务
  - OutcomeService: 实验结果回流服务

使用示例：
  from datamind.services import (
      InitializationService,
      IdentityService,
      ModelRegistrationService,
      ModelDeletionService,
      ModelLifecycleService,
      DeploymentLifecycleService,
      RuntimeControlService,
      OutcomeService,
  )
"""

from datamind.services.control import RuntimeControlService
from datamind.services.deletion import ModelDeletionService
from datamind.services.deployment import DeploymentLifecycleService
from datamind.services.initialization import InitializationService
from datamind.services.identity import IdentityService
from datamind.services.lifecycle import ModelLifecycleService
from datamind.services.outcome import OutcomeService
from datamind.services.registration import ModelRegistrationService

__all__ = [
    "InitializationService",
    "IdentityService",
    "ModelRegistrationService",
    "ModelDeletionService",
    "ModelLifecycleService",
    "DeploymentLifecycleService",
    "RuntimeControlService",
    "OutcomeService",
]
