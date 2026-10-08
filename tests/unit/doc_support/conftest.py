"""参考文档测试共用夹具.

提供源码模块加载及测试结束后的模块注册清理。

核心功能：
  - load_source: 加载临时源码供源码提取测试使用
"""

from collections.abc import Callable
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


@pytest.fixture
def load_source(monkeypatch: pytest.MonkeyPatch) -> Callable[[Path], ModuleType]:
    """提供临时源码模块加载函数."""

    def load(path: Path) -> ModuleType:
        """加载并注册临时源码模块."""
        name = f"docs_test_{path.stem}"
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None
        assert spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    return load
