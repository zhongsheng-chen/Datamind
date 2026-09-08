"""数据库健康检查

提供数据库连接状态检查能力。

核心功能：
  - health_check: 检查数据库健康状态

使用示例：
  from datamind.db.health import health_check

  result = await health_check()

  print(
      result["status"]
  )
"""

import time

import structlog
from sqlalchemy import text

from datamind.db.core.engine import get_engine


logger = structlog.get_logger(__name__)


async def health_check(
) -> dict[str, str | float | None]:
    """检查数据库健康状态

    检查范围包括数据库配置、引擎创建和连接执行。

    返回：
        包含 status、latency_ms 和 error 的字典
    """
    started_at = time.perf_counter()

    try:
        engine = get_engine()

        async with engine.connect() as connection:
            await connection.execute(
                text(
                    "SELECT 1"
                )
            )

        latency_ms = round(
            (
                time.perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        result: dict[
            str,
            str | float | None,
        ] = {
            "status": "ok",
            "latency_ms": latency_ms,
            "error": None,
        }

        logger.info(
            "数据库健康检查通过",
            status="ok",
            latency_ms=latency_ms,
        )

        return result

    except Exception as exc:
        latency_ms = round(
            (
                time.perf_counter()
                - started_at
            )
            * 1000,
            2,
        )

        error = str(
            exc
        )

        result = {
            "status": "error",
            "latency_ms": latency_ms,
            "error": error,
        }

        logger.error(
            "数据库健康检查失败",
            status="error",
            latency_ms=latency_ms,
            error=error,
        )

        return result
