# tests/models/artifact/handlers/test_sklearn.py

"""Sklearn 模型加载器测试

验证 Sklearn 模型二进制数据的反序列化调用。

核心功能：
  - test_load_sklearn_deserializes_bytes:
    验证通过 joblib 加载二进制模型数据
"""

from io import BytesIO
from types import ModuleType
from unittest.mock import Mock
import sys

import pytest

from datamind.models.artifact.handlers.sklearn import load_sklearn


def test_load_sklearn_deserializes_bytes(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通过 joblib 反序列化二进制模型数据"""
    expected = object()
    load = Mock(
        return_value=expected
    )
    joblib_module = ModuleType("joblib")
    vars(joblib_module)["load"] = load
    monkeypatch.setitem(
        sys.modules,
        "joblib",
        joblib_module,
    )

    result = load_sklearn(
        b"model data"
    )

    assert result is expected
    load.assert_called_once()
    assert load.call_args is not None
    stream = load.call_args.args[0]
    assert isinstance(stream, BytesIO)
    assert stream.getvalue() == b"model data"
