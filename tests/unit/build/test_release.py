"""正式发布编排测试.

验证正式发布元数据、仓库配置及 GitHub Actions 发布流程。

核心功能：
  - test_load_release_metadata_validates_tag_and_project_version:
    验证 Tag、项目版本与构建身份保持一致
  - test_publish_configuration_validates_destinations:
    验证正式发布目标配置
  - test_release_workflow_reuses_existing_quality_gates:
    验证正式发布复用现有测试与冒烟测试入口
"""

from argparse import Namespace
from pathlib import Path
import tomllib

import pytest

from build_support.release import (
    load_release_metadata,
    validate_dockerhub_repository,
    validate_twine_repository,
)
from scripts.release import prepare_release


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BUILD_DATE = "2026-09-22T10:20:30Z"


def write_pyproject(path: Path, version: str = "9.8.7") -> Path:
    """写入测试专用的项目与 OCI 元数据."""
    pyproject = path / "pyproject.toml"
    pyproject.write_text(
        f"""
[project]
name = "datamind-test"
version = "{version}"
description = "test-description"
license = "Apache-2.0"

[project.urls]
Source = "https://example.com/source"

[tool.datamind.oci]
vendor = "TEST VENDOR"
""".strip(),
        encoding="utf-8",
    )
    return pyproject


def test_load_release_metadata_validates_tag_and_project_version(
    tmp_path: Path,
) -> None:
    """测试发布元数据来自项目版本与统一构建身份."""
    metadata = load_release_metadata(
        write_pyproject(tmp_path),
        tag="v9.8.7",
        commit=BUILD_COMMIT,
        build_date=BUILD_DATE,
    )

    assert metadata.version == "9.8.7"
    assert metadata.tag == "v9.8.7"
    assert metadata.distribution == "datamind-test"
    assert metadata.wheel_name == "datamind_test-9.8.7-py3-none-any.whl"
    assert metadata.sdist_name == "datamind_test-9.8.7.tar.gz"
    assert metadata.commit == BUILD_COMMIT
    assert metadata.build_date == BUILD_DATE
    assert metadata.source == "https://example.com/source"
    assert metadata.license == "Apache-2.0"
    assert metadata.vendor == "TEST VENDOR"


