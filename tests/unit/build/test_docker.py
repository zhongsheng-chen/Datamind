"""Docker 构建元数据测试

验证项目元数据解析、Docker 构建参数传递、构建身份校验及发布工具
依赖边界。

核心功能：
  - test_load_docker_metadata_reads_pyproject_sources:
    验证从指定的 pyproject.toml 读取项目与 OCI 元数据
  - test_docker_build_command_forwards_all_metadata:
    验证 Docker 命令完整传递项目元数据与构建身份
  - test_resolve_build_identity_rejects_partial_input:
    验证拒绝不完整的构建身份
  - test_build_script_uses_standard_library_tomllib:
    验证构建入口使用标准库解析 TOML
  - test_compose_requires_explicit_image_tag:
    验证 Compose 部署必须显式提供镜像标签
"""

from pathlib import Path
import tomllib

import pytest

from scripts import build_docker


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BUILD_DATE = "2026-09-21T02:09:32Z"


def test_load_docker_metadata_reads_pyproject_sources(tmp_path: Path) -> None:
    """测试从指定的 pyproject.toml 读取 Docker 元数据"""
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

    metadata = build_docker.load_docker_metadata(pyproject)

    assert metadata == build_docker.DockerMetadata(
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
    """测试仓库许可证使用标准 Apache License 2.0 文本"""
    assert (
        (PROJECT_ROOT / "LICENSE")
        .read_text(encoding="utf-8")
        .lstrip()
        .startswith("Apache License\n")
    )


def test_docker_build_command_forwards_all_metadata() -> None:
    """测试 Docker 命令完整传递项目元数据与构建身份"""
    metadata = build_docker.DockerMetadata(
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

    command = build_docker.docker_build_command(
        metadata,
        tag="datamind:test",
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
    assert command[-1] == str(PROJECT_ROOT)


@pytest.mark.parametrize(
    ("commit", "build_date"),
    [
        (BUILD_COMMIT, None),
        (None, BUILD_DATE),
    ],
)
def test_resolve_build_identity_rejects_partial_input(
    monkeypatch: pytest.MonkeyPatch,
    commit: str | None,
    build_date: str | None,
) -> None:
    """测试 Docker 构建拒绝不完整的构建身份"""
    monkeypatch.delenv("DATAMIND_BUILD_COMMIT", raising=False)
    monkeypatch.delenv("DATAMIND_BUILD_DATE", raising=False)

    with pytest.raises(RuntimeError, match="必须同时设置"):
        build_docker.resolve_build_identity(commit, build_date)


def test_resolve_build_identity_requires_release_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 Docker Image 构建必须提供完整构建身份"""
    monkeypatch.delenv("DATAMIND_BUILD_COMMIT", raising=False)
    monkeypatch.delenv("DATAMIND_BUILD_DATE", raising=False)

    with pytest.raises(RuntimeError, match="必须同时设置"):
        build_docker.resolve_build_identity(None, None)


@pytest.mark.parametrize(
    ("commit", "build_date", "message"),
    [
        (" ", BUILD_DATE, "不能是空白字符串"),
        (BUILD_COMMIT[:12], BUILD_DATE, "完整的 40 位 Git SHA"),
        (BUILD_COMMIT, "2026-09-21 02:09:32Z", "UTC RFC 3339"),
    ],
)
def test_resolve_build_identity_reuses_release_validation(
    commit: str,
    build_date: str,
    message: str,
) -> None:
    """测试 Docker 与 Python 发布包共享构建身份校验规则"""
    with pytest.raises(RuntimeError, match=message):
        build_docker.resolve_build_identity(commit, build_date)


def test_build_script_uses_standard_library_tomllib() -> None:
    """测试构建入口仅使用 Python 标准库解析 TOML。"""
    script = (PROJECT_ROOT / "scripts" / "build_docker.py").read_text(
        encoding="utf-8"
    )
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    assert "import tomllib" in script
    assert "import tomli" not in script
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
def test_default_image_tag_follows_framework_contract(
        framework: str,
        expected: str,
) -> None:
    """测试完整版与专用镜像使用约定的默认标签。"""
    assert build_docker.default_image_tag(
        "docker.io/example/datamind",
        "9.8.7",
        framework,
    ) == expected


def test_parse_arguments_rejects_unknown_framework() -> None:
    """测试非法模型框架在 Docker 调用前被拒绝。"""
    with pytest.raises(SystemExit):
        build_docker.parse_arguments(["--framework", "unknown"])


def test_build_script_uses_shared_identity_without_setuptools_commands() -> None:
    """测试 Docker 构建入口不依赖 setuptools 命令模块"""
    script = (PROJECT_ROOT / "scripts" / "build_docker.py").read_text(
        encoding="utf-8"
    )

    assert "from build_support.identity import release_build_identity" in script
    assert "from build_support.commands import" not in script


def test_compose_requires_explicit_image_tag() -> None:
    """测试 Compose 部署必须显式提供镜像标签"""
    content = (PROJECT_ROOT / "docker" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )

    assert (
        "${DATAMIND_IMAGE_REPOSITORY:-docker.io/zhongshengchen/datamind}:"
        "${DATAMIND_IMAGE_TAG:?DATAMIND_IMAGE_TAG is required}" in content
    )
