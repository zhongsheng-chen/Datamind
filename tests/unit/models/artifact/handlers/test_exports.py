"""模型产物加载器实现包公共导出测试

验证各框架加载器模块均已公开并完成注册。

核心功能：
  - test_handler_exports_expected_public_api:
    验证 __all__ 包含完整且准确的加载器模块
  - test_all_declared_exports_are_available:
    验证声明的模块均可从包级访问
"""

from collections.abc import Callable
from typing import Any

import pytest

import datamind.models.artifact.handlers as handlers
from datamind.constants.framework import Framework
from datamind.models.artifact.register import get_handler


EXPECTED_EXPORTS = {
    "catboost",
    "lightgbm",
    "sklearn",
    "xgboost",
}


def test_handler_exports_expected_public_api() -> None:
    """测试加载器实现包公开完整且准确的 API"""
    assert set(handlers.__all__) == EXPECTED_EXPORTS
    assert len(handlers.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的模块均可从包级访问"""
    for name in handlers.__all__:
        assert hasattr(handlers, name), name


@pytest.mark.parametrize(
    ("framework", "handler"),
    [
        (Framework.CATBOOST, handlers.catboost.load_catboost),
        (Framework.LIGHTGBM, handlers.lightgbm.load_lightgbm),
        (Framework.SKLEARN, handlers.sklearn.load_sklearn),
        (Framework.XGBOOST, handlers.xgboost.load_xgboost),
    ],
)
def test_handler_modules_are_registered(
        framework: Framework,
        handler: Callable[[bytes], Any],
) -> None:
    """测试各框架加载器均已完成注册"""
    assert get_handler(
        str(framework)
    ) is handler
