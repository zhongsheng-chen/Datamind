"""XGBoost 模型加载器测试.

验证 XGBoost Booster 的创建和二进制模型加载。

核心功能：
  - test_load_xgboost_loads_booster_bytes:
    验证将二进制数据加载到 Booster
"""

from types import ModuleType, SimpleNamespace
from unittest.mock import Mock
import sys

import pytest

from datamind.models.artifact.handlers.xgboost import load_xgboost


def test_load_xgboost_loads_booster_bytes(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试将二进制数据加载到 XGBoost Booster."""
    booster = SimpleNamespace(
        load_model=Mock()
    )
    booster_factory = Mock(
        return_value=booster
    )
    xgboost_module = ModuleType("xgboost")
    vars(xgboost_module)["Booster"] = booster_factory
    monkeypatch.setitem(
        sys.modules,
        "xgboost",
        xgboost_module,
    )

    result = load_xgboost(
        b"model data"
    )

    assert result is booster
    booster_factory.assert_called_once_with()
    booster.load_model.assert_called_once_with(
        bytearray(b"model data")
    )
