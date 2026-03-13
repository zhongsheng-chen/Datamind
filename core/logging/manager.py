# core/logging/manager.py

import os
import sys
import time
import atexit
import threading
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Union, List
from concurrent_log_handler import ConcurrentRotatingFileHandler
from config.logging_config import LoggingConfig, LogFormat, LogLevel
from core.logging.formatters import CustomJsonFormatter, CustomTextFormatter, TimezoneFormatter
from core.logging.filters import RequestIdFilter, SensitiveDataFilter, SamplingFilter
from core.logging.handlers import TimeRotatingFileHandlerWithTimezone, AsyncLogHandler
from core.logging.cleanup import CleanupManager

# 获取 bootstrap logger 用于调试
_bootstrap_logger = logging.getLogger("datamind.bootstrap")


class LogManager:
    """
    日志管理器

    统一管理所有日志（包含完整的时间处理）
    """

    _instance = None
    _lock = threading.RLock()  # 使用可重入锁

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self.config: Optional[LoggingConfig] = None
            self.timezone_formatter: Optional[TimezoneFormatter] = None
            self.request_id_filter: Optional[RequestIdFilter] = None
            self.sensitive_filter: Optional[SensitiveDataFilter] = None
            self.sampling_filter: Optional[SamplingFilter] = None
            self.access_logger: Optional[logging.Logger] = None
            self.audit_logger: Optional[logging.Logger] = None
            self.performance_logger: Optional[logging.Logger] = None
            self.cleanup_manager: Optional[CleanupManager] = None
            self._config_digest: Optional[str] = None

    def _debug(self, msg, *args):
        """调试输出，使用 bootstrap logger"""
        if self.config and self.config.manager_debug:
            _bootstrap_logger.debug(f"[LogManager] {msg}", *args)

    def initialize(self, config: LoggingConfig):
        """初始化日志系统"""
        if self._initialized:
            return

        with self._lock:
            # 配置预检
            validation = config.validate_all()
            if not validation['valid']:
                errors = "\n".join(validation['errors'])
                raise RuntimeError(f"日志配置验证失败:\n{errors}")

            if validation['warnings']:
                for warning in validation['warnings']:
                    # 使用 bootstrap logger 输出警告
                    _bootstrap_logger.warning(f"日志配置警告: {warning}")

            self.config = config

            # 创建新的 timezone_formatter
            self.timezone_formatter = TimezoneFormatter(config)
            self._debug("initialize - Setting timezone to: %s", config.timezone)

            self._config_digest = config.get_config_digest()

            # 创建日志目录
            config.ensure_log_dirs()

            # 初始化过滤器
            self.request_id_filter = RequestIdFilter()
            self.sensitive_filter = SensitiveDataFilter(config)
            self.sampling_filter = SamplingFilter(config)

            # 初始化日志记录器
            self._init_root_logger()
            self._init_access_logger()
            self._init_audit_logger()
            self._init_performance_logger()

            # 初始化清理管理器
            self.cleanup_manager = CleanupManager(config, self.timezone_formatter)
            self.cleanup_manager.start()

            # 注册清理函数
            atexit.register(self.cleanup)

            self._initialized = True

            # 记录启动日志
            self._log_startup_info()

    def _log_startup_info(self):
        """记录启动信息"""
        root_logger = logging.getLogger()
        root_logger.log(
            self.config.to_logging_level(),
            "日志系统初始化完成",
            extra={
                "timezone": self.config.timezone.value,
                "timestamp_precision": self.config.timestamp_precision.value,
                "log_format": self.config.format.value,
                "log_file": self.config.file,
                "config_digest": self._config_digest
            }
        )

    def _create_file_handler(
            self,
            filename: str,
            level: Union[LogLevel, int, str],
            format_type: Optional[LogFormat] = None
    ) -> logging.Handler:
        """创建文件处理器"""
        if format_type is None:
            format_type = self.config.format

        # 确保日志目录存在
        log_dir = os.path.dirname(filename)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)

        # 如果文件名包含时间戳，添加时间信息
        if self.config.file_name_timestamp:
            current_time = self.timezone_formatter.format_time()
            timestamp = current_time.strftime(self.config.file_name_datetime_format)
            base, ext = os.path.splitext(filename)
            filename = f"{base}_{timestamp}{ext}"

        # 选择处理器类型
        if self.config.use_concurrent:
            handler = ConcurrentRotatingFileHandler(
                filename=filename,
                maxBytes=self.config.max_bytes,
                backupCount=self.config.backup_count,
                encoding=self.config.encoding,
                lock_file_directory=self.config.concurrent_lock_dir
            )
        elif self.config.rotation_when:
            handler = TimeRotatingFileHandlerWithTimezone(
                config=self.config,
                filename=filename,
                when=self.config.rotation_when.value,
                interval=self.config.rotation_interval,
                backupCount=self.config.backup_count,
                encoding=self.config.encoding
            )
        else:
            handler = logging.handlers.RotatingFileHandler(
                filename=filename,
                maxBytes=self.config.max_bytes,
                backupCount=self.config.backup_count,
                encoding=self.config.encoding
            )

        # 使用配置类的方法设置日志级别
        handler.setLevel(self.config.to_logging_level(level))

        # 设置格式器
        if format_type == LogFormat.JSON:
            formatter = CustomJsonFormatter(self.config)
        else:
            formatter = CustomTextFormatter(self.config)

        handler.setFormatter(formatter)

        # 添加过滤器
        handler.addFilter(self.request_id_filter)
        handler.addFilter(self.sensitive_filter)
        handler.addFilter(self.sampling_filter)

        # 如果是异步模式，包装为异步处理器
        if self.config.use_async:
            handler = AsyncLogHandler(self.config, handler)

        return handler

    def _create_console_handler(self) -> Optional[logging.Handler]:
        """创建控制台处理器"""
        if not self.config.console_output:
            return None

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.config.to_logging_level(self.config.console_level))

        # 控制台使用文本格式
        formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        return handler

    def _init_root_logger(self):
        """初始化根日志记录器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(self.config.to_logging_level(self.config.level))

        # 清除已有的处理器
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

        # 根据配置的格式添加处理器
        if self.config.format == LogFormat.TEXT:
            # 纯文本格式
            text_handler = self._create_file_handler(
                filename=self.config.file,
                level=self.config.level,
                format_type=LogFormat.TEXT
            )
            root_logger.addHandler(text_handler)

            # 错误日志单独文件
            if self.config.error_file:
                error_handler = self._create_file_handler(
                    filename=self.config.error_file,
                    level=LogLevel.ERROR,
                    format_type=LogFormat.TEXT
                )
                root_logger.addHandler(error_handler)

        elif self.config.format == LogFormat.JSON:
            # 纯JSON格式
            json_handler = self._create_file_handler(
                filename=self.config.file,
                level=self.config.level,
                format_type=LogFormat.JSON
            )
            root_logger.addHandler(json_handler)

            # 错误日志单独文件（JSON格式）
            if self.config.error_file:
                error_handler = self._create_file_handler(
                    filename=self.config.error_file,
                    level=LogLevel.ERROR,
                    format_type=LogFormat.JSON
                )
                root_logger.addHandler(error_handler)

        elif self.config.format == LogFormat.BOTH:
            # 同时输出两种格式
            text_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.file, 'text'),
                level=self.config.level,
                format_type=LogFormat.TEXT
            )
            root_logger.addHandler(text_handler)

            json_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.file, 'json'),
                level=self.config.level,
                format_type=LogFormat.JSON
            )
            root_logger.addHandler(json_handler)

            # 错误日志
            if self.config.error_file:
                error_text_handler = self._create_file_handler(
                    filename=self.cleanup_manager.get_both_filename(self.config.error_file, 'text'),
                    level=LogLevel.ERROR,
                    format_type=LogFormat.TEXT
                )
                root_logger.addHandler(error_text_handler)

                error_json_handler = self._create_file_handler(
                    filename=self.cleanup_manager.get_both_filename(self.config.error_file, 'json'),
                    level=LogLevel.ERROR,
                    format_type=LogFormat.JSON
                )
                root_logger.addHandler(error_json_handler)

        # 控制台输出
        if self.config.console_output:
            console_handler = self._create_console_handler()
            if console_handler:
                root_logger.addHandler(console_handler)

        # 记录初始化完成日志
        root_logger.log(
            self.config.to_logging_level(self.config.level),
            "根日志记录器初始化完成",
            extra={
                "format": self.config.format.value,
                "handlers": len(root_logger.handlers)
            }
        )

    def _init_access_logger(self):
        """初始化访问日志记录器"""
        if not self.config.enable_access_log:
            return

        self.access_logger = logging.getLogger('access')
        self.access_logger.setLevel(logging.INFO)
        self.access_logger.propagate = False

        if self.config.format == LogFormat.BOTH:
            text_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.access_log_file, 'text'),
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.access_logger.addHandler(text_handler)

            json_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.access_log_file, 'json'),
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.access_logger.addHandler(json_handler)
        else:
            handler = self._create_file_handler(
                filename=self.config.access_log_file,
                level=LogLevel.INFO,
                format_type=self.config.format
            )
            self.access_logger.addHandler(handler)

        self.access_logger.log(
            logging.INFO,
            "访问日志记录器初始化完成",
            extra={"format": self.config.format.value}
        )

    def _init_audit_logger(self):
        """初始化审计日志记录器"""
        if not self.config.enable_audit_log:
            return

        self.audit_logger = logging.getLogger('audit')
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.propagate = False

        # 审计日志优先使用JSON格式
        if self.config.format == LogFormat.BOTH:
            json_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.audit_log_file, 'json'),
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.audit_logger.addHandler(json_handler)

            text_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.audit_log_file, 'text'),
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.audit_logger.addHandler(text_handler)
        else:
            handler = self._create_file_handler(
                filename=self.config.audit_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.JSON  # 审计日志总是JSON
            )
            self.audit_logger.addHandler(handler)

        self.audit_logger.log(
            logging.INFO,
            "审计日志记录器初始化完成",
            extra={"format": "json"}
        )

    def _init_performance_logger(self):
        """初始化性能日志记录器"""
        if not self.config.enable_performance_log:
            return

        self.performance_logger = logging.getLogger('performance')
        self.performance_logger.setLevel(logging.INFO)
        self.performance_logger.propagate = False

        # 性能日志也使用JSON格式
        if self.config.format == LogFormat.BOTH:
            json_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.performance_log_file, 'json'),
                level=LogLevel.INFO,
                format_type=LogFormat.JSON
            )
            self.performance_logger.addHandler(json_handler)

            text_handler = self._create_file_handler(
                filename=self.cleanup_manager.get_both_filename(self.config.performance_log_file, 'text'),
                level=LogLevel.INFO,
                format_type=LogFormat.TEXT
            )
            self.performance_logger.addHandler(text_handler)
        else:
            handler = self._create_file_handler(
                filename=self.config.performance_log_file,
                level=LogLevel.INFO,
                format_type=LogFormat.JSON  # 性能日志总是JSON
            )
            self.performance_logger.addHandler(handler)

        self.performance_logger.log(
            logging.INFO,
            "性能日志记录器初始化完成",
            extra={"format": "json"}
        )

    def set_request_id(self, request_id: str):
        """设置当前请求ID"""
        if self.request_id_filter:
            self.request_id_filter.set_request_id(request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID"""
        if self.request_id_filter:
            return self.request_id_filter.get_request_id()
        return '-'

    def get_current_time(self) -> datetime:
        """获取当前时间（已应用时区）"""
        if self.timezone_formatter:
            return self.timezone_formatter.format_time()
        return datetime.now()

    def log_access(self, method: str = "GET", path: str = "/", status: int = 200,
                   duration_ms: float = 0.0, ip: str = "", user_agent: str = "",
                   **kwargs):
        """记录访问日志"""
        if not hasattr(self, 'access_logger') or not self.access_logger:
            return

        # 构建 extra 数据
        extra = {
            'method': method,
            'path': path,
            'status': status,
            'duration_ms': duration_ms,
            'ip': ip,
            'user_agent': user_agent,
        }

        # 添加其他自定义字段
        extra.update(kwargs)

        # 移除 None 值
        extra = {k: v for k, v in extra.items() if v is not None}

        # 调试输出
        self._debug("log_access extra: %s", extra)

        # 记录日志
        self.access_logger.info("访问日志", extra=extra)

    def log_audit(self, action: str, user_id: str, target_user: str = None,
                  role: str = None, ip_address: str = None, **kwargs):
        """记录审计日志"""
        if not hasattr(self, 'audit_logger') or not self.audit_logger:
            return

        # 构建 extra 数据
        extra = {
            'action': action,
            'user_id': user_id,
        }

        # 添加可选字段
        if target_user is not None:
            extra['target_user'] = target_user
        if role is not None:
            extra['role'] = role
        if ip_address is not None:
            extra['ip_address'] = ip_address

        # 添加其他自定义字段
        extra.update(kwargs)

        # 移除 None 值
        extra = {k: v for k, v in extra.items() if v is not None}

        # 调试输出
        self._debug("log_audit extra: %s", extra)

        # 记录日志
        self.audit_logger.info("审计日志", extra=extra)

    def log_performance(self, operation: str, duration_ms: float, query: str = None,
                        rows: int = None, database: str = None, **kwargs):
        """记录性能日志"""
        if not hasattr(self, 'performance_logger') or not self.performance_logger:
            return

        # 构建 extra 数据
        extra = {
            'operation': operation,
            'duration_ms': duration_ms,
        }

        # 添加可选字段
        if query is not None:
            extra['query'] = query
        if rows is not None:
            extra['rows'] = rows
        if database is not None:
            extra['database'] = database

        # 添加其他自定义字段
        extra.update(kwargs)

        # 移除 None 值
        extra = {k: v for k, v in extra.items() if v is not None}

        # 调试输出
        self._debug("log_performance extra: %s", extra)

        # 记录日志
        self.performance_logger.info("性能日志", extra=extra)

    def reload_config(self, new_config: Optional[LoggingConfig] = None) -> bool:
        """
        热重载日志配置

        Args:
            new_config: 新的配置对象，如果为None则使用当前配置的reload()方法

        Returns:
            bool: 重载是否成功
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("日志管理器尚未初始化，请先调用 initialize()")

            # 保存旧配置和状态
            old_config = self.config
            old_handlers = self._capture_current_handlers()

            try:
                # 获取新配置
                if new_config is None:
                    new_config = old_config.reload()

                # 检查配置是否有变化
                if old_config.is_equivalent_to(new_config):
                    logging.getLogger().info("配置无变化，跳过重载")
                    return True

                # 配置预检
                validation = new_config.validate_all()
                if not validation['valid']:
                    errors = "\n".join(validation['errors'])
                    raise RuntimeError(f"新配置验证失败:\n{errors}")

                # 记录重载开始
                self._log_reload_start(new_config)

                # 执行重载
                self._apply_new_config(new_config)

                # 清理旧资源
                self._cleanup_old_handlers(old_handlers)

                # 记录重载成功
                self._log_reload_success()

                return True

            except Exception as e:
                # 重载失败，回滚到旧配置
                self._rollback_config(old_config, old_handlers, e)
                raise

    def _capture_current_handlers(self) -> Dict[str, List[logging.Handler]]:
        """捕获当前所有日志器的处理器"""
        handlers = {}
        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            handlers[logger_name] = logger.handlers[:]
        return handlers

    def _log_reload_start(self, new_config: LoggingConfig):
        """记录重载开始"""
        logger = logging.getLogger()
        logger.log(
            logging.INFO,
            "开始热重载日志配置",
            extra={
                "old_timezone": self.config.timezone.value,
                "new_timezone": new_config.timezone.value,
                "old_format": self.config.format.value,
                "new_format": new_config.format.value,
                "old_digest": self._config_digest,
                "new_digest": new_config.get_config_digest(),
                "event": "config_reload_start"
            }
        )

    def _apply_new_config(self, new_config: LoggingConfig):
        """应用新配置"""
        # 临时保存请求ID过滤器（因为它是线程局部变量，需要保留）
        request_id_filter = self.request_id_filter

        # 重新初始化
        self._initialized = False
        self.config = new_config

        # 重新创建 timezone_formatter
        self.timezone_formatter = TimezoneFormatter(new_config)
        self._debug("_apply_new_config - Setting timezone to: %s", new_config.timezone)

        self._config_digest = new_config.get_config_digest()

        # 重新创建过滤器（保留旧的请求ID过滤器）
        self.sensitive_filter = SensitiveDataFilter(new_config)
        self.sampling_filter = SamplingFilter(new_config)
        self.request_id_filter = request_id_filter

        # 重新初始化清理管理器
        self.cleanup_manager = CleanupManager(new_config, self.timezone_formatter)
        self.cleanup_manager.start()

        # 清除所有日志器的处理器
        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            for h in logger.handlers[:]:
                logger.removeHandler(h)

        # 重新初始化所有日志器
        self._init_root_logger()
        self._init_access_logger()
        self._init_audit_logger()
        self._init_performance_logger()

        self._initialized = True

    def _cleanup_old_handlers(self, old_handlers: Dict[str, List[logging.Handler]]):
        """清理旧的处理器"""
        for logger_name, handlers in old_handlers.items():
            for handler in handlers:
                try:
                    if hasattr(handler, 'stop'):
                        handler.stop()
                    handler.close()
                except Exception as e:
                    logging.getLogger().debug(f"关闭处理器失败 {handler}: {e}")

    def _rollback_config(self, old_config: LoggingConfig, old_handlers: Dict[str, List[logging.Handler]],
                         error: Exception):
        """回滚到旧配置"""
        try:
            # 清理部分初始化的新处理器
            for logger_name in ['', 'access', 'audit', 'performance']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                    except:
                        pass
                    logger.removeHandler(handler)

            # 恢复旧处理器
            for logger_name, handlers in old_handlers.items():
                logger = logging.getLogger(logger_name)
                for handler in handlers:
                    logger.addHandler(handler)

            # 恢复旧配置
            self.config = old_config
            self.timezone_formatter = TimezoneFormatter(old_config)
            self._config_digest = old_config.get_config_digest()
            self._initialized = True

            # 记录回滚
            logging.getLogger().error(
                f"配置重载失败，已回滚: {error}",
                exc_info=True,
                extra={"event": "config_reload_failed"}
            )
        except Exception as rollback_error:
            # 回滚也失败了，记录严重错误
            logging.getLogger().critical(
                f"配置回滚失败，日志系统可能处于不一致状态: {rollback_error}",
                exc_info=True
            )

    def _log_reload_success(self):
        """记录重载成功"""
        logging.getLogger().info(
            "日志配置热重载成功",
            extra={
                "timezone": self.config.timezone.value,
                "format": self.config.format.value,
                "config_digest": self._config_digest,
                "event": "config_reload_success"
            }
        )

    def watch_config_changes(self, interval: int = 5) -> threading.Thread:
        """
        监控配置文件变化并自动重载

        Args:
            interval: 检查间隔（秒）

        Returns:
            监控线程
        """

        def watch_worker():
            last_mtimes = {}

            # 获取所有相关的配置文件
            env_files = self.config.get_env_files()

            # 初始化文件修改时间
            for env_file in env_files:
                try:
                    last_mtimes[env_file] = Path(env_file).stat().st_mtime
                except:
                    pass

            while self._initialized:
                try:
                    time.sleep(interval)

                    need_reload = False
                    changed_files = []

                    # 检查文件修改时间
                    for env_file in env_files:
                        try:
                            current_mtime = Path(env_file).stat().st_mtime
                            if env_file in last_mtimes and current_mtime > last_mtimes[env_file]:
                                need_reload = True
                                changed_files.append(env_file)
                            last_mtimes[env_file] = current_mtime
                        except:
                            pass

                    if need_reload:
                        logging.getLogger().info(f"检测到配置文件变化: {changed_files}")
                        self.reload_config()

                except Exception as e:
                    logging.getLogger().error(f"配置监控失败: {e}")

        # 启动监控线程
        watcher = threading.Thread(target=watch_worker, daemon=True, name="ConfigWatcher")
        watcher.start()
        return watcher

    def cleanup(self):
        """清理资源"""
        with self._lock:
            # 停止清理线程
            if self.cleanup_manager:
                self.cleanup_manager.stop()

            # 关闭所有处理器
            for logger_name in ['', 'access', 'audit', 'performance']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                        logger.removeHandler(handler)
                    except Exception as e:
                        self._debug(f"关闭处理器失败: {e}")

            self._initialized = False


# 全局日志管理器实例
log_manager = LogManager()