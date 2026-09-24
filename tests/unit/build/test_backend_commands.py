"""Python 分发包构建命令测试.

验证控制台资源检查、构建身份校验及分发包元数据传递。

核心功能：
  - test_build_requires_console_assets:
    验证构建资源检查
  - test_build_commands_validate_console_assets:
    验证打包命令调用资源检查
  - test_release_distributions_preserve_build_identity:
    验证 Wheel、sdist 及 sdist 重建 Wheel 保留相同构建身份
  - test_dockerfile_installs_wheel_only:
    验证 Docker 镜像只安装 Wheel
  - test_dockerfile_maps_oci_metadata_arguments:
    验证 OCI Labels 映射统一传入的项目与构建元数据
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib
from typing import Any
from unittest.mock import Mock

import pytest
from setuptools import Distribution

from build_support.backend import commands as build_commands
from build_support.distributions import verify_release_distributions
from build_support.identity import BuildIdentity


PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_COMMIT = "0123456789abcdef0123456789abcdef01234567"
BUILD_DATE = "2026-09-21T02:09:32Z"


def clear_build_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """清除外部构建身份输入."""
    monkeypatch.delenv("DATAMIND_BUILD_COMMIT", raising=False)
    monkeypatch.delenv("DATAMIND_BUILD_DATE", raising=False)


def run_package_build(
    command: list[str],
    *,
    working_directory: Path,
    environment: dict[str, str],
) -> None:
    """运行分发包构建，并在失败时保留完整诊断信息."""
    result = subprocess.run(
        command,
        cwd=working_directory,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        pytest.fail(
            "分发包构建失败：\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}",
            pytrace=False,
        )


def pyproject_document() -> dict[str, Any]:
    """读取项目元数据文档."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject_file:
        return tomllib.load(pyproject_file)


def project_metadata() -> dict[str, Any]:
    """读取 Python 发布元数据的正式来源."""
    document = pyproject_document()

    return document["project"]


@pytest.mark.parametrize(
    "missing",
    [
        "index.html",
        ".vite/manifest.json",
        "assets",
        "assets/index-Ab123456.js",
        "assets/index-ab123456.css",
        None,
    ],
)
def test_build_requires_console_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    missing: str | None,
) -> None:
    """测试入口页面和构建清单引用的文件必须完整存在."""
    monkeypatch.setitem(
        vars(build_commands),
        "__file__",
        str(tmp_path / "build_support" / "backend" / "commands.py"),
    )
    directory = tmp_path / "datamind" / "console" / "dist"
    directory.mkdir(parents=True)
    for name in [
        "index.html",
        ".vite/manifest.json",
        "assets",
    ]:
        if name == missing:
            continue

        path = directory / name
        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if name == "assets":
            path.mkdir()
            for filename in [
                "index-Ab123456.js",
                "index-ab123456.css",
            ]:
                if f"assets/{filename}" != missing:
                    (path / filename).write_text(
                        "content",
                        encoding="utf-8",
                    )
        elif name == ".vite/manifest.json":
            manifest = {
                "index.html": {
                    "file": "assets/index-Ab123456.js",
                    "css": ["assets/index-ab123456.css"],
                }
            }
            path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
        else:
            path.write_text(
                "page",
                encoding="utf-8",
            )

    if missing is None:
        build_commands._require_console_build()
    else:
        with pytest.raises(
            RuntimeError,
            match="npm run build:console",
        ):
            build_commands._require_console_build()


