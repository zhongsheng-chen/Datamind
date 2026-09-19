"""Datamind 发布构建身份

确保 Wheel、sdist 与 Docker 镜像使用一致且有效的构建身份。

核心功能：
  - BuildIdentity: 记录发布产物的 Commit 与 Build Date
  - release_build_identity: 校验完整 Git SHA 和 UTC RFC 3339 构建时间

使用示例：
  import os

  from build_support.identity import release_build_identity

  identity = release_build_identity(
      os.environ["DATAMIND_BUILD_COMMIT"],
      os.environ["DATAMIND_BUILD_DATE"],
  )
"""

from dataclasses import dataclass
from datetime import datetime
import re


_FULL_GIT_SHA = re.compile(r"[0-9a-fA-F]{40}")
_UTC_RFC3339 = re.compile(
    r"\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}(?:\.\d+)?Z"
)


@dataclass(frozen=True)
class BuildIdentity:
    """记录发布产物的构建身份。

    属性：
        commit: 完整的 Git Commit SHA；开发构建使用 ``dev``
        build_date: UTC RFC 3339 构建时间；开发构建使用 ``None``
    """

    commit: str
    build_date: str | None


def _required_value(name: str, value: str) -> str:
    """规范化必填构建变量。

    参数：
        name: 环境变量名称
        value: 待检查的变量值

    返回：
        去除首尾空白后的变量值

    异常：
        RuntimeError: 变量值为空或仅包含空白字符
    """
    normalized = value.strip()

    if not normalized:
        raise RuntimeError(f"{name} 不能是空白字符串")

    return normalized


def release_build_identity(commit: str, build_date: str) -> BuildIdentity:
    """校验正式发布使用的构建身份。

    参数：
        commit: 完整的 40 位 Git Commit SHA
        build_date: UTC RFC 3339 格式的构建时间，时区必须为 UTC

    返回：
        经过规范化和校验的构建身份

    异常：
        RuntimeError: Commit 或 Build Date 为空或格式不符合要求
    """
    normalized_commit = _required_value("DATAMIND_BUILD_COMMIT", commit)
    normalized_date = _required_value("DATAMIND_BUILD_DATE", build_date)

    if _FULL_GIT_SHA.fullmatch(normalized_commit) is None:
        raise RuntimeError("DATAMIND_BUILD_COMMIT 必须是完整的 40 位 Git SHA")

    if _UTC_RFC3339.fullmatch(normalized_date) is None:
        raise RuntimeError("DATAMIND_BUILD_DATE 必须使用 UTC RFC 3339 格式")

    try:
        parsed_date = datetime.fromisoformat(
            normalized_date.removesuffix("Z") + "+00:00"
        )
    except ValueError as error:
        raise RuntimeError(
            "DATAMIND_BUILD_DATE 必须是有效的 UTC RFC 3339 时间"
        ) from error

    offset = parsed_date.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise RuntimeError("DATAMIND_BUILD_DATE 必须使用 UTC")

    return BuildIdentity(
        commit=normalized_commit,
        build_date=normalized_date,
    )
