# datamind/audit/worker.py

"""审计事件消费 Worker

从队列消费审计事件并写入数据库，支持优雅启停。

核心功能：
  - audit_worker: 审计事件消费协程
  - start_audit_worker: 启动审计 Worker
  - stop_audit_worker: 停止审计 Worker

使用示例：

  import asyncio
  from datamind.audit.worker import start_audit_worker, stop_audit_worker

  async def main():
      # 启动审计 Worker
      await start_audit_worker()

      try:
          # 启动你的应用逻辑
          await run_app()
      finally:
          # 应用关闭时优雅停止 Worker
          await stop_audit_worker()

  asyncio.run(main())
"""

import time
import asyncio
import structlog
from typing import Optional

from datamind.audit.dispatcher import get_queue
from datamind.audit.writer import AuditWriter

logger = structlog.get_logger(__name__)

_worker_task: Optional[asyncio.Task] = None
_shutdown_event = asyncio.Event()

# 队列告警控制
_last_queue_warn: float = 0.0
QUEUE_BACKLOG_THRESHOLD = 100
QUEUE_WARN_INTERVAL = 5

# 重试
MAX_RETRIES = 3
BASE_DELAY = 0.1

async def _write(event) -> None:
    queue = get_queue()

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            obj = await AuditWriter.write(event)

            if obj is None:
                logger.error(
                    "审计写入返回为空，但已忽略",
                    action=event.action,
                    target_id=event.target_id,
                    trace_id=event.trace_id,
                )
                return

            logger.debug(
                "审计写入成功",
                action=event.action,
                target_id=event.target_id,
                status=event.status,
                trace_id=event.trace_id,
                request_id=event.request_id,
                source=event.source,
                user=event.user,
                ip=event.ip,
            )
            return

        except Exception as e:
            queue_size = queue.qsize()

            if attempt == MAX_RETRIES:
                logger.error(
                    "审计写入失败，重试次数已耗尽",
                    error=str(e),
                    attempt=attempt,
                    queue_size=queue_size,
                    action=event.action,
                    target_id=event.target_id,
                    trace_id=event.trace_id,
                    request_id=event.request_id,
                    source=event.source,
                    user=event.user,
                    ip=event.ip,
                    exc_info=True,
                )
                return

            delay = BASE_DELAY * (2 ** (attempt - 1))

            logger.warning(
                "审计写入重试",
                error=str(e),
                attempt=attempt,
                delay=delay,
                queue_size=queue_size,
                action=event.action,
                target_id=event.target_id,
                trace_id=event.trace_id,
                request_id=event.request_id,
                source=event.source,
                user=event.user,
                ip=event.ip,
            )

            await asyncio.sleep(delay)


async def audit_worker():
    """审计事件消费 Worker"""
    global _last_queue_warn

    queue = get_queue()

    while not _shutdown_event.is_set():
        try:
            event = await asyncio.wait_for(queue.get(), timeout=1.0)

            queue_size = queue.qsize()
            now = time.time()

            if queue_size > QUEUE_BACKLOG_THRESHOLD and now - _last_queue_warn > QUEUE_WARN_INTERVAL:
                logger.warning(
                    "审计队列出现积压",
                    queue_size=queue_size,
                    action=event.action,
                )
                _last_queue_warn = now

            logger.debug(
                "审计事件消费",
                action=event.action,
                target_id=event.target_id,
                status=event.status,
                trace_id=event.trace_id,
                request_id=event.request_id,
                source=event.source,
                user=event.user,
                ip=event.ip,
            )

        except asyncio.TimeoutError:
            continue

        try:
            await _write(event)

        except Exception as e:
            logger.error(
                "审计 Worker 异常",
                error=str(e),
                exc_info=True,
            )

        finally:
            queue.task_done()

    logger.debug("审计 Worker 已停止")


async def start_audit_worker():
    """启动审计 Worker"""
    global _worker_task

    if _worker_task and not _worker_task.done():
        logger.warning("审计 Worker 已在运行，跳过重复启动")
        return

    _shutdown_event.clear()
    _worker_task = asyncio.create_task(audit_worker())
    logger.debug("审计 Worker 启动成功")


async def stop_audit_worker():
    """停止审计 Worker"""
    global _worker_task

    if not _worker_task:
        return

    _shutdown_event.set()
    await _worker_task
    _worker_task = None