"""Datamind 正式发布元数据.

生成正式发布共用的项目元数据，并校验 Python 包与 Docker 镜像发布配置。

核心功能：
  - ReleaseMetadata: 记录同一次发布共享的版本与构建信息
  - load_release_metadata: 校验 Git Tag 并加载正式发布元数据
  - validate_twine_repository: 校验 Twine 发布配置
  - validate_dockerhub_repository: 校验 Docker Hub 发布配置

使用示例：
  from pathlib import Path

  from build_support.release import load_release_metadata

  metadata = load_release_metadata(
      Path("pyproject.toml"),
      tag="v0.1.0",
      commit="0123456789abcdef0123456789abcdef01234567",
      build_date="2026-09-22T10:20:30Z",
  )
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import tomllib
from typing import Any
from urllib.parse import urlparse

from build_support.distributions import PythonDistribution
from build_support.identity import release_build_identity


_DOCKERHUB_REPOSITORY = re.compile(
    r"docker\.io/[a-z0-9._-]+(?:/[a-z0-9._-]+)*"
)


@dataclass(frozen=True, slots=True)
class ReleaseMetadata:
    """记录一次正式发布共享的元数据.

    属性：
        tag: 与项目版本一致的 Git Tag
        distribution: pyproject.toml 中声明的 Python distribution name
        version: pyproject.toml 中声明的项目版本
        wheel_name: 本次发布生成的 Wheel 文件名
        sdist_name: 本次发布生成的 sdist 文件名
        commit: 完整的 40 位 Git 提交哈希
        build_date: UTC RFC 3339 格式的构建时间
        source: 项目源码地址
        license: 项目许可证标识
        vendor: OCI 镜像供应商
    """

    tag: str
    distribution: str
    version: str
    wheel_name: str
    sdist_name: str
    commit: str
    build_date: str
    source: str
    license: str
    vendor: str


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
        raise RuntimeError(f"缺少有效的 {location}")

    return value


def _required_string(value: object, location: str) -> str:
    """读取并规范化必填字符串."""
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"缺少有效的 {location}")

    return value.strip()


def utc_build_date() -> str:
    """生成秒级 UTC RFC 3339 构建时间.

    返回：
        以 ``Z`` 结尾的 UTC 构建时间
    """
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_release_metadata(
    pyproject_path: Path,
    *,
    tag: str,
    commit: str,
    build_date: str,
) -> ReleaseMetadata:
    """从项目正式配置生成并校验发布元数据.

    参数：
        pyproject_path: pyproject.toml 文件路径
        tag: 触发正式发布的 Git Tag
        commit: 完整的 40 位 Git 提交哈希
        build_date: UTC RFC 3339 格式的构建时间

    返回：
        经过校验的正式发布元数据

    异常：
        RuntimeError: 项目元数据缺失，或 Tag、构建身份无效
    """
    with pyproject_path.open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    project = _required_mapping(document.get("project"), "project")
    urls = _required_mapping(project.get("urls"), "project.urls")
    tool = _required_mapping(document.get("tool"), "tool")
    datamind = _required_mapping(tool.get("datamind"), "tool.datamind")
    oci = _required_mapping(
        datamind.get("oci"),
        "tool.datamind.oci",
    )

    python_distribution = PythonDistribution(
        name=_required_string(project.get("name"), "project.name"),
        version=_required_string(project.get("version"), "project.version"),
    )
    expected_tag = f"v{python_distribution.version}"
    normalized_tag = tag.strip()

    if normalized_tag != expected_tag:
        raise RuntimeError(
            f"Git Tag {normalized_tag!r} 与项目版本 "
            f"{python_distribution.version!r} 不一致；"
            f"正式标签必须为 {expected_tag!r}"
        )

    identity = release_build_identity(commit, build_date)
    source = _required_string(urls.get("Source"), "project.urls.Source")
    license_identifier = _required_string(
        project.get("license"),
        "project.license",
    )
    vendor = _required_string(
        oci.get("vendor"),
        "tool.datamind.oci.vendor",
    )

    return ReleaseMetadata(
        tag=normalized_tag,
        distribution=python_distribution.name,
        version=python_distribution.version,
        wheel_name=python_distribution.wheel_name,
        sdist_name=python_distribution.sdist_name,
        commit=identity.commit,
        build_date=identity.build_date,
        source=source,
        license=license_identifier,
        vendor=vendor,
    )


def validate_twine_repository(
    repository_url: str | None,
    username: str | None,
    password: str | None,
) -> str:
    """校验 Twine 发布配置.

    参数：
        repository_url: PyPI 或 devpi 等兼容服务的上传地址
        username: 发布用户名或 Token 用户名
        password: 发布密码或 Token

    返回：
        去除末尾分隔符的仓库上传地址

    异常：
        RuntimeError: 配置缺失或地址无效
    """
    url = _required_string(repository_url, "TWINE_REPOSITORY_URL")
    _required_string(username, "TWINE_USERNAME")
    _required_string(password, "TWINE_PASSWORD")

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname is None:
        raise RuntimeError(
            "TWINE_REPOSITORY_URL 必须是有效的 HTTPS 地址"
        )
    return url.rstrip("/")


def validate_dockerhub_repository(
    repository: str,
    username: str | None,
    token: str | None,
) -> str:
    """校验 Docker Hub 发布配置.

    参数：
        repository: pyproject.toml 中配置的镜像仓库
        username: Docker Hub 用户名
        token: Docker Hub Access Token

    返回：
        规范化后的 Docker Hub 镜像仓库

    异常：
        RuntimeError: 发布凭据缺失或镜像仓库无效
    """
    normalized_repository = _required_string(
        repository,
        "tool.datamind.docker.repository",
    ).rstrip("/")
    _required_string(username, "DOCKERHUB_USERNAME")
    _required_string(token, "DOCKERHUB_TOKEN")

    if _DOCKERHUB_REPOSITORY.fullmatch(normalized_repository) is None:
        raise RuntimeError(
            "tool.datamind.docker.repository 必须是 docker.io 下且不含 Tag "
            "的镜像仓库路径"
        )

    return normalized_repository
