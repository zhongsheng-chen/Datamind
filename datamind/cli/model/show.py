# datamind/cli/model/show.py

"""查看模型命令

提供模型和模型版本详情查看功能。

核心功能：
  - show_model: 查看模型和指定模型版本详情

使用示例：
  python -m datamind.cli.main model show scorecard --version 1.0.0
"""

import asyncio
import json
import typer
from typing import Any
from rich import box
from rich.console import Console
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import MetadataRepository, VersionRepository
from datamind.models.enums import VersionStatus
from datamind.models.resolver import ModelResolver
from datamind.utils.datetime import format_datetime, format_iso_utc

app = typer.Typer(help="查看模型命令")
console = Console()


@app.command("show")
def show_model(
    name: str | None = typer.Argument(
        None,
        help="模型名称"
    ),
    model_id: str | None = typer.Option(
        None,
        "--model-id",
        help="模型 ID"
    ),
    version: str | None = typer.Option(
        None,
        "--version",
        help="模型版本号"
    ),
    version_id: str | None = typer.Option(
        None,
        "--version-id",
        help="版本 ID"
    ),
    include_archived: bool = typer.Option(
        False,
        "--include-archived",
        help="是否包含归档版本"
    ),
    output: str = typer.Option(
        "text",
        "--format",
        help="输出格式：text/json"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        help="显示调试日志"
    ),
):
    """查看模型详情"""

    async def _run():
        if not (name or model_id):
            raise typer.BadParameter("必须提供 <name> 或 --model-id")

        if name and model_id:
            raise typer.BadParameter("<name> 与 --model-id 只能指定一个")

        if version and version_id:
            raise typer.BadParameter("--version 与 --version-id 只能指定一个")

        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)

            resolver = ModelResolver(
                metadata_repo=metadata_repo,
                version_repo=version_repo,
            )

            model = await resolver.resolve_model(
                name=name,
                model_id=model_id,
            )

            if not model:
                console.print("[red]模型不存在[/red]")
                raise typer.Exit(1)

            if version or version_id:
                ver = await resolver.resolve_version(
                    model_id=model.model_id,
                    version=version,
                    version_id=version_id,
                )

                if not ver:
                    console.print("[red]模型版本不存在[/red]")
                    raise typer.Exit(1)

                result = {
                    "model": _model_to_dict(model),
                    "version": _version_to_dict(ver),
                }

                if output == "json":
                    console.print_json(
                        json.dumps(
                            result,
                            ensure_ascii=False,
                            indent=2,
                            default=str,
                        )
                    )
                    return result

                _print_model_detail(model)
                console.print()
                _print_version_detail(ver)

                return result

            versions = await version_repo.list_versions(
                model_id=model.model_id,
            )

            if not include_archived:
                versions = [
                    item for item in versions
                    if item.status != VersionStatus.ARCHIVED.value
                ]

            result = {
                "model": _model_to_dict(model),
                "versions": [
                    _version_summary_to_dict(item)
                    for item in versions
                ],
            }

            if output == "json":
                console.print_json(
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        indent=2,
                        default=str,
                    )
                )
                return result

            _print_model_detail(model)
            console.print()
            _print_version_list(versions)

            return result

    async def runner():
        async with cli_context(
                user="system",
                source="cli",
                verbose=verbose,
                enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())


def _model_to_dict(model: Any) -> dict[str, Any]:
    """模型元数据转字典

    参数：
        model: 模型元数据对象

    返回：
        模型元数据字典
    """
    return {
        "model_id": model.model_id,
        "name": model.name,
        "model_type": model.model_type,
        "task_type": model.task_type,
        "framework": model.framework,
        "status": model.status,
        "description": model.description,
        "created_by": model.created_by,
        "created_at": format_iso_utc(model.created_at),
        "updated_by": model.updated_by,
        "updated_at": format_iso_utc(model.updated_at),
        "deleted_at": format_iso_utc(model.deleted_at),
        "deleted_by": model.deleted_by,
        "archived_at": format_iso_utc(model.archived_at),
        "archived_by": model.archived_by,
    }


def _version_to_dict(ver: Any) -> dict[str, Any]:
    """模型版本转字典

    参数：
        ver: 模型版本对象

    返回：
        模型版本字典
    """
    return {
        "version_id": ver.version_id,
        "model_id": ver.model_id,
        "version": ver.version,
        "framework": ver.framework,
        "status": ver.status,
        "bento_tag": ver.bento_tag,
        "model_path": ver.model_path,
        "model_key": ver.model_key,
        "input_schema": ver.input_schema,
        "output_schema": ver.output_schema,
        "input_schema_key": ver.input_schema_key,
        "output_schema_key": ver.output_schema_key,
        "params": ver.params,
        "metrics": ver.metrics,
        "description": ver.description,
        "created_by": ver.created_by,
        "created_at": format_iso_utc(ver.created_at),
        "updated_by": ver.updated_by,
        "updated_at": format_iso_utc(ver.updated_at),
        "deleted_at": format_iso_utc(ver.deleted_at),
        "deleted_by": ver.deleted_by,
        "archived_at": format_iso_utc(ver.archived_at),
        "archived_by": ver.archived_by,
    }


