"""构建身份校验测试.

验证正式发布使用的构建身份能够被规范化并严格校验。

核心功能：
  - test_release_build_identity_normalizes_values:
    验证构建身份规范化
  - test_release_build_identity_rejects_invalid_values:
    验证拒绝无效的构建身份
"""

import pytest

from build_support.identity import (
    BuildIdentity,
    release_build_identity,
)


BUILD_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BUILD_DATE = "2026-09-21T02:09:32Z"


def test_release_build_identity_normalizes_values() -> None:
    """测试构建身份移除输入两端的空白字符."""
    identity = release_build_identity(
        f"  {BUILD_COMMIT}  ",
        f"  {BUILD_DATE}  ",
    )

    assert identity == BuildIdentity(
        commit=BUILD_COMMIT,
        build_date=BUILD_DATE,
    )


@pytest.mark.parametrize(
    ("commit", "build_date", "message"),
    [
        (" ", BUILD_DATE, "不能是空白字符串"),
        (BUILD_COMMIT[:12], BUILD_DATE, "完整的 40 位 Git 提交哈希"),
        (BUILD_COMMIT, "2026-09-21 02:09:32Z", "UTC RFC 3339"),
    ],
)
def test_release_build_identity_rejects_invalid_values(
    commit: str,
    build_date: str,
    message: str,
) -> None:
    """测试拒绝格式无效的发布构建身份."""
    with pytest.raises(RuntimeError, match=message):
        release_build_identity(commit, build_date)
