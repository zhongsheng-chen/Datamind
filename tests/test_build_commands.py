# tests/test_build_commands.py

"""Python 发布包构建命令测试

验证控制台资源未构建时禁止生成不完整的发布包。

核心功能：
  - test_build_requires_console_assets: 验证构建资源检查
  - test_build_commands_validate_console_assets: 验证打包命令调用资源检查
"""

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from setuptools import Distribution

import build_commands


@pytest.mark.parametrize(
    "missing", ["index.html", ".vite/manifest.json", "assets",
                "assets/index-Ab123456.js", "assets/index-ab123456.css", None],
)
def test_build_requires_console_assets(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        missing: str | None,
) -> None:
    """测试入口页面和构建清单引用的文件必须完整存在"""
    monkeypatch.setattr(build_commands, "__file__", str(tmp_path / "build_commands.py"))
    directory = tmp_path / "datamind" / "console" / "dist"
    directory.mkdir(parents=True)
    for name in ["index.html", ".vite/manifest.json", "assets"]:
        if name == missing:
            continue
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name == "assets":
            path.mkdir()
            for filename in ["index-Ab123456.js", "index-ab123456.css"]:
                if f"assets/{filename}" != missing:
                    (path / filename).write_text("content", encoding="utf-8")
        elif name == ".vite/manifest.json":
            path.write_text(json.dumps({
                "index.html": {
                    "file": "assets/index-Ab123456.js",
                    "css": ["assets/index-ab123456.css"],
                },
            }), encoding="utf-8")
        else:
            path.write_text("page", encoding="utf-8")

    if missing is None:
        build_commands._require_console_build()
    else:
        with pytest.raises(RuntimeError, match="npm run build:console"):
            build_commands._require_console_build()


@pytest.mark.parametrize(
    ("command_type", "base_type"),
    [(build_commands.BuildPy, build_commands.build_py),
     (build_commands.Sdist, build_commands.sdist)],
)
def test_build_commands_validate_console_assets(
        monkeypatch: pytest.MonkeyPatch,
        command_type: type,
        base_type: type,
) -> None:
    """测试构建命令先校验控制台资源再执行打包"""
    events = []
    monkeypatch.setattr(
        build_commands, "_require_console_build",
        lambda: events.append("validate"),
    )
    run = Mock(side_effect=lambda: events.append("build"))
    monkeypatch.setattr(base_type, "run", run)

    command_type(Distribution()).run()

    assert events == ["validate", "build"]
