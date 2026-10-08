"""参考文档生成入口测试.

验证生成模式选择和参考页文件同步行为。

核心功能：
  - test_parse_arguments_selects_generation_mode:
    命令行默认生成文档，检查模式通过显式参数启用
  - test_synchronize_pages_handles_changed_missing_and_current_files:
    检查模式保留文件，生成模式仅写入变化及缺失的页面
"""

from pathlib import Path

import pytest

from scripts.generate_docs_reference import parse_arguments, synchronize_pages


@pytest.mark.parametrize("arguments, check", [([], False), (["--check"], True)])
def test_parse_arguments_selects_generation_mode(
    arguments: list[str], check: bool
) -> None:
    """命令行默认生成文档，检查模式通过显式参数启用."""
    assert parse_arguments(arguments).check is check


@pytest.mark.parametrize("check", [True, False])
def test_synchronize_pages_handles_changed_missing_and_current_files(
    tmp_path: Path, check: bool
) -> None:
    """检查模式保留文件，生成模式仅写入变化及缺失的页面."""
    current = tmp_path / "current.md"
    changed = tmp_path / "changed.md"
    missing = tmp_path / "nested" / "missing.md"
    current.write_text("current\n", encoding="utf-8")
    changed.write_text("old\n", encoding="utf-8")
    current_mtime = current.stat().st_mtime_ns
    pages = {current: "current\n", changed: "new\n", missing: "created\n"}

    assert synchronize_pages(pages, check=check) == [changed, missing]
    assert current.stat().st_mtime_ns == current_mtime
    if check:
        assert changed.read_text(encoding="utf-8") == "old\n"
        assert not missing.parent.exists()
    else:
        assert changed.read_text(encoding="utf-8") == "new\n"
        assert missing.read_text(encoding="utf-8") == "created\n"
        assert synchronize_pages(pages, check=True) == []
