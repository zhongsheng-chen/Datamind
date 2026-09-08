"""常量模块

集中管理所有常量定义。

核心功能：
  - data_type: 数据类型枚举
  - storage_type: 存储类型枚举
  - framework: 模型框架枚举
  - model_type: 模型类型枚举
  - task_type: 模型任务类型枚举
  - version: 模型版本格式
  - environment: 服务环境枚举
  - identity: 身份管理常量
  - permissions: 权限常量
  - logging_level: 日志级别枚举
  - logging_format: 日志格式枚举
  - logging_rotation: 日志轮转枚举
  - size: 存储大小常量

使用示例：
  from datamind.constants import (
      Environment,
      Framework,
      ModelType,
      TaskType,
  )

  if environment == Environment.PRODUCTION:
      enable_production_mode()

  if (
          framework == Framework.SKLEARN
          and model_type == ModelType.LOGISTIC_REGRESSION
          and task_type == TaskType.SCORING
  ):
      register_scoring_model()
"""

from datamind.constants.data_type import (
    DataType,
    SUPPORTED_DATA_TYPES,
)
from datamind.constants.environment import (
    Environment,
    SUPPORTED_ENVIRONMENTS,
)
from datamind.constants.framework import (
    Framework,
    SUPPORTED_FRAMEWORKS,
)
from datamind.constants.identity import (
    ADMINISTRATOR_DISPLAY_NAME,
    ADMINISTRATOR_PERMISSIONS,
    ADMINISTRATOR_ROLE_NAME,
    BUILTIN_ROLE_NAMES,
)
from datamind.constants.logging_format import (
    LogFormat,
    SUPPORTED_LOG_FORMATS,
)
from datamind.constants.logging_level import (
    LogLevel,
    SUPPORTED_LOG_LEVELS,
)
from datamind.constants.logging_rotation import (
    RotationType,
    RotationWhen,
    SUPPORTED_ROTATION_TYPES,
    SUPPORTED_ROTATION_WHEN,
)
from datamind.constants.model_type import (
    ModelType,
    SUPPORTED_MODEL_TYPES,
    SUPPORTED_MODEL_TYPES_BY_FRAMEWORK,
)
from datamind.constants.model_name import SUPPORTED_MODEL_NAME_PATTERN
from datamind.constants.permissions import SUPPORTED_PERMISSIONS
from datamind.constants.size import (
    GB,
    KB,
    MB,
)
from datamind.constants.storage_type import (
    StorageType,
    SUPPORTED_STORAGE_TYPES,
)
from datamind.constants.task_type import (
    SUPPORTED_TASK_TYPES,
    TaskType,
)
from datamind.constants.version import (
    SUPPORTED_MODEL_VERSION_PATTERN,
)

__all__ = [
    "DataType",
    "SUPPORTED_DATA_TYPES",
    "StorageType",
    "SUPPORTED_STORAGE_TYPES",
    "Framework",
    "SUPPORTED_FRAMEWORKS",
    "ModelType",
    "SUPPORTED_MODEL_TYPES",
    "SUPPORTED_MODEL_TYPES_BY_FRAMEWORK",
    "SUPPORTED_MODEL_NAME_PATTERN",
    "TaskType",
    "SUPPORTED_TASK_TYPES",
    "SUPPORTED_MODEL_VERSION_PATTERN",
    "Environment",
    "SUPPORTED_ENVIRONMENTS",
    "ADMINISTRATOR_DISPLAY_NAME",
    "ADMINISTRATOR_ROLE_NAME",
    "ADMINISTRATOR_PERMISSIONS",
    "BUILTIN_ROLE_NAMES",
    "SUPPORTED_PERMISSIONS",
    "LogLevel",
    "SUPPORTED_LOG_LEVELS",
    "LogFormat",
    "SUPPORTED_LOG_FORMATS",
    "RotationType",
    "SUPPORTED_ROTATION_TYPES",
    "RotationWhen",
    "SUPPORTED_ROTATION_WHEN",
    "KB",
    "MB",
    "GB",
]
