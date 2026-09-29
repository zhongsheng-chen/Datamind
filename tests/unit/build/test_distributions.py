"""Python 分发包测试.

验证 distribution name、版本与构建文件名保持一致。

核心功能：
  - test_python_distribution_generates_normalized_filenames:
    验证 Python Distribution 生成规范化的 Wheel 与 sdist 文件名
"""

import pytest

from build_support.distributions import PythonDistribution


@pytest.mark.parametrize(
    ("name", "filename_stem"),
    [
        ("example-package", "example_package"),
        ("Example.Package", "example_package"),
        ("example_package", "example_package"),
    ],
)
def test_python_distribution_generates_normalized_filenames(
    name: str,
    filename_stem: str,
) -> None:
    """测试 Python Distribution 生成规范化的分发包文件名."""
    distribution = PythonDistribution(name=name, version="1.2.3")

    assert distribution.name == name
    assert distribution.version == "1.2.3"
    assert distribution.filename_stem == filename_stem
    assert distribution.wheel_name == (
        f"{filename_stem}-1.2.3-py3-none-any.whl"
    )
    assert distribution.sdist_name == f"{filename_stem}-1.2.3.tar.gz"
