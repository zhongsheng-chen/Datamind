# datamind/cli/experiment/list.py

"""列出实验命令

提供实验列表查询功能。

核心功能：
  - list_experiments: 列出实验

使用示例：
  python -m datamind.cli.main experiment list
"""

import asyncio
import json

import structlog
import typer
from rich import box
from datamind.cli.output import CLIConsole
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.config import get_settings
from datamind.db.core import UnitOfWork
from datamind.db.models.experiments import Experiment
from datamind.db.repositories import ExperimentRepository
from datamind.models.enums import AssignmentStrategy
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime,
)

app = typer.Typer(help="列出实验命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("list")
def list_experiments(
        model_id: str | None = typer.Option(
            None,
            "--model-id",
            help="按模型 ID 过滤"
        ),
        status: str | None = typer.Option(
            None,
            "--status",
            help="按实验状态过滤，可选值：draft / running / paused / stopped / completed / archived"
        ),
        created_by: str | None = typer.Option(
            None,
            "--created-by",
            help="按创建人过滤"
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除实验",
        ),
        limit: int | None = typer.Option(
            None,
            "--limit",
            help="返回记录数量限制"
        ),
        offset: int | None = typer.Option(
            None,
            "--offset",
            help="分页偏移量"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """列出实验"""
    environment = str(get_settings().service.environment)

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if limit is not None and limit <= 0:
            raise typer.BadParameter("--limit 必须大于 0")

        if offset is not None and offset < 0:
            raise typer.BadParameter("--offset 不能小于 0")

        filters = {"environment": environment}

        if model_id is not None:
            filters["model_id"] = model_id

        if status is not None:
            filters["status"] = status

        if created_by is not None:
            filters["created_by"] = created_by

        logger.info(
            "开始列出实验",
            model_id=model_id,
            environment=environment,
            status=status,
            created_by=created_by,
            limit=limit,
            offset=offset,
        )

        async with UnitOfWork() as uow:
            repo = ExperimentRepository(uow.session)

            experiments = await repo.list_experiments(
                include_deleted=include_deleted,
                limit=limit,
                offset=offset,
                **filters,
            )

            result = []

            for experiment in experiments:
                config = _get_config(experiment)
                strategy = _get_strategy(config)
                traffic_ratio = _get_config_value(
                    config=config,
                    key="traffic_ratio",
                    default="-",
                )
                bucket_key = _get_config_value(
                    config=config,
                    key="bucket_key",
                    default="-",
                )

                result.append({
                    "experiment_id": experiment.experiment_id,
                    "model_id": experiment.model_id,
                    "environment": experiment.environment,
                    "name": experiment.name,
                    "status": experiment.status,
                    "strategy": strategy,
                    "traffic_ratio": traffic_ratio,
                    "bucket_key": bucket_key,
                    "config": experiment.config,
                    "description": experiment.description,
                    "effective_from": format_iso_utc(experiment.effective_from),
                    "effective_to": format_iso_utc(experiment.effective_to),
                    "created_by": experiment.created_by,
                    "created_at": format_iso_utc(experiment.created_at),
                    "updated_by": experiment.updated_by,
                    "updated_at": format_iso_utc(experiment.updated_at),
                    "deleted_at": format_iso_utc(experiment.deleted_at),
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

        console.print(f"[dim]共找到 {len(result)} 个实验[/dim]\n")

        if not result:
            return result

        table = Table(
            box=box.ASCII,
            header_style="bold cyan",
            show_lines=False,
            pad_edge=False,
        )

        table.add_column("EXPERIMENT ID")
        table.add_column("MODEL ID")
        table.add_column("ENVIRONMENT")
        table.add_column("NAME")
        table.add_column("STATUS")
        table.add_column("STRATEGY")
        table.add_column("TRAFFIC RATIO")
        table.add_column("BUCKET KEY")
        table.add_column("UPDATED AT")

        if include_deleted:
            table.add_column("DELETED AT")

        for item in result:
            row = [
                item["experiment_id"],
                item["model_id"],
                item["environment"],
                item["name"] or "-",
                item["status"],
                item["strategy"],
                str(item["traffic_ratio"]),
                str(item["bucket_key"]),
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


def _get_config(
        experiment: Experiment,
) -> dict:
    """获取实验配置"""
    config = experiment.config or {}

    if not isinstance(config, dict):
        return {}

    return config


def _get_strategy(
        config: dict,
) -> str:
    """获取实验分配策略"""
    return str(
        config.get("strategy")
        or AssignmentStrategy.HASH
    ).lower()


def _get_config_value(
        *,
        config: dict,
        key: str,
        default: str,
):
    """获取实验配置值"""
    value = config.get(
        key,
        default,
    )

    if value is None:
        return default

    return value
