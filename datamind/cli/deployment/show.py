# datamind/cli/deployment/show.py

"""部署详情命令

提供单个部署的详细信息查询功能。

核心功能：
  - show_deployment: 查看部署详情

使用示例：
  python -m datamind.cli.main deployment show dep_0123456789abcdef
"""

import asyncio
import json

import structlog
import typer

from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.db.core import UnitOfWork
from datamind.db.repositories.deployment import DeploymentRepository
from datamind.utils.datetime import (
    format_datetime,
    format_iso_utc,
    parse_datetime
)

app = typer.Typer(help="部署详情命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


@app.command("show")
def show_deployment(
        deployment_id: str = typer.Argument(
            ...,
            help="部署 ID"
        ),
        include_deleted: bool = typer.Option(
            False,
            "--include-deleted",
            help="包含已删除部署",
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """查看部署详情"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始查询部署详情",
            deployment_id=deployment_id,
        )

        async with UnitOfWork() as uow:
            repo = DeploymentRepository(uow.session)

            deployment = await repo.get_deployment(
                deployment_id,
                include_deleted=include_deleted,
            )

            if not deployment:
                console.error(
                    f"查看部署失败：部署不存在：{deployment_id}",
                    output_format=output,
                )
                raise typer.Exit(code=1) from None

            result = {
                "deployment_id": deployment.deployment_id,
                "model_id": deployment.model_id,
                "version_id": deployment.version_id,
                "framework": deployment.framework,
                "environment": deployment.environment,
                "rollout_type": deployment.rollout_type,
                "role": deployment.role,
                "status": deployment.status,
                "config": deployment.config,
                "description": deployment.description,
                "deployed_by": deployment.deployed_by,
                "effective_from": format_iso_utc(deployment.effective_from),
                "effective_to": format_iso_utc(deployment.effective_to),
                "created_at": format_iso_utc(deployment.created_at),
                "updated_at": format_iso_utc(deployment.updated_at),
                "deleted_at": format_iso_utc(deployment.deleted_at),
                "deleted_by": deployment.deleted_by,
                "deletion_reason": deployment.deletion_reason,
            }

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )

            logger.info(
                "部署详情输出完成",
                deployment_id=deployment_id,
                output=output,
            )
            return result

        console.info("部署详情\n")

        console.print(f"{'DEPLOYMENT ID':<16} : {result['deployment_id']}")
        console.print(f"{'MODEL ID':<16} : {result['model_id']}")
        console.print(f"{'VERSION ID':<16} : {result['version_id']}")
        console.print(f"{'FRAMEWORK':<16} : {result['framework']}")
        console.print(f"{'ENVIRONMENT':<16} : {result['environment']}")
        console.print(f"{'ROLLOUT TYPE':<16} : {result['rollout_type']}")
        console.print(f"{'ROLE':<16} : {result['role']}")
        console.print(f"{'STATUS':<16} : {result['status']}")

        if result["config"]:
            console.print(
                f"{'CONFIG':<16} : "
                f"{json.dumps(result['config'], ensure_ascii=False)}"
            )

        console.print(
            f"{'DESCRIPTION':<16} : "
            f"{result['description'] or '-'}"
        )
        console.print(
            f"{'DEPLOYED BY':<16} : "
            f"{result['deployed_by'] or '-'}"
        )
        console.print(
            f"{'CREATED AT':<16} : "
            f"{format_datetime(parse_datetime(result['created_at']))}"
        )
        console.print(
            f"{'UPDATED AT':<16} : "
            f"{format_datetime(parse_datetime(result['updated_at']))}"
        )

        if result["effective_from"]:
            console.print(
                f"{'EFFECTIVE FROM':<16} : "
                f"{format_datetime(parse_datetime(result['effective_from']))}"
            )

        if result["effective_to"]:
            console.print(
                f"{'EFFECTIVE TO':<16} : "
                f"{format_datetime(parse_datetime(result['effective_to']))}"
            )

        if result["deleted_at"]:
            console.print(
                f"{'DELETED AT':<16} : "
                f"{format_datetime(parse_datetime(result['deleted_at']))}"
            )
            console.print(
                f"{'DELETED BY':<16} : "
                f"{result['deleted_by'] or '-'}"
            )
            console.print(
                f"{'DELETE REASON':<16} : "
                f"{result['deletion_reason'] or '-'}"
            )

        logger.info(
            "部署详情输出完成",
            deployment_id=deployment_id,
            output=output,
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="deployment.read",
        ):
            await _run()

    asyncio.run(runner())
