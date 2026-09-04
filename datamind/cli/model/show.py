# datamind/cli/model/show.py

"""查看模型命令

提供模型和模型版本详情查看功能。

核心功能：
  - show_model: 查看模型和指定模型版本详情

使用示例：
  python -m datamind.cli.main model show scorecard \
    --version 1.0.0
"""

import asyncio
import json
from typing import Any

import structlog
import typer
from rich import box
from rich.table import Table

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.db.core import UnitOfWork
from datamind.db.repositories import MetadataRepository, VersionRepository
from datamind.models.errors import ModelError
from datamind.models.resolver import ModelResolver
from datamind.utils.datetime import format_datetime, format_iso_utc, parse_datetime

app = typer.Typer(help="查看模型命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


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
            help="输出格式：text / json"
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

        logger.info(
            "开始查询模型详情",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            include_archived=include_archived,
        )

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
                console.error(
                    "查看模型失败：模型不存在",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            if version or version_id:
                ver = await resolver.resolve_version(
                    model_id=model.model_id,
                    version=version,
                    version_id=version_id,
                )

                if not ver:
                    console.error(
                        "查看模型失败：模型版本不存在",
                        output_format=output,
                    )
                    raise typer.Exit(code=1) from None

                result = {
                    "model": _model_to_dict(model),
                    "version": _version_to_dict(ver),
                }

            else:
                versions = await version_repo.list_versions(
                    model_id=model.model_id,
                    include_archived=include_archived,
                )

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
                )
            )
            return result

        _print_model_detail(result["model"])
        console.print()

        if "version" in result:
            _print_version_detail(result["version"])
        else:
            _print_version_list(result["versions"])

        return result

    async def runner():
        async with cli_context(
                required_permission="model.read",
        ):
            await _run()

    try:
        asyncio.run(
            runner()
        )
    except ModelError as error:
        console.error(
            f"查看模型失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(
            code=1
        ) from None


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
        "display_name": getattr(
            model,
            "display_name",
            None,
        ),
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


def _print_model_detail(model: dict[str, Any]) -> None:
    """打印模型详情

    参数：
        model: 模型元数据字典
    """
    console.info("模型详情\n")

    console.print(f"{'MODEL ID':<16} : {model['model_id']}")
    console.print(f"{'NAME':<16} : {model['name']}")
    console.print(
        f"{'DISPLAY NAME':<16} : "
        f"{model['display_name'] or '-'}"
    )
    console.print(f"{'MODEL TYPE':<16} : {model['model_type']}")
    console.print(f"{'TASK TYPE':<16} : {model['task_type']}")
    console.print(f"{'FRAMEWORK':<16} : {model['framework']}")
    console.print(f"{'STATUS':<16} : {model['status']}")
    console.print(f"{'DESCRIPTION':<16} : {model['description'] or '-'}")
    console.print(f"{'CREATED BY':<16} : {model['created_by'] or '-'}")
    console.print(
        f"{'CREATED AT':<16} : "
        f"{format_datetime(parse_datetime(model['created_at']))}"
    )
    console.print(f"{'UPDATED BY':<16} : {model['updated_by'] or '-'}")
    console.print(
        f"{'UPDATED AT':<16} : "
        f"{format_datetime(parse_datetime(model['updated_at']))}"
    )


def _print_version_detail(ver: dict[str, Any]) -> None:
    """打印模型版本详情

    参数：
        ver: 模型版本字典
    """
    console.info("版本详情\n")

    console.print(f"{'VERSION ID':<18} : {ver['version_id']}")
    console.print(f"{'VERSION':<18} : {ver['version']}")
    console.print(f"{'FRAMEWORK':<18} : {ver['framework']}")
    console.print(f"{'STATUS':<18} : {ver['status']}")
    console.print(f"{'BENTO TAG':<18} : {ver['bento_tag'] or '-'}")
    console.print(f"{'MODEL PATH':<18} : {ver['model_path'] or '-'}")
    console.print(f"{'MODEL KEY':<18} : {ver['model_key'] or '-'}")
    console.print(f"{'DESCRIPTION':<18} : {ver['description'] or '-'}")
    console.print(f"{'CREATED BY':<18} : {ver['created_by'] or '-'}")
    console.print(
        f"{'CREATED AT':<18} : "
        f"{format_datetime(parse_datetime(ver['created_at']))}"
    )
    console.print(f"{'UPDATED BY':<18} : {ver['updated_by'] or '-'}")
    console.print(
        f"{'UPDATED AT':<18} : "
        f"{format_datetime(parse_datetime(ver['updated_at']))}"
    )


def _print_version_list(versions: list[dict[str, Any]]) -> None:
    """打印模型版本列表

    参数：
        versions: 模型版本摘要字典列表
    """
    console.info(f"模型共包含 {len(versions)} 个版本\n")

    if not versions:
        console.warning("暂无模型版本")
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
            item["version_id"],
            item["version"],
            item["framework"],
            item["status"],
            item["bento_tag"] or "-",
            format_datetime(parse_datetime(item["created_at"])),
        )

    console.print(table)
