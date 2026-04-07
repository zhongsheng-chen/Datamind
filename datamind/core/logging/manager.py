# datamind/core/logging/manager.py

"""日志管理器

负责日志系统的初始化、配置管理、日志记录器创建和生命周期管理。

核心功能：
  - initialize: 初始化日志系统，创建日志记录器和处理器
  - reload_config: 热重载日志配置
  - get_logger: 获取应用日志记录器
  - cleanup: 清理日志资源

特性：
  - 单例模式：全局唯一日志管理器实例
  - 配置热重载：支持运行时动态刷新配置
  - 多格式支持：支持 JSON 和文本两种日志格式
  - 异步日志：队列缓冲，非阻塞写入
  - 时区感知：支持 UTC 和本地时区
  - 日志轮转：支持按大小和按时间轮转
  - 敏感脱敏：自动识别并脱敏敏感字段
  - 启动缓存：缓存初始化前的日志，避免丢失
  - 链路追踪：完整的 span 追踪

使用示例：
    # 初始化日志系统
    from datamind.core.logging.manager import log_manager
    log_manager.initialize()

    # 获取日志记录器
    from datamind.core.logging.manager import log_manager

    log_manager.initialize()

    logger = log_manager.get_logger("my_module")
    logger.info("应用启动成功")

    # 设置请求ID
    from datamind.core.logging import context
    context.set_request_id("req-12345")

    # 自动管理 span
    @context.with_span()
    def process_order():
        logger.info("处理订单")

    # 热重载配置
    from datamind.core.logging.manager import log_manager
    from datamind.config import get_logging_config

    new_config = get_logging_config()
    log_manager.reload_config(new_config)

    # 清理资源
    log_manager.cleanup()
"""

import os
import sys
import atexit
import threading
import logging
import logging.handlers
import hashlib
import json
from pathlib import Path
from typing import Dict, Optional, List
from concurrent_log_handler import ConcurrentRotatingFileHandler

from datamind import PROJECT_ROOT
from datamind.config import get_logging_config
from datamind.config.logging_config import (
    LoggingConfig,
    LogFormat,
    RotationStrategy
)

from datamind.core.logging.formatters import (
    CustomJsonFormatter,
    CustomTextFormatter,
    TimezoneFormatter
)
from datamind.core.logging.filters import (
    RequestIdFilter,
    SensitiveDataFilter,
    SamplingFilter
)
from datamind.core.logging.handlers import (
    TimeRotatingFileHandlerWithTimezone,
    AsyncLogHandler
)
from datamind.core.logging.cleanup import CleanupManager

_logger = logging.getLogger(__name__)

# 管理器调试开关
_MANAGER_DEBUG = os.environ.get('DATAMIND_MANAGER_DEBUG', '').lower() in ('1', 'true', 'yes', 'on')


def _debug(msg: str, *args) -> None:
    """管理器内部调试输出"""
    if _MANAGER_DEBUG:
        if args:
            print(f"[Manager] {msg % args}", file=sys.stderr)
        else:
            print(f"[Manager] {msg}", file=sys.stderr)


