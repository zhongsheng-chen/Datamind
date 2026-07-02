# datamind/cli/model/list.py

"""列出模型命令

提供模型的列表查询功能，支持过滤、分页和多种输出格式。

核心功能：
  - list_models: 列出模型

使用示例：
  python -m datamind.cli.main model list
"""

import asyncio
import json
import typer
import structlog
from rich.console import Console
from rich.table import Table
from rich import box

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import MetadataRepository
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="列出模型命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_models(
    status: str | None = typer.Option(
        None,
        "--status",
        help="按模型状态过滤，例如 active/inactive/archived"
    ),
    framework: str | None = typer.Option(
        None,
        "--framework",
        help="按模型框架过滤，例如 sklearn/xgboost/lightgbm/catboost"
    ),
    model_type: str | None = typer.Option(
        None,
        "--model-type",
        help="按模型类型过滤，例如 logistic_regression/random_forest/xgboost"
    ),
    task_type: str | None = typer.Option(
        None,
        "--task-type",
        help="按任务类型过滤，例如 classification/scoring"
    ),
    owner: str | None = typer.Option(
        None,
        "--owner",
        help="按创建人过滤"
    ),
    output: str = typer.Option(
        "text",
        "--format",
        help="输出格式：text/json"
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
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="显示调试日志"
    ),
):
    """列出模型"""

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

        if owner is not None:
            filters["created_by"] = owner

        exclude_status = None

        # 默认隐藏 archived；如果用户显式传了 --status，则尊重用户过滤条件
        if not include_archived and status is None:
            exclude_status = "archived"

        logger.info(
            "开始列出模型",
            filters=filters,
            exclude_status=exclude_status,
            limit=limit,
            offset=offset,
            include_archived=include_archived,
        )

        async with UnitOfWork() as uow:
            repo = MetadataRepository(uow.session)

            models = await repo.list_models(
                exclude_status=exclude_status,
                limit=limit,
                offset=offset,
                **filters
            )

            logger.debug(
                "模型列表查询成功",
                count=len(models),
            )

            if output == "json":
                result = []

                for m in models:
                    result.append({
                        "model_id": m.model_id,
                        "name": m.name,
                        "status": m.status,
                        "framework": m.framework,
                        "model_type": m.model_type,
                        "task_type": m.task_type,
                        "created_by": m.created_by,
                        "created_at": format_iso_utc(m.created_at),
                        "updated_by": m.updated_by,
                        "updated_at": format_iso_utc(m.updated_at),
                    })

                logger.info(
                    "模型列表输出完成",
                    count=len(models),
                    output=output,
                )

                console.print_json(
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )
                return

            console.print(f"[dim]共找到 {len(models)} 个模型[/dim]\n")

            if not models:
                logger.info(
                    "模型列表输出完成",
                    count=0,
                    output=output,
                )
                return

            table = Table(
                box=box.ASCII,
                header_style="bold cyan",
                show_lines=False,
                pad_edge=False,
            )

            table.add_column("NAME")
            table.add_column("MODEL ID")
            table.add_column("STATUS")
            table.add_column("FRAMEWORK")
            table.add_column("MODEL TYPE")
            table.add_column("TASK TYPE")
            table.add_column("UPDATED AT")

            for m in models:
                table.add_row(
                    m.name,
                    m.model_id,
                    m.status,
                    m.framework,
                    m.model_type,
                    m.task_type,
                    format_datetime(m.updated_at),
                )

            logger.info(
                "模型列表输出完成",
                count=len(models),
                output=output,
            )

            console.print(table)

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())