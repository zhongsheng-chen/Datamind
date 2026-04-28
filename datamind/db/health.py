# datamind/db/health.py

"""数据库健康检查

提供数据库连接状态检查能力。

核心功能：
  - health_check: 检查数据库健康状态

使用示例：
  from datamind.db.health import health_check

  result = await health_check()
  print(result["status"])
"""

import time
from sqlalchemy import text

from datamind.db.core.engine import get_engine
from datamind.logging import get_logger

logger = get_logger(__name__)


async def health_check() -> dict:
    """检查数据库健康状态

    返回：
        包含 status、latency_ms、error 的字典
    """
    engine = get_engine()

    if engine is None:
        return {
            "status": "error",
            "latency_ms": 0,
            "error": "engine_not_initialized",
        }

    start = time.perf_counter()

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

        latency = (time.perf_counter() - start) * 1000

        result = {
            "status": "ok",
            "latency_ms": round(latency, 2),
            "error": None,
        }

        logger.info(
            "数据库健康检查通过",
            status=result["status"],
            latency_ms=result["latency_ms"],
        )

        return result

    except Exception as e:
        latency = (time.perf_counter() - start) * 1000

        result = {
            "status": "error",
            "latency_ms": round(latency, 2),
            "error": str(e),
        }

        logger.error(
            "数据库健康检查失败",
            status=result["status"],
            latency_ms=result["latency_ms"],
            error=result["error"],
        )

        return result