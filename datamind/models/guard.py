# datamind/models/guard.py

"""模型状态守卫器

提供模型元数据、模型版本、部署与实验的状态迁移校验。

核心功能：
  - validate_metadata_transition: 校验元数据状态迁移
  - validate_version_transition: 校验版本状态迁移
  - validate_deployment_transition: 校验部署状态迁移
  - validate_experiment_transition: 校验实验状态迁移

使用示例：
  from datamind.models.guard import ModelGuard
  from datamind.models.enums import (
      MetadataStatus,
      VersionStatus,
      DeploymentStatus,
      ExperimentStatus,
  )

  ModelGuard.validate_metadata_transition(
      current=MetadataStatus.ACTIVE,
      target=MetadataStatus.DEPRECATED,
  )

  ModelGuard.validate_version_transition(
      current=VersionStatus.ACTIVE,
      target=VersionStatus.DEPRECATED,
  )

  ModelGuard.validate_deployment_transition(
      current=DeploymentStatus.INACTIVE,
      target=DeploymentStatus.ACTIVE,
      metadata_status=MetadataStatus.ACTIVE,
  )

  ModelGuard.validate_experiment_transition(
      current=ExperimentStatus.RUNNING,
      target=ExperimentStatus.PAUSED,
  )
"""

from datamind.models.enums import (
    MetadataStatus,
    VersionStatus,
    DeploymentStatus,
    ExperimentStatus,
)
from datamind.models.errors import (
    InvalidModelStateError,
    InvalidDeploymentStateError,
    InvalidExperimentStateError,
)


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

    _VERSION_TRANSITIONS = {
        VersionStatus.ACTIVE: {
            VersionStatus.DEPRECATED,
            VersionStatus.ARCHIVED,
        },
        VersionStatus.DEPRECATED: {
            VersionStatus.ARCHIVED,
        },
        VersionStatus.ARCHIVED: set(),
    }

    _DEPLOYMENT_TRANSITIONS = {
        DeploymentStatus.INACTIVE: {
            DeploymentStatus.ACTIVE,
        },
        DeploymentStatus.ACTIVE: {
            DeploymentStatus.INACTIVE,
        },
    }

    _EXPERIMENT_TRANSITIONS = {
        ExperimentStatus.RUNNING: {
            ExperimentStatus.PAUSED,
            ExperimentStatus.COMPLETED,
            ExperimentStatus.ARCHIVED,
        },
        ExperimentStatus.PAUSED: {
            ExperimentStatus.RUNNING,
            ExperimentStatus.COMPLETED,
            ExperimentStatus.ARCHIVED,
        },
        ExperimentStatus.COMPLETED: {
            ExperimentStatus.ARCHIVED,
        },
        ExperimentStatus.ARCHIVED: set(),
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
    def validate_version_transition(
        cls,
        current: VersionStatus,
        target: VersionStatus,
    ) -> None:
        """校验版本状态迁移

        参数：
            current: 当前状态
            target: 目标状态

        异常：
            InvalidModelStateError: 非法版本状态
        """
        if current == target:
            return

        allowed = cls._VERSION_TRANSITIONS.get(current, set())

        if target not in allowed:
            raise InvalidModelStateError(
                f"非法版本状态迁移: {current.value} -> {target.value}"
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

    @classmethod
    def validate_experiment_transition(
        cls,
        current: ExperimentStatus,
        target: ExperimentStatus,
    ) -> None:
        """校验实验状态迁移

        参数：
            current: 当前实验状态
            target: 目标实验状态

        异常：
            InvalidExperimentStateError: 非法实验状态
        """
        if current == target:
            return

        allowed = cls._EXPERIMENT_TRANSITIONS.get(current, set())

        if target not in allowed:
            raise InvalidExperimentStateError(
                f"非法实验状态迁移: {current.value} -> {target.value}"
            )