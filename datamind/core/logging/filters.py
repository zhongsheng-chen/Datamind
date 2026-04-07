# datamind/core/logging/filters.py

"""日志过滤器

提供日志过滤功能，包括请求ID注入、敏感数据脱敏和日志采样。

核心功能：
  - RequestIdFilter: 向日志记录添加 request_id/trace_id/span_id
  - SensitiveDataFilter: 自动识别并脱敏敏感字段
  - SamplingFilter: 控制日志采样率（概率采样和间隔采样）

特性：
  - 请求追踪：自动注入链路追踪ID
  - 敏感脱敏：支持 JSON 和表单格式的敏感字段脱敏
  - 日志采样：支持概率采样和间隔采样两种模式
  - 统计信息：提供过滤器处理统计
  - 调试支持：可配置的调试输出
  - 线程安全：采样计数器使用线程锁保护

使用示例：
    from datamind.core.logging.filters import RequestIdFilter, SensitiveDataFilter, SamplingFilter

    # 创建过滤器
    request_id_filter = RequestIdFilter()
    sensitive_filter = SensitiveDataFilter(config)
    sampling_filter = SamplingFilter(config)

    # 添加到处理器
    handler.addFilter(request_id_filter)
    handler.addFilter(sensitive_filter)
    handler.addFilter(sampling_filter)

    # 获取统计信息
    stats = sampling_filter.get_stats()
"""

import os
import sys
import re
import time
import logging
import threading
from typing import Optional, Dict, Pattern, Any
from dataclasses import dataclass

from datamind.config.logging_config import LoggingConfig
from datamind.core.logging.context import (
    get_request_id,
    get_trace_id,
    get_span_id,
    get_parent_span_id
)

_logger = logging.getLogger(__name__)

# 过滤器调试开关
_FILTER_DEBUG = os.environ.get('DATAMIND_FILTER_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')


def _debug(msg: str, *args) -> None:
    """过滤器调试输出"""
    if _FILTER_DEBUG:
        if args:
            print(f"[Filter] {msg % args}", file=sys.stderr)
        else:
            print(f"[Filter] {msg}", file=sys.stderr)


@dataclass
class FilterStats:
    """过滤器统计信息"""
    total_processed: int = 0
    total_filtered: int = 0
    sensitive_masked: int = 0
    sampling_dropped: int = 0

    def reset(self) -> None:
        """重置统计信息"""
        self.total_processed = 0
        self.total_filtered = 0
        self.sensitive_masked = 0
        self.sampling_dropped = 0


class RequestIdFilter(logging.Filter):
    """请求ID过滤器

    向每条日志记录添加 request_id、trace_id、span_id，用于链路追踪。
    """

    def __init__(self):
        super().__init__()
        self.config: Optional[LoggingConfig] = None
        self._stats: FilterStats = FilterStats()
        self._lock: threading.Lock = threading.Lock()

    def set_config(self, config: LoggingConfig) -> None:
        """设置配置

        参数:
            config: 日志配置对象
        """
        self.config = config

    def filter(self, record: logging.LogRecord) -> bool:
        """添加 request_id, trace_id, span_id 到日志记录

        参数:
            record: 日志记录对象

        返回:
            总是返回 True，不丢弃任何日志
        """
        record.request_id = get_request_id()
        record.trace_id = get_trace_id()
        record.span_id = get_span_id()
        record.parent_span_id = get_parent_span_id()

        with self._lock:
            self._stats.total_processed += 1

        _debug("添加请求上下文: request_id=%s, trace_id=%s, span_id=%s",
               record.request_id, record.trace_id, record.span_id)

        return True

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
        with self._lock:
            return {
                'total_processed': self._stats.total_processed,
            }


