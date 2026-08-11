# tests/models/test_guard.py

"""模型状态守卫测试

验证模型、版本、部署和实验的状态迁移与部署约束。

核心功能：
  - test_metadata_transition:
    验证模型元数据状态迁移
  - test_version_transition:
    验证模型版本状态迁移
  - test_deployment_transition:
    验证部署状态迁移与模型状态约束
  - test_experiment_transition:
    验证实验状态迁移
  - test_deployable_status:
    验证模型和版本的可部署状态
  - test_enable_and_disable_deployment:
    验证部署启用与禁用约束
"""

import pytest

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
from datamind.models.guard import ModelGuard


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (MetadataStatus.ACTIVE, MetadataStatus.ACTIVE),
        (MetadataStatus.ACTIVE, MetadataStatus.DEPRECATED),
        (MetadataStatus.INACTIVE, MetadataStatus.ACTIVE),
        (MetadataStatus.INACTIVE, MetadataStatus.DEPRECATED),
        (MetadataStatus.DEPRECATED, MetadataStatus.ARCHIVED),
    ],
)
def test_metadata_transition_allows_valid_transition(
        current: MetadataStatus,
        target: MetadataStatus,
) -> None:
    """测试允许合法的模型元数据状态迁移"""
    ModelGuard.validate_metadata_transition(
        current=current,
        target=target,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (MetadataStatus.ACTIVE, MetadataStatus.ARCHIVED),
        (MetadataStatus.ARCHIVED, MetadataStatus.ACTIVE),
    ],
)
def test_metadata_transition_rejects_invalid_transition(
        current: MetadataStatus,
        target: MetadataStatus,
) -> None:
    """测试拒绝非法的模型元数据状态迁移"""
    with pytest.raises(InvalidModelStateError, match="非法模型状态迁移"):
        ModelGuard.validate_metadata_transition(
            current=current,
            target=target,
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (VersionStatus.ACTIVE, VersionStatus.ACTIVE),
        (VersionStatus.ACTIVE, VersionStatus.DEPRECATED),
        (VersionStatus.INACTIVE, VersionStatus.ACTIVE),
        (VersionStatus.INACTIVE, VersionStatus.DEPRECATED),
        (VersionStatus.DEPRECATED, VersionStatus.ARCHIVED),
    ],
)
def test_version_transition_allows_valid_transition(
        current: VersionStatus,
        target: VersionStatus,
) -> None:
    """测试允许合法的模型版本状态迁移"""
    ModelGuard.validate_version_transition(
        current=current,
        target=target,
    )


def test_version_transition_rejects_invalid_transition() -> None:
    """测试拒绝非法的模型版本状态迁移"""
    with pytest.raises(InvalidModelStateError, match="非法版本状态迁移"):
        ModelGuard.validate_version_transition(
            current=VersionStatus.ARCHIVED,
            target=VersionStatus.ACTIVE,
        )


def test_deployment_transition_allows_valid_transition() -> None:
    """测试允许合法的部署状态迁移"""
    ModelGuard.validate_deployment_transition(
        current=DeploymentStatus.INACTIVE,
        target=DeploymentStatus.ACTIVE,
        metadata_status=MetadataStatus.ACTIVE,
    )
    ModelGuard.validate_deployment_transition(
        current=DeploymentStatus.ACTIVE,
        target=DeploymentStatus.INACTIVE,
        metadata_status=MetadataStatus.INACTIVE,
    )


def test_deployment_transition_allows_same_state() -> None:
    """测试允许部署保持当前状态"""
    ModelGuard.validate_deployment_transition(
        current=DeploymentStatus.ACTIVE,
        target=DeploymentStatus.ACTIVE,
        metadata_status=MetadataStatus.INACTIVE,
    )


def test_deployment_transition_rejects_non_active_model() -> None:
    """测试非活动模型不能启用部署"""
    with pytest.raises(InvalidDeploymentStateError, match="不允许上线"):
        ModelGuard.validate_deployment_transition(
            current=DeploymentStatus.INACTIVE,
            target=DeploymentStatus.ACTIVE,
            metadata_status=MetadataStatus.INACTIVE,
        )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ExperimentStatus.DRAFT, ExperimentStatus.RUNNING),
        (ExperimentStatus.RUNNING, ExperimentStatus.PAUSED),
        (ExperimentStatus.PAUSED, ExperimentStatus.COMPLETED),
        (ExperimentStatus.STOPPED, ExperimentStatus.ARCHIVED),
    ],
)
def test_experiment_transition_allows_valid_transition(
        current: ExperimentStatus,
        target: ExperimentStatus,
) -> None:
    """测试允许合法的实验状态迁移"""
    ModelGuard.validate_experiment_transition(
        current=current,
        target=target,
    )


