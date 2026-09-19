"""恢复路由命令

提供逻辑删除路由规则的恢复功能。

核心功能：
  - restore_route: 恢复路由规则

使用示例：
  datamind route restore rtn_0123456789abcdef
"""

import asyncio
import json

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services.routing import RoutingLifecycleService

app = typer.Typer(help="恢复路由命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("restore")
def restore_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """恢复逻辑删除的路由规则"""

    @audit(
        action="route.restore",
        target_type="routing",
        target_id_func=lambda _p, result: result["routing_id"],
    )
    async def _run(actor: str) -> dict:
        if output not in {"text", "json"}:
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始恢复路由",
            routing_id=routing_id,
        )
        result = await RoutingLifecycleService().restore_routing(
            routing_id=routing_id,
            restored_by=actor,
        )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            console.info("路由恢复成功\n")
            console.print(
                f"{'ROUTING ID':<16} : "
                f"{result['routing_id']}"
            )
            console.print(
                f"{'ENABLED':<16} : "
                f"{result['enabled']}"
            )

        return result

    async def runner() -> None:
        async with cli_context(
                required_permission="routing.delete",
        ) as context:
            await _run(context.user)

    try:
        asyncio.run(runner())
    except ValueError as error:
        console.error(
            f"路由恢复失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(code=1) from None
