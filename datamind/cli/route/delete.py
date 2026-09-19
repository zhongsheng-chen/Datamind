"""删除路由命令

提供路由规则逻辑删除功能。

核心功能：
  - delete_route: 删除路由规则

使用示例：
  datamind route delete rtn_0123456789abcdef --yes
"""

import asyncio
import json

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.services.routing import RoutingLifecycleService

app = typer.Typer(help="删除路由命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("delete")
def delete_route(
        routing_id: str = typer.Argument(
            ...,
            help="路由 ID",
        ),
        reason: str | None = typer.Option(
            None,
            "--reason",
            help="删除原因",
        ),
        yes: bool = typer.Option(
            False,
            "--yes",
            help="跳过确认",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json",
        ),
) -> None:
    """逻辑删除已禁用的路由规则"""

    @audit(
        action="route.delete",
        target_type="routing",
        target_id_func=lambda _p, result: result["routing_id"],
    )
    async def _run(actor: str) -> dict:
        if output not in {"text", "json"}:
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        if not yes:
            typer.confirm(
                f"确认删除路由 {routing_id}？",
                abort=True,
            )

        logger.info(
            "开始删除路由",
            routing_id=routing_id,
        )
        result = await RoutingLifecycleService().delete_routing(
            routing_id=routing_id,
            reason=reason,
            deleted_by=actor,
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
            console.info("路由删除成功\n")
            console.print(
                f"{'ROUTING ID':<16} : "
                f"{result['routing_id']}"
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
            f"路由删除失败：{error}",
            output_format=output,
            error_type=type(error).__name__,
        )
        raise typer.Exit(code=1) from None
