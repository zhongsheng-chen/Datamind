# datamind/cli/model/verison/delete.py

"""删除版本命令

命令：
  datamind model version delete <version-id> [--purge] [--yes]
"""

import asyncio
import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.models.deleter import ModelDeleter
from datamind.models.errors import VersionNotFoundError

logger = structlog.get_logger(__name__)

app = typer.Typer()


@app.command("delete")
def delete_version(
    version_id: str = typer.Argument(..., help="版本 ID"),
    purge: bool = typer.Option(False, "--purge", help="是否执行硬删除"),
    yes: bool = typer.Option(False, "--yes", help="跳过确认"),
    verbose: bool = typer.Option(False, "--verbose", help="显示调试日志"),
):
    """
    删除版本
    """

    @audit(
        action="version.delete",
        target_type="model",
        target_id_func=lambda p, r: r["version_id"],
    )
    async def _run():
        deleter = ModelDeleter()

        try:
            if not yes:
                typer.confirm(
                    f"确定要删除版本 {version_id} 吗？",
                    abort=True,
                )

            result = await deleter.delete(
                version_id=version_id,
                purge=purge,
            )

            typer.secho("删除成功", fg=typer.colors.GREEN)

            typer.echo(f"model_id   : {result['model_id']}")
            typer.echo(f"name       : {result['name']}")
            typer.echo(f"version_id : {result.get('version_id')}")
            typer.echo(f"version    : {result.get('version')}")
            typer.echo(f"action     : {result['action']}")
            typer.echo(f"purge      : {result['purge']}")

        except VersionNotFoundError as e:
            typer.secho(f"版本不存在: {e.message}", fg=typer.colors.RED)
            raise typer.Exit(code=1)

        except Exception as e:
            logger.error("版本删除失败", error=str(e))
            typer.secho(f"删除失败: {str(e)}", fg=typer.colors.RED)
            raise typer.Exit(code=1)


    async def runner():
        async with cli_context(verbose=verbose, enable_audit=True):
            await _run()

    asyncio.run(runner())


