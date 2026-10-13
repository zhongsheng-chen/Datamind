"""Datamind 参考文档通用支持.

加载参考文档元数据，渲染模板并格式化文档内容。

核心功能：
  - reference_metadata: 加载参考文档元数据
  - render_template: 填充 Markdown 模板
  - table_rows: 生成 Markdown 表格数据行
  - schema_type: 解析 JSON Schema 类型
"""

from __future__ import annotations

import json
from enum import Enum
from functools import cache
from pathlib import Path
from string import Template
from typing import Any

from pydantic import SecretStr

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://github.com/zhongsheng-chen/Datamind/blob/main/"
ASSETS = Path(__file__).resolve().parent
TEMPLATES = ASSETS / "templates"


@cache
def reference_metadata() -> dict[str, Any]:
    """读取并缓存人工维护的参考文档元数据.

    返回：
        分组、模型说明、配置标题及单位等参考文档元数据
    """
    return json.loads((ASSETS / "metadata.json").read_text(encoding="utf-8"))


def render_template(template_name: str, **context: Any) -> str:
    """渲染 Markdown 模板.

    参数：
        template_name: 模板名称，不含扩展名
        context: 模板占位符对应的值

    返回：
        填充占位符后的 Markdown 文本

    异常：
        KeyError: 模板占位符缺少对应的上下文
    """
    template = Template(
        (TEMPLATES / f"{template_name}.md.tpl").read_text(encoding="utf-8")
    )
    return template.substitute(context)


def cell(value: Any) -> str:
    """转义表格分隔符并将多行内容合并为单行."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def code(value: Any) -> str:
    """将值包装为 Markdown 行内代码."""
    return f"`{value}`"


def table_rows(rows: list[tuple[str, ...]]) -> str:
    """转义单元格并生成 Markdown 表格数据行."""
    return "\n".join(
        "| " + " | ".join(cell(value) for value in row) + " |" for row in rows
    )


def bullet_section(title: str, values: tuple[str, ...] | list[str]) -> str:
    """生成带标题的列表段落，空列表不生成内容."""
    if not values:
        return ""
    return "\n\n" + title + "\n\n" + "\n".join("- " + cell(value) for value in values)


def value_text(value: Any) -> str:
    """将字段默认值序列化为文档展示文本."""
    if isinstance(value, SecretStr):
        value = value.get_secret_value()  # 仅处理字段声明的默认值，不读取运行时配置。
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, Path):
        value = str(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def schema_type(prop: dict[str, Any], schema: dict[str, Any]) -> str:
    """解析 JSON Schema 中的引用、枚举、联合类型和数组类型.

    参数：
        prop: 待解析的字段定义
        schema: 包含引用定义的完整 JSON Schema

    返回：
        用于文档展示的类型文本
    """
    if "$ref" in prop:
        target = prop["$ref"].rsplit("/", 1)[-1]
        definition = schema.get("$defs", {}).get(target, {})
        if "enum" not in definition:
            return target
        prop = definition
    if "enum" in prop:
        return "/".join(str(item) for item in prop["enum"])
    if "anyOf" in prop:
        return " | ".join(schema_type(item, schema) for item in prop["anyOf"])
    if "const" in prop:
        return str(prop["const"])
    kind = prop.get("type", "any")
    if kind == "array":
        return "array[" + schema_type(prop.get("items", {}), schema) + "]"
    return kind + (f" ({prop['format']})" if "format" in prop else "")
