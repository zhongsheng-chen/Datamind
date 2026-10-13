"""请求模型参考文档测试.

验证字段说明读取、缺失说明诊断和表格转义。

核心功能：
  - test_api_field_description_uses_source_metadata:
    测试根据请求模型元数据生成 API 字段说明
  - test_new_undocumented_api_field_fails_generation:
    测试请求字段缺少说明时生成失败
  - test_api_table_escapes_union_and_multiline_description_once:
    可空类型中的竖线与多行说明不会破坏 Markdown 表格
"""

import pytest
from pydantic import BaseModel, Field

from doc_support.api import api_field_description, api_field_rows
from doc_support.common import table_rows


def test_api_field_description_uses_source_metadata() -> None:
    """测试根据请求模型元数据生成 API 字段说明."""

    class DocumentedRequest(BaseModel):
        value: str = Field(description="字段用途")

    assert (
        api_field_description(
            DocumentedRequest,
            "value",
            DocumentedRequest.model_fields["value"],
        )
        == "字段用途。"
    )


def test_new_undocumented_api_field_fails_generation() -> None:
    """测试请求字段缺少说明时生成失败."""

    class UndocumentedRequest(BaseModel):
        value: str

    with pytest.raises(ValueError, match=r"UndocumentedRequest\.value"):
        api_field_description(
            UndocumentedRequest,
            "value",
            UndocumentedRequest.model_fields["value"],
        )


def test_api_table_escapes_union_and_multiline_description_once() -> None:
    """可空类型中的竖线与多行说明不会破坏 Markdown 表格."""

    class Request(BaseModel):
        value: str | None = Field(default=None, description="first | second\nnext")

    text = table_rows(api_field_rows(Request, Request.model_json_schema()))
    assert (
        text
        == "| `value` | `string \\| null` | 否 | `null` | — | first \\| second next。 |"
    )
