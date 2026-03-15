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
from core.logging.debug import debug_print, warning_print, error_print



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
            self._stats = {
                'logs_processed': 0,
                'errors': 0,
                'warnings': 0
            }

    def _debug(self, msg, *args):
        """调试输出"""
        if self.config and self.config.manager_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _warning(self, msg, *args):
        """警告输出"""
        if self.config and self.config.manager_debug:
            warning_print(f"{self.__class__.__name__}", msg, *args)
        self._stats['warnings'] += 1

    def _error(self, msg, *args):
        """错误输出"""
        if self.config and self.config.manager_debug:
            error_print(f"{self.__class__.__name__}", msg, *args)
        self._stats['errors'] += 1

    def initialize(self, config: LoggingConfig) -> bool:
        """
        初始化日志系统

        Args:
            config: 日志配置对象

        Returns:
            bool: 文件处理器是否成功创建
        """
        if self._initialized:
            return True

        with self._lock:
            self._debug("=" * 50)
            self._debug("开始初始化日志系统")

            # 配置预检
            self._debug("执行配置预检...")
            validation = config.validate_all()
            if not validation['valid']:
                errors = "\n".join(validation['errors'])
                self._error("配置验证失败: %s", errors)
                raise RuntimeError(f"日志配置验证失败:\n{errors}")

            if validation['warnings']:
                for warning in validation['warnings']:
                    self._warning("日志配置警告: %s", warning)

            self.config = config

            # 创建新的 timezone_formatter
            self._debug("创建时区格式化器: %s", config.timezone.value)
            self.timezone_formatter = TimezoneFormatter(config)
            self._debug("时区设置完成: %s", config.timezone)

            self._config_digest = config.get_config_digest()
            self._debug("配置摘要: %s", self._config_digest)

            # 创建日志目录
            self._debug("确保日志目录存在...")
            dirs_created = config.ensure_log_dirs()
            self._debug("目录创建状态: %s", dirs_created)

            # 初始化过滤器
            self._debug("初始化过滤器...")
            self.request_id_filter = RequestIdFilter()
            self.sensitive_filter = SensitiveDataFilter(config)
            self.sampling_filter = SamplingFilter(config)
            self._debug("过滤器初始化完成")

            # 设置过滤器的配置
            if hasattr(self.request_id_filter, 'set_config'):
                self.request_id_filter.set_config(config)
                self._debug("已设置请求ID过滤器的配置")

            # 设置上下文配置
            from core.logging import context
            context.set_config(config)
            self._debug("上下文调试: %s", "开启" if config.context_debug else "关闭")

            # 初始化日志记录器
            self._debug("初始化根日志记录器...")
            self._init_root_logger()
            self._debug("初始化访问日志记录器...")
            self._init_access_logger()
            self._debug("初始化审计日志记录器...")
            self._init_audit_logger()
            self._debug("初始化性能日志记录器...")
            self._init_performance_logger()

            # 初始化清理管理器
            self._debug("初始化清理管理器...")
            self.cleanup_manager = CleanupManager(config, self.timezone_formatter)
            self.cleanup_manager.start()
            self._debug("清理管理器已启动")

            # 注册清理函数
            atexit.register(self.cleanup)
            self._debug("已注册清理函数")

            self._initialized = True
            self._debug("日志系统初始化完成")
            self._debug("=" * 50)

            # 记录启动日志
            self._log_startup_info()

            # ===== 关键修改：在所有初始化完成后刷新启动日志 =====
            # 检查文件处理器
            root_logger = logging.getLogger(config.name)
            file_handlers = [h for h in root_logger.handlers
                             if isinstance(h, (logging.FileHandler,
                                               logging.handlers.RotatingFileHandler,
                                               ConcurrentRotatingFileHandler,
                                               TimeRotatingFileHandlerWithTimezone))]

            file_handlers_count = len(file_handlers)
            self._debug(f"文件处理器数量: {file_handlers_count}")

            if file_handlers_count > 0:
                self._debug("文件处理器已就绪，类型: %s",
                            [type(h).__name__ for h in file_handlers])

                # 增加等待时间，确保文件处理器完全初始化
                time.sleep(0.5)

                # 刷新启动日志
                self._debug("刷新启动日志...")
                try:
                    from core.logging.bootstrap import flush_bootstrap_logs

                    replayed_count = flush_bootstrap_logs()

                    if replayed_count > 0:
                        # 使用配置中的名称记录日志
                        logger = logging.getLogger(config.name)
                        logger.info(f"已刷新 {replayed_count} 条启动日志到文件")
                        self._debug(f"成功刷新 {replayed_count} 条启动日志")
                    else:
                        self._debug("没有启动日志需要刷新")

                except ImportError:
                    self._debug("bootstrap模块未找到，跳过启动日志刷新")
                except Exception as e:
                    self._error("刷新启动日志时出错: %s", e, exc_info=True)
            else:
                self._warning("警告: 没有找到文件处理器，启动日志无法写入文件")
            # ==================================================

            # 返回文件处理器是否成功创建
            return file_handlers_count > 0

    def _log_startup_info(self):
        """记录启动信息"""
        root_logger = logging.getLogger(self.config.name)
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
        self._debug("启动日志已记录")

    def _create_file_handler(
            self,
            filename: str,
            level: Union[LogLevel, int, str],
            format_type: Optional[LogFormat] = None
    ) -> logging.Handler:
        """创建文件处理器"""
        if format_type is None:
            format_type = self.config.format

        self._debug("创建文件处理器: 文件=%s, 级别=%s, 格式=%s", filename, level, format_type)

        # 获取基础目录
        base_dir = self.config._base_dir or Path(__file__).parent.parent.parent
        # 获取完整路径
        full_path = self.config.get_full_log_path(filename, base_dir)
        self._debug("完整路径: %s", full_path)

        # 确保日志目录存在
        full_path.parent.mkdir(parents=True, exist_ok=True)
        self._debug("确保目录存在: %s", full_path.parent)

        # 如果文件名包含时间戳，添加时间信息
        if self.config.file_name_timestamp:
            current_time = self.timezone_formatter.format_time()
            timestamp = current_time.strftime(self.config.file_name_datetime_format)
            # 只修改文件名，不修改路径
            new_filename = f"{full_path.stem}_{timestamp}{full_path.suffix}"
            full_path = full_path.parent / new_filename
            self._debug("文件名添加时间戳: %s", full_path)

        # 选择处理器类型
        handler = None
        try:
            if self.config.use_concurrent:
                self._debug("使用并发处理器")
                handler = ConcurrentRotatingFileHandler(
                    filename=str(full_path),
                    maxBytes=self.config.max_bytes,
                    backupCount=self.config.backup_count,
                    encoding=self.config.encoding,
                    lock_file_directory=self.config.concurrent_lock_dir
                )
            elif self.config.rotation_when:
                self._debug("使用时间轮转处理器: when=%s, interval=%d",
                           self.config.rotation_when.value, self.config.rotation_interval)
                handler = TimeRotatingFileHandlerWithTimezone(
                    config=self.config,
                    filename=str(full_path),
                    when=self.config.rotation_when.value,
                    interval=self.config.rotation_interval,
                    backupCount=self.config.backup_count,
                    encoding=self.config.encoding
                )
            else:
                self._debug("使用大小轮转处理器: max_bytes=%d, backup_count=%d",
                           self.config.max_bytes, self.config.backup_count)
                handler = logging.handlers.RotatingFileHandler(
                    filename=str(full_path),
                    maxBytes=self.config.max_bytes,
                    backupCount=self.config.backup_count,
                    encoding=self.config.encoding
                )

            # 使用配置类的方法设置日志级别
            handler.setLevel(self.config.to_logging_level(level))
            self._debug("设置日志级别: %s", level)

            # 设置格式器
            if format_type == LogFormat.JSON:
                formatter = CustomJsonFormatter(self.config)
                self._debug("使用JSON格式器")
            else:
                formatter = CustomTextFormatter(self.config)
                self._debug("使用文本格式器，格式: %s", self.config.text_format)

            handler.setFormatter(formatter)

            # 添加过滤器
            handler.addFilter(self.request_id_filter)
            handler.addFilter(self.sensitive_filter)
            handler.addFilter(self.sampling_filter)
            self._debug("已添加过滤器到处理器")

            # 如果是异步模式，包装为异步处理器
            if self.config.use_async:
                self._debug("包装为异步处理器，队列大小: %d", self.config.async_queue_size)
                handler = AsyncLogHandler(self.config, handler)

        except Exception as e:
            self._error("创建文件处理器失败: %s", e)
            raise

        return handler

    def _create_console_handler(self) -> Optional[logging.Handler]:
        """创建控制台处理器"""
        if not self.config.console_output:
            self._debug("控制台输出已禁用")
            return None

        self._debug("创建控制台处理器")
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.config.to_logging_level(self.config.console_level))
        self._debug("控制台日志级别: %s", self.config.console_level)

        # 控制台使用文本格式
        formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        return handler

    def _init_root_logger(self):
        """初始化根日志记录器"""
        self._debug("初始化根日志记录器")
        root_logger = logging.getLogger(self.config.name)
        root_logger.setLevel(self.config.to_logging_level(self.config.level))
        self._debug("设置根日志级别: %s", self.config.level)

        # 清除已有的处理器
        handler_count = len(root_logger.handlers)
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        self._debug("已清除 %d 个现有处理器", handler_count)

        added_handlers = 0

        # 根据配置的格式添加处理器
        try:
            if self.config.format == LogFormat.TEXT:
                self._debug("使用纯文本格式")
                # 纯文本格式
                text_handler = self._create_file_handler(
                    filename=self.config.file,
                    level=self.config.level,
                    format_type=LogFormat.TEXT
                )
                root_logger.addHandler(text_handler)
                added_handlers += 1

                # 错误日志单独文件
                if self.config.error_file:
                    error_handler = self._create_file_handler(
                        filename=self.config.error_file,
                        level=LogLevel.ERROR,
                        format_type=LogFormat.TEXT
                    )
                    root_logger.addHandler(error_handler)
                    added_handlers += 1

            elif self.config.format == LogFormat.JSON:
                self._debug("使用纯JSON格式")
                # 纯JSON格式
                json_handler = self._create_file_handler(
                    filename=self.config.file,
                    level=self.config.level,
                    format_type=LogFormat.JSON
                )
                root_logger.addHandler(json_handler)
                added_handlers += 1

                # 错误日志单独文件（JSON格式）
                if self.config.error_file:
                    error_handler = self._create_file_handler(
                        filename=self.config.error_file,
                        level=LogLevel.ERROR,
                        format_type=LogFormat.JSON
                    )
                    root_logger.addHandler(error_handler)
                    added_handlers += 1

            elif self.config.format == LogFormat.BOTH:
                self._debug("使用双格式（文本和JSON）")

                # 为文本和JSON使用不同的文件名
                base_path = Path(self.config.file)
                text_file = str(base_path.parent / f"{base_path.stem}.text{base_path.suffix}")
                json_file = str(base_path.parent / f"{base_path.stem}.json{base_path.suffix}")

                self._debug("文本文件: %s", text_file)
                self._debug("JSON文件: %s", json_file)

                # 文本处理器
                text_handler = self._create_file_handler(
                    filename=text_file,
                    level=self.config.level,
                    format_type=LogFormat.TEXT
                )
                root_logger.addHandler(text_handler)
                added_handlers += 1

                # JSON处理器
                json_handler = self._create_file_handler(
                    filename=json_file,
                    level=self.config.level,
                    format_type=LogFormat.JSON
                )
                root_logger.addHandler(json_handler)
                added_handlers += 1

                # 错误日志
                if self.config.error_file:
                    error_text_handler = self._create_file_handler(
                        filename=self.config.error_file,
                        level=LogLevel.ERROR,
                        format_type=LogFormat.TEXT
                    )
                    root_logger.addHandler(error_text_handler)
                    added_handlers += 1

                    error_json_handler = self._create_file_handler(
                        filename=self.config.error_file,
                        level=LogLevel.ERROR,
                        format_type=LogFormat.JSON
                    )
                    root_logger.addHandler(error_json_handler)
                    added_handlers += 1

            # 控制台输出
            if self.config.console_output:
                console_handler = self._create_console_handler()
                if console_handler:
                    root_logger.addHandler(console_handler)
                    added_handlers += 1

        except Exception as e:
            self._error("初始化根日志记录器失败: %s", e)
            raise

        self._debug("根日志记录器初始化完成，共 %d 个处理器", added_handlers)

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
            self._debug("访问日志已禁用")
            return

        self._debug("初始化访问日志记录器")
        self.access_logger = logging.getLogger('datamind.access')
        self.access_logger.setLevel(logging.INFO)
        self.access_logger.propagate = False

        try:
            if self.config.format == LogFormat.BOTH:
                text_handler = self._create_file_handler(
                    filename=self.config.access_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.TEXT
                )
                self.access_logger.addHandler(text_handler)

                json_handler = self._create_file_handler(
                    filename=self.config.access_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.JSON
                )
                self.access_logger.addHandler(json_handler)
                self._debug("访问日志添加了文本和JSON两个处理器")
            else:
                handler = self._create_file_handler(
                    filename=self.config.access_log_file,
                    level=LogLevel.INFO,
                    format_type=self.config.format
                )
                self.access_logger.addHandler(handler)
                self._debug("访问日志添加了处理器，格式: %s", self.config.format)

            self.access_logger.log(
                logging.INFO,
                "访问日志记录器初始化完成",
                extra={"format": self.config.format.value}
            )
        except Exception as e:
            self._error("初始化访问日志记录器失败: %s", e)
            raise

    def _init_audit_logger(self):
        """初始化审计日志记录器"""
        if not self.config.enable_audit_log:
            self._debug("审计日志已禁用")
            return

        self._debug("初始化审计日志记录器")
        self.audit_logger = logging.getLogger('datamind.audit')
        self.audit_logger.setLevel(logging.INFO)
        self.audit_logger.propagate = False

        try:
            # 审计日志优先使用JSON格式
            if self.config.format == LogFormat.BOTH:
                json_handler = self._create_file_handler(
                    filename=self.config.audit_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.JSON
                )
                self.audit_logger.addHandler(json_handler)

                text_handler = self._create_file_handler(
                    filename=self.config.audit_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.TEXT
                )
                self.audit_logger.addHandler(text_handler)
                self._debug("审计日志添加了JSON和文本两个处理器")
            else:
                handler = self._create_file_handler(
                    filename=self.config.audit_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.JSON  # 审计日志总是JSON
                )
                self.audit_logger.addHandler(handler)
                self._debug("审计日志添加了处理器，格式: JSON")

            self.audit_logger.log(
                logging.INFO,
                "审计日志记录器初始化完成",
                extra={"format": "json"}
            )
        except Exception as e:
            self._error("初始化审计日志记录器失败: %s", e)
            raise

    def _init_performance_logger(self):
        """初始化性能日志记录器"""
        if not self.config.enable_performance_log:
            self._debug("性能日志已禁用")
            return

        self._debug("初始化性能日志记录器")
        self.performance_logger = logging.getLogger('datamind.performance')
        self.performance_logger.setLevel(logging.INFO)
        self.performance_logger.propagate = False

        try:
            # 性能日志也使用JSON格式
            if self.config.format == LogFormat.BOTH:
                json_handler = self._create_file_handler(
                    filename=self.config.performance_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.JSON
                )
                self.performance_logger.addHandler(json_handler)

                text_handler = self._create_file_handler(
                    filename=self.config.performance_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.TEXT
                )
                self.performance_logger.addHandler(text_handler)
                self._debug("性能日志添加了JSON和文本两个处理器")
            else:
                handler = self._create_file_handler(
                    filename=self.config.performance_log_file,
                    level=LogLevel.INFO,
                    format_type=LogFormat.JSON  # 性能日志总是JSON
                )
                self.performance_logger.addHandler(handler)
                self._debug("性能日志添加了处理器，格式: JSON")

            self.performance_logger.log(
                logging.INFO,
                "性能日志记录器初始化完成",
                extra={"format": "json"}
            )
        except Exception as e:
            self._error("初始化性能日志记录器失败: %s", e)
            raise

    def set_request_id(self, request_id: str):
        """设置当前请求ID"""
        if self.request_id_filter:
            self.request_id_filter.set_request_id(request_id)
            self._debug("设置请求ID: %s", request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID"""
        if self.request_id_filter:
            request_id = self.request_id_filter.get_request_id()
            self._debug("获取请求ID: %s", request_id)
            return request_id
        self._debug("获取请求ID: 未找到请求ID过滤器")
        return '-'

    def get_current_time(self) -> datetime:
        """获取当前时间（已应用时区）"""
        current_time = self.timezone_formatter.format_time() if self.timezone_formatter else datetime.now()
        self._debug("获取当前时间: %s", current_time)
        return current_time

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()

    def log_access(self, method: str = "GET", path: str = "/", status: int = 200,
                   duration_ms: float = 0.0, ip: str = "", user_agent: str = "",
                   **kwargs):
        """记录访问日志"""
        if not hasattr(self, 'access_logger') or not self.access_logger:
            self._debug("访问日志记录器不可用")
            return

        # 获取当前请求ID
        request_id = self.get_request_id()

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
        self._debug("记录访问日志: %s %s, 状态=%d, 耗时=%.2fms, request_id=%s",
                    method, path, status, duration_ms, request_id)
        if self.config and self.config.manager_debug:
            # 只在前5个字符内显示extra预览
            extra_preview = str(extra)
            if len(extra_preview) > 100:
                extra_preview = extra_preview[:100] + "..."
            self._debug("extra数据预览: %s", extra_preview)

        # 记录日志
        self.access_logger.info("访问日志", extra=extra)
        self._stats['logs_processed'] += 1

    def log_audit(self, action: str, user_id: str, target_user: str = None,
                  role: str = None, ip_address: str = None, **kwargs):
        """记录审计日志"""
        if not hasattr(self, 'audit_logger') or not self.audit_logger:
            self._debug("审计日志记录器不可用")
            return

        # 获取当前请求ID
        request_id = self.get_request_id()

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
        self._debug("记录审计日志: action=%s, user=%s, request_id=%s", action, user_id, request_id)
        if self.config and self.config.manager_debug:
            extra_preview = str(extra)
            if len(extra_preview) > 100:
                extra_preview = extra_preview[:100] + "..."
            self._debug("extra数据预览: %s", extra_preview)

        # 记录日志
        self.audit_logger.info("审计日志", extra=extra)
        self._stats['logs_processed'] += 1

    def log_performance(self, operation: str, duration_ms: float, query: str = None,
                        rows: int = None, database: str = None, **kwargs):
        """记录性能日志"""
        if not hasattr(self, 'performance_logger') or not self.performance_logger:
            self._debug("性能日志记录器不可用")
            return

        # 获取当前请求ID
        request_id = self.get_request_id()

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
        self._debug("记录性能日志: operation=%s, duration=%.2fms, request_id=%s",
                    operation, duration_ms, request_id)
        if self.config and self.config.manager_debug:
            extra_preview = str(extra)
            if len(extra_preview) > 100:
                extra_preview = extra_preview[:100] + "..."
            self._debug("extra数据预览: %s", extra_preview)

        # 记录日志
        self.performance_logger.info("性能日志", extra=extra)
        self._stats['logs_processed'] += 1

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
                self._error("日志管理器尚未初始化，无法重载")
                raise RuntimeError("日志管理器尚未初始化，请先调用 initialize()")

            self._debug("=" * 50)
            self._debug("开始热重载日志配置")

            # 保存旧配置和状态
            old_config = self.config
            old_handlers = self._capture_current_handlers()
            self._debug("已保存旧配置和处理器")

            try:
                # 获取新配置
                if new_config is None:
                    self._debug("从环境文件重新加载配置")
                    new_config = old_config.reload()

                # 检查配置是否有变化
                if old_config.is_equivalent_to(new_config):
                    self._debug("配置无变化，跳过重载")
                    logging.getLogger().info("配置无变化，跳过重载")
                    return True

                self._debug("配置有变化，执行重载")
                self._debug("旧配置摘要: %s", old_config.get_config_digest()[:8])
                self._debug("新配置摘要: %s", new_config.get_config_digest()[:8])

                # 配置预检
                validation = new_config.validate_all()
                if not validation['valid']:
                    errors = "\n".join(validation['errors'])
                    self._error("新配置验证失败: %s", errors)
                    raise RuntimeError(f"新配置验证失败:\n{errors}")

                # 记录重载开始
                self._log_reload_start(new_config)

                # 执行重载
                self._debug("应用新配置...")
                self._apply_new_config(new_config)

                # 清理旧资源
                self._debug("清理旧处理器...")
                self._cleanup_old_handlers(old_handlers)

                # 记录重载成功
                self._log_reload_success()

                self._debug("热重载完成")
                self._debug("=" * 50)

                return True

            except Exception as e:
                self._error("热重载失败: %s", e)
                # 重载失败，回滚到旧配置
                self._rollback_config(old_config, old_handlers, e)
                raise

    def _capture_current_handlers(self) -> Dict[str, List[logging.Handler]]:
        """捕获当前所有日志器的处理器"""
        handlers = {}
        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            handlers[logger_name] = logger.handlers[:]
            self._debug("捕获 %s 的 %d 个处理器", logger_name or 'root', len(logger.handlers))
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
        self._debug("已记录重载开始日志")

    def _apply_new_config(self, new_config: LoggingConfig):
        """应用新配置"""
        self._debug("开始应用新配置")

        # 临时保存请求ID过滤器（因为它是线程局部变量，需要保留）
        request_id_filter = self.request_id_filter
        self._debug("保留旧的请求ID过滤器")

        # 重新初始化
        self._initialized = False
        self.config = new_config

        # 重新创建 timezone_formatter
        self._debug("重新创建时区格式化器: %s", new_config.timezone.value)
        self.timezone_formatter = TimezoneFormatter(new_config)
        self._debug("时区设置完成: %s", new_config.timezone)

        self._config_digest = new_config.get_config_digest()
        self._debug("新配置摘要: %s", self._config_digest)

        # 重新创建过滤器（保留旧的请求ID过滤器）
        self.sensitive_filter = SensitiveDataFilter(new_config)
        self.sampling_filter = SamplingFilter(new_config)
        self.request_id_filter = request_id_filter
        self._debug("重新创建了敏感数据和采样过滤器")

        # 重新初始化清理管理器
        self._debug("重新初始化清理管理器")
        self.cleanup_manager = CleanupManager(new_config, self.timezone_formatter)
        self.cleanup_manager.start()
        self._debug("清理管理器已重启")

        # 清除所有日志器的处理器
        self._debug("清除所有日志器的处理器")
        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            removed = len(logger.handlers)
            for h in logger.handlers[:]:
                logger.removeHandler(h)
            self._debug("已清除 %s 的 %d 个处理器", logger_name or 'root', removed)

        # 重新初始化所有日志器
        self._debug("重新初始化日志记录器")
        self._init_root_logger()
        self._init_access_logger()
        self._init_audit_logger()
        self._init_performance_logger()

        self._initialized = True
        self._debug("新配置应用完成")

    def _cleanup_old_handlers(self, old_handlers: Dict[str, List[logging.Handler]]):
        """清理旧的处理器"""
        total_handlers = 0
        for logger_name, handlers in old_handlers.items():
            for handler in handlers:
                try:
                    if hasattr(handler, 'stop'):
                        handler.stop()
                    handler.close()
                    total_handlers += 1
                except Exception as e:
                    self._debug("关闭处理器失败 %s: %s", handler, e)
        self._debug("已清理 %d 个旧处理器", total_handlers)

    def _rollback_config(self, old_config: LoggingConfig, old_handlers: Dict[str, List[logging.Handler]],
                         error: Exception):
        """回滚到旧配置"""
        self._debug("开始回滚到旧配置")
        try:
            # 清理部分初始化的新处理器
            self._debug("清理部分初始化的新处理器")
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
            self._debug("恢复旧处理器")
            restored = 0
            for logger_name, handlers in old_handlers.items():
                logger = logging.getLogger(logger_name)
                for handler in handlers:
                    logger.addHandler(handler)
                    restored += 1
            self._debug("已恢复 %d 个旧处理器", restored)

            # 恢复旧配置
            self.config = old_config
            self.timezone_formatter = TimezoneFormatter(old_config)
            self._config_digest = old_config.get_config_digest()
            self._initialized = True
            self._debug("已恢复旧配置")

            # 记录回滚
            logging.getLogger().error(
                f"配置重载失败，已回滚: {error}",
                exc_info=True,
                extra={"event": "config_reload_failed"}
            )
            self._debug("回滚完成")

        except Exception as rollback_error:
            self._error("回滚过程中发生错误: %s", rollback_error)
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
        self._debug("已记录重载成功日志")

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
            self._debug("监控配置文件: %s", env_files)

            # 初始化文件修改时间
            for env_file in env_files:
                try:
                    last_mtimes[env_file] = Path(env_file).stat().st_mtime
                    self._debug("初始化 %s 的修改时间: %d", env_file, last_mtimes[env_file])
                except Exception as e:
                    self._debug("无法获取文件 %s 的修改时间: %s", env_file, e)

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
                                self._debug("文件 %s 已修改: %d -> %d",
                                          env_file, last_mtimes[env_file], current_mtime)
                            last_mtimes[env_file] = current_mtime
                        except Exception as e:
                            self._debug("检查文件 %s 时出错: %s", env_file, e)

                    if need_reload:
                        self._debug("检测到配置文件变化: %s", changed_files)
                        logging.getLogger().info(f"检测到配置文件变化: {changed_files}")
                        self.reload_config()

                except Exception as e:
                    self._error("配置监控失败: %s", e)
                    logging.getLogger().error(f"配置监控失败: {e}")

        # 启动监控线程
        self._debug("启动配置监控线程，间隔: %d秒", interval)
        watcher = threading.Thread(target=watch_worker, daemon=True, name="ConfigWatcher")
        watcher.start()
        self._debug("配置监控线程已启动: %s", watcher.name)
        return watcher

    def cleanup(self):
        """清理资源"""
        self._debug("开始清理资源")
        with self._lock:
            # 停止清理线程
            if self.cleanup_manager:
                self._debug("停止清理管理器")
                self.cleanup_manager.stop()

            # 关闭所有处理器
            total_closed = 0
            for logger_name in ['', 'access', 'audit', 'performance']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                        logger.removeHandler(handler)
                        total_closed += 1
                    except Exception as e:
                        self._debug("关闭处理器失败: %s", e)

            self._debug("已关闭 %d 个处理器", total_closed)
            self._initialized = False
            self._debug("清理完成，统计信息: 处理日志=%d, 警告=%d, 错误=%d",
                       self._stats['logs_processed'],
                       self._stats['warnings'],
                       self._stats['errors'])


# 全局日志管理器实例
log_manager = LogManager()