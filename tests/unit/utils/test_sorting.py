"""多字段排序工具测试.

验证排序字段与方向的解析、编码、优先级保留和参数校验行为。

核心功能：
  - test_parse_and_encode_multiple_sort_fields:
    验证多字段排序的解析、规范化和编码
  - test_parse_sort_specs_rejects_invalid_combinations:
    验证拒绝过多、重复、不完整或方向非法的排序参数
"""

import pytest

from datamind.utils.sorting import (
    encode_sort_specs,
    parse_sort_specs,
)


def test_parse_and_encode_multiple_sort_fields() -> None:
    """测试保留多字段排序的优先级和方向."""
    specs = parse_sort_specs(
        sort_by=" status, updated_at ",
        sort_order="asc, DESC",
    )

    assert specs == (
        ("status", "asc"),
        ("updated_at", "desc"),
    )
    assert encode_sort_specs(specs) == (
        "status,updated_at",
        "asc,desc",
    )


@pytest.mark.parametrize(
    ("sort_by", "sort_order", "message"),
    [
        (
            "name,status,updated_at,model_id",
            "asc,asc,desc,asc",
            "最多支持 3 个排序字段",
        ),
        (
            "name,name",
            "asc,desc",
            "排序字段不能重复",
        ),
        (
            "name,status",
            "asc",
            "数量必须一致",
        ),
        (
            "name",
            "random",
            "排序方向只支持 asc 或 desc",
        ),
    ],
)
def test_parse_sort_specs_rejects_invalid_combinations(
        sort_by: str,
        sort_order: str,
        message: str,
) -> None:
    """测试拒绝过多、重复或不完整的排序参数."""
    with pytest.raises(ValueError, match=message):
        parse_sort_specs(
            sort_by=sort_by,
            sort_order=sort_order,
        )
