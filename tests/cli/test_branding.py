"""CLI 品牌展示测试.

验证版本信息使用短 Git 提交哈希，且不改变开发构建标识。

核心功能：
  - test_short_commit_formats_display_value: 验证 Git 提交哈希的展示形式
  - test_get_app_version_uses_short_commit: 验证应用版本使用短 Git 提交哈希
"""

import pytest

from datamind.cli import branding
from datamind.cli.branding import get_app_version, short_commit


COMMIT = "0123456789abcdef0123456789abcdef01234567"


@pytest.mark.parametrize(
    ("commit", "length", "expected"),
    [
        ("dev", 8, "dev"),
        (COMMIT, 8, "01234567"),
        (COMMIT, 12, "0123456789ab"),
    ],
)
def test_short_commit_formats_display_value(
        commit: str,
        length: int,
        expected: str,
) -> None:
    """测试提交哈希转换为用户界面展示形式."""
    assert short_commit(commit, length) == expected


def test_get_app_version_uses_short_commit(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试应用版本仅展示短提交哈希."""
    monkeypatch.setitem(vars(branding), "BUILD_COMMIT", COMMIT)
    monkeypatch.setitem(
        vars(branding),
        "version",
        lambda _distribution: "0.1.0",
    )

    assert get_app_version() == "0.1.0 (01234567)"
