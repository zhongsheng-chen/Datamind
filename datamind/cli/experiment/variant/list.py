"""列出实验分组命令.

提供实验分组列表查询功能，支持过滤、分页和多种输出格式。

核心功能：
  - list_variants: 列出实验分组

使用示例：
  python -m datamind.cli.main experiment variant list
"""

import asyncio
import json

import structlog
import typer
from rich import box
from datamind.cli.output import CLIConsole
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import VariantRepository
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

app = typer.Typer(help="列出实验分组命令")
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


@app.command("list")
def list_variants(
        experiment_id: str | None = typer.Argument(
            None,
            help="按实验 ID 过滤"
        ),
        deployment_id: str | None = typer.Option(
            None,
            "--deployment-id",
            help="按部署 ID 过滤"
        ),
        status: str | None = typer.Option(
            None,
            "--status",
            help="按实验分组状态过滤，可选值：active / inactive / archived"
        ),
        is_control: bool | None = typer.Option(
            None,
            "--control/--non-control",
            help="按是否对照组过滤"
        ),
        created_by: str | None = typer.Option(
            None,
            "--created-by",
            help="按创建人过滤"
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除实验分组",
        ),
        limit: int = typer.Option(
            10,
            "--limit",
            help="返回记录数量限制"
        ),
        offset: int = typer.Option(
            0,
            "--offset",
            help="分页偏移量"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """列出实验分组."""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if limit <= 0:
            raise typer.BadParameter("--limit 必须大于 0")

        if offset < 0:
            raise typer.BadParameter("--offset 不能小于 0")

        filters = {}

        if experiment_id is not None:
            filters["experiment_id"] = experiment_id

        if deployment_id is not None:
            filters["deployment_id"] = deployment_id

        if status is not None:
            filters["status"] = status

        if is_control is not None:
            filters["is_control"] = is_control

        if created_by is not None:
            filters["created_by"] = created_by

        logger.info(
            "开始列出实验分组",
            filters=filters,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            repo = VariantRepository(uow.session)

            variants = await repo.list_variants(
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
                **filters,
            )

            result = []

            for item in variants:
                result.append({
                    "variant_id": item.variant_id,
                    "experiment_id": item.experiment_id,
                    "name": item.name,
                    "deployment_id": item.deployment_id,
                    "environment": _get_variant_environment(item.config),
                    "weight": item.weight,
                    "is_control": item.is_control,
                    "status": item.status,
                    "config": item.config,
                    "description": item.description,
                    "created_by": item.created_by,
                    "created_at": format_iso_utc(item.created_at),
                    "updated_by": item.updated_by,
                    "updated_at": format_iso_utc(item.updated_at),
                    "deleted_at": format_iso_utc(item.deleted_at),
                })

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        console.print(f"[dim]共找到 {len(result)} 个实验分组[/dim]\n")

        if not result:
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("VARIANT ID")
        table.add_column("EXPERIMENT ID")
        table.add_column("NAME")
        table.add_column("DEPLOYMENT ID")
        table.add_column("ENVIRONMENT")
        table.add_column("WEIGHT")
        table.add_column("CONTROL")
        table.add_column("STATUS")
        table.add_column("UPDATED AT")

        if include_deleted:
            table.add_column("DELETED AT")

        for item in result:
            row = [
                item["variant_id"],
                item["experiment_id"],
                item["name"] or "-",
                item["deployment_id"],
                item["environment"] or "-",
                str(item["weight"]),
                str(item["is_control"]),
                item["status"],
                format_datetime(parse_datetime(item["updated_at"])),
            ]

            if include_deleted:
                row.append(
                    format_datetime(
                        parse_datetime(item["deleted_at"])
                    ) or "-"
                )

            table.add_row(*row)

        console.print(table)

        return result

    async def runner():
        async with cli_context(
                required_permission="experiment.read",
        ):
            await _run()

    asyncio.run(runner())
