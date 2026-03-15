# core/logging/filters.py

import re
import time
import logging
import threading
from config.logging_config import LoggingConfig
from core.logging.context import get_request_id, set_request_id
from core.logging.debug import debug_print



class RequestIdFilter(logging.Filter):
    """请求ID过滤器"""

    def __init__(self):
        super().__init__()
        self.config = None  # 将在设置时赋值

    def set_config(self, config: LoggingConfig):
        """设置配置"""
        self.config = config

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.filter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def set_request_id(self, request_id: str):
        """设置当前请求ID"""
        old_id = get_request_id()
        set_request_id(request_id)
        self._debug("设置请求ID: %s -> %s", old_id, request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID"""
        request_id = get_request_id()
        self._debug("获取请求ID: %s", request_id)
        return request_id

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
        self._debug("初始化敏感数据过滤器，敏感字段: %s", config.sensitive_fields)

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.filter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _compile_patterns(self):
        """编译脱敏模式"""
        patterns = {}
        for field in self.config.sensitive_fields:
            # 为每个敏感字段创建匹配模式 - 匹配 JSON 格式的字段
            patterns[field] = re.compile(
                rf'"{field}":\s*"([^"]+)"',
                re.IGNORECASE
            )
        self._debug("编译了 %d 个敏感字段模式", len(patterns))
        return patterns

    def _mask_value(self, value: str) -> str:
        """脱敏单个值"""
        if not value:
            return value
        # 保留前2位和后2位，中间用掩码字符替换
        if len(value) <= 4:
            return self.config.mask_char * len(value)
        return value[:2] + self.config.mask_char * (len(value) - 4) + value[-2:]

    def _mask_json_value(self, value: str) -> str:
        """脱敏JSON字符串中的值"""
        if not value:
            return value
        # 对于JSON中的值，使用固定长度的掩码
        return self.config.mask_char * 8

    def filter(self, record):
        if not self.config.mask_sensitive:
            return True

        masked_count = 0

        # 处理记录对象上的属性
        for field in self.config.sensitive_fields:
            if hasattr(record, field):
                value = getattr(record, field)
                if isinstance(value, str):
                    masked_value = self._mask_value(value)
                    setattr(record, field, masked_value)
                    masked_count += 1
                    self._debug("脱敏记录属性: %s, 原值长度: %d", field, len(value))

        # 处理消息中的 JSON 字符串
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            original_msg = record.msg
            for field, pattern in self.patterns.items():
                # 查找匹配的值
                match = pattern.search(original_msg)
                if match:
                    original_value = match.group(1)
                    masked_value = self._mask_json_value(original_value)
                    record.msg = pattern.sub(
                        f'"{field}": "{masked_value}"',
                        record.msg
                    )
                    masked_count += 1
                    self._debug("脱敏消息中的字段: %s", field)

        if masked_count > 0:
            self._debug("本次处理共脱敏 %d 处敏感信息", masked_count)

        return True


class SamplingFilter(logging.Filter):
    """日志采样过滤器"""

    def __init__(self, config: LoggingConfig):
        super().__init__()
        self.config = config
        self._lock = threading.Lock()
        self._last_log_time = {}
        self._counter = 0  # 添加计数器用于概率采样
        self._debug("初始化采样过滤器，采样率: %.2f, 采样间隔: %d秒",
                    config.sampling_rate, config.sampling_interval)

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.filter_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def filter(self, record):
        """判断是否应该记录此日志"""
        # 错误级别以上的日志总是记录
        if record.levelno >= logging.ERROR:
            return True

        # 采样率检查
        if self.config.sampling_rate < 1.0:
            with self._lock:
                self._counter += 1
                # 使用确定性算法确保均匀分布
                threshold = int(1.0 / self.config.sampling_rate)
                should_log = (self._counter % threshold) == 0

                if not should_log:
                    self._debug("采样率过滤: %s, 计数: %d, 阈值: %d",
                               record.name, self._counter, threshold)
                    return False
                else:
                    self._debug("采样率通过: %s, 计数: %d", record.name, self._counter)

        # 采样间隔检查
        if self.config.sampling_interval > 0:
            logger_name = record.name
            current_time = time.time()

            with self._lock:
                if logger_name in self._last_log_time:
                    time_diff = current_time - self._last_log_time[logger_name]
                    if time_diff < self.config.sampling_interval:
                        self._debug("采样间隔过滤: %s, 距离上次: %.2f秒, 间隔要求: %d秒",
                                   logger_name, time_diff, self.config.sampling_interval)
                        return False
                    else:
                        self._debug("采样间隔通过: %s, 距离上次: %.2f秒",
                                   logger_name, time_diff)

                self._last_log_time[logger_name] = current_time

        return True