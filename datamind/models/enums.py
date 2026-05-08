# datamind/models/enums.py

"""模型生命周期状态枚举

定义模型元数据与部署过程中的状态机，用于控制模型生命周期流转与操作权限。

核心功能：
  - MetadataStatus: 模型元数据生命周期状态
  - DeploymentStatus: 模型部署运行状态

使用示例：
  from datamind.models.enums import MetadataStatus, DeploymentStatus

  if metadata.status == MetadataStatus.ACTIVE:
      allow_deploy()
"""

from enum import StrEnum


class MetadataStatus(StrEnum):
    """模型元数据生命周期状态"""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class DeploymentStatus(StrEnum):
    """模型部署运行状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"