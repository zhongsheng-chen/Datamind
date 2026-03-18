# core/logging/cleanup.py

import os
import threading
import logging
import shutil
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from datamind.config import LoggingConfig, LogFormat
from datamind.core.logging.formatters import TimezoneFormatter
from datamind.core.logging.debug import debug_print



class CleanupManager:
    """日志清理管理器"""

    def __init__(self, config: LoggingConfig, timezone_formatter: TimezoneFormatter):
        self.config = config
        self.timezone_formatter = timezone_formatter
        self._stop_cleanup = threading.Event()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._debug("初始化清理管理器，保留天数: %d, 归档: %s",
                    config.retention_days, "开启" if config.archive_enabled else "关闭")

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.cleanup_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def start(self):
        """启动清理任务"""
        if not (self.config.archive_enabled or self.config.retention_days < 365):
            self._debug("清理任务未启动: archive_enabled=%s, retention_days=%d",
                        self.config.archive_enabled, self.config.retention_days)
            return

        def cleanup_job():
            self._debug("清理任务线程启动")
            while not self._stop_cleanup.wait(self._get_seconds_to_next_cleanup()):
                try:
                    self._debug("开始执行定期清理任务")
                    self.cleanup_old_logs()
                except Exception as e:
                    # 使用 logging 记录错误
                    logging.getLogger().error(f"清理任务执行失败: {e}")
                    # 使用调试输出记录详细信息
                    self._debug("清理任务执行失败: %s", e)

        self._cleanup_thread = threading.Thread(target=cleanup_job, daemon=True)
        self._cleanup_thread.start()
        self._debug("清理任务已启动，线程: %s", self._cleanup_thread.name)

    def stop(self):
        """停止清理任务"""
        self._debug("停止清理任务")
        if self._cleanup_thread:
            self._stop_cleanup.set()
            self._debug("清理停止信号已发送")

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
        self._debug("下次清理时间: %s, 等待: %.2f秒", cleanup_time, seconds)
        return seconds

    def get_both_filename(self, base_filename: str, suffix: str) -> str:
        """获取BOTH格式的文件名"""
        base, ext = os.path.splitext(base_filename)
        if suffix == 'text':
            suffix = self.config.text_suffix
        else:
            suffix = self.config.json_suffix
        both_filename = f"{base}.{suffix}{ext}"
        self._debug("生成BOTH文件名: %s -> %s", base_filename, both_filename)
        return both_filename

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
            self._debug("BOTH格式，添加额外的text和json文件")
            extended_files = []
            for f in log_files:
                if f:
                    text_file = self.get_both_filename(f, 'text')
                    json_file = self.get_both_filename(f, 'json')
                    extended_files.append(text_file)
                    extended_files.append(json_file)
                    self._debug("添加额外文件: %s, %s", text_file, json_file)
            log_files.extend(extended_files)

        collected = [f for f in log_files if f]
        self._debug("收集到 %d 个日志文件需要清理", len(collected))
        return collected

    def cleanup_old_logs(self):
        """清理旧日志文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=self.config.retention_days)
            cutoff_timestamp = cutoff_date.timestamp()
            self._debug("开始清理旧日志，截止日期: %s, 时间戳: %d",
                        cutoff_date, cutoff_timestamp)

            log_files = self._collect_log_files()
            total_deleted = 0
            total_archived = 0

            for log_file in log_files:
                if not log_file or not os.path.exists(log_file):
                    continue

                log_dir = os.path.dirname(log_file)
                log_name = os.path.basename(log_file)

                if not os.path.exists(log_dir):
                    self._debug("日志目录不存在: %s", log_dir)
                    continue

                self._debug("检查目录: %s, 基础文件名: %s", log_dir, log_name)
                try:
                    dir_files = os.listdir(log_dir)
                except Exception as e:
                    self._debug("无法列出目录 %s: %s", log_dir, e)
                    continue

                self._debug("目录中共有 %d 个文件", len(dir_files))

                for f in dir_files:
                    if f.startswith(log_name + ".") and f != log_name:
                        file_path = os.path.join(log_dir, f)
                        if os.path.isfile(file_path):
                            try:
                                file_mtime = os.path.getmtime(file_path)
                                file_date = datetime.fromtimestamp(file_mtime)
                                self._debug("检查文件: %s, 修改时间: %s", f, file_date)

                                if file_mtime < cutoff_timestamp:
                                    self._debug("文件需要清理: %s (修改时间: %s)", f, file_date)
                                    if self.config.archive_enabled:
                                        if self._archive_file(file_path):
                                            total_archived += 1
                                    else:
                                        os.remove(file_path)
                                        total_deleted += 1
                                        self._debug("已删除文件: %s", file_path)
                                        logging.getLogger().info(f"删除旧日志文件: {file_path}")
                                else:
                                    self._debug("文件保留: %s (修改时间: %s)", f, file_date)
                            except Exception as e:
                                self._debug("处理文件 %s 时出错: %s", f, e)

            self._debug("清理完成: 删除 %d 个文件, 归档 %d 个文件", total_deleted, total_archived)

        except Exception as e:
            logging.getLogger().error(f"日志清理失败: {e}")
            self._debug("清理过程发生异常: %s", e)

    def _archive_file(self, file_path: str) -> bool:
        """归档文件，返回是否成功"""
        temp_path = None
        try:
            self._debug("开始归档文件: %s", file_path)

            # 先复制到临时文件
            temp_path = file_path + '.tmp'
            shutil.copy2(file_path, temp_path)
            self._debug("已创建临时文件: %s", temp_path)

            # 创建归档目录
            current_time = self.timezone_formatter.format_time()
            date_str = current_time.strftime(self.config.file_name_date_format)
            archive_subdir = os.path.join(
                self.config.archive_path,
                date_str
            )
            Path(archive_subdir).mkdir(parents=True, exist_ok=True)
            self._debug("归档子目录: %s", archive_subdir)

            # 生成归档文件名
            base_name = os.path.basename(file_path)
            timestamp = current_time.strftime(self.config.archive_name_format)
            archive_name = f"{base_name}.{timestamp}.{self.config.archive_compression}"
            archive_path = os.path.join(archive_subdir, archive_name)
            self._debug("归档文件路径: %s", archive_path)

            # 压缩归档
            file_size = os.path.getsize(temp_path)
            self._debug("开始压缩，原文件大小: %d 字节", file_size)

            with open(temp_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            archived_size = os.path.getsize(archive_path)
            compression_ratio = (archived_size / file_size * 100) if file_size > 0 else 0
            self._debug("压缩完成，归档文件大小: %d 字节，压缩率: %.2f%%",
                        archived_size, compression_ratio)

            # 删除原文件和临时文件
            os.remove(file_path)
            os.remove(temp_path)
            self._debug("已删除原文件和临时文件")

            logging.getLogger().info(f"日志归档成功: {file_path} -> {archive_path}")
            return True

        except Exception as e:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    self._debug("已清理临时文件: %s", temp_path)
                except Exception as cleanup_error:
                    self._debug("清理临时文件失败: %s", cleanup_error)

            logging.getLogger().error(f"日志归档失败 {file_path}: {e}")
            self._debug("归档失败: %s", e)
            return False