# Datamind/datamind/core/logging/cleanup.py

"""日志清理管理器

自动清理过期日志文件，支持：
  - 按保留天数清理
  - 日志归档（压缩）
  - 定时清理任务
  - 多格式支持（BOTH 格式同时清理 text 和 json 文件）
  - 时区感知的归档目录命名
"""

import os
import gzip
import shutil
import threading
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List, Set, Dict, Any

from datamind.config import LoggingConfig, LogFormat
from datamind.core.logging.formatters import TimezoneFormatter
from datamind.core.logging.debug import debug_print


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
        self._debug("初始化清理管理器，保留天数: %d, 归档: %s",
                    config.retention_days, "开启" if config.archive_enabled else "关闭")

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出"""
        if self.config and self.config.cleanup_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def start(self) -> None:
        """启动清理任务"""
        if not self._should_run_cleanup():
            self._debug("清理任务未启动: archive_enabled=%s, retention_days=%d",
                        self.config.archive_enabled, self.config.retention_days)
            return

        def cleanup_job() -> None:
            self._debug("清理任务线程启动")
            while not self._stop_cleanup.wait(self._get_seconds_to_next_cleanup()):
                try:
                    self._debug("开始执行定期清理任务")
                    result = self.cleanup_old_logs()
                    if result['deleted'] > 0 or result['archived'] > 0:
                        self._debug("清理完成: %s", result)
                except Exception as e:
                    logging.getLogger().error(f"清理任务执行失败: {e}")
                    self._debug("清理任务执行失败: %s", e)

        self._cleanup_thread = threading.Thread(
            target=cleanup_job,
            daemon=True,
            name="LogCleanupThread"
        )
        self._cleanup_thread.start()
        self._debug("清理任务已启动，线程: %s", self._cleanup_thread.name)

    def stop(self) -> None:
        """停止清理任务"""
        self._debug("停止清理任务")
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5)
            if self._cleanup_thread.is_alive():
                self._debug("清理线程未在5秒内停止")
            else:
                self._debug("清理线程已停止")
        self._debug("清理停止信号已发送")

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
            self._debug("开始清理旧日志，截止日期: %s, 时间戳: %d",
                        cutoff_date, cutoff_timestamp)

            log_files = self._collect_log_files()

            for log_file in log_files:
                if not log_file or not os.path.exists(log_file):
                    continue

                log_dir = os.path.dirname(log_file)
                base_name = os.path.basename(log_file)

                if not os.path.exists(log_dir):
                    self._debug("日志目录不存在: %s", log_dir)
                    continue

                rotated_files = self._get_log_rotated_files(log_dir, base_name)
                self._debug("目录 %s 中找到 %d 个轮转文件", log_dir, len(rotated_files))

                for file_path in rotated_files:
                    if not self._should_cleanup_file(file_path, cutoff_timestamp):
                        continue

                    self._debug("文件需要清理: %s", os.path.basename(file_path))

                    if self.config.archive_enabled:
                        if self._archive_file(file_path):
                            result['archived'] += 1
                    else:
                        if self._delete_file(file_path):
                            result['deleted'] += 1

            self._debug("清理完成: 删除 %d 个文件, 归档 %d 个文件",
                        result['deleted'], result['archived'])

        except Exception as e:
            logging.getLogger().error(f"日志清理失败: {e}")
            self._debug("清理过程发生异常: %s", e)

        return result

    def run_cleanup_now(self) -> Dict[str, int]:
        """
        立即执行清理（用于手动触发）

        返回:
            清理结果统计
        """
        self._debug("手动触发清理任务")
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

        # 计算下次清理时间
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

        archive_path = Path(self.config.archive_path)
        if not archive_path.exists():
            return 0

        total_size = 0
        for file_path in archive_path.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size

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
        self._debug("下次清理时间: %s, 等待: %.2f秒", cleanup_time, seconds)
        return seconds

    def _collect_log_files(self) -> List[str]:
        """收集所有需要清理的日志文件"""
        # 基础日志文件
        base_files = [
            self.config.file,
            self.config.error_file,
            self.config.access_log_file,
            self.config.audit_log_file,
            self.config.performance_log_file
        ]

        log_files: Set[str] = set()

        for f in base_files:
            if not f:
                continue

            log_files.add(f)

            # 如果是BOTH格式，添加对应的text和json文件
            if self.config.format == LogFormat.BOTH:
                text_file = self._get_both_filename(f, 'text')
                json_file = self._get_both_filename(f, 'json')
                log_files.add(text_file)
                log_files.add(json_file)
                self._debug("BOTH格式，添加额外文件: %s, %s", text_file, json_file)

        collected = list(log_files)
        self._debug("收集到 %d 个日志文件需要清理", len(collected))
        return collected

    def _get_both_filename(self, base_filename: str, suffix: str) -> str:
        """获取BOTH格式的文件名"""
        base, ext = os.path.splitext(base_filename)
        suffix_name = self.config.text_suffix if suffix == 'text' else self.config.json_suffix
        both_filename = f"{base}.{suffix_name}{ext}"
        self._debug("生成BOTH文件名: %s -> %s", base_filename, both_filename)
        return both_filename

    def _get_log_rotated_files(self, log_dir: str, base_name: str) -> List[str]:
        """获取日志的轮转文件"""
        try:
            files = os.listdir(log_dir)
        except Exception as e:
            self._debug("无法列出目录 %s: %s", log_dir, e)
            return []

        # 匹配以 base_name. 开头的文件，但排除 base_name 本身
        return [
            os.path.join(log_dir, f)
            for f in files
            if f.startswith(base_name + ".") and f != base_name
        ]

    def _should_cleanup_file(self, file_path: str, cutoff_timestamp: float) -> bool:
        """判断文件是否需要清理"""
        try:
            if not os.path.isfile(file_path):
                return False

            file_mtime = os.path.getmtime(file_path)
            return file_mtime < cutoff_timestamp
        except Exception as e:
            self._debug("检查文件 %s 时出错: %s", file_path, e)
            return False

    def _delete_file(self, file_path: str) -> bool:
        """删除文件，返回是否成功"""
        try:
            os.remove(file_path)
            self._debug("已删除文件: %s", file_path)
            logging.getLogger().info(f"删除旧日志文件: {file_path}")
            return True
        except Exception as e:
            self._debug("删除文件 %s 失败: %s", file_path, e)
            return False

    def _archive_file(self, file_path: str) -> bool:
        """归档文件，返回是否成功"""
        temp_path = None

        try:
            self._debug("开始归档文件: %s", file_path)

            # 检查文件是否存在且可读
            if not os.path.exists(file_path):
                self._debug("文件不存在: %s", file_path)
                return False

            if not os.access(file_path, os.R_OK):
                self._debug("文件不可读: %s", file_path)
                return False

            # 复制到临时文件
            temp_path = file_path + '.tmp'
            shutil.copy2(file_path, temp_path)
            self._debug("已创建临时文件: %s", temp_path)

            # 创建归档目录
            archive_path = self._get_archive_path(file_path)
            archive_dir = os.path.dirname(archive_path)
            Path(archive_dir).mkdir(parents=True, exist_ok=True)
            self._debug("归档目录: %s", archive_dir)

            # 检查归档文件是否已存在
            if os.path.exists(archive_path):
                self._debug("归档文件已存在: %s", archive_path)
                # 添加时间戳后缀避免覆盖
                base, ext = os.path.splitext(archive_path)
                archive_path = f"{base}_{int(datetime.now().timestamp())}{ext}"
                self._debug("使用新路径: %s", archive_path)

            # 压缩归档
            file_size = os.path.getsize(temp_path)
            self._debug("开始压缩，原文件大小: %d 字节", file_size)

            with open(temp_path, 'rb') as f_in:
                with gzip.open(archive_path, 'wb', compresslevel=9) as f_out:
                    shutil.copyfileobj(f_in, f_out)

            archived_size = os.path.getsize(archive_path)
            compression_ratio = (archived_size / file_size * 100) if file_size > 0 else 0
            self._debug("压缩完成，归档文件大小: %d 字节，压缩率: %.2f%%",
                        archived_size, compression_ratio)

            # 验证归档文件完整性
            if self._verify_archive(archive_path, file_size):
                # 删除原文件和临时文件
                os.remove(file_path)
                os.remove(temp_path)
                self._debug("已删除原文件和临时文件")
                logging.getLogger().info(f"日志归档成功: {file_path} -> {archive_path}")
                return True
            else:
                self._debug("归档文件验证失败")
                # 删除损坏的归档文件
                if os.path.exists(archive_path):
                    os.remove(archive_path)
                return False

        except Exception as e:
            self._debug("归档失败: %s", e)
            logging.getLogger().error(f"日志归档失败 {file_path}: {e}")
            return False
        finally:
            # 清理临时文件
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    self._debug("已清理临时文件: %s", temp_path)
                except Exception as cleanup_error:
                    self._debug("清理临时文件失败: %s", cleanup_error)

    def _get_archive_path(self, file_path: str) -> str:
        """获取归档文件路径"""
        current_time = self.timezone_formatter.format_time()
        date_str = current_time.strftime(self.config.file_name_date_format)

        archive_subdir = os.path.join(
            self.config.archive_path,
            date_str
        )

        base_name = os.path.basename(file_path)
        timestamp = current_time.strftime(self.config.archive_name_format)
        archive_name = f"{base_name}.{timestamp}.{self.config.archive_compression}"

        return os.path.join(archive_subdir, archive_name)

    def _verify_archive(self, archive_path: str, original_size: int) -> bool:
        """验证归档文件"""
        try:
            # 检查归档文件是否存在
            if not os.path.exists(archive_path):
                return False

            # 检查文件大小是否合理（不为0）
            archive_size = os.path.getsize(archive_path)
            if archive_size == 0:
                self._debug("归档文件大小为0")
                return False

            # 尝试读取归档文件头部验证是否为有效的gzip文件
            with gzip.open(archive_path, 'rb') as f:
                # 尝试读取前几个字节
                f.read(1024)

            return True
        except Exception as e:
            self._debug("验证归档文件失败: %s", e)
            return False

    # ######## 上下文管理器支持 ########
    def __enter__(self) -> 'CleanupManager':
        """进入上下文时启动清理任务"""
        self.start()
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[Exception], exc_tb: Optional[Any]) -> None:
        """退出上下文时停止清理任务"""
        self.stop()