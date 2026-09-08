# build_commands.py

"""Python 发布包构建命令

在打包前检查控制台构建产物，避免发布缺少前端资源的安装包。

核心功能：
  - BuildPy: 构建 Python 包
  - Sdist: 构建源码发行包
"""

import json
from pathlib import Path

from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist


def _require_console_build() -> None:
    """检查控制台入口及构建清单引用的资源是否完整"""
    directory = Path(__file__).parent / "datamind" / "console" / "dist"
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
        complete = all(
            (root / name).resolve().is_relative_to(root)
            and (root / name).is_file()
            for name in files
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        complete = False
    if not complete:
        raise RuntimeError(
            "控制台静态资源未构建或不完整，请先运行 npm ci 和 npm run build:console。"
        )


class BuildPy(build_py):
    """包含控制台构建检查的 Python 包构建命令"""

    def run(self) -> None:
        """检查控制台资源并构建 Python 包"""
        _require_console_build()
        super().run()


class Sdist(sdist):
    """包含控制台构建检查的源码发行包构建命令"""

    def run(self) -> None:
        """检查控制台资源并构建源码发行包"""
        _require_console_build()
        super().run()
