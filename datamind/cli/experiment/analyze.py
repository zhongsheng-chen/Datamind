# datamind/cli/experiment/analyze.py

"""实验分析命令

提供 A/B 实验效果分析功能。

核心功能：
  - analyze_experiment: 分析实验效果

使用示例：
  python -m datamind.cli.main experiment analyze exp_a1b2c3d4
"""

import asyncio
import json
import typer
import structlog
from typing import Any
from rich import box
from rich.console import Console
from rich.table import Table

from datamind.ab_test.analyzer import ABTestAnalyzer
from datamind.ab_test.metrics import ABTestMetricEvaluator
from datamind.cli.common import cli_context
from datamind.db.core import UnitOfWork
from datamind.db.repositories import (
    ExperimentRepository,
    OutcomeRepository,
    VariantRepository,
)

app = typer.Typer(help="实验分析命令")
console = Console()

logger = structlog.get_logger(__name__)


@app.command("analyze")
def analyze_experiment(
    experiment_id: str = typer.Argument(
        ...,
        help="实验 ID"
    ),
    baseline_variant_id: str | None = typer.Option(
        None,
        "--baseline-variant-id",
        help="基准分组 ID"
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="实验结果数量限制"
    ),
    offset: int | None = typer.Option(
        None,
        "--offset",
        help="实验结果分页偏移"
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
    """分析实验效果"""

    async def _run():
        if output not in ("text", "json"):
            raise typer.BadParameter("--format 只支持 text 或 json")

        logger.info(
            "开始分析实验",
            experiment_id=experiment_id,
            baseline_variant_id=baseline_variant_id,
        )

        async with UnitOfWork() as uow:
            analyzer = ABTestAnalyzer(
                experiment_repo=ExperimentRepository(uow.session),
                variant_repo=VariantRepository(uow.session),
                outcome_repo=OutcomeRepository(uow.session),
                metric_evaluator=ABTestMetricEvaluator(),
            )

            analysis = await analyzer.analyze_experiment(
                experiment_id=experiment_id,
                baseline_variant_id=baseline_variant_id,
                limit=limit,
                offset=offset,
            )

        result = analysis.to_dict()

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

        _print_analysis(result)

        return result

    async def runner():
        async with cli_context(
            verbose=verbose,
            enable_audit=False,
        ):
            await _run()

    asyncio.run(runner())


def _print_analysis(result: dict[str, Any]) -> None:
    """打印实验分析结果

    参数：
        result: 实验分析结果
    """
    console.print("[green]实验分析结果[/green]\n")

    console.print(f"[cyan]{'EXPERIMENT ID':<20}[/cyan] : {result['experiment_id']}")
    console.print(f"[cyan]{'MODEL ID':<20}[/cyan] : {result['model_id']}")
    console.print(f"[cyan]{'NAME':<20}[/cyan] : {result['name'] or '-'}")
    console.print(f"[cyan]{'STATUS':<20}[/cyan] : {result['status']}")
    console.print(f"[cyan]{'BASELINE VARIANT':<20}[/cyan] : {result['baseline_variant_id'] or '-'}")
    console.print(f"[cyan]{'OUTCOME COUNT':<20}[/cyan] : {result['outcome_count']}")

    console.print()
    _print_metrics_table(result["metrics"]["variants"])

    comparisons = result["metrics"].get("comparisons") or {}

    if comparisons:
        console.print()
        _print_comparison_table(comparisons)

    warnings = result.get("warnings") or []

    if warnings:
        console.print()
        console.print("[yellow]提示[/yellow]")

        for item in warnings:
            console.print(f"- {item}")


def _print_metrics_table(variants: dict[str, Any]) -> None:
    """打印分组指标表

    参数：
        variants: 分组指标字典
    """
    table = Table(
        title="分组指标",
        box=box.ASCII,
        header_style="bold cyan",
        show_lines=False,
        pad_edge=False,
    )

    table.add_column("VARIANT ID")
    table.add_column("TOTAL")
    table.add_column("APPROVAL")
    table.add_column("CONVERSION")
    table.add_column("DEFAULT")
    table.add_column("BAD")
    table.add_column("AVG AMOUNT")

    for variant_id, metrics in variants.items():
        table.add_row(
            str(variant_id),
            str(metrics["total_count"]),
            _format_rate(metrics["approval_rate"]),
            _format_rate(metrics["conversion_rate"]),
            _format_rate(metrics["default_rate"]),
            _format_rate(metrics["bad_rate"]),
            f"{metrics['average_amount']:.2f}",
        )

    console.print(table)


def _print_comparison_table(comparisons: dict[str, Any]) -> None:
    """打印 Lift 对比表

    参数：
        comparisons: Lift 对比结果
    """
    table = Table(
        title="Lift 对比",
        box=box.ASCII,
        header_style="bold cyan",
        show_lines=False,
        pad_edge=False,
    )

    table.add_column("VARIANT ID")
    table.add_column("METRIC")
    table.add_column("BASELINE")
    table.add_column("VARIANT")
    table.add_column("ABS LIFT")
    table.add_column("REL LIFT")

    for variant_id, metric_map in comparisons.items():
        for metric, comparison in metric_map.items():
            relative_lift = comparison["relative_lift"]

            if relative_lift is None:
                relative_lift_text = "-"
            else:
                relative_lift_text = _format_rate(relative_lift)

            table.add_row(
                str(variant_id),
                str(metric),
                _format_float(comparison["baseline_value"]),
                _format_float(comparison["variant_value"]),
                _format_float(comparison["absolute_lift"]),
                relative_lift_text,
            )

    console.print(table)


def _format_rate(value: float) -> str:
    """格式化比例"""
    return f"{value:.2%}"


def _format_float(value: float) -> str:
    """格式化浮点数"""
    return f"{value:.4f}"