class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器

    自动识别并脱敏日志中的敏感信息，如密码、token、身份证号等。
    支持 JSON 格式和表单格式的脱敏。
    """

    def __init__(self, config: LoggingConfig):
        """
        初始化敏感数据过滤器

        参数:
            config: 日志配置对象
        """
        super().__init__()
        self.config = config
        self._stats: FilterStats = FilterStats()
        self._lock: threading.Lock = threading.Lock()
        self._sensitive_keywords = set(config.sensitive_fields)
        self._patterns: Dict[str, Pattern] = self._compile_patterns()
        self._combined_pattern: Optional[Pattern] = self._compile_combined_pattern()

    def _is_sensitive_key(self, key: str) -> bool:
        """检查是否为敏感字段（精确匹配）"""
        return key.lower() in self._sensitive_keywords

    def _compile_patterns(self) -> Dict[str, Pattern]:
        """编译脱敏模式

        返回:
            字段名到正则表达式的映射
        """
        patterns = {}
        for field in self.config.sensitive_fields:
            patterns[field] = re.compile(
                rf'"{field}":\s*"([^"]+)"',
                re.IGNORECASE
            )
            patterns[f"{field}_single"] = re.compile(
                rf"'{field}':\s*'([^']+)'",
                re.IGNORECASE
            )
        return patterns

    def _compile_combined_pattern(self) -> Optional[Pattern]:
        """编译组合正则表达式，一次匹配所有敏感字段

        返回:
            组合正则表达式对象，如果没有敏感字段则返回 None
        """
        if not self.config.sensitive_fields:
            return None

        patterns = []
        for i, field in enumerate(self.config.sensitive_fields):
            escaped_field = re.escape(field)

            patterns.append(
                rf'(?P<p{i}j>"{escaped_field}":\s*")(?P<v{i}j>[^"]+)(?P<s{i}j>")'
            )
            patterns.append(
                rf"(?P<p{i}s>'{escaped_field}':\s*')(?P<v{i}s>[^']+)(?P<s{i}s>')"
            )

        combined = "|".join(patterns)
        return re.compile(combined, re.IGNORECASE)

    def _mask(self, value: str, keep_prefix: int = 3, keep_suffix: int = 3) -> str:
        """脱敏单个值

        参数:
            value: 原始值
            keep_prefix: 保留前缀字符数
            keep_suffix: 保留后缀字符数

        返回:
            脱敏后的值
        """
        if not value:
            return value

        mask_char = self.config.mask_char

        if len(value) <= keep_prefix + keep_suffix:
            return mask_char * len(value)

        return (value[:keep_prefix] +
                mask_char * (len(value) - keep_prefix - keep_suffix) +
                value[-keep_suffix:])

    def _mask_json(self, value: str) -> str:
        """脱敏JSON字符串中的值

        参数:
            value: JSON 字符串值

        返回:
            脱敏后的值（固定长度掩码）
        """
        if not value:
            return value

        mask_length = min(8, len(value))
        return self.config.mask_char * mask_length

    def _mask_record(self, record: logging.LogRecord) -> int:
        """脱敏记录对象上的属性

        参数:
            record: 日志记录对象

        返回:
            脱敏的属性数量
        """
        masked_count = 0

        for attr_name in list(record.__dict__.keys()):
            if attr_name.startswith('_'):
                continue
            if self._is_sensitive_key(attr_name):
                value = getattr(record, attr_name)
                if isinstance(value, str):
                    masked_value = self._mask(value)
                    setattr(record, attr_name, masked_value)
                    masked_count += 1

        return masked_count

    def _mask_message(self, msg: str) -> tuple[str, int]:
        """脱敏消息字符串

        参数:
            msg: 原始消息

        返回:
            (脱敏后的消息, 脱敏次数)
        """
        masked_count = 0
        new_msg = msg

        if self._combined_pattern:
            def replacer(match):
                nonlocal masked_count

                for i, field in enumerate(self.config.sensitive_fields):
                    prefix = match.group(f"p{i}j")
                    if prefix is not None:
                        value = match.group(f"v{i}j")
                        suffix = match.group(f"s{i}j")
                        masked_count += 1
                        return f'{prefix}{self._mask_json(value)}{suffix}'

                    prefix = match.group(f"p{i}s")
                    if prefix is not None:
                        value = match.group(f"v{i}s")
                        suffix = match.group(f"s{i}s")
                        masked_count += 1
                        return f"{prefix}{self._mask_json(value)}{suffix}"

                return match.group(0)

            new_msg = self._combined_pattern.sub(replacer, new_msg)

        return new_msg, masked_count

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤敏感数据

        参数:
            record: 日志记录对象

        返回:
            总是返回 True，不丢弃任何日志
        """
        if not self.config.mask_sensitive:
            return True

        with self._lock:
            self._stats.total_processed += 1

        attr_masked = self._mask_record(record)

        if isinstance(record.msg, str):
            new_msg, msg_masked = self._mask_message(record.msg)
            if new_msg != record.msg:
                record.msg = new_msg
                record.args = ()
                attr_masked += msg_masked

        if attr_masked > 0:
            with self._lock:
                self._stats.sensitive_masked += attr_masked

            _debug("敏感数据过滤完成: 脱敏 %d 个字段", attr_masked)

        return True

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
        with self._lock:
            return {
                'total_processed': self._stats.total_processed,
                'sensitive_masked': self._stats.sensitive_masked,
            }


