# tests/models/artifact/test_loader.py

"""模型产物加载器测试

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
from datamind.models.artifact.loader import ModelArtifactLoader


def test_load_dispatches_to_registered_handler(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试将二进制产物分派给指定框架加载器"""
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
    """测试拒绝不支持的模型框架"""
    with pytest.raises(KeyError, match="不支持的框架"):
        ModelArtifactLoader.load(
            "unsupported_framework",
            b"model data",
        )
