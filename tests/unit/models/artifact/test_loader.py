"""模型产物加载器测试.

验证模型产物按框架分派到已注册加载器。

核心功能：
  - test_load_dispatches_to_registered_handler:
    验证加载请求与二进制数据正确分派
  - test_load_rejects_unsupported_framework:
    验证拒绝不支持的模型框架
"""

from unittest.mock import Mock

import pytest

import datamind.models.artifact.loader as loader_module
from datamind.core.inference.errors import FrameworkDependencyError
from datamind.models.artifact.loader import ModelArtifactLoader


def test_load_dispatches_to_registered_handler(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试将二进制产物分派给指定框架加载器."""
    expected = object()
    handler = Mock(
        return_value=expected
    )

    def get_handler(framework: str):
        assert framework == "custom"
        return handler

    monkeypatch.setitem(
        vars(loader_module),
        "get_handler",
        get_handler,
    )

    result = ModelArtifactLoader.load(
        "custom",
        b"model data",
    )

    assert result is expected
    handler.assert_called_once_with(
        b"model data"
    )


def test_load_rejects_unsupported_framework() -> None:
    """测试拒绝不支持的模型框架."""
    with pytest.raises(KeyError, match="不支持的框架"):
        ModelArtifactLoader.load(
            "unsupported_framework",
            b"model data",
        )


def test_load_reports_missing_framework_dependency(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试模型加载缺少可选依赖时返回明确安装建议."""
    def missing_dependency(_data: bytes):
        raise ModuleNotFoundError(
            "No module named 'joblib'",
            name="joblib",
        )

    monkeypatch.setitem(
        vars(loader_module),
        "get_handler",
        lambda _framework: missing_dependency,
    )

    with pytest.raises(
            FrameworkDependencyError,
            match=r"sklearn.*joblib.*datamind\[sklearn\] 可选依赖",
    ) as exc_info:
        ModelArtifactLoader.load("sklearn", b"model data")

    assert exc_info.value.framework == "sklearn"
    assert exc_info.value.dependency == "joblib"
