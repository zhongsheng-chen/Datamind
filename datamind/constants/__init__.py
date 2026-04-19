# datamind/constants/__init__.py

"""常量模块

集中管理 Datamind 平台的所有常量定义。

常量分类：
  - storage_type: 存储类型常量
  - framework: 模型框架常量
  - model_type: 模型类型常量
  - model_stage: 模型阶段常量
  - environment: 服务环境常量
  - ab_strategy: AB测试策略常量
  - logging_level: 日志级别常量
  - logging_format: 日志格式常量
  - logging_rotation: 日志轮转常量
  - size: 存储大小常量
  - header: HTTP头常量

使用示例：
  from datamind.constants import (
      StorageType, SUPPORTED_STORAGE_TYPES,
      Framework, SUPPORTED_FRAMEWORKS,
      ModelType, SUPPORTED_MODEL_TYPES,
      ModelStage, SUPPORTED_MODEL_STAGES,
      Environment, SUPPORTED_ENVIRONMENTS,
      ABStrategy, SUPPORTED_AB_STRATEGIES,
      LogLevel, SUPPORTED_LOG_LEVELS,
      LogFormat, SUPPORTED_LOG_FORMATS,
      RotationType, SUPPORTED_ROTATION_TYPES,
      RotationWhen, SUPPORTED_ROTATION_WHEN,
      KB, MB, GB,
      Header
  )
"""

from datamind.constants.storage_type import StorageType, SUPPORTED_STORAGE_TYPES
from datamind.constants.framework import Framework, SUPPORTED_FRAMEWORKS
from datamind.constants.model_type import ModelType, SUPPORTED_MODEL_TYPES
from datamind.constants.model_stage import ModelStage, SUPPORTED_MODEL_STAGES
from datamind.constants.environment import Environment, SUPPORTED_ENVIRONMENTS
from datamind.constants.ab_strategy import ABStrategy, SUPPORTED_AB_STRATEGIES
from datamind.constants.logging_level import LogLevel, SUPPORTED_LOG_LEVELS
from datamind.constants.logging_format import LogFormat, SUPPORTED_LOG_FORMATS
from datamind.constants.logging_rotation import RotationType, SUPPORTED_ROTATION_TYPES, RotationWhen, SUPPORTED_ROTATION_WHEN
from datamind.constants.size import KB, MB, GB
from datamind.constants.header import Header

__all__ = [
    "StorageType",
    "SUPPORTED_STORAGE_TYPES",
    "Framework",
    "SUPPORTED_FRAMEWORKS",
    "ModelType",
    "SUPPORTED_MODEL_TYPES",
    "ModelStage",
    "SUPPORTED_MODEL_STAGES",
    "Environment",
    "SUPPORTED_ENVIRONMENTS",
    "ABStrategy",
    "SUPPORTED_AB_STRATEGIES",
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
    "Header",
]