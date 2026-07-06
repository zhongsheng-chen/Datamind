# datamind/cli/experiment/create.py

"""创建实验命令

提供 A/B 实验创建功能。

核心功能：
  - create_experiment: 创建实验

使用示例：
  python -m datamind.cli.main experiment create \
    --model-id mdl_a1b2c3d4 \
    --name scorecard_ab_test \
    --traffic-ratio 0.5 \
    --bucket-key customer_id \
    --owner admin

  python -m datamind.cli.main experiment create \
    --model-id mdl_a1b2c3d4 \
    --name scorecard_ab_test \
    --effective-from 2026-07-01T09:00:00+08:00 \
    --effective-to 2026-07-31T23:59:59+08:00

说明：
  - effective_from 默认当前 UTC 时间
  - effective_to 默认 None，表示不限制结束时间
  - effective_from / effective_to 使用 ISO 日期时间格式
  - bucket_key 表示分桶主体字段，用于从请求数据中提取 subject_key
"""

import asyncio
import json
from datetime import datetime, timezone

import structlog
import typer
from rich.console import Console

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import ExperimentRepository, MetadataRepository
from datamind.utils.datetime import parse_datetime, format_datetime, format_iso_utc
from datamind.utils.generator import generate_random_id

app = typer.Typer(help="创建实验命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("create")
def create_experiment(
        model_id: str = typer.Option(
            ...,
            "--model-id",
            help="模型 ID"
        ),
        name: str | None = typer.Option(
            None,
            "--name",
            help="实验名称"
        ),
        traffic_ratio: float = typer.Option(
            1.0,
            "--traffic-ratio",
            help="实验流量比例，范围 0~1"
        ),
        bucket_key: str = typer.Option(
            "customer_id",
            "--bucket-key",
            help="分桶主体字段，例如 customer_id / order_id / apply_id"
        ),
        config: str | None = typer.Option(
            None,
            "--config",
            help="实验配置 JSON 字符串"
        ),
        description: str | None = typer.Option(
            None,
            "--description",
            help="实验描述"
        ),
        owner: str = typer.Option(
            "system",
            "--owner",
            help="创建人"
        ),
        effective_from: str | None = typer.Option(
            None,
            "--effective-from",
            help="生效开始时间，ISO 格式，例如 2026-07-01T09:00:00+08:00；默认当前时间"
        ),
        effective_to: str | None = typer.Option(
            None,
            "--effective-to",
            help="生效结束时间，ISO 格式，例如 2026-07-31T23:59:59+08:00；默认不限制结束时间"
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
    """创建实验"""

    @audit(
        action="experiment.create",
        target_type="experiment",
        target_id_func=lambda p, r: r["experiment_id"],
    )
    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        if traffic_ratio <= 0 or traffic_ratio > 1:
            raise typer.BadParameter("--traffic-ratio 必须在 0 到 1 之间")

        experiment_config = {}

        if config:
            try:
                experiment_config = json.loads(config)
            except json.JSONDecodeError as exc:
                console.print(f"[red]config JSON 解析失败: {exc}[/red]")
                raise typer.Exit(1)

            if not isinstance(experiment_config, dict):
                raise typer.BadParameter("--config 必须是 JSON 对象")

        experiment_config.setdefault("strategy", "hash")
        experiment_config["traffic_ratio"] = traffic_ratio
        experiment_config["bucket_key"] = bucket_key

        try:
            effective_from_value = parse_datetime(effective_from)
            effective_to_value = parse_datetime(effective_to)
        except ValueError:
            console.print("[red]时间格式错误，请使用 ISO 格式[/red]")
            raise typer.Exit(1)

        if effective_from_value is None:
            effective_from_value = datetime.now(timezone.utc)

        if (
                effective_to_value is not None
                and effective_to_value <= effective_from_value
        ):
            raise typer.BadParameter("--effective-to 必须晚于 --effective-from")

        logger.info(
            "开始创建实验",
            model_id=model_id,
            name=name,
            traffic_ratio=traffic_ratio,
            bucket_key=bucket_key,
            effective_from=effective_from_value,
            effective_to=effective_to_value,
        )

        async with UnitOfWork() as uow:
            model_repo = MetadataRepository(uow.session)
            experiment_repo = ExperimentRepository(uow.session)

            model = await model_repo.get_model(
                model_id=model_id,
            )

            if model is None:
                console.print(f"[red]模型不存在: {model_id}[/red]")
                raise typer.Exit(1)

            experiment = experiment_repo.create_experiment(
                experiment_id=generate_random_id(
                    prefix="exp"
                ),
                model_id=model_id,
                name=name,
                description=description,
                config=experiment_config,
                effective_from=effective_from_value,
                effective_to=effective_to_value,
                created_by=owner,
            )

            await experiment_repo.flush()

            effective_from_text = format_datetime(experiment.effective_from)
            effective_to_text = format_datetime(experiment.effective_to)

            result = {
                "experiment_id": experiment.experiment_id,
                "model_id": experiment.model_id,
                "name": experiment.name,
                "status": experiment.status,
                "config": experiment.config,
                "description": experiment.description,
                "effective_from": format_iso_utc(experiment.effective_from),
                "effective_to": format_iso_utc(experiment.effective_to),
                "created_by": experiment.created_by,
                "created_at": format_iso_utc(experiment.created_at),
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

        console.print("[green]实验创建成功[/green]\n")

        console.print(f"[cyan]{'EXPERIMENT ID':<18}[/cyan] : {result['experiment_id']}")
        console.print(f"[cyan]{'MODEL ID':<18}[/cyan] : {result['model_id']}")
        console.print(f"[cyan]{'NAME':<18}[/cyan] : {result['name'] or '-'}")
        console.print(f"[cyan]{'STATUS':<18}[/cyan] : {result['status']}")
        console.print(f"[cyan]{'TRAFFIC RATIO':<18}[/cyan] : {traffic_ratio}")
        console.print(f"[cyan]{'BUCKET KEY':<18}[/cyan] : {bucket_key}")
        console.print(f"[cyan]{'EFFECTIVE FROM':<18}[/cyan] : {effective_from_text}")
        console.print(f"[cyan]{'EFFECTIVE TO':<18}[/cyan] : {effective_to_text}")
        console.print(f"[cyan]{'CREATED BY':<18}[/cyan] : {result['created_by'] or '-'}")

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
