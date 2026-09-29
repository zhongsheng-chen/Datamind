"""模型制品格式测试.

验证框架格式映射、客户端能力声明和模型文件扩展名校验。

核心功能：
  - test_artifact_extension_capabilities_cover_supported_frameworks:
    验证格式能力覆盖所有支持框架
  - test_validate_artifact_extension_accepts_supported_formats:
    验证接受各框架支持的文件扩展名
  - test_validate_artifact_extension_rejects_unsupported_format:
    验证拒绝所选框架不支持的文件扩展名
  - test_validate_artifact_extension_rejects_missing_extension:
    验证拒绝缺少扩展名的模型文件
"""

from pathlib import Path

import pytest

from datamind.constants.framework import Framework
from datamind.models.artifact.formats import (
    SUPPORTED_ARTIFACT_EXTENSIONS,
    artifact_extension_capabilities,
    validate_artifact_extension,
)
from datamind.models.errors import ArtifactError


def test_artifact_extension_capabilities_cover_supported_frameworks() -> None:
    """测试客户端能力与后端格式支持来自同一映射."""
    assert artifact_extension_capabilities() == {
        "sklearn": [".pkl", ".pickle", ".joblib"],
        "xgboost": [".json", ".ubj", ".model"],
        "lightgbm": [".txt", ".model"],
        "catboost": [".cbm"],
    }
    assert set(SUPPORTED_ARTIFACT_EXTENSIONS) == set(Framework)


@pytest.mark.parametrize(
    "framework, filename",
    [
        (Framework.SKLEARN, "model.JOBLIB"),
        (Framework.XGBOOST, "model.ubj"),
        (Framework.LIGHTGBM, "model.txt"),
        (Framework.CATBOOST, "model.cbm"),
    ],
)
def test_validate_artifact_extension_accepts_supported_formats(
        framework: Framework,
        filename: str,
) -> None:
    """测试格式校验接受各框架支持的后缀且忽略大小写."""
    validate_artifact_extension(
        framework=framework,
        path=Path(filename),
    )


def test_validate_artifact_extension_rejects_unsupported_format() -> None:
    """测试格式校验返回所选框架的支持格式."""
    with pytest.raises(
            ArtifactError,
            match=(
                "框架 sklearn 不支持模型文件后缀 .onnx；"
                "支持格式：.pkl、.pickle、.joblib"
            ),
    ):
        validate_artifact_extension(
            framework=Framework.SKLEARN,
            path="model.onnx",
        )


def test_validate_artifact_extension_rejects_missing_extension() -> None:
    """测试格式校验清晰提示模型文件缺少扩展名."""
    with pytest.raises(
            ArtifactError,
            match=(
                "框架 catboost 的模型文件缺少扩展名；"
                "支持格式：.cbm"
            ),
    ):
        validate_artifact_extension(
            framework=Framework.CATBOOST,
            path="model",
        )
