"""命令参考文档测试.

验证命令遍历、源码提取、参数展示和文档渲染。

核心功能：
  - test_walk_reads_typer_nested_commands:
    遍历 Typer 实际生成的命令树，保留分组路径和叶子命令
  - test_command_source_excludes_other_functions:
    命令保留嵌套函数的信息，同时排除同文件中的其他函数
  - test_cli_parameter_rows_formats_choices:
    参数选项为空时保留类型，存在选项时显示可选值
  - test_cli_parameter_rows_formats_enum_choices:
    枚举选项显示实际值，保留可重复参数标记
  - test_render_cli_command_uses_extracted_metadata:
    渲染只依赖传入元数据，无参数命令不生成空表格
"""

from collections.abc import Callable
from enum import Enum
from functools import wraps
import inspect
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import typer

from doc_support.cli import (
    CommandSource,
    cli_parameter_rows,
    command_source,
    render_cli_command,
    walk,
)


def test_walk_reads_typer_nested_commands() -> None:
    """遍历 Typer 实际生成的命令树，保留分组路径和叶子命令."""
    app = typer.Typer()
    group = typer.Typer()
    app.add_typer(group, name="model")

    @group.command()
    def show() -> None:
        """显示模型."""

    entries = list(walk(typer.main.get_command(app)))
    assert len(entries) == 1
    path, command = entries[0]
    assert path == ("model", "show")
    assert inspect.unwrap(command.callback) is show


def test_command_source_excludes_other_functions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    load_source: Callable[[Path], ModuleType],
) -> None:
    """命令保留嵌套函数的信息，同时排除同文件中的其他函数."""
    source = tmp_path / "commands.py"
    source.write_text(
        """def helper():
    authorize(required_permission="unrelated.write")
    result = {"unrelated": True}
    raise ValueError("unrelated error")


def selected():
    async def runner():
        authorize(required_permission="model.write")
        result = {"model_id": "example"}
        raise ValueError("selected error")
    return runner


def other():
    authorize(required_permission="other.write")
    result = {"other": True}
    raise ValueError("other error")
""",
        encoding="utf-8",
    )
    module = load_source(source)
    monkeypatch.setattr("doc_support.cli.ROOT", tmp_path)

    @wraps(module.selected)
    def wrapped():
        return module.selected()

    assert command_source(SimpleNamespace(callback=wrapped)) == CommandSource(
        path=Path("commands.py"),
        permissions=("model.write",),
        errors=("selected error",),
        result_keys=("model_id",),
    )


@pytest.mark.parametrize(
    "choices, expected",
    [(None, "字符串"), ([], "字符串"), (["first", "second"], "first/second")],
)
def test_cli_parameter_rows_formats_choices(
    choices: list[str] | None, expected: str
) -> None:
    """参数选项为空时保留类型，存在选项时显示可选值."""
    parameter = SimpleNamespace(
        opts=["--mode"],
        param_type_name="option",
        type=SimpleNamespace(name="text", choices=choices),
        required=False,
        default="first",
    )
    rows = cli_parameter_rows(SimpleNamespace(params=[parameter]))
    assert rows[0][1] == expected


def test_cli_parameter_rows_formats_enum_choices() -> None:
    """枚举选项显示实际值，保留可重复参数标记."""

    class Mode(Enum):
        FIRST = "first"
        SECOND = "second"

    parameter = SimpleNamespace(
        opts=["--mode"],
        param_type_name="option",
        type=SimpleNamespace(name="choice", choices=list(Mode)),
        required=False,
        default=Mode.FIRST,
        multiple=True,
    )
    rows = cli_parameter_rows(SimpleNamespace(params=[parameter]))
    assert rows[0][1] == "first/second（可重复）"
    assert rows[0][3] == '`"first"`'


def test_render_cli_command_uses_extracted_metadata() -> None:
    """渲染只依赖传入元数据，无参数命令不生成空表格."""
    command = SimpleNamespace(help="查看模型。", params=[])
    source = CommandSource(
        path=Path("commands.py"),
        permissions=("model.read",),
        errors=("invalid model",),
        result_keys=("model_id",),
    )
    text = render_cli_command(("model", "show"), command, source)
    assert "## datamind model show" in text
    assert "权限：`model.read`" in text
    assert "- invalid model" in text
    assert "输出对象字段：`model_id`。" in text
    assert "无额外参数。" in text
    assert "| 参数 |" not in text
