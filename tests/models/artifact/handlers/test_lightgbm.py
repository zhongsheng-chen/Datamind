"""LightGBM 模型加载器测试

验证 LightGBM Booster 通过文本模型数据创建。

核心功能：
  - test_load_lightgbm_decodes_model_text:
    验证解码二进制数据并创建 Booster
"""

from types import ModuleType
from unittest.mock import Mock
import sys

import pytest

from datamind.models.artifact.handlers.lightgbm import load_lightgbm


def test_load_lightgbm_decodes_model_text(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试解码模型文本并创建 LightGBM Booster"""
    expected = object()
    booster_factory = Mock(
        return_value=expected
    )
    lightgbm_module = ModuleType("lightgbm")
    vars(lightgbm_module)["Booster"] = booster_factory
    monkeypatch.setitem(
        sys.modules,
        "lightgbm",
        lightgbm_module,
    )

    result = load_lightgbm(
        "model text".encode("utf-8")
    )

    assert result is expected
    booster_factory.assert_called_once_with(
        model_str="model text"
    )