@pytest.mark.parametrize(
    ("command_type", "run_target", "expected_events"),
    [
        (
            build_commands.BuildPy,
            "setuptools.command.build_py.build_py.run",
            ["validate", "identity", "build", "metadata"],
        ),
        (
            build_commands.Sdist,
            "setuptools.command.sdist.sdist.run",
            ["validate", "identity", "build"],
        ),
    ],
)
def test_build_commands_validate_console_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    command_type: (type[build_commands.BuildPy] | type[build_commands.Sdist]),
    run_target: str,
    expected_events: list[str],
) -> None:
    """测试构建命令先校验控制台资源再执行打包."""
    events: list[str] = []
    monkeypatch.setitem(
        vars(build_commands),
        "_require_console_build",
        lambda: events.append("validate"),
    )
    identity = build_commands.BuildIdentity(
        commit=BUILD_COMMIT,
        build_date=BUILD_DATE,
    )

    def build_identity() -> build_commands.BuildIdentity:
        events.append("identity")
        return identity

    monkeypatch.setitem(
        vars(build_commands),
        "_build_identity",
        build_identity,
    )
    monkeypatch.setitem(
        vars(build_commands),
        "_write_build_metadata",
        lambda *_args: events.append("metadata"),
    )
    run = Mock(side_effect=lambda: events.append("build"))
    monkeypatch.setattr(
        run_target,
        run,
    )

    command = command_type(Distribution())
    if isinstance(command, build_commands.BuildPy):
        command.build_lib = str(tmp_path / "build")
    command.run()

    assert events == expected_events


def test_build_identity_defaults_to_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试未注入发布身份时使用源码开发默认值."""
    clear_build_environment(monkeypatch)

    identity = build_commands._build_identity()

    assert identity is None


def test_build_identity_uses_explicit_release_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试同时注入 Commit 与 Build Date 时清理并保留完整值."""
    monkeypatch.setenv("DATAMIND_BUILD_COMMIT", f"  {BUILD_COMMIT}  ")
    monkeypatch.setenv("DATAMIND_BUILD_DATE", f"  {BUILD_DATE}  ")

    identity = build_commands._build_identity()

    assert identity == build_commands.BuildIdentity(
        commit=BUILD_COMMIT,
        build_date=BUILD_DATE,
    )


@pytest.mark.parametrize(
    "configured",
    [
        {"DATAMIND_BUILD_COMMIT": BUILD_COMMIT},
        {"DATAMIND_BUILD_DATE": BUILD_DATE},
    ],
)
def test_build_identity_rejects_partial_input(
    monkeypatch: pytest.MonkeyPatch,
    configured: dict[str, str],
) -> None:
    """测试构建身份只配置一项时拒绝构建."""
    clear_build_environment(monkeypatch)
    for name, value in configured.items():
        monkeypatch.setenv(name, value)

    with pytest.raises(RuntimeError, match="必须同时设置"):
        build_commands._build_identity()


@pytest.mark.parametrize(
    ("commit", "build_date", "message"),
    [
        ("   ", BUILD_DATE, "DATAMIND_BUILD_COMMIT 不能是空白字符串"),
        (BUILD_COMMIT, "   ", "DATAMIND_BUILD_DATE 不能是空白字符串"),
    ],
)
def test_build_identity_rejects_blank_input(
    monkeypatch: pytest.MonkeyPatch,
    commit: str,
    build_date: str,
    message: str,
) -> None:
    """测试显式空白 Commit 或 Build Date 被拒绝."""
    monkeypatch.setenv("DATAMIND_BUILD_COMMIT", commit)
    monkeypatch.setenv("DATAMIND_BUILD_DATE", build_date)

    with pytest.raises(RuntimeError, match=message):
        build_commands._build_identity()


@pytest.mark.parametrize(
    "build_date",
    [
        "2026-09-21 02:09:32Z",
        "2026-09-21T02:09:32+00:00",
        "2026-09-21T02:09:32",
        "2026-02-30T02:09:32Z",
    ],
)
def test_build_identity_rejects_invalid_build_date(
    monkeypatch: pytest.MonkeyPatch,
    build_date: str,
) -> None:
    """测试非 UTC RFC 3339 或无效日历时间被拒绝."""
    monkeypatch.setenv("DATAMIND_BUILD_COMMIT", BUILD_COMMIT)
    monkeypatch.setenv("DATAMIND_BUILD_DATE", build_date)

    with pytest.raises(RuntimeError, match="DATAMIND_BUILD_DATE"):
        build_commands._build_identity()


