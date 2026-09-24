"""Datamind Docker 镜像构建支持.

加载项目与 OCI 元数据并生成 Docker 构建命令。

核心功能：
  - DockerMetadata: 记录 Docker 镜像使用的项目与 OCI 元数据
  - load_docker_metadata: 从 pyproject.toml 加载 Docker 镜像元数据
  - docker_build_command: 生成 Docker 镜像构建命令

使用示例：
  from build_support.docker import (
      docker_build_command,
      load_docker_metadata,
  )

  metadata = load_docker_metadata()
  command = docker_build_command(
      metadata,
      image="docker.io/zhongshengchen/datamind:0.1.0",
      framework="full",
      commit="0123456789abcdef0123456789abcdef01234567",
      build_date="2026-09-23T00:00:00Z",
  )
"""

from __future__ import annotations

from dataclasses import dataclass
from email.utils import formataddr
from pathlib import Path
import tomllib
from typing import Any


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
    """记录 Docker 镜像使用的项目与 OCI 元数据.

    属性：
        repository: 不含标签的镜像仓库
        title: 镜像标题
        description: 镜像描述
        version: 项目版本
        authors: 镜像作者
        vendor: 镜像供应商
        licenses: 项目许可证标识
        source: 项目源码地址
        url: 项目主页地址
        documentation: 项目文档地址
    """

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
        """生成 Dockerfile 使用的项目元数据参数.

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
    """读取必填的 TOML 映射.

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
    """读取 TOML 映射中的必填字符串.

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
    """生成 OCI authors 元数据.

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
    """加载 Docker 镜像使用的项目元数据.

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


def docker_build_command(
    metadata: DockerMetadata,
    *,
    image: str,
    framework: str,
    commit: str,
    build_date: str,
    pull: bool = False,
    no_cache: bool = False,
    pip_index_url: str | None = None,
) -> list[str]:
    """生成 Docker 镜像构建命令.

    参数：
        metadata: 从 pyproject.toml 加载的项目与 OCI 元数据
        image: 完整 Docker 镜像引用
        framework: 镜像支持的模型框架，full 表示支持全部框架
        commit: 完整的 40 位 Git 提交哈希
        build_date: UTC RFC 3339 格式的构建时间
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
        image,
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
