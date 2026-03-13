# core/logging/filters.py
import logging
import re
import random
import time
import threading
from typing import Dict

from config.logging_config import LoggingConfig
from core.logging.context import get_request_id, set_request_id


class RequestIdFilter(logging.Filter):
    """请求ID过滤器"""

    def __init__(self):
        super().__init__()

    def set_request_id(self, request_id: str):
        """设置当前请求ID"""
        set_request_id(request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID"""
        return get_request_id()

    def filter(self, record):
        """添加 request_id 到日志记录"""
        record.request_id = self.get_request_id()
        return True


class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器"""

    def __init__(self, config: LoggingConfig):
        super().__init__()
        self.config = config
        self.patterns = self._compile_patterns()

    def _compile_patterns(self):
        """编译脱敏模式"""
        patterns = {}
        for field in self.config.sensitive_fields:
            # 为每个敏感字段创建匹配模式 - 匹配 JSON 格式的字段
            patterns[field] = re.compile(
                rf'"{field}":\s*"([^"]+)"',
                re.IGNORECASE
            )
        return patterns

    def filter(self, record):
        if not self.config.mask_sensitive:
            return True

        # 处理记录对象上的属性
        for field in self.config.sensitive_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if isinstance(value, str):
                    setattr(
                        record,
                        field,
                        self.config.mask_char * 8
                    )

        # 处理消息中的 JSON 字符串
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for field, pattern in self.patterns.items():
                record.msg = pattern.sub(
                    f'"{field}": "{self.config.mask_char * 8}"',
                    record.msg
                )

        return True


class SamplingFilter(logging.Filter):
    """日志采样过滤器"""

    def __init__(self, config: LoggingConfig):
        super().__init__()
        self.config = config
        self._lock = threading.Lock()
        self._last_log_time = {}

    def filter(self, record):
        """判断是否应该记录此日志"""
        # 错误级别以上的日志总是记录
        if record.levelno >= logging.ERROR:
            return True

        # 采样率检查
        if self.config.sampling_rate < 1.0:
            if random.random() > self.config.sampling_rate:
                return False

        # 采样间隔检查
        if self.config.sampling_interval > 0:
            logger_name = record.name
            current_time = time.time()

            with self._lock:
                if logger_name in self._last_log_time:
                    if current_time - self._last_log_time[logger_name] < self.config.sampling_interval:
                        return False

                self._last_log_time[logger_name] = current_time

        return True