def test_build_identity_rejects_incomplete_git_sha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试发布 Commit 必须是完整 Git SHA."""
    monkeypatch.setenv("DATAMIND_BUILD_COMMIT", BUILD_COMMIT[:12])
    monkeypatch.setenv("DATAMIND_BUILD_DATE", BUILD_DATE)

    with pytest.raises(RuntimeError, match="完整的 40 位 Git 提交哈希"):
        build_commands._build_identity()


def test_write_build_metadata_generates_stable_module(tmp_path: Path) -> None:
    """测试 Build Metadata 使用稳定 UTF-8 Python 格式."""
    target = tmp_path / "datamind" / "_build.py"

    build_commands._write_build_metadata(
        target,
        build_commands.BuildIdentity(
            commit=BUILD_COMMIT,
            build_date=BUILD_DATE,
        ),
    )

    assert target.read_text(encoding="utf-8") == (
        '"""Datamind build metadata."""\n\n'
        f'BUILD_COMMIT: str = "{BUILD_COMMIT}"\n'
        f'BUILD_DATE: str | None = "{BUILD_DATE}"\n'
    )


def test_write_build_metadata_generates_development_defaults(
    tmp_path: Path,
) -> None:
    """测试未提供正式构建身份时写入开发默认值."""
    target = tmp_path / "datamind" / "_build.py"

    build_commands._write_build_metadata(target, None)

    assert target.read_text(encoding="utf-8") == (
        '"""Datamind build metadata."""\n\n'
        'BUILD_COMMIT: str = "dev"\n'
        "BUILD_DATE: str | None = None\n"
    )


def test_sdist_writes_metadata_only_to_release_tree(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """测试 sdist 仅覆盖临时 release tree 中的 Build Metadata."""
    release_tree = tmp_path / (
        f"{project_metadata()['name']}-{project_metadata()['version']}"
    )
    release_tree.mkdir()
    identity = build_commands.BuildIdentity(
        commit=BUILD_COMMIT,
        build_date=BUILD_DATE,
    )
    writes: list[tuple[Path, build_commands.BuildIdentity]] = []
    monkeypatch.setattr(
        "setuptools.command.sdist.sdist.make_release_tree",
        lambda *_args: None,
    )
    monkeypatch.setitem(
        vars(build_commands),
        "_write_build_metadata",
        lambda path, value: writes.append((path, value)),
    )
    command = build_commands.Sdist(Distribution())
    command._datamind_build_identity = identity

    command.make_release_tree(str(release_tree), [])

    assert writes == [(release_tree / "datamind" / "_build.py", identity)]


def test_release_distributions_preserve_build_identity(tmp_path: Path) -> None:
    """测试 Wheel、sdist 和 sdist 重建 Wheel 保留相同发布身份."""
    source_metadata = PROJECT_ROOT / "datamind" / "_build.py"
    original_content = source_metadata.read_bytes()
    distribution_directory = tmp_path / "dist"
    build_environment = os.environ.copy()
    build_environment.update(
        {
            "DATAMIND_BUILD_COMMIT": BUILD_COMMIT,
            "DATAMIND_BUILD_DATE": BUILD_DATE,
        }
    )

    run_package_build(
        [
            sys.executable,
            "-m",
            "build",
            str(PROJECT_ROOT),
            "--wheel",
            "--sdist",
            "--no-isolation",
            "--outdir",
            str(distribution_directory),
        ],
        working_directory=tmp_path,
        environment=build_environment,
    )

    wheel, sdist = verify_release_distributions(
        distribution_directory,
        PROJECT_ROOT,
        BuildIdentity(commit=BUILD_COMMIT, build_date=BUILD_DATE),
    )

    assert wheel.name == "pydatamind-0.1.0-py3-none-any.whl"
    assert sdist.name == "pydatamind-0.1.0.tar.gz"
    assert source_metadata.read_bytes() == original_content


def test_dockerfile_installs_wheel_only() -> None:
    """测试 Docker 镜像仅安装构建后的 Wheel."""
    content = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "AS console-builder" in content
    assert "AS package-builder" in content
    assert "AS runtime" in content
    assert "COPY . ." not in content
    assert "WORKDIR /app" not in content
    assert "COPY pyproject.toml README.md LICENSE ./" in content
    assert "COPY build_support ./build_support" in content
    assert "COPY --from=package-builder /dist/ /tmp/dist/" in content
    assert '"${wheel_path}[${DATAMIND_PYTHON_EXTRA}]"' in content
    assert "ARG DATAMIND_PYTHON_EXTRA=full" in content
    assert (
        'CMD ["python", "-m", "bentoml", "serve", '
        '"datamind.runtime.server.service:DatamindRuntimeService", '
        '"--host", "0.0.0.0", "--port", "8700"]'
        in content
    )


def test_dockerfile_pins_builder_and_runtime_images() -> None:
    """测试 Node Builder 与 Python Runtime 均使用精确镜像摘要."""
    content = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG NODE_VERSION=24.21.0" in content
    assert (
        "ARG NODE_BASE_DIGEST="
        "sha256:5cbc7caba8c2c0f0bca675d1b61b9f2857e1cf1853c6164ee9dd409501a936e7"
        in content
    )
    assert (
        "FROM node:${NODE_VERSION}-bookworm-slim@${NODE_BASE_DIGEST} "
        "AS console-builder" in content
    )
    assert (
        "ARG PYTHON_BASE_DIGEST="
        "sha256:1aaa65a85fda306ffb8b910824d4e93bdce61e212c7e87168123ea3073b41a1a"
        in content
    )
    assert content.count(
        "FROM python:${PYTHON_VERSION}-slim-bookworm@${PYTHON_BASE_DIGEST}"
    ) == 2


def test_dockerfile_defaults_to_official_python_package_index() -> None:
    """测试 Docker 构建默认使用官方 Python 包索引."""
    content = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(
        encoding="utf-8"
    )

    assert content.count("ARG PIP_INDEX_URL=https://pypi.org/simple") == 2


def test_dockerfile_maps_oci_metadata_arguments() -> None:
    """测试 OCI Labels 只映射统一传入的元数据."""
    content = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG DATAMIND_BUILD_COMMIT" in content
    assert "ARG DATAMIND_BUILD_COMMIT=dev" not in content
    assert "ARG DATAMIND_BUILD_DATE" in content
    assert 'org.opencontainers.image.title="${DATAMIND_TITLE}"' in content
    assert 'org.opencontainers.image.description="${DATAMIND_DESCRIPTION}"' in content
    assert 'org.opencontainers.image.version="${DATAMIND_VERSION}"' in content
    assert 'org.opencontainers.image.revision="${DATAMIND_BUILD_COMMIT}"' in content
    assert 'org.opencontainers.image.created="${DATAMIND_BUILD_DATE}"' in content
    assert 'org.opencontainers.image.source="${DATAMIND_SOURCE_URL}"' in content
    assert 'org.opencontainers.image.authors="${DATAMIND_AUTHORS}"' in content
    assert 'org.opencontainers.image.vendor="${DATAMIND_VENDOR}"' in content
    assert 'org.opencontainers.image.licenses="${DATAMIND_LICENSES}"' in content
    assert 'org.opencontainers.image.base.digest="${PYTHON_BASE_DIGEST}"' in content
    assert 'DATAMIND_BUILD_COMMIT="${DATAMIND_BUILD_COMMIT}"' in content
    assert 'DATAMIND_BUILD_DATE="${DATAMIND_BUILD_DATE}"' in content


def test_dockerfile_does_not_hardcode_project_metadata() -> None:
    """测试 Dockerfile 不维护第二套项目元数据."""
    content = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    document = pyproject_document()
    configured = document["project"]
    oci = document["tool"]["datamind"]["oci"]

    for author in configured["authors"]:
        assert author["name"] not in content
        assert author["email"] not in content
    for value in [
        configured["description"],
        configured["license"],
        configured["version"],
        *configured["urls"].values(),
        oci["title"],
        oci["vendor"],
    ]:
        assert f'"{value}"' not in content


def test_dockerfile_does_not_use_ref_name_label() -> None:
    """测试 ref.name 不会被误用为普通 Docker LABEL."""
    content = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")

    assert "org.opencontainers.image.ref.name" not in content
