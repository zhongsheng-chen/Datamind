"""Datamind 请求模型参考文档支持.

读取请求模型定义，校验说明和示例并生成参考文档。

核心功能：
  - api_field_description: 读取请求字段说明
  - api_field_rows: 提取请求字段表格数据
  - api_pages: 生成请求模型参考页
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .common import (
    ROOT,
    code,
    reference_metadata,
    render_template,
    schema_type,
    table_rows,
    value_text,
)


def api_field_description(cls: type[BaseModel], field: str, info: FieldInfo) -> str:
    """读取请求模型字段的源码说明.

    参数：
        cls: 请求模型类
        field: 字段名称
        info: Pydantic 字段元数据

    返回：
        统一句末标点后的字段说明

    异常：
        ValueError: 字段缺少说明
    """
    if not info.description:
        raise ValueError(f"Missing API field description: {cls.__name__}.{field}")
    return info.description.rstrip(".。") + "。"


def api_field_rows(
    cls: type[BaseModel], schema: dict[str, Any]
) -> list[tuple[str, ...]]:
    """从请求模型及其 JSON Schema 中提取字段表格数据.

    参数：
        cls: 请求模型类
        schema: 请求模型的 JSON Schema

    返回：
        字段名称、类型、必填标记、默认值、约束及说明组成的表格数据行

    异常：
        ValueError: 字段缺少说明
    """
    rows = []
    for field, info in cls.model_fields.items():
        prop = schema["properties"][field]
        constraints = []
        for variant in [prop, *prop.get("anyOf", [])]:
            constraints.extend(
                f"{key}={value}"
                for key, value in variant.items()
                if key
                in {
                    "minLength",
                    "maxLength",
                    "minItems",
                    "maxItems",
                    "minProperties",
                    "minimum",
                    "maximum",
                }
            )
        default = (
            "—"
            if info.is_required()
            else value_text(info.get_default(call_default_factory=False))
        )
        rows.append(
            (
                code(field),
                code(schema_type(prop, schema)),
                "是" if info.is_required() else "否",
                code(default),
                ", ".join(dict.fromkeys(constraints)) or "—",
                api_field_description(cls, field, info),
            )
        )
    return rows


def api_pages() -> dict[Path, str]:
    """校验请求模型说明及示例并生成运行时请求参考页.

    返回：
        请求模型参考页的路径及 Markdown 内容

    异常：
        ValueError: 模型或字段缺少说明、模型缺少指导元数据，或示例校验失败
    """
    from datamind.runtime.server import schemas

    models = []
    guidance_by_model = reference_metadata()["api_models"]
    for name, cls in vars(schemas).items():
        if (
            not inspect.isclass(cls)
            or cls.__module__ != schemas.__name__
            or not issubclass(cls, BaseModel)
            or name == "RuntimeRequest"
        ):
            continue
        guidance = guidance_by_model.get(name)
        if guidance is None:
            raise ValueError(f"Missing API model guidance: {name}")
        schema = cls.model_json_schema()
        description = str(schema.get("description") or "").strip()
        if not description:
            raise ValueError(f"Missing API model description: {name}")
        try:
            example = cls.model_validate(guidance["example"]).model_dump(
                mode="json", exclude_none=True
            )
        except Exception as exc:
            raise ValueError(f"Invalid API example: {name}") from exc
        models.append(
            render_template(
                "runtime-model",
                name=name,
                description=description.rstrip(".。") + "。",
                endpoints=guidance["endpoints"],
                fields=table_rows(api_field_rows(cls, schema)),
                conditions="\n".join(
                    f"- {condition}" for condition in guidance["conditions"]
                ),
                example_title="实例结构示例："
                if name == "PredictionInstance"
                else "请求对象示例（不含外层 `request`）：",
                example=json.dumps(example, ensure_ascii=False, indent=2),
            )
        )
    return {
        ROOT / "docs/reference/runtime-schemas.md": render_template(
            "runtime-schemas", models="\n".join(models)
        )
    }
