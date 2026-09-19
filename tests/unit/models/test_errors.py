"""模型异常测试

验证模型与实验异常的继承关系和错误信息契约。

核心功能：
  - test_model_error_preserves_message:
    验证模型异常保留错误信息
  - test_experiment_error_preserves_message:
    验证实验异常保留错误信息
  - test_specialized_error_inheritance:
    验证专用异常的继承契约
"""

import pytest

from datamind.models.errors import (
    ArtifactError,
    BackendError,
    DeploymentError,
    DeploymentNotFoundError,
    ExperimentError,
    InvalidDeploymentStateError,
    InvalidExperimentConfigError,
    InvalidExperimentStateError,
    InvalidModelStateError,
    ModelAlreadyExistsError,
    ModelError,
    ModelNotFoundError,
    RuntimeRouteError,
    VersionNotFoundError,
)


MODEL_ERROR_TYPES: list[type[ModelError]] = [
    ModelError,
    ModelNotFoundError,
    ModelAlreadyExistsError,
    VersionNotFoundError,
    InvalidModelStateError,
    DeploymentError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
    RuntimeRouteError,
    BackendError,
    ArtifactError,
]

EXPERIMENT_ERROR_TYPES: list[type[ExperimentError]] = [
    ExperimentError,
    InvalidExperimentStateError,
    InvalidExperimentConfigError,
]


@pytest.mark.parametrize(
    "error_type",
    MODEL_ERROR_TYPES,
)
def test_model_error_preserves_message(
        error_type: type[ModelError],
) -> None:
    """测试模型异常保留错误信息"""
    error = error_type("模型错误")

    assert error.message == "模型错误"
    assert str(error) == "模型错误"


@pytest.mark.parametrize(
    "error_type",
    EXPERIMENT_ERROR_TYPES,
)
def test_experiment_error_preserves_message(
        error_type: type[ExperimentError],
) -> None:
    """测试实验异常保留错误信息"""
    error = error_type("实验错误")

    assert error.message == "实验错误"
    assert str(error) == "实验错误"


@pytest.mark.parametrize(
    ("error_type", "base_type"),
    [
        (DeploymentError, ModelError),
        (DeploymentNotFoundError, DeploymentError),
        (InvalidDeploymentStateError, DeploymentError),
        (InvalidExperimentStateError, ExperimentError),
        (InvalidExperimentConfigError, ExperimentError),
    ],
)
def test_specialized_error_inheritance(
        error_type: type[Exception],
        base_type: type[Exception],
) -> None:
    """测试专用异常继承正确的基础异常"""
    assert issubclass(
        error_type,
        base_type,
    )
