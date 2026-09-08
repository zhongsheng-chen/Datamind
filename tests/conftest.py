"""Pytest 全局测试配置

提供所有测试共用的 Fixture。

核心功能：
  - reset_context: 在每个测试前后清理请求上下文
"""

from collections.abc import Iterator

import pytest

from datamind.context import clear_context


@pytest.fixture(autouse=True)
def reset_context() -> Iterator[None]:
    """在每个测试前后清理请求上下文"""
    clear_context()

    yield

    clear_context()
