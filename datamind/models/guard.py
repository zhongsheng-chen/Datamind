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

  # 状态迁移校验
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

  # 模型是否允许部署
  ModelGuard.validate_model_deployable(
      status=MetadataStatus.ACTIVE,
  )

  # 版本是否允许部署
  ModelGuard.validate_version_deployable(
      status=VersionStatus.ACTIVE,
  )
"""

from datamind.models.enums import (
    DeploymentStatus,
    ExperimentStatus,
    MetadataStatus,
    VersionStatus,
)
from datamind.models.errors import (
    InvalidDeploymentStateError,
    InvalidExperimentStateError,
    InvalidModelStateError,
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
            MetadataStatus.DEPRECATED,
            MetadataStatus.ARCHIVED,
        },
        MetadataStatus.ARCHIVED: set(),
    }

    _VERSION_TRANSITIONS = {
        VersionStatus.ACTIVE: {
            VersionStatus.DEPRECATED,
            VersionStatus.INACTIVE,
        },
        VersionStatus.INACTIVE: {
            VersionStatus.ACTIVE,
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
        ExperimentStatus.DRAFT: {
            ExperimentStatus.RUNNING,
            ExperimentStatus.ARCHIVED,
        },
        ExperimentStatus.RUNNING: {
            ExperimentStatus.PAUSED,
            ExperimentStatus.STOPPED,
            ExperimentStatus.COMPLETED,
            ExperimentStatus.ARCHIVED,
        },
        ExperimentStatus.PAUSED: {
            ExperimentStatus.RUNNING,
            ExperimentStatus.STOPPED,
            ExperimentStatus.COMPLETED,
            ExperimentStatus.ARCHIVED,
        },
        ExperimentStatus.STOPPED: {
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
                f"非法模型状态迁移: {current} -> {target}"
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
                f"非法版本状态迁移: {current} -> {target}"
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

        if (
                target == DeploymentStatus.ACTIVE
                and metadata_status != MetadataStatus.ACTIVE
        ):
            raise InvalidDeploymentStateError(
                f"当前模型状态为 {metadata_status}，不允许上线"
            )

        allowed = cls._DEPLOYMENT_TRANSITIONS.get(current, set())

        if target not in allowed:
            raise InvalidDeploymentStateError(
                f"非法部署状态迁移: {current} -> {target}"
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
            if (
                    current == ExperimentStatus.DRAFT
                    and target == ExperimentStatus.STOPPED
            ):
                raise InvalidExperimentStateError(
                    "草稿状态的实验无法停止"
                )

            if (
                    current == ExperimentStatus.DRAFT
                    and target == ExperimentStatus.PAUSED
            ):
                raise InvalidExperimentStateError(
                    "草稿状态的实验无法暂停"
                )

            raise InvalidExperimentStateError(
                f"非法实验状态迁移: {current} -> {target}"
            )

    @classmethod
    def validate_model_deployable(
            cls,
            status: MetadataStatus,
    ) -> None:
        """校验模型是否允许部署

        参数：
            status: 模型状态

        异常：
            InvalidModelStateError: 不允许部署
        """
        if status == MetadataStatus.ACTIVE:
            return

        if status == MetadataStatus.INACTIVE:
            raise InvalidModelStateError("模型未激活，不允许部署")

        if status == MetadataStatus.DEPRECATED:
            raise InvalidModelStateError("模型已废弃，不允许部署")

        if status == MetadataStatus.ARCHIVED:
            raise InvalidModelStateError("模型已归档，不允许部署")

    @classmethod
    def validate_version_deployable(
            cls,
            status: VersionStatus,
    ) -> None:
        """校验版本是否允许部署

        参数：
            status: 版本状态

        异常：
            InvalidModelStateError: 不允许部署
        """
        if status == VersionStatus.ACTIVE:
            return

        if status == VersionStatus.INACTIVE:
            raise InvalidModelStateError("版本未激活，不允许部署")

        if status == VersionStatus.DEPRECATED:
            raise InvalidModelStateError("版本已废弃，不允许部署")

        if status == VersionStatus.ARCHIVED:
            raise InvalidModelStateError("版本已归档，不允许部署")

    @classmethod
    def validate_enable_deployment(
            cls,
            *,
            current: DeploymentStatus,
            metadata_status: MetadataStatus,
    ) -> None:
        """校验是否允许启用部署

        参数：
            current: 当前部署状态
            metadata_status: 模型元数据状态

        异常：
            InvalidDeploymentStateError: 不允许启用部署
        """
        if current == DeploymentStatus.ACTIVE:
            return

        if metadata_status != MetadataStatus.ACTIVE:
            raise InvalidDeploymentStateError(
                f"当前模型状态为 {metadata_status}，不允许启用部署"
            )

        allowed = cls._DEPLOYMENT_TRANSITIONS.get(current, set())

        if DeploymentStatus.ACTIVE not in allowed:
            raise InvalidDeploymentStateError(
                "非法部署状态迁移: "
                f"{current} -> {DeploymentStatus.ACTIVE}"
            )

    @classmethod
    def validate_disable_deployment(
            cls,
            *,
            current: DeploymentStatus,
    ) -> None:
        """校验是否允许禁用部署

        参数：
            current: 当前部署状态

        异常：
            InvalidDeploymentStateError: 不允许禁用部署
        """
        if current == DeploymentStatus.INACTIVE:
            return

        allowed = cls._DEPLOYMENT_TRANSITIONS.get(current, set())

        if DeploymentStatus.INACTIVE not in allowed:
            raise InvalidDeploymentStateError(
                "非法部署状态迁移: "
                f"{current} -> {DeploymentStatus.INACTIVE}"
            )
