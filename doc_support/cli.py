"""Datamind 命令参考文档支持.

读取命令定义和源码信息，生成命令参考文档。

核心功能：
  - CommandSource: 记录命令源码信息
  - walk: 遍历命令树
  - command_source: 提取命令源码信息
  - cli_pages: 生成命令参考页和索引页
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, cast

import typer

from .common import (
    ROOT,
    SOURCE_URL,
    bullet_section,
    code,
    reference_metadata,
    render_template,
    table_rows,
    value_text,
)


@dataclass(frozen=True)
class CommandSource:
    """记录从命令源码提取的信息.

    属性：
        path: 相对于项目根目录的源码路径
        permissions: 命令要求的资源权限，按名称排序
        errors: 命令及其嵌套函数中显式抛出的静态错误消息
        result_keys: 显式赋给 result 的字典字段，按名称排序
    """

    path: Path
    permissions: tuple[str, ...]
    errors: tuple[str, ...]
    result_keys: tuple[str, ...]


def walk(
    command: Any, path: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], Any]]:
    """递归遍历 Click 命令树，返回叶子命令及其路径.

    参数：
        command: 待遍历的命令或命令分组
        path: 当前命令路径，默认从根命令开始

    返回：
        依次产生命令路径及叶子命令的迭代器
    """
    if hasattr(command, "commands"):
        for name, child in command.commands.items():
            yield from walk(child, (*path, name))
    else:
        yield path, command


def cli_group(path: tuple[str, ...]) -> str:
    """根据命令路径确定参考文档分组.

    参数：
        path: 不含程序名称的叶子命令路径

    返回：
        参考文档分组名称
    """
    if path[:2] == ("experiment", "variant"):
        return "variant"
    return {
        "route": "routing",
        "user": "identity",
        "role": "identity",
        "service": "processes",
        "worker": "processes",
        "console": "processes",
        "runtime": "processes",
    }.get(
        path[0], path[0] if path[0] in reference_metadata()["cli_groups"] else "system"
    )


def command_source(command: Any) -> CommandSource:
    """提取命令回调及其嵌套函数中的源码元数据.

    参数：
        command: 包含回调函数的 CLI 命令

    返回：
        命令源码路径、权限、显式校验消息及输出字段

    异常：
        ValueError: 无法定位命令回调的源码文件
    """
    callback = inspect.unwrap(command.callback)
    source_file = inspect.getsourcefile(callback)
    if source_file is None:
        raise ValueError(f"无法定位命令源码：{callback.__qualname__}")
    source_path = Path(source_file).relative_to(ROOT)
    tree = ast.parse(textwrap.dedent(inspect.getsource(callback)))
    permission_values: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            value = keyword.value
            if (
                keyword.arg == "required_permission"
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
            ):
                permission_values.add(value.value)
    errors = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and node.exc.args
        ):
            arg = node.exc.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if arg.value not in errors:
                    errors.append(arg.value)
    # 仅提取显式赋给 result 的字典字段，避免混入请求和配置字段。
    keys: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "result" for t in node.targets)
            and isinstance(node.value, ast.Dict)
        ):
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return CommandSource(
        path=source_path,
        permissions=tuple(sorted(permission_values)),
        errors=tuple(errors),
        result_keys=tuple(sorted(keys)),
    )


def cli_parameter_rows(command: Any) -> list[tuple[str, ...]]:
    """从 Click 参数定义中提取名称、类型、默认值和说明.

    参数：
        command: 待提取参数定义的 CLI 命令

    返回：
        参数名称、类型、必填标记、默认值及说明组成的表格数据行
    """
    rows = []
    for param in command.params:
        opts = "/".join([*param.opts, *getattr(param, "secondary_opts", [])])
        if param.param_type_name == "argument":
            opts = "<" + param.name + ">"
        type_name = getattr(param.type, "name", "text")
        kind = {
            "text": "字符串",
            "integer": "整数",
            "float": "数值",
            "boolean": "布尔",
            "path": "路径",
            "integer range": "整数范围",
        }.get(type_name, type_name)
        choices = getattr(param.type, "choices", None)
        if isinstance(choices, Iterable) and choices:
            kind = "/".join(
                str(cast(Any, choice.value))
                if isinstance(choice, Enum)
                else str(choice)
                for choice in choices
            )
        if getattr(param, "multiple", False):
            kind += "（可重复）"
        default = "—" if param.required else value_text(param.default)
        rows.append(
            (
                code(opts),
                kind,
                "是" if param.required else "否",
                code(default),
                getattr(param, "help", "") or "",
            )
        )
    return rows


def render_cli_command(
    path: tuple[str, ...], command: Any, source: CommandSource
) -> str:
    """根据命令参数及源码元数据渲染命令参考文档.

    参数：
        path: 不含程序名称的命令路径
        command: 待渲染的 CLI 命令
        source: 从命令源码提取的信息

    返回：
        命令参考文档的 Markdown 文本
    """
    name = "datamind " + " ".join(path)
    positional = [
        param for param in command.params if param.param_type_name == "argument"
    ]
    usage = (
        name
        + "".join(
            f" <{param.name}>" if param.required else f" [<{param.name}>]"
            for param in positional
        )
        + " [OPTIONS]"
    )
    rows = cli_parameter_rows(command)
    parameters = (
        render_template("cli-parameters", rows=table_rows(rows)).rstrip("\n")
        if rows
        else "无额外参数。\n"
    )
    output_fields = (
        "\n\n输出对象字段：" + "、".join(code(key) for key in source.result_keys) + "。"
        if source.result_keys
        else ""
    )
    return render_template(
        "cli-command",
        name=name,
        description=(command.help or "").strip().rstrip(".。") + "。",
        permissions=", ".join(code(permission) for permission in source.permissions)
        or "无需资源权限",
        source_url=SOURCE_URL + source.path.as_posix(),
        usage=usage,
        parameters=parameters,
        validation=bullet_section("输入校验（命令函数内的显式检查）：", source.errors),
        output_fields=output_fields,
    )


def cli_pages() -> dict[Path, str]:
    """按命令分组生成 CLI 参考页和索引页.

    返回：
        命令参考页和索引页的路径及 Markdown 内容
    """
    from datamind.cli.main import app

    entries = list(walk(typer.main.get_command(app)))
    pages = {}
    groups = []
    for group, metadata in reference_metadata()["cli_groups"].items():
        commands = [
            (path, command) for path, command in entries if cli_group(path) == group
        ]
        groups.append((f"[{metadata['title']}]({group}.md)", str(len(commands))))
        rendered = [
            render_cli_command(path, command, command_source(command))
            for path, command in commands
        ]
        pages[ROOT / "docs/cli" / f"{group}.md"] = (
            render_template(
                "cli-group", **metadata, commands="\n".join(rendered)
            ).rstrip()
            + "\n"
        )
    pages[ROOT / "docs/cli/index.md"] = render_template(
        "cli-index", groups=table_rows(groups), command_count=len(entries)
    )
    return pages
