# Datamind/datamind/core/logging/manager.py

import os
import sys
import time
import atexit
import threading
import logging
import logging.handlers
import hashlib
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from concurrent_log_handler import ConcurrentRotatingFileHandler

from datamind.config import (
    LoggingConfig,
    LogFormat,
    LogLevel,
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
from datamind.core.logging.debug import debug_print, warning_print, error_print


class LogManager:
    """
    日志管理器

    统一管理所有日志（包含完整的时间处理）

    注意：
        - 应用日志必须通过 `log_manager` 获取 logger： log_access(), log_audit(), log_performance()
        - 禁止直接使用 `logging.getLogger()` 记录业务日志
        - root logger 仅用于捕获第三方库日志，级别设置为 WARNING 避免干扰
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
            self._initialized = False
            self.config: Optional[LoggingConfig] = None
            self.timezone_formatter: Optional[TimezoneFormatter] = None
            self.request_id_filter: Optional[RequestIdFilter] = None
            self.sensitive_filter: Optional[SensitiveDataFilter] = None
            self.sampling_filter: Optional[SamplingFilter] = None
            self.app_logger: Optional[logging.Logger] = None
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
            self._app_name = os.getenv("DATAMIND_APP_NAME", "datamind").lower()

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

    def _validate_config(self, config: LoggingConfig):
        """验证配置"""
        # 基本验证
        if not config.log_dir:
            raise ValueError("log_dir 不能为空")

        if config.sampling_rate < 0 or config.sampling_rate > 1:
            raise ValueError("sampling_rate 必须在 0-1 之间")

        if config.rotation_strategy == RotationStrategy.SIZE and config.max_bytes <= 0:
            raise ValueError("使用 SIZE 轮转策略时，max_bytes 必须大于 0")

        if config.rotation_strategy == RotationStrategy.TIME and not config.rotation_when:
            raise ValueError("使用 TIME 轮转策略时，rotation_when 不能为空")

        # 检查日志目录权限（可选）
        try:
            log_path = Path(config.log_dir)
            if log_path.exists() and not os.access(log_path, os.W_OK):
                self._warning(f"日志目录不可写: {log_path}")
        except Exception as e:
            self._warning(f"检查日志目录失败: {e}")

        self._debug("配置验证通过")

    def _generate_config_digest(self, config: LoggingConfig) -> str:
        """生成配置摘要"""
        # 排除可能变化的字段
        exclude = {'_env', '_base_dir', '_last_modified'}
        config_dict = config.model_dump(exclude=exclude)
        config_str = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _ensure_directories(self):
        """确保日志目录存在"""
        self._debug("确保日志目录存在...")

        # 主日志目录
        log_path = Path(self.config.log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        self._debug(f"主日志目录: {log_path}")

        # 并发锁目录
        if self.config.use_concurrent:
            lock_dir = Path(self.config.concurrent_lock_dir)
            lock_dir.mkdir(parents=True, exist_ok=True)
            self._debug(f"并发锁目录已创建: {lock_dir}")

        # 归档目录
        if self.config.archive_enabled:
            archive_path = Path(self.config.archive_path)
            if not archive_path.is_absolute():
                archive_path = log_path / archive_path
            archive_path.mkdir(parents=True, exist_ok=True)
            self._debug(f"归档目录已创建: {archive_path}")

        self._debug("目录创建完成")

    def initialize(self, config: Optional[LoggingConfig] = None) -> bool:
        """
        初始化日志系统

        参数:
            config: 日志配置对象

        返回:
            bool: 文件处理器是否成功创建
        """
        if self._initialized:
            return True

        with self._lock:
            self._debug("=" * 50)
            self._debug("开始初始化日志系统")

            try:
                # 如果没有传入配置，创建默认配置
                if config is None:
                    config = LoggingConfig()
                    self._debug("使用默认配置")

                # 使用传入配置（不要再 new）
                self.config = config

                # 设置 app_name
                self._app_name = config.name
                self._debug(f"设置应用名称: {self._app_name}")

                os.environ["DATAMIND_APP_NAME"] = self._app_name
                os.environ["DATAMIND_LOG_NAME"] = self._app_name
                self._debug(f"同步环境变量: APP_NAME={self._app_name}, LOG_NAME={self._app_name}")

                # 配置验证
                self._debug("执行配置验证...")
                self._validate_config(config)

                # 创建时区格式化器
                self._init_timezone_formatter()

                # 生成配置摘要
                self._config_digest = self._generate_config_digest(config)
                self._debug("配置摘要: %s", self._config_digest)

                # 创建日志目录
                self._ensure_directories()
                self._debug("日志目录创建完成: %s", self.config.log_dir)

                # 初始化过滤器
                self._init_filters()
                self._debug("过滤器初始化完成")

                # 设置上下文配置
                self._init_context()
                self._debug("上下文配置完成")

                # 初始化所有日志记录器
                self._debug("开始初始化所有日志记录器...")
                self._init_all_loggers()
                self._debug("所有日志记录器初始化完成")

                # 初始化清理管理器
                self._init_cleanup_manager()
                self._debug("清理管理器初始化完成")

                # 注册清理函数
                atexit.register(self.cleanup)
                self._debug("已注册清理函数")

                # 记录启动日志
                self._log_startup_info()
                self._debug("启动日志已记录")

                # 检查文件处理器
                file_handlers_count = self._check_file_handlers()
                self._debug("文件处理器检查完成，数量: %d", file_handlers_count)

                # 如果是异步模式，确保处理器正常工作
                if self.config.use_async:
                    self._debug("异步模式已启用，等待处理器初始化...")
                    time.sleep(0.2)

                # 刷新启动日志
                self._flush_bootstrap_logs()
                self._debug("启动日志刷新完成")

                self._initialized = True
                self._debug("日志组件初始化完成")

                # 最终状态检查
                self._debug("")
                self._debug("=" * 50)
                self._debug("日志组件初始化完成")
                self._debug("-" * 50)
                self._debug(f"配置名称                  : {self.config.name}")
                self._debug(f"应用名称                  : {self._app_name}")
                self._debug(f"环境变量 DATAMIND_APP_NAME: {os.getenv('DATAMIND_APP_NAME')}")
                self._debug(f"环境变量 DATAMIND_LOG_NAME: {os.getenv('DATAMIND_LOG_NAME')}")
                self._debug(f"日志记录器                 : {logging.getLogger(self._app_name).name}")
                self._debug("=" * 50)
                self._debug("")

                return file_handlers_count > 0

            except Exception as e:
                self._error("初始化失败: %s", e)
                import traceback
                traceback.print_exc()
                raise

    def _init_timezone_formatter(self):
        """初始化时区格式化器"""
        self._debug("创建时区格式化器: %s", self.config.timezone.value)
        self.timezone_formatter = TimezoneFormatter(self.config)
        self._debug("时区设置完成: %s", self.config.timezone)

    def _init_filters(self):
        """初始化过滤器"""
        self._debug("初始化过滤器...")
        self.request_id_filter = RequestIdFilter()
        self.sensitive_filter = SensitiveDataFilter(self.config)
        self.sampling_filter = SamplingFilter(self.config)
        self._debug("过滤器初始化完成")

        if hasattr(self.request_id_filter, 'set_config'):
            self.request_id_filter.set_config(self.config)
            self._debug("已设置请求ID过滤器的配置")

    def _init_context(self):
        """初始化上下文"""
        from datamind.core.logging import context
        context.set_config(self.config)
        self._debug("上下文调试: %s", "开启" if self.config.context_debug else "关闭")

    def _init_all_loggers(self):
        """初始化所有日志记录器"""
        self._debug("=" * 30)
        self._debug("开始初始化所有日志记录器")

        # 初始化根日志记录器
        self._debug("初始化根日志记录器...")
        self._init_root_logger()
        self._debug("根日志记录器初始化完成")

        # 初始化应用日志记录器
        self._debug("初始化应用日志记录器: %s...", self._app_name)
        self._init_app_logger()
        self._debug("应用日志记录器初始化完成")

        # 初始化分类日志记录器
        if self.config.enable_access_log:
            self._debug("初始化访问日志记录器...")
            self._init_access_logger()
            self._debug("访问日志记录器初始化完成")
        else:
            self._debug("访问日志已禁用")

        if self.config.enable_audit_log:
            self._debug("初始化审计日志记录器...")
            self._init_audit_logger()
            self._debug("审计日志记录器初始化完成")
        else:
            self._debug("审计日志已禁用")

        if self.config.enable_performance_log:
            self._debug("初始化性能日志记录器...")
            self._init_performance_logger()
            self._debug("性能日志记录器初始化完成")
        else:
            self._debug("性能日志已禁用")

        self._debug("所有日志记录器初始化完成")
        self._debug("=" * 30)

    def _init_cleanup_manager(self):
        """初始化清理管理器"""
        self._debug("初始化清理管理器...")
        self.cleanup_manager = CleanupManager(self.config, self.timezone_formatter)
        self.cleanup_manager.start()
        self._debug("清理管理器已启动")

    def _check_file_handlers(self) -> int:
        """检查文件处理器"""
        app_logger = logging.getLogger(self._app_name)
        file_handlers = [h for h in app_logger.handlers
                         if isinstance(h, (logging.FileHandler,
                                           logging.handlers.RotatingFileHandler,
                                           ConcurrentRotatingFileHandler,
                                           TimeRotatingFileHandlerWithTimezone))]

        file_handlers_count = len(file_handlers)
        self._debug(f"应用日志文件处理器数量: {file_handlers_count}")

        if file_handlers_count > 0:
            self._debug("文件处理器已就绪，类型: %s",
                        [type(h).__name__ for h in file_handlers])

            # 输出每个处理器的文件名
            for i, h in enumerate(file_handlers):
                if hasattr(h, 'baseFilename'):
                    self._debug(f"  处理器 {i} 文件: {h.baseFilename}")

            time.sleep(0.5)  # 确保文件处理器完全初始化
        else:
            self._warning("警告: 没有找到文件处理器，启动日志无法写入文件")

        return file_handlers_count

    def _flush_bootstrap_logs(self):
        """刷新启动日志"""
        self._debug("刷新启动日志...")
        try:
            from datamind.core.logging.bootstrap import flush_bootstrap_logs, _bootstrap_handler

            # 确保bootstrap处理器有内容需要刷新
            if _bootstrap_handler and hasattr(_bootstrap_handler, 'buffer'):
                buffer_size = len(_bootstrap_handler.buffer)
                self._debug(f"Bootstrap缓存中有 {buffer_size} 条日志")

            replayed_count = flush_bootstrap_logs()

            if replayed_count > 0:
                app_logger = logging.getLogger(self._app_name)
                app_logger.info(f"已刷新 {replayed_count} 条启动日志到文件")
                self._debug(f"成功刷新 {replayed_count} 条启动日志")

                # 强制刷新所有处理器
                for handler in app_logger.handlers:
                    handler.flush()
            else:
                self._debug("没有启动日志需要刷新")

                # 如果缓存为空，尝试直接写入一条测试日志
                if _bootstrap_handler and hasattr(_bootstrap_handler, 'buffer'):
                    if len(_bootstrap_handler.buffer) == 0:
                        from datamind.core.logging.bootstrap import bootstrap_info
                        bootstrap_info("测试启动日志")
                        time.sleep(0.1)
                        replayed_count = flush_bootstrap_logs()
                        self._debug(f"写入测试日志后刷新了 {replayed_count} 条")

        except ImportError as e:
            self._debug(f"bootstrap模块未找到: {e}")
        except Exception as e:
            self._error("刷新启动日志时出错: %s", e, exc_info=True)

    def _init_logger(self, name: str, filename: str, level: LogLevel,
                     format_type: LogFormat, propagate: bool = False) -> logging.Logger:
        """
        初始化 logger

        参数:
            name: logger名称
            filename: 日志文件名
            format_type: 日志格式类型
            propagate: 是否传播到父logger

        返回:
            配置好的logger实例
        """
        logger = logging.getLogger(name)
        logger.setLevel(level.value)
        logger.propagate = propagate

        # 清除现有的处理器
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        self._debug(f"创建处理器: {name} - {filename} - {format_type.value}")

        # 创建文件处理器
        handler = self._create_file_handler(
            filename=filename,
            level=level,
            format_type=format_type
        )
        logger.addHandler(handler)

        # 如果是主应用日志且启用了控制台输出，添加控制台处理器
        if name == self._app_name and self.config.console_output:
            console_handler = self._create_console_handler()
            if console_handler:
                logger.addHandler(console_handler)

        self._debug(f"初始化 logger '{name}' 完成，格式: {format_type.value}")
        return logger

    def _init_root_logger(self):
        """初始化 root logger"""
        self._debug("初始化根日志记录器")
        root_logger = logging.getLogger()

        # 设置级别
        root_logger.setLevel(logging.WARNING)

        # 清除现有的处理器
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

        # 添加控制台处理器
        if self.config and self.config.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.WARNING)
            formatter = CustomTextFormatter(self.config)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            self._debug("根日志记录器已添加控制台处理器")

        # 添加文件处理器
        if self.config and self.config.error_file:
            error_handler = self._create_file_handler(
                filename=self.config.error_file,
                level=LogLevel.WARNING,
                format_type=LogFormat.TEXT
            )
            root_logger.addHandler(error_handler)
            self._debug("根日志记录器已添加错误文件处理器")

        self._debug("根日志记录器初始化完成")

    def _init_app_logger(self):
        """初始化应用日志记录器"""
        self._debug("=" * 20)
        self._debug("开始初始化应用日志记录器: %s", self._app_name)
        self._debug("日志格式: %s", self.config.format)
        self._debug("日志级别: %s", self.config.level)
        self._debug("日志文件: %s", self.config.file)
        self._debug("错误日志文件: %s", self.config.error_file)

        # 根据配置的格式选择合适的初始化方式
        if self.config.format == LogFormat.BOTH:
            # 双格式：为文本和JSON使用不同的文件名
            base_path = Path(self.config.file)
            text_file = str(base_path.parent / f"{base_path.stem}.text{base_path.suffix}")
            json_file = str(base_path.parent / f"{base_path.stem}.json{base_path.suffix}")

            self._debug(f"双格式文件: text={text_file}, json={json_file}")

            self.app_logger = logging.getLogger(self._app_name)
            self.app_logger.setLevel(self.config.level.value)
            self.app_logger.propagate = False

            # 清除现有的处理器
            for handler in self.app_logger.handlers[:]:
                handler.close()
                self.app_logger.removeHandler(handler)

            # 添加文本处理器
            text_handler = self._create_file_handler(
                filename=text_file,
                level=self.config.level,
                format_type=LogFormat.TEXT
            )
            self.app_logger.addHandler(text_handler)

            # 添加JSON处理器
            json_handler = self._create_file_handler(
                filename=json_file,
                level=self.config.level,
                format_type=LogFormat.JSON
            )
            self.app_logger.addHandler(json_handler)

            # 错误日志单独处理
            if self.config.error_file:
                error_base_path = Path(self.config.error_file)
                error_text_file = str(error_base_path.parent / f"{error_base_path.stem}.text{error_base_path.suffix}")
                error_json_file = str(error_base_path.parent / f"{error_base_path.stem}.json{error_base_path.suffix}")

                self._debug(f"错误日志双格式: text={error_text_file}, json={error_json_file}")

                # 创建错误日志处理器，设置级别为 ERROR
                error_text_handler = self._create_file_handler(
                    filename=error_text_file,
                    level=LogLevel.ERROR,
                    format_type=LogFormat.TEXT
                )

                error_json_handler = self._create_file_handler(
                    filename=error_json_file,
                    level=LogLevel.ERROR,
                    format_type=LogFormat.JSON
                )

                self.app_logger.addHandler(error_text_handler)
                self.app_logger.addHandler(error_json_handler)

                self._debug("错误日志处理器已挂载到 app_logger，只处理 ERROR 及以上级别")
        else:
            # 单一格式
            self._debug(f"单一格式: {self.config.format.value}")
            self.app_logger = self._init_logger(
                name=self._app_name,
                filename=self.config.file,
                level=self.config.level,
                format_type=self.config.format,
                propagate=False
            )

            # 错误日志单独处理
            if self.config.error_file:
                self._debug(f"添加错误日志处理器: {self.config.error_file}")
                error_handler = self._create_file_handler(
                    filename=self.config.error_file,
                    level=LogLevel.ERROR,  # 关键：设置级别为 ERROR
                    format_type=self.config.format
                )

                self.app_logger.addHandler(error_handler)
                self._debug("错误日志处理器已挂载到 app_logger，只处理 ERROR 及以上级别")

        # 添加控制台输出
        if self.config.console_output:
            console_handler = self._create_console_handler()
            if console_handler:
                self.app_logger.addHandler(console_handler)
                self._debug("已添加控制台处理器")

        # 记录初始化完成日志
        self.app_logger.log(
            self.config.level.value,
            "应用日志记录器初始化完成",
            extra={
                "format": self.config.format.value,
                "handlers": len(self.app_logger.handlers)
            }
        )

        self._debug("应用日志记录器初始化完成，处理器数量: %d", len(self.app_logger.handlers))
        self._debug("=" * 20)

    def _init_access_logger(self):
        """初始化访问日志记录器"""
        if not self.config.enable_access_log:
            self._debug("访问日志已禁用")
            return

        self._debug("初始化访问日志记录器")
        self.access_logger = self._init_logger(
            name=f'{self._app_name}.access',
            filename=self.config.access_log_file,
            level=LogLevel.INFO,
            format_type=self.config.format,
            propagate=False
        )

        self.access_logger.log(
            logging.INFO,
            "访问日志记录器初始化完成",
            extra={"format": self.config.format.value}
        )

    def _init_audit_logger(self):
        """初始化审计日志记录器"""
        if not self.config.enable_audit_log:
            self._debug("审计日志已禁用")
            return

        self._debug("初始化审计日志记录器")
        # 审计日志优先使用JSON格式
        format_type = LogFormat.JSON if self.config.format == LogFormat.BOTH else self.config.format

        self.audit_logger = self._init_logger(
            name=f'{self._app_name}.audit',
            filename=self.config.audit_log_file,
            level=LogLevel.INFO,
            format_type=format_type,
            propagate=False
        )

        self.audit_logger.log(
            logging.INFO,
            "审计日志记录器初始化完成",
            extra={"format": "json"}
        )

    def _init_performance_logger(self):
        """初始化性能日志记录器"""
        if not self.config.enable_performance_log:
            self._debug("性能日志已禁用")
            return

        self._debug("初始化性能日志记录器")
        # 性能日志也使用JSON格式
        format_type = LogFormat.JSON if self.config.format == LogFormat.BOTH else self.config.format

        self.performance_logger = self._init_logger(
            name=f'{self._app_name}.performance',
            filename=self.config.performance_log_file,
            level=LogLevel.INFO,
            format_type=format_type,
            propagate=False
        )

        self.performance_logger.log(
            logging.INFO,
            "性能日志记录器初始化完成",
            extra={"format": "json"}
        )

    def _create_file_handler(
            self,
            filename: str,
            level: LogLevel,
            format_type: LogFormat
    ) -> logging.Handler:
        """创建文件处理器"""
        log_path = Path(self.config.log_dir) / filename
        self._debug(f"创建文件处理器: {log_path}")

        # 根据轮转策略选择处理器
        if self.config.rotation_strategy == RotationStrategy.SIZE:
            handler_class = logging.handlers.RotatingFileHandler
            kwargs = {
                'filename': str(log_path),
                'maxBytes': self.config.max_bytes,
                'backupCount': self.config.backup_count,
                'encoding': self.config.encoding
            }
            self._debug(f"使用大小轮转: maxBytes={self.config.max_bytes}, backupCount={self.config.backup_count}")
        else:
            handler_class = logging.handlers.TimedRotatingFileHandler
            kwargs = {
                'filename': str(log_path),
                'when': self.config.rotation_when.value if self.config.rotation_when else 'midnight',
                'interval': self.config.rotation_interval,
                'backupCount': self.config.backup_count,
                'encoding': self.config.encoding,
                'utc': self.config.rotation_utc
            }
            self._debug(f"使用时间轮转: when={kwargs['when']}, interval={kwargs['interval']}")

        # 并发日志
        if self.config.use_concurrent and handler_class.__name__ == "RotatingFileHandler":
            from concurrent_log_handler import ConcurrentRotatingFileHandler
            handler = ConcurrentRotatingFileHandler(**kwargs)
            self._debug("使用并发处理器: ConcurrentRotatingFileHandler")
        else:
            handler = handler_class(**kwargs)
            self._debug(f"使用处理器: {handler_class.__name__}")

        handler.setLevel(level.value)

        # 格式化器
        if format_type == LogFormat.JSON:
            formatter = CustomJsonFormatter(self.config)
            self._debug("使用JSON格式化器")
        else:
            formatter = CustomTextFormatter(self.config)
            self._debug("使用文本格式化器")

        handler.setFormatter(formatter)

        # 添加过滤器
        if self.request_id_filter:
            handler.addFilter(self.request_id_filter)
            self._debug("添加请求ID过滤器")

        if self.sensitive_filter:
            handler.addFilter(self.sensitive_filter)
            self._debug("添加敏感数据过滤器")

        if self.sampling_filter:
            handler.addFilter(self.sampling_filter)
            self._debug("添加采样过滤器")

        # 异步处理
        if self.config.use_async:
            async_handler = AsyncLogHandler(self.config, handler)
            # 设置相同的级别和过滤器
            async_handler.setLevel(level.value)
            if self.request_id_filter:
                async_handler.addFilter(self.request_id_filter)
            if self.sensitive_filter:
                async_handler.addFilter(self.sensitive_filter)
            if self.sampling_filter:
                async_handler.addFilter(self.sampling_filter)
            self._debug("包装为异步处理器")
            return async_handler

        return handler

    def _create_console_handler(self) -> Optional[logging.Handler]:
        """创建控制台处理器"""
        if not self.config.console_output:
            self._debug("控制台输出已禁用")
            return None

        self._debug("创建控制台处理器")
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.config.console_level.value)
        self._debug("控制台日志级别: %s", self.config.console_level)

        # 控制台使用文本格式
        formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        return handler

    def log_access(self, method: str = "GET", path: str = "/", status: int = 200,
                   duration_ms: float = 0.0, ip: str = "", user_agent: str = "",
                   **kwargs):
        """记录访问日志"""
        if not hasattr(self, 'access_logger') or not self.access_logger:
            self._debug("访问日志记录器不可用")
            return

        request_id = self.get_request_id()

        extra = {
            'method': method,
            'path': path,
            'status': status,
            'duration_ms': duration_ms,
            'ip': ip,
            'user_agent': user_agent,
        }
        extra.update(kwargs)
        extra = {k: v for k, v in extra.items() if v is not None}

        self._debug("记录访问日志: %s %s, 状态=%d, 耗时=%.2fms, request_id=%s",
                    method, path, status, duration_ms, request_id)

        self.access_logger.info("访问日志", extra=extra)
        self._stats['logs_processed'] += 1

    def log_audit(self, action: str, user_id: str, target_user: str = None,
                  role: str = None, ip_address: str = None, **kwargs):
        """记录审计日志"""
        if not hasattr(self, 'audit_logger') or not self.audit_logger:
            self._debug("审计日志记录器不可用")
            return

        request_id = self.get_request_id()

        extra = {
            'action': action,
            'user_id': user_id,
        }
        if target_user is not None:
            extra['target_user'] = target_user
        if role is not None:
            extra['role'] = role
        if ip_address is not None:
            extra['ip_address'] = ip_address
        extra.update(kwargs)
        extra = {k: v for k, v in extra.items() if v is not None}

        self._debug("记录审计日志: action=%s, user=%s, request_id=%s", action, user_id, request_id)
        self.audit_logger.info("审计日志", extra=extra)
        self._stats['logs_processed'] += 1

    def log_performance(self, operation: str, duration_ms: float, query: str = None,
                        rows: int = None, database: str = None, **kwargs):
        """记录性能日志"""
        if not hasattr(self, 'performance_logger') or not self.performance_logger:
            self._debug("性能日志记录器不可用")
            return

        request_id = self.get_request_id()

        extra = {
            'operation': operation,
            'duration_ms': duration_ms,
        }
        if query is not None:
            extra['query'] = query
        if rows is not None:
            extra['rows'] = rows
        if database is not None:
            extra['database'] = database
        extra.update(kwargs)
        extra = {k: v for k, v in extra.items() if v is not None}

        self._debug("记录性能日志: operation=%s, duration=%.2fms, request_id=%s",
                    operation, duration_ms, request_id)
        self.performance_logger.info("性能日志", extra=extra)
        self._stats['logs_processed'] += 1

    def _log_startup_info(self):
        """记录启动信息"""
        app_logger = logging.getLogger(self._app_name)
        app_logger.log(
            self.config.level.value,
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

    def _capture_current_handlers(self) -> Dict[str, List[logging.Handler]]:
        """捕获当前所有日志器的处理器"""
        handlers = {}
        for logger_name in ['', 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            handlers[logger_name] = logger.handlers[:]
            self._debug("捕获 %s 的 %d 个处理器", logger_name or 'root', len(logger.handlers))
        return handlers

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

    def _log_reload_start(self, old_config: LoggingConfig, new_config: LoggingConfig):
        """记录重载开始"""
        logger = logging.getLogger()
        logger.log(
            logging.INFO,
            "开始热重载日志配置",
            extra={
                "old_timezone": old_config.timezone.value,
                "new_timezone": new_config.timezone.value,
                "old_format": old_config.format.value,
                "new_format": new_config.format.value,
                "old_digest": self._config_digest,
                "new_digest": self._generate_config_digest(new_config),
                "event": "config_reload_start"
            }
        )
        self._debug("已记录重载开始日志")

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

    def reload_config(self, new_config: Optional[LoggingConfig] = None) -> bool:
        """
        热重载日志配置

        参数:
            new_config: 新的配置对象，如果为None则创建新实例

        返回:
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
                    self._debug("创建新配置实例")
                    # 使用环境变量创建新配置
                    new_config = LoggingConfig()

                # 检查配置是否有变化（通过摘要比较）
                old_digest = self._config_digest
                new_digest = self._generate_config_digest(new_config)

                if old_digest == new_digest:
                    self._debug("配置无变化，跳过重载")
                    logging.getLogger().info("配置无变化，跳过重载")
                    return True

                self._debug("配置有变化，执行重载")
                self._debug("旧配置摘要: %s", old_digest[:8])
                self._debug("新配置摘要: %s", new_digest[:8])

                # 配置验证
                self._validate_config(new_config)

                # 记录重载开始
                self._log_reload_start(old_config, new_config)

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
        self._init_timezone_formatter()

        self._config_digest = self._generate_config_digest(new_config)
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
        for logger_name in ['', self._app_name, 'access', 'audit', 'performance']:
            logger = logging.getLogger(logger_name)
            removed = len(logger.handlers)
            for h in logger.handlers[:]:
                h.close()
                logger.removeHandler(h)
            self._debug("已清除 %s 的 %d 个处理器", logger_name or 'root', removed)

        # 重新初始化所有日志器
        self._debug("重新初始化日志记录器")
        self._init_root_logger()
        self._init_app_logger()
        self._init_access_logger()
        self._init_audit_logger()
        self._init_performance_logger()

        self._initialized = True
        self._debug("新配置应用完成")

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
            self._config_digest = self._generate_config_digest(old_config)
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
            logging.getLogger().critical(
                f"配置回滚失败，日志系统可能处于不一致状态: {rollback_error}",
                exc_info=True
            )

    def watch_config_changes(self, interval: int = 5) -> threading.Thread:
        """
        监控配置文件变化并自动重载

        参数:
            interval: 检查间隔（秒）

        返回:
            监控线程
        """

        def watch_worker():
            last_mtimes = {}

            # 监控 .env 文件
            env_files = ['.env', f'.env.{os.getenv("DATAMIND_ENV", "development")}']
            self._debug("监控配置文件: %s", env_files)

            # 初始化文件修改时间
            for env_file in env_files:
                env_path = Path(env_file)
                if env_path.exists():
                    try:
                        last_mtimes[env_file] = env_path.stat().st_mtime
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
                        env_path = Path(env_file)
                        if env_path.exists():
                            try:
                                current_mtime = env_path.stat().st_mtime
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
                        # 创建新配置并重载
                        new_config = LoggingConfig()
                        self.reload_config(new_config)

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
            # 强制刷新所有异步处理器
            self._debug("强制刷新所有处理器...")
            for logger_name in ['', self._app_name, 'access', 'audit', 'performance']:
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers:
                    try:
                        if isinstance(handler, AsyncLogHandler):
                            self._debug(f"刷新异步处理器: {handler}")
                            handler.flush()
                            time.sleep(0.1)  # 给异步处理一点时间
                        handler.flush()
                    except Exception as e:
                        self._debug(f"刷新处理器失败: {e}")

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