"""Datamind Docker 镜像构建工具.

加载构建元数据并构建 Docker 镜像。

运行方式：
  DATAMIND_BUILD_COMMIT="$(git rev-parse HEAD)" \
  DATAMIND_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  python -m scripts.build_docker
"""

from __future__ import annotations

import argparse
import os
import subprocess

from build_support.docker import (
    DEFAULT_FRAMEWORK,
    PROJECT_ROOT,
    SUPPORTED_FRAMEWORKS,
    docker_build_command,
    load_docker_metadata,
)
from build_support.identity import release_build_identity


def parse_framework(value: str) -> str:
    """解析并校验镜像支持的模型框架."""
    if value not in SUPPORTED_FRAMEWORKS:
        supported = ", ".join(sorted(SUPPORTED_FRAMEWORKS))
        raise argparse.ArgumentTypeError(
            f"不支持的模型框架: {value}；可选值：{supported}"
        )

    return value


def parse_arguments(
    arguments: list[str] | None = None,
) -> argparse.Namespace:
    """解析命令行参数.

    参数：
        arguments: 待解析的命令行参数，默认读取当前进程参数

    返回：
        解析后的命令行参数
    """
    parser = argparse.ArgumentParser(description="构建 Datamind Docker 镜像")
    destination = parser.add_mutually_exclusive_group()
    destination.add_argument(
        "--image",
        help="镜像引用",
    )
    destination.add_argument(
        "--repository",
        help="镜像仓库",
    )
    parser.add_argument(
        "--framework",
        type=parse_framework,
        metavar="FRAMEWORK",
        default=DEFAULT_FRAMEWORK,
        help="模型框架（默认：%(default)s）",
    )
    parser.add_argument(
        "--build-commit",
        default=os.getenv("DATAMIND_BUILD_COMMIT"),
        help="完整的 40 位 Git 提交哈希",
    )
    parser.add_argument(
        "--build-date",
        default=os.getenv("DATAMIND_BUILD_DATE"),
        help="UTC RFC 3339 格式的构建时间",
    )
    parser.add_argument("--pull", action="store_true", help="构建前拉取基础镜像")
    parser.add_argument("--no-cache", action="store_true", help="禁用构建缓存")
    parser.add_argument(
        "--print",
        action="store_true",
        help="输出镜像引用，不执行构建",
    )
    return parser.parse_args(arguments)


def resolve_image(
    *,
    image: str | None,
    repository: str,
    version: str,
    framework: str,
) -> str:
    """解析 Docker 构建使用的镜像引用.

    参数：
        image: 命令行显式指定的镜像引用
        repository: 不含协议与标签的 Docker 镜像仓库
        version: pyproject.toml 中声明的项目版本
        framework: 镜像支持的模型框架

    返回：
        完整 Docker 镜像引用

    异常：
        ValueError: 镜像仓库或模型框架无效
    """
    if image:
        return image

    repository = repository.strip().rstrip("/")
    if not repository or "://" in repository:
        raise ValueError("Docker 镜像仓库必须是不含协议的有效仓库路径")

    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"不支持的模型框架: {framework}")

    if framework == "full":
        return f"{repository}:{version}"

    return f"{repository}:{version}-{framework}"


def main() -> None:
    """执行镜像构建流程."""
    arguments = parse_arguments()
    metadata = load_docker_metadata()
    image = resolve_image(
        image=arguments.image,
        repository=arguments.repository or metadata.repository,
        version=metadata.version,
        framework=arguments.framework,
    )

    if arguments.print:
        print(image)
        return

    if arguments.build_commit is None or arguments.build_date is None:
        raise RuntimeError(
            "构建 Docker 镜像必须同时设置 "
            "DATAMIND_BUILD_COMMIT 与 DATAMIND_BUILD_DATE"
        )

    identity = release_build_identity(
        arguments.build_commit,
        arguments.build_date,
    )
    command = docker_build_command(
        metadata,
        image=image,
        framework=arguments.framework,
        commit=identity.commit,
        build_date=identity.build_date,
        pull=arguments.pull,
        no_cache=arguments.no_cache,
        pip_index_url=os.getenv("PIP_INDEX_URL"),
    )

    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


if __name__ == "__main__":
    main()
