"""多字段排序工具.

提供排序字段与方向的解析、校验和编码能力，
用于在接口参数和有序排序规则之间转换。

核心功能：
  - parse_sort_specs: 解析并校验多字段排序参数
  - encode_sort_specs: 将排序规则编码为接口参数

使用示例：
  from datamind.utils.sorting import (
      encode_sort_specs,
      parse_sort_specs,
  )

  specs = parse_sort_specs(
      sort_by="status,updated_at",
      sort_order="asc,desc",
  )
  sort_by, sort_order = encode_sort_specs(
      specs
  )
"""

from typing import Literal


SortDirection = Literal["asc", "desc"]
SortSpec = tuple[str, SortDirection]

MAX_SORT_FIELDS = 3


def parse_sort_specs(
        *,
        sort_by: str | None,
        sort_order: str = "asc",
) -> tuple[SortSpec, ...]:
    """解析逗号分隔的排序字段和方向."""
    if sort_by is None or not sort_by.strip():
        return ()

    fields = tuple(
        field.strip()
        for field in sort_by.split(",")
    )
    directions = tuple(
        direction.strip().lower()
        for direction in sort_order.split(",")
    )

    if any(not field for field in fields):
        raise ValueError("排序字段不能为空")

    if len(fields) > MAX_SORT_FIELDS:
        raise ValueError(
            f"最多支持 {MAX_SORT_FIELDS} 个排序字段"
        )

    if len(set(fields)) != len(fields):
        raise ValueError("排序字段不能重复")

    if len(directions) != len(fields):
        raise ValueError("排序字段和排序方向数量必须一致")

    specs: list[SortSpec] = []
    for field, direction in zip(
            fields,
            directions,
            strict=True,
    ):
        if direction == "asc":
            normalized_direction: SortDirection = "asc"
        elif direction == "desc":
            normalized_direction = "desc"
        else:
            raise ValueError("排序方向只支持 asc 或 desc")

        specs.append((field, normalized_direction))

    return tuple(specs)


def encode_sort_specs(
        specs: tuple[SortSpec, ...],
) -> tuple[str | None, str]:
    """将规范化的排序规则转换为接口参数."""
    if not specs:
        return None, "asc"

    return (
        ",".join(field for field, _direction in specs),
        ",".join(direction for _field, direction in specs),
    )
