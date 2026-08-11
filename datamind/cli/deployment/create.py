# datamind/cli/deployment/create.py

"""创建部署命令

提供模型部署创建功能。

核心功能：
  - create_deployment: 创建部署

使用示例：
  python -m datamind.cli.main deployment create scorecard \
    --version 1.0.0 \
    --rollout full \
    --config-file config.json
"""

import asyncio
import json

import structlog
import typer

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.cli.output import CLIConsole
from datamind.config import get_settings
from datamind.models.errors import (
    DeploymentError,
    InvalidModelStateError,
)
from datamind.services import DeploymentLifecycleService

app = typer.Typer(help="创建部署命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


def _resolve_release_options(
        *,
        rollout: str,
        role: str | None,
) -> tuple[str, str]:
    """规范化发布方式，并推导或校验部署角色。"""
    normalized_rollout = rollout.strip().lower()

    if normalized_rollout == "full":
        if role is not None:
            raise typer.BadParameter(
                "全量发布自动使用 champion，无需指定 --role",
                param_hint="--role",
            )
        return normalized_rollout, "champion"

    if normalized_rollout == "shadow":
        if role is not None:
            raise typer.BadParameter(
                "影子发布自动使用 shadow，无需指定 --role",
                param_hint="--role",
            )
        return normalized_rollout, "shadow"

    if normalized_rollout != "canary":
        try:
            DeploymentLifecycleService.validate_release_mode(
                rollout_type=normalized_rollout,
                role="champion",
            )
        except DeploymentError as rollout_error:
            raise typer.BadParameter(
                str(rollout_error),
                param_hint="--rollout",
            ) from None

    if role is None or role.strip() == "":
        raise typer.BadParameter(
            "金丝雀发布必须指定 --role：champion 或 challenger",
            param_hint="--role",
        )

    normalized_role = role.strip().lower()
    try:
        DeploymentLifecycleService.validate_release_mode(
            rollout_type=normalized_rollout,
            role=normalized_role,
        )
    except DeploymentError as role_error:
        raise typer.BadParameter(
            str(role_error),
            param_hint="--role",
        ) from None

    return normalized_rollout, normalized_role


@app.command("create")
def create_deployment(
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
        rollout: str = typer.Option(
            "full",
            "--rollout",
            help="发布方式，可选值：full / canary / shadow"
        ),
        role: str | None = typer.Option(
            None,
            "--role",
            help="金丝雀发布的部署角色：champion / challenger"
        ),
        config_file: str | None = typer.Option(
            None,
            "--config-file",
            help="运行时配置文件(JSON)"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="部署描述"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
):
    """创建部署

    全量发布自动使用 champion，影子发布自动使用 shadow；
    金丝雀发布需要通过 --role 指定 champion 或 challenger。
    """
    settings = get_settings()
    service_config = settings.service

    environment = service_config.environment
    normalized_rollout, resolved_role = _resolve_release_options(
        rollout=rollout,
        role=role,
    )

    @audit(
        action="deploy.create",
        target_type="deployment",
        target_id_func=lambda p, r: r["deployment_id"],
    )
    async def _run(
            actor: str,
    ):
        if not (name or model_id):
            raise typer.BadParameter(
                "必须提供 <name> 或 --model-id"
            )

        if name and model_id:
            raise typer.BadParameter(
                "<name> 与 --model-id 只能指定一个"
            )

        if version and version_id:
            raise typer.BadParameter(
                "--version 与 --version-id 只能指定一个"
            )

        if output not in ("text", "json"):
            raise typer.BadParameter(
                "--format 只支持 text 或 json"
            )

        logger.info(
            "开始创建部署",
            name=name,
            model_id=model_id,
            version=version,
            version_id=version_id,
            environment=environment,
            rollout=normalized_rollout,
            role=resolved_role,
            config_file=config_file,
        )

        cfg = None

        if config_file:
            logger.debug(
                "读取部署配置文件",
                config_file=config_file,
            )

            try:
                with open(
                        config_file,
                        "r",
                        encoding="utf-8",
                ) as f:
                    cfg = json.load(f)

                logger.debug(
                    "部署配置文件解析成功",
                    config=cfg,
                )

            except FileNotFoundError as file_error:
                raise typer.BadParameter(
                    f"--config-file 文件不存在：{config_file}"
                ) from file_error

            except json.JSONDecodeError as json_error:
                raise typer.BadParameter(
                    f"--config-file JSON 解析失败：{json_error}"
                ) from json_error

            if not isinstance(
                    cfg,
                    dict,
            ):
                raise typer.BadParameter(
                    "--config-file 必须是 JSON 对象"
                )

        deployer = DeploymentLifecycleService()

        try:
            result = await deployer.create_deployment(
                name=name,
                model_id=model_id,
                version=version,
                version_id=version_id,
                environment=environment,
                rollout_type=normalized_rollout,
                role=resolved_role,
                config=cfg,
                description=description,
                deployed_by=actor,
            )
        except (
            DeploymentError,
            InvalidModelStateError,
        ) as deployment_error:
            console.error(
                f"创建部署失败：{deployment_error}",
                output_format=output,
                error_type=type(deployment_error).__name__,
            )
            raise typer.Exit(code=1) from None

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return result

        console.info("部署创建成功\n")

        console.print(
            f"{'DEPLOYMENT ID':<16} : "
            f"{result['deployment_id']}"
        )
        console.print(
            f"{'MODEL ID':<16} : "
            f"{result['model_id']}"
        )
        console.print(
            f"{'VERSION ID':<16} : "
            f"{result['version_id']}"
        )
        console.print(
            f"{'ENVIRONMENT':<16} : "
            f"{result['environment']}"
        )
        console.print(
            f"{'ROLLOUT TYPE':<16} : "
            f"{result['rollout_type']}"
        )
        console.print(
            f"{'ROLE':<16} : "
            f"{result['role']}"
        )
        console.print(
            f"{'STATUS':<16} : "
            f"{result['status']}"
        )

        return result

    async def runner():
        async with cli_context(
                required_permission="deployment.write",
        ) as context:
            await _run(
                context.user
            )

    asyncio.run(runner())
