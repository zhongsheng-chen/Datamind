# datamind/cli/model/show.py

"""查看模型详情命令

提供模型详情查询功能。

核心功能：
  - show_model: 查看模型详情

使用示例：
  python -m datamind.cli.main model show scorecard
  python -m datamind.cli.main model show --model-id mdl_a1b2c3d4
  python -m datamind.cli.main model show scorecard --format json
  python -m datamind.cli.main model show scorecard --version 1.0.0
"""

import asyncio
import json
import typer
import structlog
from rich import box
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import MetadataRepository, VersionRepository
from datamind.models.resolver import ModelResolver
from datamind.utils.datetime import format_datetime, format_iso_utc
from datamind.models.errors import ModelNotFoundError, VersionNotFoundError

app = typer.Typer(help="查看模型详情命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_model(
    name: str = typer.Argument(None, help="模型名称（与 --model-id 二选一）"),
    model_id: str = typer.Option(None, "--model-id", help="模型 ID"),
    version: str = typer.Option(None, "--version", help="版本号"),
    version_id: str = typer.Option(None, "--version-id", help="版本 ID"),
    output: str = typer.Option("table", "--format", help="输出格式：table/json"),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """查看模型详情"""
    async def _run():
        if not name and not model_id:
            raise typer.BadParameter("必须提供 <name> 或 --model-id")

        logger.info(
            "开始查看模型",
            model_id=model_id,
            name=name,
            version=version,
            version_id=version_id,
        )

        async with UnitOfWork() as uow:
            session = uow.session

            metadata_repo = MetadataRepository(session)
            version_repo = VersionRepository(session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            # 解析模型
            try:
                model = await resolver.resolve_model(
                    model_id=model_id,
                    name=name,
                )
            except ModelNotFoundError:
                console.print("[yellow]模型不存在[/yellow]")
                raise typer.Exit(1)

            logger.debug(
                "模型解析成功",
                model_id=model.model_id,
                name=model.name,
            )

            # 解析版本
            target_version = None

            if version or version_id:
                try:
                    target_version = await resolver.resolve_version(
                        model_id=model.model_id,
                        version_id=version_id,
                        version=version,
                    )
                except VersionNotFoundError:
                    console.print("[yellow]版本不存在[/yellow]")
                    raise typer.Exit(1)

                logger.debug(
                    "版本解析成功",
                    version_id=target_version.version_id,
                    version=target_version.version,
                )

            # JSON 输出
            if output == "json":
                result = {
                    "model": {
                        "model_id": model.model_id,
                        "name": model.name,
                        "status": model.status,
                        "framework": model.framework,
                        "model_type": model.model_type,
                        "task_type": model.task_type,
                        "description": model.description,
                        "created_by": model.created_by,
                        "created_at": format_iso_utc(model.created_at),
                        "updated_by": model.updated_by,
                        "updated_at": format_iso_utc(model.updated_at),
                    }
                }

                if target_version:
                    result["version"] = {
                        "version_id": target_version.version_id,
                        "version": target_version.version,
                        "status": target_version.status,
                        "framework": target_version.framework,
                        "bento_tag": target_version.bento_tag,
                        "storage_key": target_version.storage_key,
                        "model_path": target_version.model_path,
                    }

                logger.info(
                    "模型详情查询完成",
                    model_id=model.model_id,
                )

                console.print_json(json.dumps(result, ensure_ascii=False, indent=2))
                return

            # Table 输出
            table = Table(
                box=box.ASCII,
                show_header=False,
                show_lines=False,
                pad_edge=False,
            )

            table.add_column(style="cyan")
            table.add_column()

            table.add_row("NAME", model.name)
            table.add_row("MODEL ID", model.model_id)
            table.add_row("STATUS", model.status)
            table.add_row("FRAMEWORK", model.framework)
            table.add_row("MODEL TYPE", model.model_type)
            table.add_row("TASK TYPE", model.task_type)
            table.add_row("DESCRIPTION", model.description or "-")
            table.add_row("CREATED BY", model.created_by or "-")
            table.add_row("CREATED AT", format_datetime(model.created_at))
            table.add_row("UPDATED BY", model.updated_by or "-")
            table.add_row("UPDATED AT", format_datetime(model.updated_at))

            if target_version:
                table.add_row("VERSION ID", target_version.version_id)
                table.add_row("VERSION", target_version.version)
                table.add_row("VERSION STATUS", target_version.status)
                table.add_row("BENTO TAG", target_version.bento_tag)
                table.add_row("STORAGE KEY", target_version.storage_key or "-")
                table.add_row("MODEL PATH", target_version.model_path or "-")

            logger.info(
                "模型详情查询完成",
                model_id=model.model_id,
            )

            console.print(table)

    async def runner():
        async with cli_context(verbose=verbose, enable_audit=False):
            await _run()

    asyncio.run(runner())