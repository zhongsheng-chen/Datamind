"""Datamind Python 分发包支持.

提供 Python 分发包的命名与发布验证。

核心功能：
  - verify_release_distributions: 验证同一次发布生成的 Python 分发包

使用示例：
  from pathlib import Path

  from build_support.distributions import verify_release_distributions
  from build_support.identity import release_build_identity

  identity = release_build_identity(
      "0123456789abcdef0123456789abcdef01234567",
      "2026-09-23T00:00:00Z",
  )
  wheel, sdist = verify_release_distributions(
      Path("dist"),
      Path.cwd(),
      identity,
  )
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import formataddr
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from typing import Any
import zipfile

from build_support.identity import BuildIdentity, release_build_identity


_FILENAME_SEPARATOR = re.compile(r"[-_.]+")


@dataclass(frozen=True, slots=True)
class PythonDistribution:
    """Python Distribution 文件命名.

    属性：
        name: 名称
        version: 版本
        filename_stem: 发行包名
        wheel_name: Wheel 文件名
        sdist_name: sdist 文件名
    """

    name: str
    version: str

    def __post_init__(self) -> None:
        """校验并规范化 distribution 构建元数据."""
        for field_name in ("name", "version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise RuntimeError(
                    f"缺少有效的 project.{field_name}"
                )
            object.__setattr__(self, field_name, value.strip())

    @property
    def filename_stem(self) -> str:
        """生成分发包文件名使用的规范化项目名."""
        return _FILENAME_SEPARATOR.sub("_", self.name.lower())

    @property
    def wheel_name(self) -> str:
        """生成 Wheel 文件名."""
        return f"{self.filename_stem}-{self.version}-py3-none-any.whl"

    @property
    def sdist_name(self) -> str:
        """生成 sdist 文件名."""
        return f"{self.filename_stem}-{self.version}.tar.gz"


def _project_metadata(pyproject_path: Path) -> dict[str, Any]:
    """读取 pyproject.toml 中的正式项目元数据."""
    with pyproject_path.open("rb") as pyproject_file:
        document = tomllib.load(pyproject_file)

    project = document.get("project")
    if not isinstance(project, dict):
        raise RuntimeError(
            "pyproject.toml 缺少有效的 project"
        )

    return project


def _required_string(value: object, location: str) -> str:
    """读取并规范化必填字符串."""
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(
            f"缺少有效的 {location}"
        )

    return value.strip()


def _verify_package_metadata(
    content: bytes,
    project: dict[str, Any],
) -> None:
    """验证 Core Metadata 与项目正式配置一致."""
    from packaging.specifiers import SpecifierSet

    metadata = BytesParser(policy=policy.default).parsebytes(content)
    authors = project.get("authors")
    if not isinstance(authors, list):
        raise RuntimeError(
            "pyproject.toml 缺少有效的 project.authors"
        )

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

    scalar_fields = {
        "Name": project["name"],
        "Version": project["version"],
        "Summary": project["description"],
        "License-Expression": project["license"],
    }
    for name, expected in scalar_fields.items():
        if metadata[name] != expected:
            raise RuntimeError(
                f"分发包元数据 {name} 与 pyproject.toml 不一致"
            )

    list_fields = {
        "Classifier": project.get("classifiers", []),
        "Author-email": expected_author_emails,
        "Author": expected_authors,
    }
    for name, expected in list_fields.items():
        if metadata.get_all(name, []) != expected:
            raise RuntimeError(
                f"分发包 {name} 与 pyproject.toml 不一致"
            )

    requires_python = SpecifierSet(metadata["Requires-Python"])
    expected_python = SpecifierSet(project["requires-python"])
    if requires_python != expected_python:
        raise RuntimeError(
            "分发包 Requires-Python 与 pyproject.toml 不一致"
        )

    if "LICENSE" not in metadata.get_all("License-File", []):
        raise RuntimeError(
            "分发包元数据缺少 LICENSE"
        )


def _verify_license(content: str, project_root: Path) -> None:
    """验证分发包中的许可证内容并忽略平台换行符差异."""
    expected = (project_root / "LICENSE").read_text(encoding="utf-8")
    if content.splitlines() != expected.splitlines():
        raise RuntimeError(
            "分发包中的 LICENSE 与源码许可证不一致"
        )


def _read_build_identity(content: str, location: str) -> BuildIdentity:
    """读取分发包中记录的构建身份."""
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
        raise RuntimeError(
            f"{location} 中的构建身份无效"
        ) from error

    if not isinstance(commit, str) or not isinstance(build_date, str):
        raise RuntimeError(
            f"{location} 中的构建身份不完整"
        )

    return release_build_identity(commit, build_date)


def _verify_identity(
    content: str,
    expected: BuildIdentity,
    location: str,
) -> None:
    """验证分发包的构建身份与发布元数据一致."""
    if _read_build_identity(content, location) != expected:
        raise RuntimeError(
            f"{location} 中的构建身份与 Release 不一致"
        )


def _required_zip_entry(
    names: list[str],
    suffix: str,
) -> str:
    """查找 Wheel 中以指定路径结尾的必需文件."""
    entry = next((name for name in names if name.endswith(suffix)), None)
    if entry is None:
        raise RuntimeError(
            f"Wheel 中缺少以 {suffix} 结尾的必需文件"
        )

    return entry


def _verify_wheel(
    wheel: Path,
    project: dict[str, Any],
    project_root: Path,
    identity: BuildIdentity,
) -> None:
    """验证 Wheel 标签、元数据、许可证与构建身份."""
    if not wheel.name.endswith("-py3-none-any.whl"):
        raise RuntimeError(
            "正式 Wheel 必须使用 py3-none-any 标签"
        )

    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        metadata_name = _required_zip_entry(
            names,
            ".dist-info/METADATA",
        )
        license_name = _required_zip_entry(
            names,
            ".dist-info/licenses/LICENSE",
        )
        if "datamind/_build.py" not in names:
            raise RuntimeError(
                "Wheel 缺少 datamind/_build.py"
            )

        if any(name.startswith("build_support/") for name in names):
            raise RuntimeError(
                "Wheel 不应包含 build_support"
            )

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


def _required_tar_member(
    members: list[tarfile.TarInfo],
    suffix: str,
) -> tarfile.TarInfo:
    """查找 sdist 中以指定路径结尾的必需文件."""
    member = next((item for item in members if item.name.endswith(suffix)), None)
    if member is None:
        raise RuntimeError(
            f"sdist 中缺少以 {suffix} 结尾的必需文件"
        )

    return member


def _read_tar_member(
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
) -> bytes:
    """读取 sdist 文件成员."""
    member_file = archive.extractfile(member)
    if member_file is None:
        raise RuntimeError(
            "无法读取 sdist 发布文件"
        )

    return member_file.read()


def _extract_and_verify_sdist(
    sdist: Path,
    project: dict[str, Any],
    project_root: Path,
    identity: BuildIdentity,
    extraction_root: Path,
) -> Path:
    """验证 sdist 内容并将源码解压到临时目录."""
    source_root = extraction_root / "source"

    with tarfile.open(sdist, "r:gz") as archive:
        members = archive.getmembers()
        metadata_member = _required_tar_member(members, "/PKG-INFO")
        license_member = _required_tar_member(members, "/LICENSE")
        identity_member = _required_tar_member(members, "/datamind/_build.py")
        _required_tar_member(members, "/build_support/identity.py")

        _verify_package_metadata(
            _read_tar_member(archive, metadata_member),
            project,
        )
        _verify_license(
            _read_tar_member(archive, license_member).decode("utf-8"),
            project_root,
        )
        _verify_identity(
            _read_tar_member(archive, identity_member).decode("utf-8"),
            identity,
            f"{sdist.name}:datamind/_build.py",
        )

        source_root.mkdir()
        archive.extractall(source_root, filter="data")

    return next(source_root.iterdir())


def _rebuild_wheel(source_root: Path, rebuild_root: Path) -> Path:
    """从解压后的 sdist 源码重建 Wheel."""
    rebuilt_directory = rebuild_root / "wheel"
    environment = os.environ.copy()
    environment.pop("DATAMIND_BUILD_COMMIT", None)
    environment.pop("DATAMIND_BUILD_DATE", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            str(source_root),
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
        raise RuntimeError(
            "从 sdist 重建后未得到唯一 Wheel"
        )

    return rebuilt[0]


def _verify_sdist(
    sdist: Path,
    project: dict[str, Any],
    project_root: Path,
    identity: BuildIdentity,
    rebuild_root: Path,
) -> Path:
    """验证 sdist，并从中重建 Wheel."""
    source_root = _extract_and_verify_sdist(
        sdist,
        project,
        project_root,
        identity,
        rebuild_root,
    )
    return _rebuild_wheel(source_root, rebuild_root)


def verify_release_distributions(
    distribution_directory: Path,
    project_root: Path,
    identity: BuildIdentity,
) -> tuple[Path, Path]:
    """验证用于发布的 Wheel、sdist 及 sdist 重建结果.

    参数：
        distribution_directory: 包含待验证 Wheel 和 sdist 的目录
        project_root: Datamind 项目根目录
        identity: 本次发布统一使用的构建身份

    返回：
        已通过验证的 Wheel 与 sdist 路径

    异常：
        RuntimeError: 分发包数量、标签、元数据或重建结果不符合要求
    """
    project = _project_metadata(project_root / "pyproject.toml")
    python_distribution = PythonDistribution(
        name=_required_string(project.get("name"), "project.name"),
        version=_required_string(project.get("version"), "project.version"),
    )
    expected_wheel = distribution_directory / python_distribution.wheel_name
    expected_sdist = distribution_directory / python_distribution.sdist_name

    wheels = list(distribution_directory.glob("*.whl"))
    sdists = list(distribution_directory.glob("*.tar.gz"))
    if wheels != [expected_wheel] or sdists != [expected_sdist]:
        raise RuntimeError(
            "发布目录必须且只能包含预期的 Wheel 与 sdist"
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
