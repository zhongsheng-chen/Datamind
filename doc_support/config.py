"""Datamind 配置参考文档支持.

读取配置定义和源码说明，生成环境变量参考文档。

核心功能：
  - documented_attributes: 读取文档字符串中的属性说明
  - config_description: 读取配置字段说明
  - config_validators: 提取配置校验消息
  - config_pages: 生成环境变量参考页
"""

from __future__ import annotations

import ast
import importlib
import json
import inspect
import re
import textwrap
from pathlib import Path

from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings

from .common import (
    ROOT,
    SOURCE_URL,
    bullet_section,
    code,
    reference_metadata,
    render_template,
    schema_type,
    table_rows,
    value_text,
)


def documented_attributes(docstring: str | None) -> dict[str, str]:
    """读取文档字符串中的属性及环境变量说明，移除默认值描述.

    参数：
        docstring: 类或模块的文档字符串，可以为空

    返回：
        属性或环境变量名称及说明，不含重复的默认值描述
    """
    lines = (docstring or "").splitlines()
    descriptions = {}
    for index, line in enumerate(lines):
        match = re.match(r"\s*-\s*([a-zA-Z_][a-zA-Z_0-9]*):\s*(.*)$", line)
        if not match:
            continue
        key, description = match.groups()
        if not description and index + 1 < len(lines):
            continuation = lines[index + 1]
            if continuation.startswith(" ") and not continuation.lstrip().startswith(
                "-"
            ):
                description = continuation.strip()
        if description:
            descriptions[key] = re.sub(r"[，,]\s*默认.*$", "", description)
    return descriptions


def config_description(cls: type[BaseSettings], field: str, info: FieldInfo) -> str:
    """按字段、类和模块的优先级读取配置说明.

    参数：
        cls: 配置类
        field: 字段名称
        info: Pydantic 字段元数据

    返回：
        配置说明及人工维护的单位补充说明

    异常：
        ValueError: 字段缺少说明
    """
    module = inspect.getmodule(cls)
    class_docs = documented_attributes(cls.__doc__)
    module_docs = documented_attributes(module.__doc__ if module else None)
    env_name = cls.model_config["env_prefix"] + field.upper()
    description = (
        info.description
        or class_docs.get(field)
        or module_docs.get(field)
        or module_docs.get(env_name)
    )
    if not description:
        raise ValueError(f"Missing configuration description: {cls.__name__}.{field}")
    note = reference_metadata()["config_units"].get(cls.__name__, {}).get(field, "")
    return description.rstrip("。") + "。" + note


def config_field_rows(cls: type[BaseSettings]) -> list[tuple[str, ...]]:
    """提取配置类的环境变量、类型、默认值和说明.

    参数：
        cls: 配置类

    返回：
        环境变量名称、类型、默认值及说明组成的表格数据行，不含嵌套配置

    异常：
        ValueError: 字段缺少说明
    """
    schema = cls.model_json_schema()
    rows = []
    for field, info in cls.model_fields.items():
        if inspect.isclass(info.annotation) and issubclass(
            info.annotation, BaseSettings
        ):
            continue
        default = (
            "必需"
            if info.is_required()
            else value_text(info.get_default(call_default_factory=False))
        )
        if default.startswith('"') and default != '""':
            default = json.loads(default)
        rows.append(
            (
                code(cls.model_config["env_prefix"] + field.upper()),
                code(schema_type(schema["properties"][field], schema)),
                code(default),
                config_description(cls, field, info),
            )
        )
    return rows


def config_validators(cls: type[BaseSettings]) -> list[str]:
    """提取配置类中显式抛出的校验消息.

    参数：
        cls: 配置类

    返回：
        从异常首个参数提取的校验消息，格式化字符串仅保留静态文本
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
    validators = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Raise)
            and isinstance(node.exc, ast.Call)
            and node.exc.args
        ):
            continue
        arg = node.exc.args[0]
        message = ""
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            message = arg.value
        elif isinstance(arg, ast.JoinedStr):
            fragments: list[str] = []
            for value in arg.values:
                if not isinstance(value, ast.Constant):
                    continue
                text = value.value
                if isinstance(text, str):
                    fragments.append(text)
            message = "".join(fragments)
        if message and message not in validators:
            validators.append(message.split("当前值")[0].rstrip("，:： "))
    return validators


def config_pages() -> dict[Path, str]:
    """遍历配置模块并生成环境变量参考页.

    返回：
        环境变量参考页的路径及 Markdown 内容

    异常：
        ValueError: 配置字段缺少说明
    """
    sections = []
    titles = reference_metadata()["config_titles"]
    paths: list[Path] = sorted(
        (ROOT / "datamind/config").glob("*.py"),
        key=lambda source_path: source_path.name,
    )
    for path in paths:
        if path.stem in {"__init__", "settings", "providers"}:
            continue
        module = importlib.import_module("datamind.config." + path.stem)
        for name, cls in vars(module).items():
            if (
                not inspect.isclass(cls)
                or cls.__module__ != module.__name__
                or not issubclass(cls, BaseSettings)
            ):
                continue
            sections.append(
                render_template(
                    "config-section",
                    title=titles.get(name, name),
                    prefix=cls.model_config["env_prefix"],
                    source_url=SOURCE_URL + f"datamind/config/{path.name}",
                    fields=table_rows(config_field_rows(cls)),
                    validation=bullet_section("校验规则：", config_validators(cls)),
                )
            )
    return {
        ROOT / "docs/reference/environment-variables.md": render_template(
            "environment-variables", sections="\n".join(sections)
        )
    }
