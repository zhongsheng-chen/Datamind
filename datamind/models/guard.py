# datamind/models/guard.py

"""模型状态守卫器

提供模型元数据和部署的状态迁移校验。

核心功能：
  - validate_metadata_transition: 校验元数据状态迁移
  - validate_deployment_transition: 校验部署状态迁移

使用示例：
  from datamind.models.guard import ModelGuard
  from datamind.models.enums import MetadataStatus, DeploymentStatus

  ModelGuard.validate_metadata_transition(
      current=MetadataStatus.ACTIVE,
      target=MetadataStatus.DEPRECATED,
  )

  ModelGuard.validate_deployment_transition(
      current=DeploymentStatus.INACTIVE,
      target=DeploymentStatus.ACTIVE,
      metadata_status=MetadataStatus.ACTIVE,
  )
"""

from datamind.models.enums import MetadataStatus, DeploymentStatus
from datamind.models.errors import InvalidModelStateError, InvalidDeploymentStateError


class ModelGuard:
    """模型状态守卫器"""

    _METADATA_TRANSITIONS = {
        MetadataStatus.ACTIVE: {
            MetadataStatus.DEPRECATED,
            MetadataStatus.INACTIVE,
        },
        MetadataStatus.DEPRECATED: {
            MetadataStatus.ARCHIVED,
        },
        MetadataStatus.INACTIVE: {
            MetadataStatus.ACTIVE,
            MetadataStatus.ARCHIVED,
        },
        MetadataStatus.ARCHIVED: set(),
    }

    _DEPLOYMENT_TRANSITIONS = {
        DeploymentStatus.INACTIVE: {
            DeploymentStatus.ACTIVE,
        },
        DeploymentStatus.ACTIVE: {
            DeploymentStatus.INACTIVE,
        },
    }

    @classmethod
    def validate_metadata_transition(
        cls,
        current: MetadataStatus,
        target: MetadataStatus,
    ) -> None:
        """校验元数据状态迁移

        参数：
            current: 当前状态
            target: 目标状态

        异常：
            InvalidModelStateError: 非法模型状态
        """
        if current == target:
            return

        allowed = cls._METADATA_TRANSITIONS.get(current, set())

        if target not in allowed:
            raise InvalidModelStateError(
                f"非法模型状态迁移: {current.value} -> {target.value}"
            )

    @classmethod
    def validate_deployment_transition(
        cls,
        current: DeploymentStatus,
        target: DeploymentStatus,
        metadata_status: MetadataStatus,
    ) -> None:
        """校验部署状态迁移

        参数：
            current: 当前部署状态
            target: 目标部署状态
            metadata_status: 关联的模型元数据状态

        异常：
            InvalidDeploymentStateError: 非法部署状态
        """
        if current == target:
            return

        if target == DeploymentStatus.ACTIVE and metadata_status != MetadataStatus.ACTIVE:
            raise InvalidDeploymentStateError(
                f"当前模型状态为 {metadata_status.value}，不允许上线"
            )

        allowed = cls._DEPLOYMENT_TRANSITIONS.get(current, set())

        if target not in allowed:
            raise InvalidDeploymentStateError(
                f"非法部署状态迁移: {current.value} -> {target.value}"
            )