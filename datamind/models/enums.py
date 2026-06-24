# datamind/models/enums.py

"""模型生命周期状态枚举

定义模型元数据、模型版本、部署与实验过程中的状态机，
用于控制生命周期流转与操作权限。

核心功能：
  - MetadataStatus: 模型元数据生命周期状态
  - VersionStatus: 模型版本生命周期状态
  - DeploymentStatus: 模型部署运行状态
  - ExperimentStatus: 实验生命周期状态
  - ExperimentVariantStatus: 实验分组状态
  - AssignmentStrategy: 实验分桶策略
  - DecisionStrategy: 请求决策策略

使用示例：
  from datamind.models.enums import (
      MetadataStatus,
      VersionStatus,
      DeploymentStatus,
      ExperimentStatus,
  )

  # 判断模型是否允许进入部署流程
  if metadata.status == MetadataStatus.ACTIVE:
      allow_deploy()

  # 实验必须处于运行状态才允许流量分配
  if experiment.status == ExperimentStatus.RUNNING:
      allow_assignment()
"""

from enum import Enum


class BaseEnum(str, Enum):
    """字符串枚举基类"""
    pass


class MetadataStatus(BaseEnum):
    """模型元数据生命周期状态"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class VersionStatus(BaseEnum):
    """模型版本生命周期状态"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class DeploymentStatus(BaseEnum):
    """模型部署运行状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"


class ExperimentStatus(BaseEnum):
    """实验生命周期状态"""

    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ExperimentVariantStatus(BaseEnum):
    """实验分组状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class AssignmentStrategy(BaseEnum):
    """实验分桶策略"""

    HASH = "hash"
    MANUAL = "manual"


class DecisionStrategy(BaseEnum):
    """请求决策策略"""

    EXPERIMENT = "experiment"
    ROUTING = "routing"
    DEPLOYMENT = "deployment"
    SHADOW = "shadow"
    MANUAL = "manual"