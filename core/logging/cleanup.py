# core/logging/cleanup.py
import os
import threading
import logging
import shutil
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from config.logging_config import LoggingConfig, LogFormat
from core.logging.formatters import TimezoneFormatter


class CleanupManager:
    """日志清理管理器"""

    def __init__(self, config: LoggingConfig, timezone_formatter: TimezoneFormatter):
        self.config = config
        self.timezone_formatter = timezone_formatter
        self._stop_cleanup = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None

    def start(self):
        """启动清理任务"""
        if not (self.config.archive_enabled or self.config.retention_days < 365):
            return

        def cleanup_job():
            while not self._stop_cleanup.wait(self._get_seconds_to_next_cleanup()):
                try:
                    self.cleanup_old_logs()
                except Exception as e:
                    logging.getLogger().error(f"清理任务执行失败: {e}")

        self._cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
        self._cleanup_thread.start()

    def stop(self):
        """停止清理任务"""
        if self._cleanup_thread:
            self._stop_cleanup.set()

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

        return (cleanup_time - now).total_seconds()

    def get_both_filename(self, base_filename: str, suffix: str) -> str:
        """获取BOTH格式的文件名"""
        base, ext = os.path.splitext(base_filename)
        if suffix == 'text':
            suffix = self.config.text_suffix
        else:
            suffix = self.config.json_suffix
        return f"{base}.{suffix}{ext}"

    def _collect_log_files(self) -> List[str]:
        """收集所有需要清理的日志文件"""
        log_files = [
            self.config.file,
            self.config.error_file,
            self.config.access_log_file,
            self.config.audit_log_file,
            self.config.performance_log_file
        ]

        # 如果是BOTH格式，还需要清理对应的text和json文件
        if self.config.format == LogFormat.BOTH:
            extended_files = []
            for f in log_files:
                if f:
                    extended_files.append(self.get_both_filename(f, 'text'))
                    extended_files.append(self.get_both_filename(f, 'json'))
            log_files.extend(extended_files)

        return [f for f in log_files if f]

    def cleanup_old_logs(self):
        """清理旧日志文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            cutoff_timestamp = cutoff_date.timestamp()

            log_files = self._collect_log_files()

            for log_file in log_files:
                if not log_file or not os.path.exists(log_file):
                    continue

                log_dir = os.path.dirname(log_file)
                log_name = os.path.basename(log_file)

                if not os.path.exists(log_dir):
                    continue

                for f in os.listdir(log_dir):
                    if f.startswith(log_name + ".") and f != log_name:
                        file_path = os.path.join(log_dir, f)
                        if os.path.isfile(file_path):
                            file_mtime = os.path.getmtime(file_path)

                            if file_mtime < cutoff_timestamp:
                                if self.config.archive_enabled:
                                    self._archive_file(file_path)
                                else:
                                    os.remove(file_path)
                                    logging.getLogger().info(f"删除旧日志文件: {file_path}")

        except Exception as e:
            logging.getLogger().error(f"日志清理失败: {e}")

    def _archive_file(self, file_path: str):
        """归档文件"""
        temp_path = None
        try:
            # 先复制到临时文件
            temp_path = file_path + '.tmp'
            shutil.copy2(file_path, temp_path)

            # 创建归档目录
            current_time = self.timezone_formatter.format_time()
            date_str = current_time.strftime(self.config.file_name_date_format)
            archive_subdir = os.path.join(
                self.config.archive_path,
                date_str
            )
            Path(archive_subdir).mkdir(parents=True, exist_ok=True)

            # 生成归档文件名
            base_name = os.path.basename(file_path)
            timestamp = current_time.strftime(self.config.archive_name_format)
            archive_name = f"{base_name}.{timestamp}.{self.config.archive_compression}"
            archive_path = os.path.join(archive_subdir, archive_name)

            # 压缩归档
            with open(temp_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # 删除原文件和临时文件
            os.remove(file_path)
            os.remove(temp_path)

            logging.getLogger().info(f"日志归档成功: {file_path} -> {archive_path}")

        except Exception as e:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            logging.getLogger().error(f"日志归档失败 {file_path}: {e}")