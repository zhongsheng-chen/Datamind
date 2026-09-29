"""Datamind Python 分发包发布验证脚本.

验证用于发布的 Wheel、sdist 及其构建身份，并确认 sdist 可以重新构建
出一致的 Wheel。

运行方式：
  python -m scripts.verify_distributions \
    --dist dist \
    --build-commit 0123456789abcdef0123456789abcdef01234567 \
    --build-date 2026-09-23T00:00:00Z
"""

from __future__ import annotations

import argparse
from pathlib import Path

from build_support.distributions import verify_release_distributions
from build_support.identity import release_build_identity


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_arguments(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    """解析命令行参数.

    参数：
        arguments: 待解析的命令行参数，默认读取当前进程参数

    返回：
        解析后的命令行参数
    """
    parser = argparse.ArgumentParser(description="验证 Datamind Python 分发包")
    parser.add_argument(
        "--dist",
        type=Path,
        metavar="DIRECTORY",
        default=PROJECT_ROOT / "dist",
        help="分发包目录（默认：项目根目录下的 dist）",
    )
    parser.add_argument(
        "--build-commit",
        required=True,
        help="完整的 40 位 Git 提交哈希",
    )
    parser.add_argument(
        "--build-date",
        required=True,
        help="UTC RFC 3339 格式的构建时间",
    )
    return parser.parse_args(arguments)


def main() -> None:
    """执行验证流程."""
    arguments = parse_arguments()
    identity = release_build_identity(
        arguments.build_commit,
        arguments.build_date,
    )
    wheel, sdist = verify_release_distributions(
        arguments.dist.resolve(),
        PROJECT_ROOT,
        identity,
    )
    print(f"Python 分发包验证通过：{wheel.name}, {sdist.name}")


if __name__ == "__main__":
    main()
