# datamind/core/logging/cleanup.py

"""日志清理管理器

自动清理过期日志文件，支持按保留天数清理、日志归档和定时清理任务。

核心功能：
  - start: 启动定时清理任务
  - stop: 停止清理任务
  - cleanup_old_logs: 立即执行清理
  - run_cleanup_now: 手动触发清理
  - get_stats: 获取清理管理器统计信息

特性：
  - 按保留天数清理：删除超过指定天数的日志文件
  - 日志归档：自动压缩归档过期日志
  - 定时清理任务：按配置时间自动执行清理
  - 时区感知：归档目录按日期分组
  - 多压缩格式：支持 gz/bz2/xz 压缩格式
  - 跨平台：支持 Windows/Linux/macOS

使用示例：
    from datamind.core.logging.cleanup import CleanupManager
    from datamind.core.logging.formatters import TimezoneFormatter

    manager = CleanupManager(config, timezone_formatter)
    manager.start()

    # 手动触发清理
    result = manager.run_cleanup_now()
    print(f"删除了 {result['deleted']} 个文件，归档了 {result['archived']} 个文件")

    # 获取统计信息
    stats = manager.get_stats()

    # 停止清理任务
    manager.stop()
"""

import os
import sys
import shutil
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from datamind import PROJECT_ROOT
from datamind.config.logging_config import LoggingConfig
from datamind.core.logging.formatters import TimezoneFormatter

_logger = logging.getLogger(__name__)

# 清理管理器调试开关
_CLEANUP_DEBUG = os.environ.get('DATAMIND_CLEANUP_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')


def _debug(msg: str, *args) -> None:
    """清理管理器内部调试输出"""
    if _CLEANUP_DEBUG:
        if args:
            print(f"[Cleanup] {msg % args}", file=sys.stderr)
        else:
            print(f"[Cleanup] {msg}", file=sys.stderr)


def _format_seconds(seconds: float) -> str:
    """将秒数格式化为可读的时间字符串"""
    if seconds < 0:
        return "0秒"

    minutes, seconds = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分钟")
    if seconds > 0 and not parts:
        parts.append(f"{seconds}秒")

    return "".join(parts) if parts else "0秒"


