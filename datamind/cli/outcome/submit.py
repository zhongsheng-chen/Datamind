"""实验结果提交命令

提供延迟业务结果的幂等回流功能。

核心功能：
  - submit_outcome: 提交或更新实验结果

使用示例：
  python -m datamind.cli.main outcome submit customer_001 \
    --decision-id dec_0123456789abcdef \
    --approved \
    --amount 1000
"""

import asyncio
import json
from datetime import datetime
from typing import Any

import structlog
import typer
from datamind.cli.output import CLIConsole

from datamind.audit import audit
from datamind.cli.common import cli_context
from datamind.services import OutcomeService
from datamind.utils.datetime import format_iso_utc, parse_datetime
from datamind.utils.generator import generate_random_id

app = typer.Typer(help="实验结果提交命令")
console = CLIConsole()

logger = structlog.get_logger(__name__)


def _parse_context(
        value: str | None,
) -> dict[str, Any] | None:
    """解析结果上下文 JSON"""
    if value is None:
        return None

    parsed = json.loads(
        value
    )

    if not isinstance(parsed, dict):
        raise typer.BadParameter(
            "--context 必须是 JSON 对象"
        )

    return parsed


@app.command("submit")
def submit_outcome(
        subject_key: str = typer.Argument(
            ...,
            help="结果主体标识"
        ),
        decision_id: str | None = typer.Option(
            None,
            "--decision-id",
            help="原始决策 ID"
        ),
        request_id: str | None = typer.Option(
            None,
            "--request-id",
            help="原始请求 ID"
        ),
        outcome_id: str | None = typer.Option(
            None,
            "--outcome-id",
            help="上游结果唯一标识，默认自动生成"
        ),
        subject_type: str | None = typer.Option(
            None,
            "--subject-type",
            help="结果主体类型"
        ),
        approved: bool | None = typer.Option(
            None,
            "--approved/--not-approved",
            help="是否审批通过"
        ),
        converted: bool | None = typer.Option(
            None,
            "--converted/--not-converted",
            help="是否发生转化"
        ),
        defaulted: bool | None = typer.Option(
            None,
            "--defaulted/--not-defaulted",
            help="是否发生违约"
        ),
        overdue_days: int | None = typer.Option(
            None,
            "--overdue-days",
            help="最大逾期天数"
        ),
        amount: float | None = typer.Option(
            None,
            "--amount",
            help="结果金额"
        ),
        label: str | None = typer.Option(
            None,
            "--label",
            help="结果标签"
        ),
        context: str | None = typer.Option(
            None,
            "--context",
            help="结果上下文 JSON 对象"
        ),
        outcome_time: datetime | None = typer.Option(
            None,
            "--outcome-time",
            parser=parse_datetime,
            help="结果发生时间，ISO 8601 格式"
        ),
        output: str = typer.Option(
            "text",
            "--format",
            help="输出格式：text / json"
        ),
) -> None:
    """提交或更新实验结果"""
    target_outcome_id = (
        outcome_id
        or generate_random_id(
            prefix="out"
        )
    )

    @audit(
        action="outcome.submit",
        target_type="outcome",
        target_id_from="target_id",
    )
    async def _run(
            *,
            target_id: str,
    ) -> dict[str, Any]:
        logger.info(
            "开始提交实验结果",
            outcome_id=target_id,
            subject_type=subject_type,
            decision_id=decision_id,
            request_id=request_id,
        )

        result = await OutcomeService().submit(
            outcome_id=target_id,
            subject_key=subject_key,
            decision_id=decision_id,
            request_id=request_id,
            subject_type=subject_type,
            approved=approved,
            converted=converted,
            defaulted=defaulted,
            overdue_days=overdue_days,
            amount=amount,
            label=label,
            context=_parse_context(
                context
            ),
            outcome_time=outcome_time,
        )

        outcome = result["outcome"]

        for field in (
                "outcome_time",
                "created_at",
                "updated_at",
        ):
            outcome[field] = format_iso_utc(
                outcome[field]
            )

        return result

    async def runner() -> None:
        async with cli_context(
                required_permission="outcome.write",
        ):
            result = await _run(
                target_id=target_outcome_id
            )

        if output == "json":
            console.print_json(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return

        outcome = result["outcome"]
        action = (
            "创建"
            if result["created"]
            else "更新"
        )
        console.info(f"实验结果{action}成功")
        console.print(
            f"{'OUTCOME ID':<18} : "
            f"{outcome['outcome_id']}"
        )
        console.print(
            f"{'DECISION ID':<18} : "
            f"{outcome['decision_id']}"
        )

    asyncio.run(
        runner()
    )
