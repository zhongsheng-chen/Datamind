"""Python 分发包构建命令.

负责校验控制台静态资源，并在 Wheel 与 sdist 的临时构建目录中写入
构建身份，保持源码工作区不变。

核心功能：
  - BuildPy: 校验控制台资源，并构建包含构建身份的 Wheel
  - Sdist: 在临时源码发行目录中固化相同的构建身份

使用示例：
  DATAMIND_BUILD_COMMIT="$(git rev-parse HEAD)" \
  DATAMIND_BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  python -m build
"""

import ast
import json
import os
from pathlib import Path
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

from build_support.identity import BuildIdentity, release_build_identity


_BUILD_COMMIT_ENVIRONMENT = "DATAMIND_BUILD_COMMIT"
_BUILD_DATE_ENVIRONMENT = "DATAMIND_BUILD_DATE"


def _project_root() -> Path:
    """定位构建支持包所在的项目根目录."""
    return Path(__file__).resolve().parents[2]


def _source_build_metadata() -> Path:
    """定位源码树中的构建元数据模块."""
    return _project_root() / "datamind" / "_build.py"


def _require_console_build() -> None:
    """验证控制台入口、构建清单及其引用的静态资源.

    异常：
        RuntimeError: 控制台构建产物缺失、不完整或包含越界路径
    """
    directory = _project_root() / "datamind" / "console" / "dist"

    try:
        manifest = json.loads(
            (directory / ".vite" / "manifest.json").read_text(encoding="utf-8")
        )
        files = {"index.html", manifest["index.html"]["file"]}

        for chunk in manifest.values():
            files.add(chunk["file"])
            files.update(chunk.get("css", []))
            files.update(chunk.get("assets", []))

        root = directory.resolve()
        complete = True

        for name in files:
            asset = root / name
            if not asset.resolve().is_relative_to(root) or not asset.is_file():
                complete = False
                break
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        complete = False

    if not complete:
        raise RuntimeError(
            "控制台静态资源未构建或不完整，请先运行 npm ci 和 npm run build:console。"
        )


def _embedded_build_identity(path: Path) -> BuildIdentity | None:
    """从源码树或 sdist 中读取已固化的构建身份.

    参数：
        path: 构建元数据模块的路径

    返回：
        元数据模块记录的正式构建身份；开发源码返回 ``None``

    异常：
        RuntimeError: 元数据模块无效或构建身份不完整
    """
    if not path.is_file():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(path))
        values: dict[str, object] = {}

        for statement in tree.body:
            if not isinstance(statement, ast.AnnAssign):
                continue

            target = statement.target
            if (
                isinstance(target, ast.Name)
                and target.id
                in {
                    "BUILD_COMMIT",
                    "BUILD_DATE",
                }
                and statement.value is not None
            ):
                values[target.id] = ast.literal_eval(statement.value)

        commit = values["BUILD_COMMIT"]
        build_date = values["BUILD_DATE"]
    except (OSError, SyntaxError, ValueError, KeyError) as error:
        raise RuntimeError(f"{path} 中的构建元数据无效") from error

    if commit == "dev" and build_date is None:
        return None

    if not isinstance(commit, str) or not isinstance(build_date, str):
        raise RuntimeError(f"{path} 中的构建元数据不完整")

    return release_build_identity(commit, build_date)


def _build_identity() -> BuildIdentity | None:
    """解析显式构建输入，未提供时继承现有构建身份.

    返回：
        本次构建使用的正式构建身份；开发构建返回 ``None``

    异常：
        RuntimeError: 构建环境变量不完整或不符合正式构建要求
    """
    commit = os.getenv(_BUILD_COMMIT_ENVIRONMENT)
    build_date = os.getenv(_BUILD_DATE_ENVIRONMENT)

    if commit is None and build_date is None:
        return _embedded_build_identity(_source_build_metadata())

    if commit is None or build_date is None:
        message = "DATAMIND_BUILD_COMMIT 与 DATAMIND_BUILD_DATE 必须同时设置"
        raise RuntimeError(message)

    return release_build_identity(commit, build_date)


def _write_build_metadata(
    path: Path,
    identity: BuildIdentity | None,
) -> None:
    """以稳定格式将构建身份写入 UTF-8 Python 模块.

    参数：
        path: 目标构建元数据模块的路径
        identity: 写入分发包的正式构建身份；开发构建使用 ``None``
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if identity is None:
        commit = "dev"
        build_date = "None"
    else:
        commit = identity.commit
        build_date = f'"{identity.build_date}"'

    path.write_text(
        '"""Datamind build metadata."""\n\n'
        f'BUILD_COMMIT: str = "{commit}"\n'
        f"BUILD_DATE: str | None = {build_date}\n",
        encoding="utf-8",
        newline="\n",
    )


class BuildPy(build_py):
    """为 Wheel 构建校验控制台资源并注入构建身份."""

    def run(self) -> None:
        """执行标准包构建，并在临时输出目录写入构建元数据."""
        _require_console_build()
        identity = _build_identity()

        super().run()

        _write_build_metadata(
            Path(self.build_lib) / "datamind" / "_build.py",
            identity,
        )


class Sdist(sdist):
    """为 sdist 构建校验控制台资源并保留构建身份."""

    _datamind_build_identity: BuildIdentity | None = None

    def run(self) -> None:
        """校验控制台资源与构建身份，并生成源码发行包."""
        _require_console_build()
        self._datamind_build_identity = _build_identity()

        super().run()

    def make_release_tree(
        self,
        base_dir: str,
        files: list[str],
    ) -> None:
        """在临时源码发行目录中写入构建元数据.

        参数：
            base_dir: setuptools 创建的临时源码发行目录
            files: 需要复制到该目录的源码文件
        """
        super().make_release_tree(base_dir, files)

        identity = self._datamind_build_identity or _build_identity()

        _write_build_metadata(
            Path(base_dir) / "datamind" / "_build.py",
            identity,
        )