def test_experiment_transition_rejects_invalid_transition() -> None:
    """测试拒绝非法的实验状态迁移"""
    with pytest.raises(InvalidExperimentStateError, match="非法实验状态迁移"):
        ModelGuard.validate_experiment_transition(
            current=ExperimentStatus.ARCHIVED,
            target=ExperimentStatus.RUNNING,
        )


@pytest.mark.parametrize(
    ("target", "message"),
    [
        (
            ExperimentStatus.STOPPED,
            "草稿状态的实验无法停止",
        ),
        (
            ExperimentStatus.PAUSED,
            "草稿状态的实验无法暂停",
        ),
    ],
)
def test_draft_experiment_transition_uses_actionable_message(
        target: ExperimentStatus,
        message: str,
) -> None:
    """测试草稿实验使用明确的操作错误"""
    with pytest.raises(
            InvalidExperimentStateError,
            match=message,
    ):
        ModelGuard.validate_experiment_transition(
            current=ExperimentStatus.DRAFT,
            target=target,
        )


def test_experiment_transition_allows_same_state() -> None:
    """测试允许实验保持当前状态"""
    ModelGuard.validate_experiment_transition(
        current=ExperimentStatus.RUNNING,
        target=ExperimentStatus.RUNNING,
    )


def test_active_model_and_version_are_deployable() -> None:
    """测试活动模型和版本允许部署"""
    ModelGuard.validate_model_deployable(
        MetadataStatus.ACTIVE
    )
    ModelGuard.validate_version_deployable(
        VersionStatus.ACTIVE
    )


@pytest.mark.parametrize(
    "status",
    [
        MetadataStatus.INACTIVE,
        MetadataStatus.DEPRECATED,
        MetadataStatus.ARCHIVED,
    ],
)
def test_non_active_model_is_not_deployable(
        status: MetadataStatus,
) -> None:
    """测试非活动模型不允许部署"""
    with pytest.raises(InvalidModelStateError, match="不允许部署"):
        ModelGuard.validate_model_deployable(
            status
        )


@pytest.mark.parametrize(
    "status",
    [
        VersionStatus.INACTIVE,
        VersionStatus.DEPRECATED,
        VersionStatus.ARCHIVED,
    ],
)
def test_non_active_version_is_not_deployable(
        status: VersionStatus,
) -> None:
    """测试非活动版本不允许部署"""
    with pytest.raises(InvalidModelStateError, match="不允许部署"):
        ModelGuard.validate_version_deployable(
            status
        )


@pytest.mark.parametrize(
    ("current", "metadata_status"),
    [
        (DeploymentStatus.ACTIVE, MetadataStatus.INACTIVE),
        (DeploymentStatus.INACTIVE, MetadataStatus.ACTIVE),
    ],
)
def test_enable_deployment_allows_valid_state(
        current: DeploymentStatus,
        metadata_status: MetadataStatus,
) -> None:
    """测试允许合法状态的部署启用操作"""
    ModelGuard.validate_enable_deployment(
        current=current,
        metadata_status=metadata_status,
    )


def test_enable_deployment_rejects_non_active_model() -> None:
    """测试非活动模型不能启用部署"""
    with pytest.raises(InvalidDeploymentStateError):
        ModelGuard.validate_enable_deployment(
            current=DeploymentStatus.INACTIVE,
            metadata_status=MetadataStatus.INACTIVE,
        )


@pytest.mark.parametrize(
    "current",
    [
        DeploymentStatus.ACTIVE,
        DeploymentStatus.INACTIVE,
    ],
)
def test_disable_deployment_allows_valid_state(
        current: DeploymentStatus,
) -> None:
    """测试允许活动或已禁用部署执行禁用操作"""
    ModelGuard.validate_disable_deployment(
        current=current,
    )
