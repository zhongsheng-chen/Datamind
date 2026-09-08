"""模型产物注册器测试

验证框架名称规范化、加载器注册和查找。

核心功能：
  - test_register_and_get_handler:
    验证按规范化框架名称注册和获取加载器
  - test_get_handler_rejects_unsupported_framework:
    验证拒绝不支持的框架
"""

from collections.abc import Iterator

import pytest

import datamind.models.artifact.register as register_module
from datamind.models.artifact.register import ModelArtifactRegister, get_handler


@pytest.fixture(autouse=True)
def isolate_registered_handlers() -> Iterator[None]:
    """隔离全局加载器注册表"""
    handlers = vars(register_module)["_HANDLERS"]
    original_handlers = handlers.copy()

    yield

    handlers.clear()
    handlers.update(original_handlers)


def test_register_and_get_handler() -> None:
    """测试按规范化框架名称注册和获取加载器"""
    def handler(data: bytes) -> bytes:
        return data

    registered = ModelArtifactRegister.register(" TEST_FRAMEWORK ")(handler)

    assert registered is handler
    assert get_handler("test_framework") is handler


def test_get_handler_rejects_unsupported_framework() -> None:
    """测试拒绝不支持的框架"""
    with pytest.raises(KeyError, match="不支持的框架"):
        get_handler("unsupported_framework")
