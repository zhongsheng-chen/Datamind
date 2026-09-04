# tests/runtime/test_backend.py

"""BentoML 模型后端测试

验证框架后端选择以及模型保存和加载委托行为。

核心功能：
  - test_backend_resolves_supported_framework:
    验证解析受支持的框架后端
  - test_backend_rejects_unsupported_framework:
    验证拒绝不受支持的框架
  - test_save_delegates_to_framework_backend:
    验证模型保存委托给框架后端
  - test_load_delegates_to_framework_backend:
    验证模型加载委托给框架后端
"""

from unittest.mock import MagicMock

import pytest

import datamind.runtime.backend as backend_module
from datamind.runtime.backend import BentoBackend


@pytest.mark.parametrize(
    "framework",
    [
        "sklearn",
        "xgboost",
        "lightgbm",
        "catboost",
    ],
)
def test_backend_resolves_supported_framework(
        framework: str,
) -> None:
    """测试解析受支持的 BentoML 框架后端"""
    assert BentoBackend._get_backend(
        framework
    ) is backend_module.FRAMEWORK_TO_BENTOML[framework]


def test_backend_rejects_unsupported_framework() -> None:
    """测试拒绝不受支持的模型框架"""
    with pytest.raises(
            KeyError,
            match="不支持的框架: onnx",
    ):
        BentoBackend._get_backend("onnx")


def test_save_delegates_to_framework_backend(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试保存模型委托给对应框架后端"""
    framework_backend = MagicMock()
    expected = object()
    framework_backend.save_model.return_value = expected
    monkeypatch.setitem(
        backend_module.FRAMEWORK_TO_BENTOML,
        "sklearn",
        framework_backend,
    )
    model = object()

    result = BentoBackend().save(
        name="scorecard",
        framework="sklearn",
        model=model,
        signatures={"predict": {"batchable": True}},
    )

    assert result is expected
    framework_backend.save_model.assert_called_once_with(
        name="scorecard",
        model=model,
        signatures={"predict": {"batchable": True}},
    )


def test_load_delegates_to_framework_backend(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试加载模型委托给对应框架后端"""
    framework_backend = MagicMock()
    expected = object()
    framework_backend.load_model.return_value = expected
    monkeypatch.setitem(
        backend_module.FRAMEWORK_TO_BENTOML,
        "sklearn",
        framework_backend,
    )

    result = BentoBackend().load(
        framework="sklearn",
        tag="scorecard:test",
    )

    assert result is expected
    framework_backend.load_model.assert_called_once_with(
        "scorecard:test"
    )