def test_project_uses_public_distribution_name() -> None:
    """测试正式项目元数据声明 pydatamind distribution."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    assert document["project"]["name"] == "pydatamind"
    assert document["project"]["scripts"] == {
        "datamind": "datamind.cli.main:app",
    }


def test_release_metadata_writes_distribution_outputs(tmp_path: Path) -> None:
    """测试发布准备步骤输出正式分发包名称."""
    github_output = tmp_path / "github-output"

    prepare_release(
        Namespace(
            pyproject=write_pyproject(tmp_path),
            tag="v9.8.7",
            commit=BUILD_COMMIT,
            build_date=BUILD_DATE,
            github_output=github_output,
        )
    )

    assert github_output.read_text(encoding="utf-8").splitlines() == [
        "tag=v9.8.7",
        "distribution=datamind-test",
        "version=9.8.7",
        "wheel_name=datamind_test-9.8.7-py3-none-any.whl",
        "sdist_name=datamind_test-9.8.7.tar.gz",
        f"commit={BUILD_COMMIT}",
        f"build_date={BUILD_DATE}",
    ]


@pytest.mark.parametrize("tag", ["9.8.7", "v9.8.6", "latest", ""])
def test_load_release_metadata_rejects_mismatched_tag(
    tmp_path: Path,
    tag: str,
) -> None:
    """测试正式 Tag 必须与 pyproject.toml 版本完全一致."""
    with pytest.raises(RuntimeError, match="不一致"):
        load_release_metadata(
            write_pyproject(tmp_path),
            tag=tag,
            commit=BUILD_COMMIT,
            build_date=BUILD_DATE,
        )


@pytest.mark.parametrize(
    ("url", "username", "password", "message"),
    [
        (None, "user", "secret", "TWINE_REPOSITORY_URL"),
        ("ftp://packages.example.com", "user", "secret", "HTTPS"),
        ("https://packages.example.com", None, "secret", "TWINE_USERNAME"),
        ("https://packages.example.com", "user", " ", "TWINE_PASSWORD"),
    ],
)
def test_twine_configuration_rejects_invalid_values(
    url: str | None,
    username: str | None,
    password: str | None,
    message: str,
) -> None:
    """测试 Twine 发布配置完整且地址有效."""
    with pytest.raises(RuntimeError, match=message):
        validate_twine_repository(url, username, password)


@pytest.mark.parametrize(
    "repository_url",
    [
        "https://upload.pypi.org/legacy/",
        "https://packages.example.com/repository/python/",
    ],
)
def test_twine_configuration_accepts_compatible_repository(
    repository_url: str,
) -> None:
    """测试 Twine 支持 PyPI-compatible 仓库."""
    assert validate_twine_repository(
        repository_url,
        "release-user",
        "release-secret",
    ) == repository_url.rstrip("/")


@pytest.mark.parametrize(
    ("repository", "username", "token", "message"),
    [
        (
            "quay.io/team/datamind",
            "user",
            "secret",
            "docker.io",
        ),
        (
            "docker.io/team/datamind:latest",
            "user",
            "secret",
            "不含 Tag",
        ),
        (
            "docker.io/team/datamind",
            None,
            "secret",
            "DOCKERHUB_USERNAME",
        ),
        (
            "docker.io/team/datamind",
            "user",
            " ",
            "DOCKERHUB_TOKEN",
        ),
    ],
)
def test_dockerhub_configuration_rejects_invalid_values(
    repository: str,
    username: str | None,
    token: str | None,
    message: str,
) -> None:
    """测试 Docker Hub 发布拒绝无效仓库或缺失凭据."""
    with pytest.raises(RuntimeError, match=message):
        validate_dockerhub_repository(
            repository,
            username,
            token,
        )


def test_dockerhub_configuration_accepts_repository() -> None:
    """测试 Docker Hub 发布使用项目配置的镜像仓库."""
    assert validate_dockerhub_repository(
        "docker.io/zhongshengchen/datamind",
        "release-user",
        "release-secret",
    ) == "docker.io/zhongshengchen/datamind"


def test_release_dependency_group_owns_twine() -> None:
    """测试 Twine 属于发布工具依赖，不进入 Runtime dependencies."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    runtime = document["project"]["dependencies"]
    release = document["project"]["optional-dependencies"]["release"]

    assert all(not dependency.startswith("twine") for dependency in runtime)
    assert any(dependency.startswith("twine") for dependency in release)


def test_release_workflow_reuses_existing_quality_gates() -> None:
    """测试 Release Workflow 复用现有测试与 Smoke 入口."""
    workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "release.yml"
    ).read_text(encoding="utf-8")

    assert 'tags:\n      - "v*"' in workflow
    assert "uses: ./.github/workflows/test.yml" in workflow
    assert "tests/smoke/test_wheel.py" in workflow
    assert "tests/smoke/test_docker.py" in workflow
    assert "environment: release" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "pypi.org" not in workflow
    assert "docker.io/zhongshengchen/datamind" not in workflow
    assert "TWINE_REPOSITORY_URL" in workflow
    assert "TWINE_USERNAME" in workflow
    assert "TWINE_PASSWORD" in workflow
    assert "DOCKERHUB_USERNAME" in workflow
    assert "DOCKERHUB_TOKEN" in workflow
    assert "PYPI_REPOSITORY_URL" not in workflow
    assert "DOCKER_REPOSITORY" not in workflow
    assert "outputs.distribution" in workflow
    assert "outputs.wheel_name" in workflow
    assert "outputs.sdist_name" in workflow
    assert "dist/datamind-${{" not in workflow


def test_release_configuration_check_is_non_publishing() -> None:
    """测试发布配置检查仅执行校验与 Docker Hub 登录."""
    workflow = (
        PROJECT_ROOT / ".github" / "workflows" / "release-check.yml"
    ).read_text(encoding="utf-8")

    assert 'branches:\n      - main' in workflow
    assert 'paths:\n      - ".github/workflows/release-check.yml"' in workflow
    assert "workflow_dispatch:" in workflow
    assert "environment: release" in workflow
    assert "validate-twine-config" in workflow
    assert "validate-dockerhub-config" in workflow
    assert "docker login docker.io" in workflow
    assert "twine upload" not in workflow
    assert "docker push" not in workflow
    assert "gh release create" not in workflow


def test_tests_workflow_is_reusable_release_gate() -> None:
    """测试 Tests Workflow 同时支持 workflow_call."""
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "test.yml").read_text(
        encoding="utf-8"
    )

    assert "  workflow_call:" in workflow
