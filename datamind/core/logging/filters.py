# Datamind/datamind/core/logging/filters.py

"""日志过滤器

提供日志过滤功能：
  - RequestIdFilter: 请求ID过滤器，向日志记录添加 request_id/trace_id/span_id
  - SensitiveDataFilter: 敏感数据过滤器，脱敏敏感字段
  - SamplingFilter: 采样过滤器，控制日志采样率（在 Filter 层实现，避免空行污染）
"""

import re
import time
import logging
import threading
from typing import Optional, Dict, Any, Pattern
from dataclasses import dataclass

from datamind.config import LoggingConfig
from datamind.core.logging.debug import debug_print
from datamind.core.logging.context import (
    get_request_id,
    get_trace_id,
    get_span_id,
)


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

    def set_config(self, config: LoggingConfig) -> None:
        """设置配置

        参数:
            config: 日志配置对象
        """
        self.config = config

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.filter_debug:
            debug_print(self.__class__.__name__, msg, *args)

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

        self._stats.total_processed += 1

        if self.config and self.config.filter_debug:
            self._debug("添加请求上下文: request_id=%s, trace_id=%s, span_id=%s",
                        record.request_id, record.trace_id, record.span_id)

        return True

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
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
        self._patterns: Dict[str, Pattern] = self._compile_patterns()
        self._combined_pattern: Optional[Pattern] = self._compile_combined_pattern()
        self._json_pattern: Pattern = self._compile_json_pattern()

        self._debug("初始化敏感数据过滤器，敏感字段: %s", config.sensitive_fields)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.filter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _compile_patterns(self) -> Dict[str, Pattern]:
        """编译脱敏模式

        返回:
            字段名到正则表达式的映射
        """
        patterns = {}
        for field in self.config.sensitive_fields:
            # 匹配 JSON 格式的字段：{"field": "value"}
            patterns[field] = re.compile(
                rf'"{field}":\s*"([^"]+)"',
                re.IGNORECASE
            )
            # 也支持单引号格式：{'field': 'value'}
            patterns[f"{field}_single"] = re.compile(
                rf"'{field}':\s*'([^']+)'",
                re.IGNORECASE
            )

        self._debug("编译了 %d 个敏感字段模式", len(self.config.sensitive_fields))
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
            # 使用 f-string 构建整个模式，确保 {i} 被替换
            escaped_field = re.escape(field)

            # JSON 双引号格式
            patterns.append(
                rf'(?P<p{i}j>"{escaped_field}":\s*")(?P<v{i}j>[^"]+)(?P<s{i}j>")'
            )
            # JSON 单引号格式
            patterns.append(
                rf"(?P<p{i}s>'{escaped_field}':\s*')(?P<v{i}s>[^']+)(?P<s{i}s>')"
            )

        combined = "|".join(patterns)
        self._debug("编译组合正则表达式，共 %d 个模式", len(patterns))
        self._debug("组合正则表达式预览: %s", combined[:200])
        return re.compile(combined, re.IGNORECASE)

    def _compile_json_pattern(self) -> Pattern:
        """编译完整的 JSON 对象脱敏模式

        返回:
            脱敏 JSON 对象中敏感字段的正则表达式
        """
        if not self.config.sensitive_fields:
            return re.compile(r'(?!)')  # 永不匹配的正则

        # 匹配包含敏感字段的 JSON 对象
        fields_pattern = "|".join(f'"{field}"' for field in self.config.sensitive_fields)
        return re.compile(
            rf'\{{[^{{}}]*?(?:{fields_pattern})[^{{}}]*?\}}',
            re.IGNORECASE
        )

    def _mask_value(self, value: str, keep_prefix: int = 2, keep_suffix: int = 2) -> str:
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

        # 如果值太短，完全脱敏
        if len(value) <= keep_prefix + keep_suffix:
            return self.config.mask_char * len(value)

        # 保留前后部分，中间脱敏
        return (value[:keep_prefix] +
                self.config.mask_char * (len(value) - keep_prefix - keep_suffix) +
                value[-keep_suffix:])

    def _mask_json_value(self, value: str) -> str:
        """脱敏JSON字符串中的值

        参数:
            value: JSON 字符串值

        返回:
            脱敏后的值（固定长度掩码）
        """
        if not value:
            return value

        # 根据值长度决定掩码长度
        mask_length = min(8, len(value))
        return self.config.mask_char * mask_length

    def _mask_record_attributes(self, record: logging.LogRecord) -> int:
        """脱敏记录对象上的属性

        参数:
            record: 日志记录对象

        返回:
            脱敏的属性数量
        """
        masked_count = 0

        for field in self.config.sensitive_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if isinstance(value, str):
                    masked_value = self._mask_value(value)
                    setattr(record, field, masked_value)
                    masked_count += 1
                    self._debug("脱敏记录属性: %s, 原值长度: %d", field, len(value))

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
                    # JSON 双引号格式
                    prefix = match.group(f"p{i}j")
                    if prefix is not None:
                        value = match.group(f"v{i}j")
                        suffix = match.group(f"s{i}j")
                        masked_count += 1
                        self._debug("脱敏JSON字段: %s", field)
                        return f'{prefix}{self._mask_json_value(value)}{suffix}'

                    # JSON 单引号格式
                    prefix = match.group(f"p{i}s")
                    if prefix is not None:
                        value = match.group(f"v{i}s")
                        suffix = match.group(f"s{i}s")
                        masked_count += 1
                        self._debug("脱敏JSON字段(单引号): %s", field)
                        return f"{prefix}{self._mask_json_value(value)}{suffix}"

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

        self._stats.total_processed += 1

        # 脱敏记录属性
        attr_masked = self._mask_record_attributes(record)

        # 脱敏消息内容
        if isinstance(record.msg, str):
            new_msg, msg_masked = self._mask_message(record.msg)
            if new_msg != record.msg:
                record.msg = new_msg
                attr_masked += msg_masked

        if attr_masked > 0:
            self._stats.sensitive_masked += attr_masked
            self._debug("本次处理共脱敏 %d 处敏感信息", attr_masked)

        return True

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
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

        # 预计算阈值
        self._update_threshold()

        self._debug("初始化采样过滤器，采样率: %.2f, 采样间隔: %d秒",
                    config.sampling_rate, config.sampling_interval)

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.filter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _update_threshold(self) -> None:
        """更新采样阈值"""
        if self.config.sampling_rate > 0:
            self._threshold = int(1.0 / self.config.sampling_rate)
        else:
            self._threshold = None  # 采样率为 0，丢弃所有非错误日志

    def _should_sample_by_rate(self) -> bool:
        """根据采样率判断是否采样

        返回:
            True 表示应该采样，False 表示丢弃
        """
        if self._threshold is None:
            return False  # 采样率为 0，丢弃

        if self.config.sampling_rate >= 1.0:
            return True  # 采样率为 100%，全部保留

        with self._lock:
            self._counter += 1
            should_log = (self._counter % self._threshold) == 0

        if not should_log:
            self._debug("采样率过滤: 计数: %d, 阈值: %d", self._counter, self._threshold)

        return should_log

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
                    self._debug("采样间隔过滤: %s, 距离上次: %.2f秒, 间隔要求: %d秒",
                                logger_name, time_diff, self.config.sampling_interval)
                    return False

                self._debug("采样间隔通过: %s, 距离上次: %.2f秒",
                            logger_name, time_diff)

            self._last_log_time[logger_name] = current_time

        return True

    def filter(self, record: logging.LogRecord) -> bool:
        """判断是否应该记录此日志

        采样优先级：
            1. 错误级别以上的日志 -> 总是记录
            2. 采样率检查 -> 按比例丢弃
            3. 采样间隔检查 -> 按时间间隔丢弃

        参数:
            record: 日志记录对象

        返回:
            True 表示记录，False 表示丢弃
        """
        self._stats.total_processed += 1

        # 错误级别以上的日志总是记录
        if record.levelno >= logging.ERROR:
            return True

        # 采样率检查
        if not self._should_sample_by_rate():
            self._stats.sampling_dropped += 1
            return False

        # 采样间隔检查
        if not self._should_sample_by_interval(record.name):
            self._stats.sampling_dropped += 1
            return False

        return True

    def update_config(self, config: LoggingConfig) -> None:
        """更新配置（支持动态调整）

        参数:
            config: 新的日志配置
        """
        self.config = config
        self._update_threshold()
        self._debug("配置已更新: 采样率=%.2f, 采样间隔=%d秒",
                    config.sampling_rate, config.sampling_interval)

    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats.reset()
        with self._lock:
            self._counter = 0
            self._last_log_time.clear()

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
        retention_rate = 0
        if self._stats.total_processed > 0:
            retention_rate = (1 - self._stats.sampling_dropped / self._stats.total_processed) * 100

        return {
            'total_processed': self._stats.total_processed,
            'sampling_dropped': self._stats.sampling_dropped,
            'retention_rate': round(retention_rate, 2),
        }