class CleanupManager:
    """日志清理管理器"""

    def __init__(self, config: LoggingConfig, timezone_formatter: TimezoneFormatter):
        """
        初始化清理管理器

        参数:
            config: 日志配置
            timezone_formatter: 时区格式化器
        """
        self.config: LoggingConfig = config
        self.timezone_formatter: TimezoneFormatter = timezone_formatter
        self._stop_cleanup: threading.Event = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._lock: threading.Lock = threading.Lock()
        _debug("初始化清理管理器，保留天数: %d, 归档: %s",
               config.retention_days, "开启" if config.archive_enabled else "关闭")

    def start(self) -> None:
        """启动清理任务"""
        if not self._should_run_cleanup():
            _debug("清理任务未启动: archive_enabled=%s, retention_days=%d",
                   self.config.archive_enabled, self.config.retention_days)
            return

        def cleanup_job() -> None:
            _debug("清理任务线程启动")
            while not self._stop_cleanup.wait(self._get_seconds_to_next_cleanup()):
                try:
                    result = self.cleanup_old_logs()
                    if result['deleted'] > 0 or result['archived'] > 0:
                        _debug("清理完成: 删除 %d 个文件, 归档 %d 个文件",
                               result['deleted'], result['archived'])
                except Exception as e:
                    _logger.error("清理任务执行失败: %s", e, exc_info=True)

        self._cleanup_thread = threading.Thread(
            target=cleanup_job,
            daemon=True,
            name="LogCleanupThread"
        )
        self._cleanup_thread.start()
        _debug("清理任务已启动，线程: %s", self._cleanup_thread.name)

    def stop(self) -> None:
        """停止清理任务"""
        _debug("停止清理任务")
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5)
            if self._cleanup_thread.is_alive():
                _logger.warning("清理线程未在5秒内停止")
            else:
                _debug("清理线程已停止")

    def cleanup_old_logs(self) -> Dict[str, int]:
        """
        清理旧日志文件

        返回:
            清理结果统计 {'deleted': int, 'archived': int}
        """
        result = {'deleted': 0, 'archived': 0}

        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            cutoff_timestamp = cutoff_date.timestamp()
            _debug("开始清理旧日志，截止日期: %s", cutoff_date)

            log_files = self._collect_log_files()

            for log_file in log_files:
                if not log_file or not os.path.exists(log_file):
                    continue

                log_dir = os.path.dirname(log_file)
                base_name = os.path.basename(log_file)

                if not os.path.exists(log_dir):
                    _debug("日志目录不存在: %s", log_dir)
                    continue

                rotated_files = self._get_log_rotated_files(log_dir, base_name)
                _debug("目录 %s 中找到 %d 个轮转文件", log_dir, len(rotated_files))

                for file_path in rotated_files:
                    if not self._should_cleanup_file(file_path, cutoff_timestamp):
                        continue

                    _debug("文件需要清理: %s", os.path.basename(file_path))

                    if self.config.archive_enabled:
                        if self._archive_file(file_path):
                            result['archived'] += 1
                    else:
                        if self._delete_file(file_path):
                            result['deleted'] += 1

            _debug("清理完成: 删除 %d 个文件, 归档 %d 个文件",
                   result['deleted'], result['archived'])

        except Exception as e:
            _logger.error("日志清理失败: %s", e, exc_info=True)

        return result

    def run_cleanup_now(self) -> Dict[str, int]:
        """
        立即执行清理（用于手动触发）

        返回:
            清理结果统计
        """
        _debug("手动触发清理任务")
        return self.cleanup_old_logs()

    def get_stats(self) -> Dict[str, Any]:
        """
        获取清理管理器统计信息

        返回:
            统计信息字典
        """
        stats = {
            'running': self._cleanup_thread is not None and self._cleanup_thread.is_alive(),
            'retention_days': self.config.retention_days,
            'archive_enabled': self.config.archive_enabled,
            'cleanup_time': self.config.cleanup_at_time,
        }

        if stats['running']:
            stats['next_cleanup_seconds'] = self._get_seconds_to_next_cleanup()

        return stats

    def get_archive_size(self) -> int:
        """
        获取归档目录大小（字节）

        返回:
            归档目录总大小
        """
        if not self.config.archive_enabled:
            return 0

        archive_path = self._get_resolved_archive_path()
        if not archive_path.exists():
            return 0

        total_size = 0
        for file_path in archive_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size

    def _get_resolved_log_dir(self) -> Path:
        """获取解析后的日志目录"""
        log_dir = Path(self.config.log_dir)
        if log_dir.is_absolute():
            return log_dir
        return PROJECT_ROOT / self.config.log_dir

    def _get_resolved_archive_path(self) -> Path:
        """获取解析后的归档路径"""
        archive_path = Path(self.config.archive_path)
        if archive_path.is_absolute():
            return archive_path

        log_dir = self._get_resolved_log_dir()
        return log_dir / self.config.archive_path

    def _should_run_cleanup(self) -> bool:
        """判断是否应该运行清理任务"""
        return self.config.archive_enabled or self.config.retention_days < 365

    def _get_seconds_to_next_cleanup(self) -> float:
        """计算到下次清理时间的秒数"""
        now = datetime.now()
        cleanup_hour, cleanup_minute = map(int, self.config.cleanup_at_time.split(':'))
        cleanup_time = now.replace(
            hour=cleanup_hour,
            minute=cleanup_minute,
            second=0,
            microsecond=0
        )

        if cleanup_time <= now:
            cleanup_time += timedelta(days=1)

        seconds = (cleanup_time - now).total_seconds()
        _debug("下次清理时间: %s, 等待: %s", cleanup_time, _format_seconds(seconds))
        return seconds

    def _collect_log_files(self) -> List[str]:
        """收集所有需要清理的日志文件"""
        return [self.config.log_file] if self.config.log_file else []

    @staticmethod
    def _get_log_rotated_files(log_dir: str, base_name: str) -> List[str]:
        """获取日志的轮转文件"""
        try:
            files = os.listdir(log_dir)
        except OSError as e:
            _logger.warning("无法列出目录 %s: %s", log_dir, e)
            return []

        return [
            os.path.join(log_dir, f)
            for f in files
            if f.startswith(base_name + ".") and f != base_name
        ]

    @staticmethod
    def _should_cleanup_file(file_path: str, cutoff_timestamp: float) -> bool:
        """判断文件是否需要清理"""
        try:
            if not os.path.isfile(file_path):
                return False
            return os.path.getmtime(file_path) < cutoff_timestamp
        except OSError as e:
            _logger.warning("检查文件 %s 时出错: %s", file_path, e)
            return False

    @staticmethod
    def _delete_file(file_path: str) -> bool:
        """删除文件，返回是否成功"""
        try:
            os.remove(file_path)
            _debug("已删除文件: %s", file_path)
            return True
        except OSError as e:
            _logger.error("删除文件失败 %s: %s", file_path, e)
            return False

    def _compress_file(self, source_path: str, target_path: str) -> None:
        """根据配置的压缩格式压缩文件"""
        compression = self.config.archive_compression

        if compression == "gz":
            import gzip
            with open(source_path, 'rb') as f_in:
                with gzip.open(target_path, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif compression == "bz2":
            import bz2
            with open(source_path, 'rb') as f_in:
                with bz2.open(target_path, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif compression == "xz":
            import lzma
            with open(source_path, 'rb') as f_in:
                with lzma.open(target_path, 'wb', preset=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            raise ValueError(f"不支持的压缩格式: {compression}")

    def _archive_file(self, file_path: str) -> bool:
        """归档文件，返回是否成功"""
        temp_path = None

        try:
            if not os.path.exists(file_path):
                _debug("文件不存在: %s", file_path)
                return False

            if not os.access(file_path, os.R_OK):
                _logger.warning("文件不可读: %s", file_path)
                return False

            temp_path = file_path + '.tmp'
            shutil.copy2(file_path, temp_path)
            _debug("已创建临时文件: %s", temp_path)

            archive_path = self._get_archive_path(file_path)
            archive_dir = os.path.dirname(archive_path)
            Path(archive_dir).mkdir(parents=True, exist_ok=True)
            _debug("归档目录: %s", archive_dir)

            if os.path.exists(archive_path):
                _debug("归档文件已存在: %s", archive_path)
                base, ext = os.path.splitext(archive_path)
                archive_path = f"{base}_{int(datetime.now().timestamp())}{ext}"
                _debug("使用新路径: %s", archive_path)

            self._compress_file(temp_path, archive_path)

            os.remove(file_path)
            os.remove(temp_path)
            _debug("日志归档成功: %s -> %s", file_path, archive_path)
            return True

        except Exception as e:
            _logger.error("日志归档失败 %s: %s", file_path, e, exc_info=True)
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _get_archive_path(self, file_path: str) -> str:
        """获取归档文件路径"""
        current_time = self.timezone_formatter.format_time()
        date_str = current_time.strftime(self.config.file_name_date_format)

        archive_base = self._get_resolved_archive_path()
        archive_subdir = archive_base / date_str

        base_name = os.path.basename(file_path)
        timestamp = current_time.strftime(self.config.archive_name_format)
        archive_name = f"{base_name}.{timestamp}.{self.config.archive_compression}"

        return str(archive_subdir / archive_name)

    def __enter__(self) -> 'CleanupManager':
        self.start()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        self.stop()


__all__ = ["CleanupManager"]