class SamplingFilter(logging.Filter):
    """日志采样过滤器

    在 Filter 层实现日志采样，避免在 Formatter 层产生空行污染。

    采样策略：
        - 错误级别以上的日志总是记录
        - 根据采样率随机丢弃日志
        - 支持按时间间隔采样

    使用示例：
        handler.addFilter(SamplingFilter(config))
    """

    def __init__(self, config: LoggingConfig):
        """
        初始化采样过滤器

        参数:
            config: 日志配置对象
        """
        super().__init__()
        self.config = config
        self._stats: FilterStats = FilterStats()
        self._lock: threading.Lock = threading.Lock()
        self._last_log_time: Dict[str, float] = {}
        self._counter: int = 0
        self._threshold: Optional[int] = None

        self._update_threshold()

    def _update_threshold(self) -> None:
        """更新采样阈值"""
        if self.config.sampling_rate > 0:
            self._threshold = int(1.0 / self.config.sampling_rate)
        else:
            self._threshold = None

    def _should_sample_by_rate(self) -> bool:
        """根据采样率判断是否采样

        返回:
            True 表示应该采样，False 表示丢弃
        """
        if self._threshold is None:
            return False

        if self.config.sampling_rate >= 1.0:
            return True

        with self._lock:
            self._counter += 1
            return (self._counter % self._threshold) == 0

    def _should_sample_by_interval(self, logger_name: str) -> bool:
        """根据时间间隔判断是否采样

        参数:
            logger_name: 日志器名称

        返回:
            True 表示应该采样，False 表示需要等待
        """
        if self.config.sampling_interval <= 0:
            return True

        current_time = time.time()

        with self._lock:
            last_time = self._last_log_time.get(logger_name)

            if last_time is not None:
                time_diff = current_time - last_time
                if time_diff < self.config.sampling_interval:
                    return False

            self._last_log_time[logger_name] = current_time

        return True

    def filter(self, record: logging.LogRecord) -> bool:
        """判断是否应该记录此日志

        采样优先级：
            - 错误级别以上的日志 -> 总是记录
            - 采样率检查 -> 按比例丢弃
            - 采样间隔检查 -> 按时间间隔丢弃

        参数:
            record: 日志记录对象

        返回:
            True 表示记录，False 表示丢弃
        """
        with self._lock:
            self._stats.total_processed += 1

        if record.levelno >= logging.ERROR:
            return True

        if not self._should_sample_by_rate():
            with self._lock:
                self._stats.sampling_dropped += 1
            _debug("采样丢弃: 采样率限制, logger=%s", record.name)
            return False

        if not self._should_sample_by_interval(record.name):
            with self._lock:
                self._stats.sampling_dropped += 1
            _debug("采样丢弃: 间隔限制, logger=%s", record.name)
            return False

        return True

    def update_config(self, config: LoggingConfig) -> None:
        """更新配置（支持动态调整）

        参数:
            config: 新的日志配置
        """
        self.config = config
        self._update_threshold()

    def reset_stats(self) -> None:
        """重置统计信息"""
        with self._lock:
            self._stats.reset()
            self._counter = 0
            self._last_log_time.clear()

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
        with self._lock:
            retention_rate = 0
            if self._stats.total_processed > 0:
                retention_rate = (1 - self._stats.sampling_dropped / self._stats.total_processed) * 100

            return {
                'total_processed': self._stats.total_processed,
                'sampling_dropped': self._stats.sampling_dropped,
                'retention_rate': round(retention_rate, 2),
            }


__all__ = [
    "RequestIdFilter",
    "SensitiveDataFilter",
    "SamplingFilter",
    "FilterStats",
]