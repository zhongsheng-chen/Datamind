"""管理控制台导出格式.

负责生成 CSV 行、转换字段值和统一导出文件名。

核心功能：
  - encode_csv_row: 编码 CSV 表头或数据行
  - export_filename: 生成导出文件名
"""

import csv
import io
import json
from datetime import (
    datetime,
    timezone,
)
from typing import Any

from datamind.config import get_logging_config
from datamind.utils.datetime import format_datetime


def encode_csv_row(
        fieldnames: list[str],
        item: dict[str, Any],
        *,
        header: bool = False,
) -> str:
    """编码 CSV 表头或数据行."""
    output = io.StringIO(
        newline=""
    )
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )

    if header:
        writer.writeheader()
    else:
        writer.writerow({
            field: csv_value(
                item.get(field)
            )
            for field in fieldnames
        })

    return output.getvalue()


def csv_value(
        value: Any,
) -> Any:
    """转换 CSV 字段并规避表格公式注入."""
    if value is None:
        return ""

    if isinstance(
            value,
            (dict, list),
    ):
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    if isinstance(value, bool):
        return str(value).lower()

    if (
            isinstance(value, str)
            and value.startswith((
                "=",
                "+",
                "-",
                "@",
            ))
    ):
        return f"'{value}"

    return value


def export_filename(
        section: str,
        *,
        now: datetime | None = None,
        timezone_name: str | None = None,
) -> str:
    """生成统一的控制台导出文件名."""
    export_time = (
        now
        if now is not None
        else datetime.now(
            timezone.utc
        )
    )
    resolved_timezone = (
        timezone_name
        if timezone_name is not None
        else get_logging_config().timezone
    )
    timestamp = format_datetime(
        export_time,
        "%Y%m%d_%H%M%S",
        timezone_name=resolved_timezone,
    )

    return f"{section}_{timestamp}.csv"
