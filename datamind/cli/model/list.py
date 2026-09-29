"""列出模型命令.

提供模型的列表查询功能，支持过滤、分页和多种输出格式。

核心功能：
  - list_models: 列出模型

使用示例：
  python -m datamind.cli.main model list
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
from datamind.db.repositories import MetadataRepository
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

app = typer.Typer(help="列出模型命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_models(
        status: str | None = typer.Option(
            None,
            "--status",
            help="按模型状态过滤，可选值：active / deprecated / inactive / archived"
        ),
        framework: str | None = typer.Option(
            None,
            "--framework",
            help="按模型框架过滤，可选值：sklearn / xgboost / lightgbm / catboost"
        ),
        model_type: str | None = typer.Option(
            None,
            "--model-type",
            help=(
                "按模型类型过滤，可选值：logistic_regression / "
                "decision_tree / random_forest / xgboost / "
                "lightgbm / catboost"
            )
        ),
        task_type: str | None = typer.Option(
            None,
            "--task-type",
            help="按任务类型过滤，可选值：classification / scoring"
        ),
        created_by: str | None = typer.Option(
            None,
            "--created-by",
            help="按创建人过滤"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
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
        include_archived: bool = typer.Option(
            False,
            "--include-archived",
            help="包含已归档的模型，默认不显示"
        ),
):
    """列出模型."""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if limit <= 0:
            raise typer.BadParameter("--limit 必须大于 0")

        if offset < 0:
            raise typer.BadParameter("--offset 不能小于 0")

        filters = {}

        if status is not None:
            filters["status"] = status

        if framework is not None:
            filters["framework"] = framework

        if model_type is not None:
            filters["model_type"] = model_type

        if task_type is not None:
            filters["task_type"] = task_type

        if created_by is not None:
            filters["created_by"] = created_by

        logger.info(
            "开始列出模型",
            filters=filters,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
        )

        async with UnitOfWork() as uow:
            repo = MetadataRepository(uow.session)

            models = await repo.list_models(
                include_archived=include_archived,
                limit=limit,
                offset=offset,
                **filters
            )

            logger.debug(
                "模型列表查询成功",
                count=len(models),
            )

            result = []

            for model in models:
                result.append({
                    "model_id": model.model_id,
                    "name": model.name,
                    "display_name": getattr(
                        model,
                        "display_name",
                        None,
                    ),
                    "status": model.status,
                    "framework": model.framework,
                    "model_type": model.model_type,
                    "task_type": model.task_type,
                    "created_by": model.created_by,
                    "created_at": format_iso_utc(model.created_at),
                    "updated_by": model.updated_by,
                    "updated_at": format_iso_utc(model.updated_at),
                })

        if output == "json":
            logger.info(
                "模型列表输出完成",
                count=len(result),
                output=output,
            )

            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        console.print(f"[dim]共找到 {len(result)} 个模型[/dim]\n")

        if not result:
            logger.info(
                "模型列表输出完成",
                count=0,
                output=output,
            )
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("NAME")
        table.add_column("DISPLAY NAME")
        table.add_column("MODEL ID")
        table.add_column("STATUS")
        table.add_column("FRAMEWORK")
        table.add_column("MODEL TYPE")
        table.add_column("TASK TYPE")
        table.add_column("UPDATED AT")

        for item in result:
            table.add_row(
                item["name"],
                item["display_name"] or "-",
                item["model_id"],
                item["status"],
                item["framework"],
                item["model_type"],
                item["task_type"],
                format_datetime(parse_datetime(item["updated_at"])),
            )

        logger.info(
            "模型列表输出完成",
            count=len(result),
            output=output,
        )

        console.print(table)

        return result

    async def runner():
        async with cli_context(
                required_permission="model.read",
        ):
            await _run()

    asyncio.run(runner())
