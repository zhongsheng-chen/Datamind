"""Datamind Python 发布制品验证

验证 Wheel、sdist 与 sdist 重建 Wheel 的元数据、许可证和构建身份。

核心功能：
  - verify_release_artifacts: 验证同一次正式发布生成的 Python 制品

使用示例：
  identity = release_build_identity(commit, build_date)
  wheel, sdist = verify_release_artifacts(
      Path("dist"),
      Path.cwd(),
      identity,
  )
"""

from __future__ import annotations

import ast
from email import policy
from email.parser import BytesParser
from email.utils import formataddr
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from typing import Any
import zipfile

from packaging.specifiers import SpecifierSet

from .identity import BuildIdentity, release_build_identity


def _project_metadata(pyproject_path: Path) -> dict[str, Any]:
    """读取 pyproject.toml 中的正式项目元数据。"""
    with pyproject_path.open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    project = document.get("project")
    if not isinstance(project, dict):
        raise RuntimeError("pyproject.toml 缺少有效的 project")

    return project


def _verify_package_metadata(
    content: bytes,
    project: dict[str, Any],
) -> None:
    """验证 Core Metadata 与项目正式配置一致。"""
    metadata = BytesParser(policy=policy.default).parsebytes(content)
    authors = project.get("authors")
    if not isinstance(authors, list):
        raise RuntimeError("pyproject.toml 缺少有效的 project.authors")

    expected_author_emails = [
        formataddr((author["name"], author["email"]))
        for author in authors
        if "email" in author
    ]
    expected_authors = [
        author["name"]
        for author in authors
        if "email" not in author
    ]

    checks = {
        "Name": project["name"],
        "Version": project["version"],
        "Summary": project["description"],
        "License-Expression": project["license"],
    }
    for name, expected in checks.items():
        if metadata[name] != expected:
            raise RuntimeError(
                f"发布包元数据 {name} 与 pyproject.toml 不一致"
            )

    if metadata.get_all("Classifier", []) != project.get("classifiers", []):
        raise RuntimeError("发布包 Classifier 与 pyproject.toml 不一致")
    if metadata.get_all("Author-email", []) != expected_author_emails:
        raise RuntimeError("发布包 Author-email 与 pyproject.toml 不一致")
    if metadata.get_all("Author", []) != expected_authors:
        raise RuntimeError("发布包 Author 与 pyproject.toml 不一致")
    if SpecifierSet(metadata["Requires-Python"]) != SpecifierSet(
        project["requires-python"]
    ):
        raise RuntimeError("发布包 Requires-Python 与 pyproject.toml 不一致")
    if "LICENSE" not in metadata.get_all("License-File", []):
        raise RuntimeError("发布包元数据缺少 LICENSE")


def _verify_license(content: str, project_root: Path) -> None:
    """验证发布包许可证内容并忽略平台换行符差异。"""
    expected = (project_root / "LICENSE").read_text(encoding="utf-8")
    if content.splitlines() != expected.splitlines():
        raise RuntimeError("发布包 LICENSE 与源码许可证不一致")


def _read_build_identity(content: str, location: str) -> BuildIdentity:
    """读取发布包中固化的构建身份。"""
    try:
        tree = ast.parse(content, filename=location)
        values: dict[str, object] = {}
        for statement in tree.body:
            if (
                isinstance(statement, ast.AnnAssign)
                and isinstance(statement.target, ast.Name)
                and statement.target.id in {"BUILD_COMMIT", "BUILD_DATE"}
                and statement.value is not None
            ):
                values[statement.target.id] = ast.literal_eval(statement.value)
        commit = values["BUILD_COMMIT"]
        build_date = values["BUILD_DATE"]
    except (SyntaxError, ValueError, KeyError) as error:
        raise RuntimeError(f"{location} 中的构建身份无效") from error

    if not isinstance(commit, str) or not isinstance(build_date, str):
        raise RuntimeError(f"{location} 中的构建身份不完整")

    return release_build_identity(commit, build_date)


def _verify_identity(
    content: str,
    expected: BuildIdentity,
    location: str,
) -> None:
    """验证发布包构建身份与正式发布元数据一致。"""
    if _read_build_identity(content, location) != expected:
        raise RuntimeError(f"{location} 中的构建身份与 Release 不一致")


