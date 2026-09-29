"""查看实验分组命令.

提供实验分组详情查看功能。

核心功能：
  - show_variant: 查看实验分组详情

使用示例：
  python -m datamind.cli.main experiment variant show var_0123456789abcdef
"""

import asyncio
import json
from typing import Any

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.db.core import UnitOfWork
from datamind.db.repositories import VariantRepository
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

app = typer.Typer(help="查看实验分组命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


def _get_variant_environment(
        config: dict | None,
) -> str | None:
    """获取实验分组环境."""
    if not isinstance(
            config,
            dict,
    ):
        return None

    value = config.get(
        "environment"
    )

    if not isinstance(
            value,
            str,
    ):
        return None

    return value


@app.command("show")
def show_variant(
        variant_id: str = typer.Argument(
            ...,
            help="实验分组 ID"
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除实验分组",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """查看实验分组详情."""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查看实验分组详情",
            variant_id=variant_id,
        )

        async with UnitOfWork() as uow:
            repo = VariantRepository(uow.session)

            variant = await repo.get_variant(
                variant_id,
                include_deleted=include_deleted,
            )

            if variant is None:
                console.error(
                    f"查看分组失败：分组不存在：{variant_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            result: dict[str, Any] = {
                "variant_id": variant.variant_id,
                "experiment_id": variant.experiment_id,
                "name": variant.name,
                "deployment_id": variant.deployment_id,
                "environment": _get_variant_environment(variant.config),
                "weight": variant.weight,
                "is_control": variant.is_control,
                "status": variant.status,
                "config": variant.config,
                "description": variant.description,
                "created_by": variant.created_by,
                "created_at": format_iso_utc(variant.created_at),
                "updated_by": variant.updated_by,
                "updated_at": format_iso_utc(variant.updated_at),
                "deleted_at": format_iso_utc(variant.deleted_at),
                "deleted_by": variant.deleted_by,
                "deletion_reason": variant.deletion_reason,
            }

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        console.info("分组详情\n")

        console.print(f"{'VARIANT ID':<16} : {result['variant_id']}")
        console.print(f"{'EXPERIMENT ID':<16} : {result['experiment_id']}")
        console.print(f"{'NAME':<16} : {result['name'] or '-'}")
        console.print(f"{'DEPLOYMENT ID':<16} : {result['deployment_id']}")
        console.print(
            f"{'ENVIRONMENT':<16} : "
            f"{result['environment'] or '-'}"
        )
        console.print(f"{'WEIGHT':<16} : {result['weight']}")
        console.print(f"{'CONTROL':<16} : {result['is_control']}")
        console.print(f"{'STATUS':<16} : {result['status']}")
        console.print(
            f"{'DESCRIPTION':<16} : "
            f"{result['description'] or '-'}"
        )
        console.print(
            f"{'CREATED BY':<16} : "
            f"{result['created_by'] or '-'}"
        )
        console.print(
            f"{'CREATED AT':<16} : "
            f"{format_datetime(parse_datetime(result['created_at']))}"
        )
        console.print(
            f"{'UPDATED AT':<16} : "
            f"{format_datetime(parse_datetime(result['updated_at']))}"
        )

        if result["config"]:
            console.print(
                f"{'CONFIG':<16} : "
                f"{json.dumps(result['config'], ensure_ascii=False)}"
            )

        if result["deleted_at"]:
            console.print(
                f"{'DELETED AT':<16} : "
                f"{format_datetime(parse_datetime(result['deleted_at']))}"
            )
            console.print(
                f"{'DELETED BY':<16} : "
                f"{result['deleted_by'] or '-'}"
            )
            console.print(
                f"{'DELETE REASON':<16} : "
                f"{result['deletion_reason'] or '-'}"
            )

        return result

    async def runner():
        async with cli_context(
                required_permission="experiment.read",
        ):
            await _run()

    asyncio.run(runner())
