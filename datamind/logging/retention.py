"""日志保留管理

提供日志文件清理和后台定期清理功能。

核心功能：
  - cleanup_logs: 清理过期日志文件
  - start_retention_worker: 启动日志保留线程
  - stop_retention_worker: 停止日志保留线程

使用示例：
  from datamind.logging.retention import (
      start_retention_worker,
      stop_retention_worker,
  )

  start_retention_worker(config)

  # 进程退出前显式调用
  stop_retention_worker()
"""

import threading
from datetime import (
    datetime,
    timedelta,
)
from pathlib import Path
from typing import Final
from zoneinfo import (
    ZoneInfo,
    ZoneInfoNotFoundError,
)

import structlog

from datamind.config.logging import LoggingConfig


logger = structlog.get_logger(__name__)

_CHECK_INTERVAL_SECONDS: Final[float] = 3600.0
_STOP_TIMEOUT_SECONDS: Final[float] = 5.0

_RETENTION_THREAD: threading.Thread | None = None
_RETENTION_STOP_EVENT = threading.Event()
_RETENTION_LOCK = threading.Lock()


def cleanup_logs(
        log_dir: Path,
        retention_days: int,
        timezone: str,
) -> None:
    """清理过期日志文件

    参数：
        log_dir: 日志目录路径
        retention_days: 日志保留天数
        timezone: IANA 时区名称

    异常：
        ZoneInfoNotFoundError: 时区名称无效
    """
    if retention_days <= 0:
        return

    if not log_dir.exists():
        return

    tz = ZoneInfo(timezone)
    expire_time = (
        datetime.now(tz)
        - timedelta(days=retention_days)
    )

    for file_path in log_dir.glob("*.log*"):
        if not file_path.is_file():
            continue

        try:
            modified_time = datetime.fromtimestamp(
                file_path.stat().st_mtime,
                tz,
            )

            if modified_time < expire_time:
                file_path.unlink()
                logger.debug(
                    "删除过期日志文件",
                    file=str(file_path),
                )

        except FileNotFoundError:
            continue

        except PermissionError:
            logger.warning(
                "权限不足，无法删除日志文件",
                file=str(file_path),
            )

        except OSError as exc:
            logger.warning(
                "删除日志文件失败",
                file=str(file_path),
                error=str(exc),
            )


def start_retention_worker(
        config: LoggingConfig,
) -> None:
    """启动日志保留线程

    已运行时重复调用不会创建新的线程。

    参数：
        config: 日志配置对象
    """
    global _RETENTION_THREAD

    with _RETENTION_LOCK:
        if (
            _RETENTION_THREAD is not None
            and _RETENTION_THREAD.is_alive()
        ):
            return

        _RETENTION_STOP_EVENT.clear()

        def worker() -> None:
            while not _RETENTION_STOP_EVENT.is_set():
                try:
                    cleanup_logs(
                        config.dir,
                        config.retention_days,
                        config.timezone,
                    )

                except ZoneInfoNotFoundError as exc:
                    logger.error(
                        "日志保留线程时区配置无效",
                        timezone=config.timezone,
                        error=str(exc),
                    )

                except OSError as exc:
                    logger.warning(
                        "日志保留线程清理失败",
                        log_dir=str(config.dir),
                        error=str(exc),
                    )

                if _RETENTION_STOP_EVENT.wait(
                        _CHECK_INTERVAL_SECONDS
                ):
                    break

        thread = threading.Thread(
            target=worker,
            daemon=True,
            name="datamind-log-retention",
        )
        _RETENTION_THREAD = thread
        thread.start()

    logger.debug(
        "日志保留线程已启动",
        check_interval=_CHECK_INTERVAL_SECONDS,
    )


def stop_retention_worker() -> None:
    """停止日志保留线程"""
    global _RETENTION_THREAD

    with _RETENTION_LOCK:
        thread = _RETENTION_THREAD

        if thread is None:
            return

        _RETENTION_STOP_EVENT.set()

    thread.join(
        timeout=_STOP_TIMEOUT_SECONDS
    )

    with _RETENTION_LOCK:
        if thread.is_alive():
            logger.warning(
                "日志保留线程未在超时时间内停止",
                timeout=_STOP_TIMEOUT_SECONDS,
            )
            return

        if _RETENTION_THREAD is thread:
            _RETENTION_THREAD = None

    logger.debug(
        "日志保留线程已停止"
    )
