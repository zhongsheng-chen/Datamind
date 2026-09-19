"""Datamind Docker 镜像构建工具

加载构建元数据并构建 Docker 镜像。

运行方式：
  DATAMIND_BUILD_COMMIT="$(git rev-parse HEAD)" \
  DATAMIND_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  python -m scripts.build_docker
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.utils import formataddr
import os
from pathlib import Path
import subprocess
import tomllib
from typing import Any

from build_support.identity import release_build_identity


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_FILE = PROJECT_ROOT / "pyproject.toml"
DOCKERFILE = PROJECT_ROOT / "docker" / "Dockerfile"
SUPPORTED_FRAMEWORKS = frozenset({
    "sklearn",
    "xgboost",
    "lightgbm",
    "catboost",
    "full",
})
DEFAULT_FRAMEWORK = "full"


@dataclass(frozen=True)
class DockerMetadata:
    """汇总 Docker 镜像使用的项目与 OCI 元数据。"""

    repository: str
    title: str
    description: str
    version: str
    authors: str
    vendor: str
    licenses: str
    source: str
    url: str
    documentation: str

    def build_arguments(self) -> dict[str, str]:
        """生成 Dockerfile 使用的项目元数据参数。

        返回：
            Docker 构建参数名称及其正式元数据值
        """
        return {
            "DATAMIND_TITLE": self.title,
            "DATAMIND_DESCRIPTION": self.description,
            "DATAMIND_VERSION": self.version,
            "DATAMIND_AUTHORS": self.authors,
            "DATAMIND_VENDOR": self.vendor,
            "DATAMIND_LICENSES": self.licenses,
            "DATAMIND_SOURCE_URL": self.source,
            "DATAMIND_PROJECT_URL": self.url,
            "DATAMIND_DOCUMENTATION_URL": self.documentation,
        }


def _required_mapping(value: object, location: str) -> dict[str, Any]:
    """读取必填的 TOML 映射。

    参数：
        value: 待检查的 TOML 值
        location: 值在 pyproject.toml 中的位置

    返回：
        经过类型检查的 TOML 映射

    异常：
        RuntimeError: 指定位置不存在或不是映射
    """
    if not isinstance(value, dict):
        raise RuntimeError(f"pyproject.toml 缺少有效的 {location}")

    return value


def _required_string(mapping: dict[str, Any], key: str, location: str) -> str:
    """读取 TOML 映射中的必填字符串。

    参数：
        mapping: 包含目标值的 TOML 映射
        key: 目标字段名称
        location: 映射在 pyproject.toml 中的位置

    返回：
        去除首尾空白后的字段值

    异常：
        RuntimeError: 字段不存在、不是字符串或仅包含空白字符
    """
    value = mapping.get(key)

    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"pyproject.toml 缺少有效的 {location}.{key}")

    return value.strip()


def _project_authors(project: dict[str, Any]) -> str:
    """生成 OCI authors 元数据。

    参数：
        project: pyproject.toml 中的 project 映射

    返回：
        由 PEP 621 作者列表生成的 OCI authors 值

    异常：
        RuntimeError: 作者列表或作者姓名、邮箱配置无效
    """
    configured = project.get("authors")

    if not isinstance(configured, list) or not configured:
        raise RuntimeError("pyproject.toml 缺少有效的 project.authors")

    authors: list[str] = []

    for index, author in enumerate(configured):
        entry = _required_mapping(author, f"project.authors[{index}]")
        name = _required_string(entry, "name", f"project.authors[{index}]")
        email = _required_string(entry, "email", f"project.authors[{index}]")
        authors.append(formataddr((name, email)))

    return ", ".join(authors)


def load_docker_metadata(path: Path = PYPROJECT_FILE) -> DockerMetadata:
    """加载 Docker 镜像使用的项目元数据。

    参数：
        path: pyproject.toml 文件路径

    返回：
        由项目正式元数据构造的 Docker 元数据

    异常：
        RuntimeError: 必填的项目或 OCI 元数据缺失或格式无效
    """
    with path.open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    project = _required_mapping(document.get("project"), "project")
    urls = _required_mapping(project.get("urls"), "project.urls")
    tool = _required_mapping(document.get("tool"), "tool")
    datamind = _required_mapping(tool.get("datamind"), "tool.datamind")
    oci = _required_mapping(datamind.get("oci"), "tool.datamind.oci")
    docker = _required_mapping(
        datamind.get("docker"),
        "tool.datamind.docker",
    )

    return DockerMetadata(
        repository=_required_string(
            docker,
            "repository",
            "tool.datamind.docker",
        ),
        title=_required_string(oci, "title", "tool.datamind.oci"),
        description=_required_string(project, "description", "project"),
        version=_required_string(project, "version", "project"),
        authors=_project_authors(project),
        vendor=_required_string(oci, "vendor", "tool.datamind.oci"),
        licenses=_required_string(project, "license", "project"),
        source=_required_string(urls, "Source", "project.urls"),
        url=_required_string(urls, "Homepage", "project.urls"),
        documentation=_required_string(
            urls,
            "Documentation",
            "project.urls",
        ),
    )


def resolve_build_identity(
    commit: str | None,
    build_date: str | None,
) -> tuple[str, str]:
    """解析 Docker 镜像的构建身份。

    参数：
        commit: 源码对应的 40 位 Git 提交哈希
        build_date: 镜像构建时间，采用 UTC RFC 3339 格式

    返回：
        传给 Dockerfile 的 Commit 与 Build Date

    异常：
        RuntimeError: 构建身份不完整或格式无效
    """
    resolved_commit = (
        commit if commit is not None else os.getenv("DATAMIND_BUILD_COMMIT")
    )
    resolved_date = (
        build_date if build_date is not None else os.getenv("DATAMIND_BUILD_DATE")
    )

    if resolved_commit is None or resolved_date is None:
        raise RuntimeError(
            "构建 Docker Image 必须同时设置 "
            "DATAMIND_BUILD_COMMIT 与 DATAMIND_BUILD_DATE"
        )

    identity = release_build_identity(resolved_commit, resolved_date)
    assert identity.build_date is not None
    return identity.commit, identity.build_date


def default_image_tag(
        repository: str,
        version: str,
        framework: str,
) -> str:
    """生成 Docker 镜像的默认标签。"""
    if framework not in SUPPORTED_FRAMEWORKS:
        raise ValueError(f"不支持的模型框架: {framework}")

    if framework == "full":
        return f"{repository}:{version}"

    return f"{repository}:{version}-{framework}"


def parse_framework(value: str) -> str:
    """解析并校验镜像支持的模型框架。"""
    if value not in SUPPORTED_FRAMEWORKS:
        supported = ", ".join(sorted(SUPPORTED_FRAMEWORKS))
        raise argparse.ArgumentTypeError(
            f"不支持的模型框架: {value}；可选值：{supported}"
        )

    return value


def docker_build_command(
    metadata: DockerMetadata,
    *,
    tag: str,
    framework: str,
    commit: str,
    build_date: str,
    pull: bool = False,
    no_cache: bool = False,
    pip_index_url: str | None = None,
) -> list[str]:
    """生成 Docker 镜像构建命令。

    参数：
        metadata: 从 pyproject.toml 加载的项目与 OCI 元数据
        tag: 最终 Docker 镜像标签
        framework: 镜像支持的模型框架，full 表示支持全部框架
        commit: 源码对应的 40 位 Git 提交哈希
        build_date: 镜像构建时间，采用 UTC RFC 3339 格式
        pull: 是否在构建前拉取基础镜像
        no_cache: 是否禁用 Docker 构建缓存
        pip_index_url: Python 包索引地址

    返回：
        可直接交给子进程执行的 Docker 命令及参数
    """
    command = [
        "docker",
        "build",
        "--file",
        str(DOCKERFILE),
        "--tag",
        tag,
    ]

    if pull:
        command.append("--pull")
    if no_cache:
        command.append("--no-cache")

    build_arguments = metadata.build_arguments()
    build_arguments.update(
        {
            "DATAMIND_BUILD_COMMIT": commit,
            "DATAMIND_BUILD_DATE": build_date,
            "DATAMIND_PYTHON_EXTRA": framework,
        }
    )

    if pip_index_url:
        build_arguments["PIP_INDEX_URL"] = pip_index_url

    for name, value in build_arguments.items():
        command.extend(["--build-arg", f"{name}={value}"])

    command.append(str(PROJECT_ROOT))
    return command


def parse_arguments(arguments: list[str] | None = None) -> argparse.Namespace:
    """解析命令行提供的 Docker 镜像构建参数。

    返回：
        解析后的命令行参数
    """
    parser = argparse.ArgumentParser(description="构建 Datamind Docker 镜像")
    parser.add_argument(
        "--tag",
        help="镜像标签",
    )
    parser.add_argument(
        "--framework",
        type=parse_framework,
        metavar="FRAMEWORK",
        default=DEFAULT_FRAMEWORK,
        help="镜像支持的模型框架，默认为 full",
    )
    parser.add_argument(
        "--build-commit",
        help="构建时 Git 提交 SHA 值（40 位）",
    )
    parser.add_argument(
        "--build-date",
        help="构建时间（RFC 3339，UTC）",
    )
    parser.add_argument("--pull", action="store_true", help="构建前拉取基础镜像")
    parser.add_argument("--no-cache", action="store_true", help="禁用构建缓存")
    return parser.parse_args(arguments)


def main() -> None:
    """加载构建元数据并构建 Datamind 运行时镜像。"""
    arguments = parse_arguments()
    metadata = load_docker_metadata()
    commit, build_date = resolve_build_identity(
        arguments.build_commit,
        arguments.build_date,
    )
    tag = arguments.tag or default_image_tag(
        metadata.repository,
        metadata.version,
        arguments.framework,
    )
    command = docker_build_command(
        metadata,
        tag=tag,
        framework=arguments.framework,
        commit=commit,
        build_date=build_date,
        pull=arguments.pull,
        no_cache=arguments.no_cache,
        pip_index_url=os.getenv("PIP_INDEX_URL"),
    )

    subprocess.run(command, cwd=PROJECT_ROOT, check=True)


if __name__ == "__main__":
    main()
