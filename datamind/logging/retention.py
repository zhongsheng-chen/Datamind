# datamind/logging/retention.py

"""日志保留管理

提供日志文件清理功能，自动删除超过保留天数的日志文件。

核心功能：
  - cleanup_logs: 清理过期日志文件
  - start_retention_worker: 启动定期清理后台线程

使用示例：
  from datamind.logging.retention import start_retention_worker

  start_retention_worker(config)
"""

from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import threading
import time
import structlog

logger = structlog.get_logger(__name__)


def cleanup_logs(log_dir: Path, retention_days: int, timezone: str) -> None:
    """清理过期日志文件

    参数：
        log_dir: 日志目录路径
        retention_days: 日志保留天数
        timezone: 时区
    """
    if retention_days <= 0:
        return

    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    expire = now - timedelta(days=retention_days)

    for file in log_dir.glob("*.log*"):
        try:
            mtime = datetime.fromtimestamp(file.stat().st_mtime, tz)

            if mtime < expire:
                file.unlink()
                logger.debug("删除过期日志文件", file=str(file))

        except FileNotFoundError:
            pass
        except PermissionError:
            logger.warning("权限不足，无法删除日志文件", file=str(file))
        except OSError as e:
            logger.warning("删除日志文件失败", file=str(file), error=str(e))


def start_retention_worker(config) -> None:
    """启动定期清理后台线程

    参数：
        config: 日志配置对象（需包含 dir、retention_days、timezone 属性）
    """
    def worker():
        while True:
            cleanup_logs(
                config.dir,
                config.retention_days,
                config.timezone,
            )
            time.sleep(3600)  # 每小时检查一次

    thread = threading.Thread(
        target=worker,
        daemon=True,
        name="datamind-log-retention",
    )
    thread.start()