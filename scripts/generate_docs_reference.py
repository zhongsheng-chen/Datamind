"""Datamind 参考文档生成工具.

根据源码定义生成参考文档。

运行方式：
  python -m scripts.generate_docs_reference
  python -m scripts.generate_docs_reference --check
"""

from __future__ import annotations

import argparse
from pathlib import Path

from doc_support.api import api_pages
from doc_support.cli import cli_pages
from doc_support.common import ROOT
from doc_support.config import config_pages


def parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数.

    参数：
        arguments: 待解析的命令行参数，默认读取当前进程参数

    返回：
        解析后的命令行参数
    """
    parser = argparse.ArgumentParser(description="生成 Datamind 参考文档")
    parser.add_argument(
        "--check", action="store_true", help="检查参考文档是否一致，不写入文件"
    )
    return parser.parse_args(arguments)


def synchronize_pages(pages: dict[Path, str], *, check: bool) -> list[Path]:
    """检查参考页差异，并在生成模式下写入变更.

    参数：
        pages: 参考页路径及生成内容
        check: 是否仅检查而不写入文件

    返回：
        内容不一致或尚不存在的参考页路径
    """
    changed = []
    for path, text in pages.items():
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        changed.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    return changed


def main() -> None:
    """执行参考文档生成或检查流程."""
    arguments = parse_arguments()
    pages = {**cli_pages(), **config_pages(), **api_pages()}
    changed = synchronize_pages(pages, check=arguments.check)
    if arguments.check and changed:
        names = ", ".join(path.relative_to(ROOT).as_posix() for path in changed)
        raise SystemExit("Reference drift: " + names)
    action = "checked" if arguments.check else "generated"
    print(f"{len(pages)} reference pages {action}")


if __name__ == "__main__":
    main()
