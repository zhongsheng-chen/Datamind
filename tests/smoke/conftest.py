"""Docker Smoke 测试公共配置

提供 Docker Smoke 测试使用的模型框架参数。

核心功能：
  - pytest_addoption: 注册模型框架参数
  - framework: 返回测试使用的模型框架
"""

import pytest

from scripts.build_docker import (
    DEFAULT_FRAMEWORK,
    SUPPORTED_FRAMEWORKS,
)


def pytest_addoption(parser: pytest.Parser) -> None:
    """注册 Docker Smoke 测试参数"""
    parser.addoption(
        "--framework",
        choices=sorted(SUPPORTED_FRAMEWORKS),
        default=DEFAULT_FRAMEWORK,
        help="Docker Smoke 测试使用的模型框架",
    )


@pytest.fixture
def framework(request: pytest.FixtureRequest) -> str:
    """返回 Docker Smoke 测试使用的模型框架"""
    return str(request.config.getoption("--framework"))
