# datamind/cli/experiment/variant/add.py

"""添加实验分组命令

提供 A/B 实验分组添加功能。

核心功能：
  - add_variant: 添加实验分组

使用示例：
  python -m datamind.cli.main experiment variant add exp_a1b2c3d4 \
    --name control \
    --deployment-id dep_control \
    --weight 0.5 \
    --control \
    --owner admin
"""

import asyncio
import json

import typer
import structlog
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import ExperimentRepository, VariantRepository
from datamind.models.enums import ExperimentVariantStatus
from datamind.utils.datetime import format_iso_utc
from datamind.utils.generator import generate_random_id

app = typer.Typer(help="添加实验分组命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("add")
def add_variant(
    experiment_id: str = typer.Argument(
        ...,
        help="实验 ID"
    ),
    name: str = typer.Option(
        ...,
        "--name",
        help="实验分组名称，例如 control / treatment"
    ),
    deployment_id: str = typer.Option(
        ...,
        "--deployment-id",
        help="部署 ID"
    ),
    weight: float = typer.Option(
        ...,
        "--weight",
        help="实验分组权重，范围 0~1"
    ),
    control: bool = typer.Option(
        False,
        "--control",
        help="是否为对照组"
    ),
    config: str | None = typer.Option(
        None,
        "--config",
        help="分组配置 JSON 字符串"
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        help="分组描述"
    ),
    owner: str = typer.Option(
        "system",
        "--owner",
        help="创建人"
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
    """添加实验分组"""

    @audit(
        action="experiment.variant.add",
        target_type="variant",
        target_id_func=lambda p, r: r["variant_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if weight < 0 or weight > 1:
            raise typer.BadParameter("--weight 必须在 0 到 1 之间")

        variant_config = {}

        if config:
            try:
                variant_config = json.loads(config)
            except json.JSONDecodeError as e:
                console.print(f"[red]config JSON 解析失败: {e}[/red]")
                raise typer.Exit(1)

            if not isinstance(variant_config, dict):
                raise typer.BadParameter("--config 必须是 JSON 对象")

        logger.info(
            "开始添加实验分组",
            experiment_id=experiment_id,
            name=name,
            deployment_id=deployment_id,
            weight=weight,
            control=control,
        )

        async with UnitOfWork() as uow:
            experiment_repo = ExperimentRepository(uow.session)
            variant_repo = VariantRepository(uow.session)

            experiment = await experiment_repo.get_experiment(experiment_id)

            if experiment is None:
                console.print(f"[red]实验不存在: {experiment_id}[/red]")
                raise typer.Exit(1)

            variant = variant_repo.create_variant(
                variant_id=generate_random_id(prefix="var"),
                experiment_id=experiment_id,
                name=name,
                deployment_id=deployment_id,
                weight=weight,
                is_control=control,
                status=ExperimentVariantStatus.ACTIVE,
                config=variant_config,
                description=description,
                created_by=owner,
            )

            await variant_repo.flush()

            result = {
                "variant_id": variant.variant_id,
                "experiment_id": variant.experiment_id,
                "name": variant.name,
                "deployment_id": variant.deployment_id,
                "weight": variant.weight,
                "is_control": variant.is_control,
                "status": variant.status,
                "config": variant.config,
                "description": variant.description,
                "created_by": variant.created_by,
                "created_at": format_iso_utc(variant.created_at),
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

        console.print("[green]实验分组创建成功[/green]\n")

        console.print(f"[cyan]{'VARIANT ID':<16}[/cyan] : {result['variant_id']}")
        console.print(f"[cyan]{'EXPERIMENT ID':<16}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'NAME':<16}[/cyan] : {result['name']}")
        console.print(f"[cyan]{'DEPLOYMENT ID':<16}[/cyan] : {result['deployment_id']}")
        console.print(f"[cyan]{'WEIGHT':<16}[/cyan] : {result['weight']}")
        console.print(f"[cyan]{'CONTROL':<16}[/cyan] : {result['is_control']}")
        console.print(f"[cyan]{'STATUS':<16}[/cyan] : {result['status']}")

        return result

    async def runner():
        async with cli_context(
            user=owner,
            source="cli",
            verbose=verbose,
            enable_audit=True,
        ):
            await _run()

    asyncio.run(runner())