def _verify_wheel(
    wheel: Path,
    project: dict[str, Any],
    project_root: Path,
    identity: BuildIdentity,
) -> None:
    """验证 Wheel 标签、元数据、许可证与构建身份。"""
    if not wheel.name.endswith("-py3-none-any.whl"):
        raise RuntimeError("正式 Wheel 必须使用 py3-none-any 标签")

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")),
            None,
        )
        license_name = next(
            (
                name
                for name in names
                if name.endswith(".dist-info/licenses/LICENSE")
            ),
            None,
        )
        if metadata_name is None or license_name is None:
            raise RuntimeError("Wheel 缺少 METADATA 或 LICENSE")
        if "datamind/_build.py" not in names:
            raise RuntimeError("Wheel 缺少 datamind/_build.py")
        if any(name.startswith("build_support/") for name in names):
            raise RuntimeError("Wheel 不应包含 build_support")

        _verify_package_metadata(archive.read(metadata_name), project)
        _verify_license(
            archive.read(license_name).decode("utf-8"),
            project_root,
        )
        _verify_identity(
            archive.read("datamind/_build.py").decode("utf-8"),
            identity,
            f"{wheel.name}:datamind/_build.py",
        )


def _verify_sdist(
    sdist: Path,
    project: dict[str, Any],
    project_root: Path,
    identity: BuildIdentity,
    rebuild_root: Path,
) -> Path:
    """验证 sdist，并从中重建 Wheel。"""
    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        metadata_member = next(
            (item for item in members if item.name.endswith("/PKG-INFO")),
            None,
        )
        license_member = next(
            (item for item in members if item.name.endswith("/LICENSE")),
            None,
        )
        identity_member = next(
            (
                item
                for item in members
                if item.name.endswith("/datamind/_build.py")
            ),
            None,
        )
        support_member = next(
            (
                item
                for item in members
                if item.name.endswith("/build_support/identity.py")
            ),
            None,
        )
        if any(
            item is None
            for item in (
                metadata_member,
                license_member,
                identity_member,
                support_member,
            )
        ):
            raise RuntimeError("sdist 缺少发布元数据、许可证或构建支持文件")

        assert metadata_member is not None
        assert license_member is not None
        assert identity_member is not None
        metadata_file = archive.extractfile(metadata_member)
        license_file = archive.extractfile(license_member)
        identity_file = archive.extractfile(identity_member)
        if metadata_file is None or license_file is None or identity_file is None:
            raise RuntimeError("无法读取 sdist 发布文件")

        _verify_package_metadata(metadata_file.read(), project)
        _verify_license(license_file.read().decode("utf-8"), project_root)
        _verify_identity(
            identity_file.read().decode("utf-8"),
            identity,
            f"{sdist.name}:datamind/_build.py",
        )

        source_root = rebuild_root / "source"
        source_root.mkdir()
        archive.extractall(source_root, filter="data")

    extracted = next(source_root.iterdir())
    rebuilt_directory = rebuild_root / "wheel"
    environment = os.environ.copy()
    environment.pop("DATAMIND_BUILD_COMMIT", None)
    environment.pop("DATAMIND_BUILD_DATE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            str(extracted),
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(rebuilt_directory),
        ],
        cwd=rebuild_root,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "从 sdist 重建 Wheel 失败：\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    rebuilt = list(rebuilt_directory.glob("*.whl"))
    if len(rebuilt) != 1:
        raise RuntimeError("从 sdist 重建后未得到唯一 Wheel")

    return rebuilt[0]


def verify_release_artifacts(
    distribution_directory: Path,
    project_root: Path,
    identity: BuildIdentity,
) -> tuple[Path, Path]:
    """验证正式 Wheel、sdist 及 sdist 重建结果。

    参数：
        distribution_directory: 包含正式发布制品的目录
        project_root: Datamind 项目根目录
        identity: 本次正式发布统一使用的构建身份

    返回：
        已通过验证的 Wheel 与 sdist 路径

    异常：
        RuntimeError: 制品数量、标签、元数据或重建结果不符合要求
    """
    project = _project_metadata(project_root / "pyproject.toml")
    distribution = str(project["name"]).replace("-", "_")
    version = str(project["version"])
    expected_wheel = distribution_directory / (
        f"{distribution}-{version}-py3-none-any.whl"
    )
    expected_sdist = distribution_directory / f"{project['name']}-{version}.tar.gz"

    wheels = list(distribution_directory.glob("*.whl"))
    sdists = list(distribution_directory.glob("*.tar.gz"))
    if wheels != [expected_wheel] or sdists != [expected_sdist]:
        raise RuntimeError(
            "正式发布目录必须且只能包含预期的 Wheel 与 sdist"
        )

    _verify_wheel(expected_wheel, project, project_root, identity)

    with tempfile.TemporaryDirectory(prefix="datamind-sdist-") as temporary:
        rebuilt = _verify_sdist(
            expected_sdist,
            project,
            project_root,
            identity,
            Path(temporary),
        )
        _verify_wheel(rebuilt, project, project_root, identity)

    return expected_wheel, expected_sdist