def _version_summary_to_dict(ver: Any) -> dict[str, Any]:
    """模型版本摘要转字典

    参数：
        ver: 模型版本对象

    返回：
        模型版本摘要字典
    """
    return {
        "version_id": ver.version_id,
        "version": ver.version,
        "framework": ver.framework,
        "status": ver.status,
        "bento_tag": ver.bento_tag,
        "created_by": ver.created_by,
        "created_at": format_iso_utc(ver.created_at),
        "updated_by": ver.updated_by,
        "updated_at": format_iso_utc(ver.updated_at),
    }


def _print_model_detail(model: Any) -> None:
    """打印模型详情

    参数：
        model: 模型元数据对象
    """
    console.print("[green]模型详情[/green]\n")

    console.print(f"[cyan]{'MODEL ID':<16}[/cyan] : {model.model_id}")
    console.print(f"[cyan]{'NAME':<16}[/cyan] : {model.name}")
    console.print(f"[cyan]{'MODEL TYPE':<16}[/cyan] : {model.model_type}")
    console.print(f"[cyan]{'TASK TYPE':<16}[/cyan] : {model.task_type}")
    console.print(f"[cyan]{'FRAMEWORK':<16}[/cyan] : {model.framework}")
    console.print(f"[cyan]{'STATUS':<16}[/cyan] : {model.status}")
    console.print(f"[cyan]{'DESCRIPTION':<16}[/cyan] : {model.description or '-'}")
    console.print(f"[cyan]{'CREATED BY':<16}[/cyan] : {model.created_by or '-'}")
    console.print(f"[cyan]{'CREATED AT':<16}[/cyan] : {format_datetime(model.created_at)}")
    console.print(f"[cyan]{'UPDATED BY':<16}[/cyan] : {model.updated_by or '-'}")
    console.print(f"[cyan]{'UPDATED AT':<16}[/cyan] : {format_datetime(model.updated_at)}")


def _print_version_detail(ver: Any) -> None:
    """打印模型版本详情

    参数：
        ver: 模型版本对象
    """
    console.print("[green]版本详情[/green]\n")

    console.print(f"[cyan]{'VERSION ID':<18}[/cyan] : {ver.version_id}")
    console.print(f"[cyan]{'VERSION':<18}[/cyan] : {ver.version}")
    console.print(f"[cyan]{'FRAMEWORK':<18}[/cyan] : {ver.framework}")
    console.print(f"[cyan]{'STATUS':<18}[/cyan] : {ver.status}")
    console.print(f"[cyan]{'BENTO TAG':<18}[/cyan] : {ver.bento_tag or '-'}")
    console.print(f"[cyan]{'MODEL PATH':<18}[/cyan] : {ver.model_path or '-'}")
    console.print(f"[cyan]{'MODEL KEY':<18}[/cyan] : {ver.model_key or '-'}")
    console.print(f"[cyan]{'INPUT SCHEMA KEY':<18}[/cyan] : {ver.input_schema_key or '-'}")
    console.print(f"[cyan]{'OUTPUT SCHEMA KEY':<18}[/cyan] : {ver.output_schema_key or '-'}")
    console.print(f"[cyan]{'DESCRIPTION':<18}[/cyan] : {ver.description or '-'}")
    console.print(f"[cyan]{'CREATED BY':<18}[/cyan] : {ver.created_by or '-'}")
    console.print(f"[cyan]{'CREATED AT':<18}[/cyan] : {format_datetime(ver.created_at)}")
    console.print(f"[cyan]{'UPDATED BY':<18}[/cyan] : {ver.updated_by or '-'}")
    console.print(f"[cyan]{'UPDATED AT':<18}[/cyan] : {format_datetime(ver.updated_at)}")


def _print_version_list(versions: list[Any]) -> None:
    """打印模型版本列表

    参数：
        versions: 模型版本列表
    """
    console.print(f"[green]模型共包含 {len(versions)} 个版本[/green]\n")

    if not versions:
        console.print("[yellow]暂无模型版本[/yellow]")
        return

    table = Table(
        box=box.ASCII,
        header_style="bold cyan",
        show_lines=False,
        pad_edge=False,
    )

    table.add_column("VERSION ID")
    table.add_column("VERSION")
    table.add_column("FRAMEWORK")
    table.add_column("STATUS")
    table.add_column("BENTO TAG")
    table.add_column("CREATED AT")

    for item in versions:
        table.add_row(
            item.version_id,
            item.version,
            item.framework,
            item.status,
            item.bento_tag or "-",
            format_datetime(item.created_at),
        )

    console.print(table)