"""Docker 构建元数据测试.

验证项目元数据解析、镜像引用选择与 Docker 构建参数传递，并确认 Docker
构建支持不负责解析构建身份。

核心功能：
  - test_load_docker_metadata_reads_pyproject_sources:
    验证从指定的 pyproject.toml 读取项目与 OCI 元数据
  - test_docker_build_command_forwards_all_metadata:
    验证 Docker 命令完整传递项目元数据与构建身份
  - test_docker_support_uses_standard_library_tomllib:
    验证 Docker 构建支持使用标准库解析 TOML
  - test_compose_requires_explicit_image_tag:
    验证 Compose 部署必须显式提供镜像标签
  - test_project_license_file_is_apache_20:
    测试仓库许可证使用标准 Apache License 2.0 文本
  - test_resolve_image_follows_framework_contract:
    测试完整版与框架专用镜像采用约定的默认引用
  - test_resolve_image_prefers_explicit_reference:
    测试显式镜像引用优先于默认镜像名称
  - test_repository_override_keeps_image_reference_generation:
    测试镜像仓库覆盖仍复用默认镜像引用格式
  - test_image_and_repository_override_are_mutually_exclusive:
    测试完整镜像引用与镜像仓库覆盖不能同时指定
  - test_parse_arguments_reads_build_identity_from_environment:
    测试 Docker 构建参数从环境变量读取构建身份
  - test_parse_arguments_rejects_unknown_framework:
    测试非法模型框架在 Docker 调用前被拒绝
  - test_docker_support_has_no_build_identity_dependency:
    测试 Docker 构建支持不负责解析构建身份
"""

from pathlib import Path
import tomllib

import pytest

from build_support import docker as docker_support
from scripts import build_docker


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BUILD_DATE = "2026-09-21T02:09:32Z"


def test_load_docker_metadata_reads_pyproject_sources(tmp_path: Path) -> None:
    """测试从指定的 pyproject.toml 读取 Docker 元数据."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[project]
name = "datamind-test"
version = "9.8.7"
description = "test-description"
authors = [
    { name = "Test Author", email = "test@example.com" },
]
license = "Apache-2.0"

[project.urls]
Homepage = "https://example.com/project"
Documentation = "https://example.com/docs"
Source = "https://example.com/source"

[tool.datamind.oci]
title = "Test Datamind"
vendor = "TEST VENDOR"

[tool.datamind.docker]
repository = "docker.io/example/datamind-test"
""".strip(),
        encoding="utf-8",
    )

    metadata = docker_support.load_docker_metadata(pyproject)

    assert metadata == docker_support.DockerMetadata(
        repository="docker.io/example/datamind-test",
        title="Test Datamind",
        description="test-description",
        version="9.8.7",
        authors="Test Author <test@example.com>",
        vendor="TEST VENDOR",
        licenses="Apache-2.0",
        source="https://example.com/source",
        url="https://example.com/project",
        documentation="https://example.com/docs",
    )


def test_project_license_file_is_apache_20() -> None:
    """测试仓库许可证使用标准 Apache License 2.0 文本."""
    assert (
        (PROJECT_ROOT / "LICENSE")
        .read_text(encoding="utf-8")
        .lstrip()
        .startswith("Apache License\n")
    )


def test_docker_build_command_forwards_all_metadata() -> None:
    """测试 Docker 命令完整传递项目元数据与构建身份."""
    metadata = docker_support.DockerMetadata(
        repository="docker.io/example/datamind-test",
        title="Test Datamind",
        description="test-description",
        version="9.8.7",
        authors="Test Author <test@example.com>",
        vendor="TEST VENDOR",
        licenses="Test-License",
        source="https://example.com/source",
        url="https://example.com/project",
        documentation="https://example.com/docs",
    )

    command = docker_support.docker_build_command(
        metadata,
        image="datamind:test",
        framework="xgboost",
        commit=BUILD_COMMIT,
        build_date=BUILD_DATE,
        pip_index_url="https://mirrors.aliyun.com/pypi/simple/",
    )

    arguments = {
        command[index + 1]
        for index, value in enumerate(command[:-1])
        if value == "--build-arg"
    }
    assert arguments == {
        "DATAMIND_AUTHORS=Test Author <test@example.com>",
        f"DATAMIND_BUILD_COMMIT={BUILD_COMMIT}",
        f"DATAMIND_BUILD_DATE={BUILD_DATE}",
        "DATAMIND_DESCRIPTION=test-description",
        "DATAMIND_DOCUMENTATION_URL=https://example.com/docs",
        "DATAMIND_LICENSES=Test-License",
        "DATAMIND_PROJECT_URL=https://example.com/project",
        "DATAMIND_PYTHON_EXTRA=xgboost",
        "DATAMIND_SOURCE_URL=https://example.com/source",
        "DATAMIND_TITLE=Test Datamind",
        "DATAMIND_VENDOR=TEST VENDOR",
        "DATAMIND_VERSION=9.8.7",
        "PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/",
    }
    assert command[command.index("--tag") + 1] == "datamind:test"
    assert command[-1] == str(PROJECT_ROOT)


