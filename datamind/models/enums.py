# datamind/models/enums.py

"""模型生命周期与运行状态枚举

定义模型元数据、模型版本、部署、运行控制、实验与请求决策
过程中的状态和策略枚举。

核心功能：
  - MetadataStatus: 模型元数据生命周期状态
  - VersionStatus: 模型版本生命周期状态
  - DeploymentStatus: 模型部署状态
  - RuntimeControlStatus: 运行控制目标状态
  - ExperimentStatus: 实验生命周期状态
  - ExperimentVariantStatus: 实验分组状态
  - AssignmentStrategy: 实验分桶策略
  - DecisionStrategy: 请求决策策略

使用示例：
  from datamind.models.enums import (
      DeploymentStatus,
      RuntimeControlStatus,
  )

  if deployment.status == DeploymentStatus.ACTIVE:
      allow_deploy()

  if control.desired_status == RuntimeControlStatus.LOADED:
      load_runtime_model()
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
    """模型部署状态

    ACTIVE:
        部署处于启用状态，可以参与路由和运行。

    INACTIVE:
        部署处于停用状态，不允许参与正常运行。
    """

    ACTIVE = "active"
    INACTIVE = "inactive"


class RuntimeControlStatus(BaseEnum):
    """运行控制目标状态

    表示各 Worker 对指定 Deployment
    应达到的期望运行状态。

    LOADED:
        各 Worker 应加载该部署对应的模型。

    UNLOADED:
        各 Worker 应卸载该部署对应的模型。

    说明：
        该状态表示运行控制目标状态，
        不代表某个 Worker 当前的实际运行状态。

        Worker 的实际运行状态由 Runtime 记录维护，
        例如：
          - loading
          - loaded
          - failed
          - unloaded

        reload 操作通过 generation 递增实现，
        不需要单独定义 reloading 状态。
    """

    LOADED = "loaded"
    UNLOADED = "unloaded"


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


__all__ = [
    "BaseEnum",
    "MetadataStatus",
    "VersionStatus",
    "DeploymentStatus",
    "RuntimeControlStatus",
    "ExperimentStatus",
    "ExperimentVariantStatus",
    "AssignmentStrategy",
    "DecisionStrategy",
]
