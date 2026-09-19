"""模型版本常量测试

验证模型版本正则表达式接受和拒绝的版本格式。

核心功能：
  - test_model_version_pattern_accepts_semantic_versions:
    验证接受合法的语义化版本
  - test_model_version_pattern_rejects_invalid_versions:
    验证拒绝不合法的版本格式
"""

import re

import pytest

from datamind.constants.version import (
    SUPPORTED_MODEL_VERSION_PATTERN,
)


@pytest.mark.parametrize(
    "version",
    [
        "0.0.1",
        "1.0.0",
        "2.1.0-rc.1",
        "2.1.0+build.5",
        "2.1.0-rc.1+build.5",
    ],
)
def test_model_version_pattern_accepts_semantic_versions(
        version: str,
) -> None:
    """测试接受语义化模型版本"""
    assert re.fullmatch(
        SUPPORTED_MODEL_VERSION_PATTERN,
        version,
    )


@pytest.mark.parametrize(
    "version",
    [
        "1",
        "1.0",
        "01.0.0",
        "1.0.0-01",
        "latest",
        "",
    ],
)
def test_model_version_pattern_rejects_invalid_versions(
        version: str,
) -> None:
    """测试拒绝非语义化模型版本"""
    assert re.fullmatch(
        SUPPORTED_MODEL_VERSION_PATTERN,
        version,
    ) is None