def test_docker_support_uses_standard_library_tomllib() -> None:
    """测试 Docker 构建支持仅使用 Python 标准库解析 TOML."""
    support = (PROJECT_ROOT / "build_support" / "docker.py").read_text(
        encoding="utf-8"
    )
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    assert "import tomllib" in support
    assert "import tomli" not in support
    optional = document["project"]["optional-dependencies"]

    assert all("tomli" not in dependency for dependency in optional["release"])


@pytest.mark.parametrize(
    ("framework", "expected"),
    [
        ("full", "docker.io/example/datamind:9.8.7"),
        ("sklearn", "docker.io/example/datamind:9.8.7-sklearn"),
        ("xgboost", "docker.io/example/datamind:9.8.7-xgboost"),
        ("lightgbm", "docker.io/example/datamind:9.8.7-lightgbm"),
        ("catboost", "docker.io/example/datamind:9.8.7-catboost"),
    ],
)
def test_resolve_image_follows_framework_contract(
    framework: str,
    expected: str,
) -> None:
    """测试完整版与框架专用镜像采用约定的默认引用."""
    assert build_docker.resolve_image(
        image=None,
        repository="docker.io/example/datamind",
        version="9.8.7",
        framework=framework,
    ) == expected


def test_resolve_image_prefers_explicit_reference() -> None:
    """测试显式镜像引用优先于默认镜像名称."""
    assert build_docker.resolve_image(
        image="registry.example.com/team/datamind:custom",
        repository="docker.io/example/datamind",
        version="9.8.7",
        framework="full",
    ) == "registry.example.com/team/datamind:custom"


def test_repository_override_keeps_image_reference_generation() -> None:
    """测试镜像仓库覆盖仍复用默认镜像引用格式."""
    arguments = build_docker.parse_arguments(
        [
            "--repository",
            "registry.example.com/team/datamind",
            "--framework",
            "sklearn",
            "--print",
        ]
    )

    assert arguments.repository == "registry.example.com/team/datamind"
    assert arguments.framework == "sklearn"
    assert arguments.print is True
    assert build_docker.resolve_image(
        image=arguments.image,
        repository=arguments.repository,
        version="9.8.7",
        framework=arguments.framework,
    ) == "registry.example.com/team/datamind:9.8.7-sklearn"


def test_image_and_repository_override_are_mutually_exclusive() -> None:
    """测试完整镜像引用与镜像仓库覆盖不能同时指定."""
    with pytest.raises(SystemExit):
        build_docker.parse_arguments(
            [
                "--image",
                "datamind:test",
                "--repository",
                "registry.example.com/team/datamind",
            ]
        )


def test_parse_arguments_reads_build_identity_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Docker 构建参数从环境变量读取构建身份."""
    monkeypatch.setenv("DATAMIND_BUILD_COMMIT", BUILD_COMMIT)
    monkeypatch.setenv("DATAMIND_BUILD_DATE", BUILD_DATE)

    arguments = build_docker.parse_arguments([])

    assert arguments.build_commit == BUILD_COMMIT
    assert arguments.build_date == BUILD_DATE


def test_parse_arguments_rejects_unknown_framework() -> None:
    """测试非法模型框架在 Docker 调用前被拒绝."""
    with pytest.raises(SystemExit):
        build_docker.parse_arguments(["--framework", "unknown"])


def test_docker_support_has_no_build_identity_dependency() -> None:
    """测试 Docker 构建支持不负责解析构建身份."""
    support = (PROJECT_ROOT / "build_support" / "docker.py").read_text(
        encoding="utf-8"
    )

    assert "build_support.identity" not in support
    assert "build_support.backend.commands" not in support


def test_compose_requires_explicit_image_tag() -> None:
    """测试 Compose 部署必须显式提供镜像标签."""
    content = (PROJECT_ROOT / "docker" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert (
        "${DATAMIND_IMAGE_REPOSITORY:-docker.io/zhongshengchen/datamind}:"
        "${DATAMIND_IMAGE_TAG:?DATAMIND_IMAGE_TAG is required}" in content
    )
