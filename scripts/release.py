"""Datamind 正式发布工具.

生成同一次发布共用的元数据，并在上传前校验发布目标。

运行方式：
  python -m scripts.release prepare --tag v0.1.0 --commit SHA
  python -m scripts.release validate-twine-config
  python -m scripts.release validate-dockerhub-config
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

from build_support.docker import load_docker_metadata
from build_support.release import (
    ReleaseMetadata,
    load_release_metadata,
    utc_build_date,
    validate_dockerhub_repository,
    validate_twine_repository,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"


def _write_github_output(path: Path, metadata: ReleaseMetadata) -> None:
    """将发布元数据写入 GitHub Actions 作业输出."""
    values = {
        "tag": metadata.tag,
        "distribution": metadata.distribution,
        "version": metadata.version,
        "wheel_name": metadata.wheel_name,
        "sdist_name": metadata.sdist_name,
        "commit": metadata.commit,
        "build_date": metadata.build_date,
    }
    with path.open("a", encoding="utf-8", newline="\n") as output:
        for name, value in values.items():
            output.write(f"{name}={value}\n")


def prepare_release(arguments: argparse.Namespace) -> None:
    """校验标签并生成本次发布唯一的元数据."""
    metadata = load_release_metadata(
        arguments.pyproject,
        tag=arguments.tag,
        commit=arguments.commit,
        build_date=arguments.build_date or utc_build_date(),
    )

    if arguments.github_output is not None:
        _write_github_output(arguments.github_output, metadata)

    print(json.dumps(asdict(metadata), ensure_ascii=False, sort_keys=True))


def validate_twine_configuration(_arguments: argparse.Namespace) -> None:
    """校验 Twine 发布配置."""
    repository_url = validate_twine_repository(
        os.getenv("TWINE_REPOSITORY_URL"),
        os.getenv("TWINE_USERNAME"),
        os.getenv("TWINE_PASSWORD"),
    )
    print(f"Twine 发布配置有效：{repository_url}")


def validate_dockerhub_configuration(arguments: argparse.Namespace) -> None:
    """校验 Docker Hub 发布配置."""
    metadata = load_docker_metadata(arguments.pyproject)
    repository = validate_dockerhub_repository(
        metadata.repository,
        os.getenv("DOCKERHUB_USERNAME"),
        os.getenv("DOCKERHUB_TOKEN"),
    )
    print(f"Docker Hub 发布配置有效：{repository}")


def parse_arguments(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    """解析命令行参数.

    参数：
        arguments: 待解析的命令行参数，默认读取当前进程参数

    返回：
        解析后的命令行参数
    """
    parser = argparse.ArgumentParser(description="Datamind 正式发布支持工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="生成 Release 元数据")
    prepare.add_argument("--tag", required=True)
    prepare.add_argument(
        "--commit",
        required=True,
        help="完整的 40 位 Git 提交哈希",
    )
    prepare.add_argument(
        "--build-date",
        help="UTC RFC 3339 格式的构建时间（默认：当前时间）",
    )
    prepare.add_argument("--pyproject", type=Path, default=PYPROJECT_FILE)
    prepare.add_argument("--github-output", type=Path)
    prepare.set_defaults(handler=prepare_release)

    python_configuration = subparsers.add_parser(
        "validate-twine-config",
        help="校验 Twine 发布配置",
    )
    python_configuration.set_defaults(handler=validate_twine_configuration)

    docker_configuration = subparsers.add_parser(
        "validate-dockerhub-config",
        help="校验 Docker Hub 发布配置",
    )
    docker_configuration.add_argument(
        "--pyproject",
        type=Path,
        default=PYPROJECT_FILE,
    )
    docker_configuration.set_defaults(handler=validate_dockerhub_configuration)

    return parser.parse_args(arguments)


def main() -> None:
    """执行正式发布支持命令."""
    arguments = parse_arguments()
    arguments.handler(arguments)


if __name__ == "__main__":
    main()
