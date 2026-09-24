"""CatBoost 模型加载器测试.

验证 CatBoost 模型通过临时文件加载。

核心功能：
  - test_load_catboost_loads_temporary_model_file:
    验证创建临时文件并加载 CatBoost 模型
"""

from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock
import sys

import pytest

import datamind.models.artifact.handlers.catboost as catboost_module
from datamind.models.artifact.handlers.catboost import load_catboost


def test_load_catboost_loads_temporary_model_file(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试通过临时文件加载 CatBoost 模型."""
    model = SimpleNamespace(
        load_model=Mock()
    )
    model_factory = Mock(
        return_value=model
    )
    received: dict[str, object] = {}

    @contextmanager
    def create_temp_file(
            data: bytes,
            suffix: str,
    ) -> Iterator[str]:
        received["data"] = data
        received["suffix"] = suffix
        yield "temporary-model.cbm"

    library_module = ModuleType("catboost")
    vars(library_module)["CatBoost"] = model_factory
    monkeypatch.setitem(
        sys.modules,
        "catboost",
        library_module,
    )
    monkeypatch.setitem(
        vars(catboost_module),
        "temp_file",
        create_temp_file,
    )

    result = load_catboost(
        b"model data"
    )

    assert result is model
    assert received == {
        "data": b"model data",
        "suffix": ".cbm",
    }
    model_factory.assert_called_once_with()
    model.load_model.assert_called_once_with(
        "temporary-model.cbm"
    )
