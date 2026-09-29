"""存储大小常量测试.

验证 KB、MB、GB 的数值、换算关系和配置计算行为。

核心功能：
  - test_size_constants_are_integers:
    验证存储大小常量均为整数
  - test_kilobyte_value:
    验证 KB 的字节数
  - test_megabyte_value:
    验证 MB 的数值和换算关系
  - test_gigabyte_value:
    验证 GB 的数值和换算关系
  - test_size_constants_have_binary_relationship:
    验证相邻存储单位按 1024 换算
  - test_size_constants_support_configuration_calculation:
    验证常量可用于配置值计算
"""

from datamind.constants.size import (
    GB,
    KB,
    MB,
)


def test_size_constants_are_integers() -> None:
    """测试存储大小常量均为整数."""
    assert isinstance(
        KB,
        int,
    )
    assert isinstance(
        MB,
        int,
    )
    assert isinstance(
        GB,
        int,
    )


def test_kilobyte_value() -> None:
    """测试 KB 等于 1024 字节."""
    assert KB == 1024


def test_megabyte_value() -> None:
    """测试 MB 等于 1024 KB."""
    assert MB == 1024 * KB
    assert MB == 1_048_576


def test_gigabyte_value() -> None:
    """测试 GB 等于 1024 MB."""
    assert GB == 1024 * MB
    assert GB == 1_073_741_824


def test_size_constants_have_binary_relationship() -> None:
    """测试相邻存储单位之间按 1024 换算."""
    assert MB // KB == 1024
    assert GB // MB == 1024
    assert GB // KB == 1024 * 1024


def test_size_constants_support_configuration_calculation() -> None:
    """测试存储大小常量可用于配置值计算."""
    max_file_size = 200 * MB
    cache_size = 2 * GB

    assert max_file_size == 209_715_200
    assert cache_size == 2_147_483_648