class LogManager:
    """日志管理器

    统一管理所有日志，提供初始化和配置管理功能。
    """

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized: bool = False
            self.config: Optional[LoggingConfig] = None
            self.timezone_formatter: Optional[TimezoneFormatter] = None
            self.request_id_filter: Optional[RequestIdFilter] = None
            self.sensitive_filter: Optional[SensitiveDataFilter] = None
            self.sampling_filter: Optional[SamplingFilter] = None
            self.logger: Optional[logging.Logger] = None
            self.cleanup_manager: Optional[CleanupManager] = None
            self._config_digest: Optional[str] = None
            self._stats: Dict[str, int] = {
                'logs_processed': 0,
                'errors': 0,
                'warnings': 0
            }
            self._watch_thread: Optional[threading.Thread] = None
            self._shutdown_called: bool = False

    def _get_logger_names(self) -> List[str]:
        """获取所有需要管理的日志器名称列表"""
        if self.config:
            return ['', self.config.name.lower()]
        return ['']

    @staticmethod
    def _generate_config_digest(config: LoggingConfig) -> str:
        """生成配置摘要"""
        config_dict = config.model_dump()
        config_str = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _ensure_directories(self) -> None:
        """确保日志目录存在"""
        log_path = self.config.get_log_path().parent
        log_path.mkdir(parents=True, exist_ok=True)
        _debug("日志目录已创建: %s", log_path)

        if self.config.use_concurrent:
            lock_dir = Path(self.config.concurrent_lock_dir)
            if not lock_dir.is_absolute():
                lock_dir = PROJECT_ROOT / lock_dir
            lock_dir.mkdir(parents=True, exist_ok=True)
            _debug("并发锁目录已创建: %s", lock_dir)

        if self.config.archive_enabled:
            archive_path = Path(self.config.archive_path)
            if not archive_path.is_absolute():
                archive_path = log_path / archive_path
            archive_path.mkdir(parents=True, exist_ok=True)
            _debug("归档目录已创建: %s", archive_path)

    def initialize(self, config: Optional[LoggingConfig] = None) -> bool:
        """初始化日志系统

        参数:
            config: 日志配置对象，如果为 None 则通过 get_logging_config() 获取

        返回:
            是否成功初始化
        """
        if self._initialized:
            _debug("日志系统已初始化，跳过重复初始化")
            return True

        with self._lock:
            if self._initialized:
                return True

            _debug("=" * 50)
            _debug("开始初始化日志系统")

            try:
                if config is None:
                    config = get_logging_config()
                    _debug("通过 get_logging_config() 获取配置")
                else:
                    _debug("使用传入的配置: log_dir=%s, log_file=%s, format=%s",
                           config.log_dir, config.log_file, config.format)

                self.config = config

                self._config_digest = self._generate_config_digest(config)
                _debug("配置摘要: %s", self._config_digest[:8])

                self._ensure_directories()
                self._init_timezone_formatter()
                self._init_filters()
                self._init_context()
                self._init_logger()
                self._init_cleanup_manager()

                atexit.register(self.cleanup)

                self._flush_bootstrap_logs()
                self._initialized = True

                _debug("日志系统初始化完成")
                return True

            except Exception as e:
                _logger.error("日志系统初始化失败: %s", e, exc_info=True)
                self._initialized = False
                raise

    def _init_timezone_formatter(self) -> None:
        """初始化时区格式化器"""
        self.timezone_formatter = TimezoneFormatter(self.config)
        _debug("时区格式化器已创建: %s", self.config.timezone)

    def _init_filters(self) -> None:
        """初始化过滤器"""
        self.request_id_filter = RequestIdFilter()
        self.sensitive_filter = SensitiveDataFilter(self.config)
        self.sampling_filter = SamplingFilter(self.config)

        if hasattr(self.request_id_filter, 'set_config'):
            self.request_id_filter.set_config(self.config)

        _debug("过滤器已初始化")

    def _init_context(self) -> None:
        """初始化上下文"""
        from datamind.core.logging import context
        context.set_config(self.config)

    def _init_logger(self) -> None:
        """初始化应用日志记录器"""
        logger_name = self.config.name.lower()
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self.config.level)
        self.logger.propagate = False

        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

        file_handler = self._create_file_handler(
            level=self.config.level,
            format_type=self.config.format
        )
        self.logger.addHandler(file_handler)
        _debug("文件处理器已创建: %s", self.config.get_log_path())

        if self.config.console_output:
            console_handler = self._create_console_handler()
            if console_handler:
                self.logger.addHandler(console_handler)
                _debug("控制台处理器已创建")

    def _init_cleanup_manager(self) -> None:
        """初始化清理管理器"""
        self.cleanup_manager = CleanupManager(self.config, self.timezone_formatter)
        self.cleanup_manager.start()
        _debug("清理管理器已启动")

    def _flush_bootstrap_logs(self) -> None:
        """刷新启动日志"""
        try:
            from datamind.core.logging.bootstrap import flush_bootstrap_logs
        except ImportError as e:
            _logger.warning("bootstrap 模块未找到，跳过启动日志刷新: %s", e)
            return

        try:
            if self.logger and self.logger.handlers:
                target_handler = self.logger.handlers[0]
                replayed_count = flush_bootstrap_logs(target_handler)
                if replayed_count > 0:
                    _debug("已刷新 %d 条启动日志", replayed_count)
        except Exception as e:
            _logger.warning("刷新启动日志失败: %s", e)

    def _create_file_handler(self, level: int, format_type: LogFormat) -> logging.Handler:
        """创建文件处理器

        参数:
            level: 日志级别
            format_type: 日志格式

        返回:
            日志处理器
        """
        log_path = self.config.get_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        _debug("创建文件处理器: %s", log_path)

        if self.config.rotation_strategy == RotationStrategy.SIZE:
            handler_class = logging.handlers.RotatingFileHandler
            kwargs = {
                'filename': str(log_path),
                'maxBytes': self.config.max_bytes,
                'backupCount': self.config.backup_count,
                'encoding': self.config.encoding
            }
        else:
            handler_class = TimeRotatingFileHandlerWithTimezone
            kwargs = {
                'filename': str(log_path),
                'when': self.config.rotation_when.value if self.config.rotation_when else 'midnight',
                'interval': self.config.rotation_interval,
                'backupCount': self.config.backup_count,
                'encoding': self.config.encoding,
                'config': self.config
            }

        if self.config.use_concurrent and handler_class.__name__ == "RotatingFileHandler":
            handler = ConcurrentRotatingFileHandler(**kwargs)
        else:
            handler = handler_class(**kwargs)

        handler.setLevel(level)

        if format_type == LogFormat.JSON:
            formatter = CustomJsonFormatter(self.config)
        else:
            formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        if self.config.use_async:
            async_handler = AsyncLogHandler(self.config, handler)
            async_handler.setLevel(level)
            async_handler.addFilter(self.request_id_filter)
            async_handler.addFilter(self.sensitive_filter)
            async_handler.addFilter(self.sampling_filter)
            _debug("已包装为异步处理器")
            return async_handler

        handler.addFilter(self.request_id_filter)
        handler.addFilter(self.sensitive_filter)
        handler.addFilter(self.sampling_filter)
        return handler

    def _create_console_handler(self) -> Optional[logging.Handler]:
        """创建控制台处理器"""
        if not self.config.console_output:
            return None

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.config.console_level)

        formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        return handler

    def get_logger(self, name: str = None) -> logging.Logger:
        """获取应用日志记录器

        参数:
            name: 子日志记录器名称（可选）

        返回:
            日志记录器实例
        """
        if self.logger is None:
            return logging.getLogger(name or __name__)
        if name is None:
            return self.logger
        return self.logger.getChild(name)

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
        return self._stats.copy()

    def reload_config(self, new_config: Optional[LoggingConfig] = None) -> bool:
        """热重载日志配置

        参数:
            new_config: 新的配置对象，如果为 None 则通过 get_logging_config() 获取

        返回:
            重载是否成功
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("日志管理器尚未初始化，请先调用 initialize()")

            _debug("=" * 50)
            _debug("开始热重载日志配置")

            old_config = self.config
            old_handlers = self._capture_current_handlers()

            try:
                if new_config is None:
                    new_config = get_logging_config()
                    _debug("通过 get_logging_config() 获取新配置")

                old_digest = self._config_digest
                new_digest = self._generate_config_digest(new_config)

                if old_digest == new_digest:
                    _debug("配置无变化，跳过重载")
                    return True

                self._apply_new_config(new_config)
                self._cleanup_old_handlers(old_handlers)

                _debug("热重载完成")
                return True

            except Exception as e:
                _logger.error("热重载失败: %s", e, exc_info=True)
                self._rollback_config(old_config, old_handlers, e)
                raise

    def _capture_current_handlers(self) -> Dict[str, List[logging.Handler]]:
        """捕获当前所有日志器的处理器"""
        handlers = {}
        for logger_name in self._get_logger_names():
            logger = logging.getLogger(logger_name)
            handlers[logger_name] = logger.handlers[:]
        return handlers

    @staticmethod
    def _cleanup_old_handlers(old_handlers: Dict[str, List[logging.Handler]]) -> None:
        """清理旧的处理器"""
        total_handlers = 0
        for handlers in old_handlers.values():
            for handler in handlers:
                try:
                    if hasattr(handler, 'stop'):
                        handler.stop()
                    handler.close()
                    total_handlers += 1
                except (AttributeError, OSError, RuntimeError) as e:
                    _logger.debug("关闭处理器失败: %s", e)
        _logger.debug("已清理 %d 个旧处理器", total_handlers)

    def _apply_new_config(self, new_config: LoggingConfig) -> None:
        """应用新配置"""
        request_id_filter = self.request_id_filter

        self._initialized = False
        self.config = new_config

        self._config_digest = self._generate_config_digest(new_config)

        self.sensitive_filter = SensitiveDataFilter(new_config)
        self.sampling_filter = SamplingFilter(new_config)
        self.request_id_filter = request_id_filter

        if self.cleanup_manager:
            self.cleanup_manager.stop()
        self.cleanup_manager = CleanupManager(new_config, self.timezone_formatter)
        self.cleanup_manager.start()

        for logger_name in self._get_logger_names():
            logger = logging.getLogger(logger_name)
            for h in logger.handlers[:]:
                h.close()
                logger.removeHandler(h)

        self._init_logger()
        self._initialized = True

    def _rollback_config(self, old_config: LoggingConfig,
                         old_handlers: Dict[str, List[logging.Handler]],
                         error: Exception) -> None:
        """回滚到旧配置"""
        _logger.warning("配置重载失败，开始回滚: %s", error)
        try:
            for logger_name in self._get_logger_names():
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                    except (AttributeError, OSError, RuntimeError) as e:
                        _logger.debug("关闭处理器失败: %s", e)
                    finally:
                        logger.removeHandler(handler)

            for logger_name, handlers in old_handlers.items():
                logger = logging.getLogger(logger_name)
                for handler in handlers:
                    logger.addHandler(handler)

            self.config = old_config
            self.timezone_formatter = TimezoneFormatter(old_config)
            self._config_digest = self._generate_config_digest(old_config)
            self._initialized = True

        except Exception as rollback_error:
            _logger.error("回滚过程中发生错误: %s", rollback_error)

    def cleanup(self) -> None:
        """清理资源"""
        if self._shutdown_called:
            return
        self._shutdown_called = True

        _debug("开始清理日志资源")
        with self._lock:
            for logger_name in self._get_logger_names():
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers:
                    try:
                        if isinstance(handler, AsyncLogHandler):
                            handler.flush()
                        handler.flush()
                    except (AttributeError, OSError, RuntimeError) as e:
                        _logger.debug("刷新处理器失败: %s", e)

            if self.cleanup_manager:
                self.cleanup_manager.stop()

            for logger_name in self._get_logger_names():
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                        logger.removeHandler(handler)
                    except (AttributeError, OSError, RuntimeError) as e:
                        _logger.debug("关闭处理器失败: %s", e)

            self._initialized = False
            _debug("日志资源清理完成")


# 全局日志管理器实例
log_manager = LogManager()