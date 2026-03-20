# Datamind/datamind/core/logging/manager.py

"""日志管理器

统一管理所有日志的核心组件，提供：
  - 日志初始化与配置管理
  - 日志记录器创建与管理（app/access/audit/performance）
  - 日志处理器管理（文件轮转、异步处理）
  - 过滤器管理（请求ID、敏感数据、采样）
  - 配置热重载
  - 日志清理管理
  - 统计信息收集
"""

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
from typing import Dict, Optional, List, Any, Union
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

    统一管理所有日志

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
            self._initialized: bool = False
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
            self._stats: Dict[str, int] = {
                'logs_processed': 0,
                'errors': 0,
                'warnings': 0
            }
            self._app_name: str = os.getenv("DATAMIND_APP_NAME", "datamind").lower()
            self._watch_thread: Optional[threading.Thread] = None
            self._shutdown_called: bool = False

    def _get_logger_names(self) -> List[str]:
        """获取所有需要管理的日志器名称列表

        返回:
            日志器名称列表
        """
        return [
            '',  # root logger
            self._app_name,
            f'{self._app_name}.access',
            f'{self._app_name}.audit',
            f'{self._app_name}.performance'
        ]

    def _debug(self, msg: str, *args: Any) -> None:
        """调试输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.manager_debug:
            debug_print(self.__class__.__name__, msg, *args)

    def _warning(self, msg: str, *args: Any) -> None:
        """警告输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.manager_debug:
            warning_print(f"{self.__class__.__name__}", msg, *args)
        self._stats['warnings'] += 1

    def _error(self, msg: str, *args: Any) -> None:
        """错误输出

        参数:
            msg: 消息模板
            *args: 消息格式化参数
        """
        if self.config and self.config.manager_debug:
            error_print(f"{self.__class__.__name__}", msg, *args)
        self._stats['errors'] += 1

    def _validate_config(self, config: LoggingConfig) -> None:
        """验证配置

        参数:
            config: 日志配置对象

        抛出:
            ValueError: 配置无效时抛出
        """
        self._debug("验证配置: log_dir='%s'", config.log_dir)

        if not config.log_dir or config.log_dir.strip() == "":
            self._debug("log_dir 为空，抛出异常")
            raise ValueError("log_dir 不能为空")

        if config.sampling_rate < 0 or config.sampling_rate > 1:
            raise ValueError("sampling_rate 必须在 0-1 之间")

        if config.rotation_strategy == RotationStrategy.SIZE and config.max_bytes <= 0:
            raise ValueError("使用 SIZE 轮转策略时，max_bytes 必须大于 0")

        if config.rotation_strategy == RotationStrategy.TIME and not config.rotation_when:
            raise ValueError("使用 TIME 轮转策略时，rotation_when 不能为空")

        # 检查日志目录权限
        try:
            log_path = Path(config.log_dir)
            if log_path.exists() and not os.access(log_path, os.W_OK):
                self._warning(f"日志目录不可写: {log_path}")
        except Exception as e:
            self._warning(f"检查日志目录失败: {e}")

        self._debug("配置验证通过")

    def _generate_config_digest(self, config: LoggingConfig) -> str:
        """生成配置摘要

        参数:
            config: 日志配置对象

        返回:
            配置的 MD5 摘要
        """
        exclude = {'_env', '_base_dir', '_last_modified'}
        config_dict = config.model_dump(exclude=exclude)
        config_str = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.md5(config_str.encode()).hexdigest()

    def _ensure_directories(self) -> None:
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
        """初始化日志系统

        参数:
            config: 日志配置对象，如果为 None 则使用默认配置

        返回:
            文件处理器是否成功创建
        """
        if self._initialized:
            return True

        with self._lock:
            self._debug("=" * 50)
            self._debug("开始初始化日志系统")

            try:
                if config is None:
                    config = LoggingConfig()
                    self._debug("使用默认配置")
                else:
                    self._debug("使用自定义配置")
                    self._debug(f"   - log_dir: {config.log_dir}")
                    self._debug(f"   - file: {config.file}")
                    self._debug(f"   - name: {config.name}")
                    self._debug(f"   - format: {config.format}")

                # 保存配置副本，防止被环境变量覆盖
                self.config = config
                self._app_name = config.name

                # 同步环境变量（但不要覆盖用户配置）
                if not os.environ.get("DATAMIND_APP_NAME"):
                    os.environ["DATAMIND_APP_NAME"] = self._app_name
                if not os.environ.get("DATAMIND_LOG_NAME"):
                    os.environ["DATAMIND_LOG_NAME"] = self._app_name
                self._debug(f"同步环境变量: APP_NAME={self._app_name}")

                # 验证配置
                self._validate_config(config)
                self._init_timezone_formatter()
                self._config_digest = self._generate_config_digest(config)
                self._debug("配置摘要: %s", self._config_digest[:8])

                self._ensure_directories()
                self._init_filters()
                self._init_context()
                self._init_all_loggers()
                self._init_cleanup_manager()

                atexit.register(self.cleanup)
                self._debug("已注册清理函数")

                self._log_startup_info()
                file_handlers_count = self._check_file_handlers()

                if self.config.use_async:
                    time.sleep(0.2)

                self._flush_bootstrap_logs()
                self._initialized = True

                self._print_init_summary(file_handlers_count)
                return file_handlers_count > 0

            except Exception as e:
                self._error("初始化失败: %s", e)
                import traceback
                traceback.print_exc()
                raise

    def _print_init_summary(self, file_handlers_count: int) -> None:
        """打印初始化摘要

        参数:
            file_handlers_count: 文件处理器数量
        """
        self._debug("")
        self._debug("=" * 50)
        self._debug("日志组件初始化完成")
        self._debug("-" * 50)
        self._debug(f"配置名称                  : {self.config.name}")
        self._debug(f"应用名称                  : {self._app_name}")
        self._debug(f"环境变量 DATAMIND_APP_NAME: {os.getenv('DATAMIND_APP_NAME')}")
        self._debug(f"环境变量 DATAMIND_LOG_NAME: {os.getenv('DATAMIND_LOG_NAME')}")
        self._debug(f"日志记录器                 : {logging.getLogger(self._app_name).name}")
        self._debug(f"文件处理器数量             : {file_handlers_count}")
        self._debug("=" * 50)
        self._debug("")

    def _init_timezone_formatter(self) -> None:
        """初始化时区格式化器"""
        self._debug("创建时区格式化器: %s", self.config.timezone.value)
        self.timezone_formatter = TimezoneFormatter(self.config)

    def _init_filters(self) -> None:
        """初始化过滤器"""
        self._debug("初始化过滤器...")
        self.request_id_filter = RequestIdFilter()
        self.sensitive_filter = SensitiveDataFilter(self.config)
        self.sampling_filter = SamplingFilter(self.config)

        if hasattr(self.request_id_filter, 'set_config'):
            self.request_id_filter.set_config(self.config)
            self._debug("已设置请求ID过滤器的配置")

        self._debug("过滤器初始化完成")

    def _init_context(self) -> None:
        """初始化上下文"""
        from datamind.core.logging import context
        context.set_config(self.config)
        self._debug("上下文调试: %s", "开启" if self.config.context_debug else "关闭")

    def _init_all_loggers(self) -> None:
        """初始化所有日志记录器"""
        self._debug("=" * 30)
        self._debug("开始初始化所有日志记录器")

        self._init_root_logger()
        self._init_app_logger()

        if self.config.enable_access_log:
            self._init_access_logger()
        else:
            self._debug("访问日志已禁用")

        if self.config.enable_audit_log:
            self._init_audit_logger()
        else:
            self._debug("审计日志已禁用")

        if self.config.enable_performance_log:
            self._init_performance_logger()
        else:
            self._debug("性能日志已禁用")

        self._debug("所有日志记录器初始化完成")
        self._debug("=" * 30)

    def _init_cleanup_manager(self) -> None:
        """初始化清理管理器"""
        self._debug("初始化清理管理器...")
        self.cleanup_manager = CleanupManager(self.config, self.timezone_formatter)
        self.cleanup_manager.start()

    def _check_file_handlers(self) -> int:
        """检查文件处理器

        返回:
            文件处理器数量
        """
        app_logger = logging.getLogger(self._app_name)
        file_handlers = [h for h in app_logger.handlers
                         if isinstance(h, (logging.FileHandler,
                                           logging.handlers.RotatingFileHandler,
                                           ConcurrentRotatingFileHandler,
                                           TimeRotatingFileHandlerWithTimezone,
                                           AsyncLogHandler))]

        file_handlers_count = len(file_handlers)
        self._debug(f"应用日志文件处理器数量: {file_handlers_count}")

        if file_handlers_count > 0:
            self._debug("文件处理器已就绪，类型: %s",
                        [type(h).__name__ for h in file_handlers])

            for i, h in enumerate(file_handlers):
                if hasattr(h, 'baseFilename'):
                    self._debug(f"  处理器 {i} 文件: {h.baseFilename}")
                elif hasattr(h, 'target_handler') and hasattr(h.target_handler, 'baseFilename'):
                    self._debug(f"  处理器 {i} 目标文件: {h.target_handler.baseFilename}")

            time.sleep(0.5)
        else:
            self._warning("警告: 没有找到文件处理器，启动日志无法写入文件")

        return file_handlers_count

    def _flush_bootstrap_logs(self) -> None:
        """刷新启动日志"""
        self._debug("刷新启动日志...")
        try:
            from datamind.core.logging.bootstrap import flush_bootstrap_logs, _bootstrap_handler

            if _bootstrap_handler and hasattr(_bootstrap_handler, 'buffer'):
                buffer_size = len(_bootstrap_handler.buffer)
                self._debug(f"Bootstrap缓存中有 {buffer_size} 条日志")

            # 短暂等待确保处理器已完全初始化
            time.sleep(0.1)

            # 检查应用日志器的处理器
            app_logger = logging.getLogger(self._app_name)
            self._debug(f"应用日志器 '{self._app_name}' 有 {len(app_logger.handlers)} 个处理器")
            for i, h in enumerate(app_logger.handlers):
                self._debug(f"  处理器 {i}: {type(h).__name__}")

            replayed_count = flush_bootstrap_logs()

            if replayed_count > 0:
                self._debug(f"成功刷新 {replayed_count} 条启动日志")

                for handler in app_logger.handlers:
                    handler.flush()
            else:
                self._debug("没有启动日志需要刷新")

        except ImportError as e:
            self._debug(f"bootstrap模块未找到: {e}")
        except Exception as e:
            self._error("刷新启动日志时出错: %s", e)

    def _init_root_logger(self) -> None:
        """初始化 root logger"""
        self._debug("初始化根日志记录器")
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)

        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)

        if self.config and self.config.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.WARNING)
            formatter = CustomTextFormatter(self.config)
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
            self._debug("根日志记录器已添加控制台处理器")

        if self.config and self.config.error_file:
            error_handler = self._create_file_handler(
                filename=self.config.error_file,
                level=LogLevel.WARNING,
                format_type=LogFormat.TEXT
            )
            root_logger.addHandler(error_handler)
            self._debug("根日志记录器已添加错误文件处理器")

    def _init_app_logger(self) -> None:
        """初始化应用日志记录器"""
        self._debug("=" * 20)
        self._debug("开始初始化应用日志记录器: %s", self._app_name)
        self._debug("日志格式: %s", self.config.format)
        self._debug("日志级别: %s", self.config.level)
        self._debug("日志文件: %s", self.config.file)

        if self.config.format == LogFormat.BOTH:
            self._init_app_logger_both()
        else:
            self._init_app_logger_single()

        if self.config.console_output:
            console_handler = self._create_console_handler()
            if console_handler:
                self.app_logger.addHandler(console_handler)
                self._debug("已添加控制台处理器")

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

    def _init_app_logger_both(self) -> None:
        """初始化双格式应用日志记录器"""
        base_path = Path(self.config.file)
        text_file = str(base_path.parent / f"{base_path.stem}.text{base_path.suffix}")
        json_file = str(base_path.parent / f"{base_path.stem}.json{base_path.suffix}")

        self._debug(f"双格式文件: text={text_file}, json={json_file}")

        self.app_logger = logging.getLogger(self._app_name)
        self.app_logger.setLevel(self.config.level.value)
        self.app_logger.propagate = False

        for handler in self.app_logger.handlers[:]:
            handler.close()
            self.app_logger.removeHandler(handler)

        text_handler = self._create_file_handler(
            filename=text_file,
            level=self.config.level,
            format_type=LogFormat.TEXT
        )
        json_handler = self._create_file_handler(
            filename=json_file,
            level=self.config.level,
            format_type=LogFormat.JSON
        )
        self.app_logger.addHandler(text_handler)
        self.app_logger.addHandler(json_handler)

        if self.config.error_file:
            error_base_path = Path(self.config.error_file)
            error_text_file = str(error_base_path.parent / f"{error_base_path.stem}.text{error_base_path.suffix}")
            error_json_file = str(error_base_path.parent / f"{error_base_path.stem}.json{error_base_path.suffix}")

            self._debug(f"错误日志双格式: text={error_text_file}, json={error_json_file}")

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

    def _init_app_logger_single(self) -> None:
        """初始化单格式应用日志记录器"""
        self._debug("=" * 15)
        self._debug("初始化单格式应用日志记录器")
        self._debug("   - app_name: %s", self._app_name)
        self._debug("   - filename: %s", self.config.file)
        self._debug("   - format: %s", self.config.format)
        self._debug("   - level: %s", self.config.level)

        try:
            self.app_logger = self._init_logger(
                name=self._app_name,
                filename=self.config.file,
                level=self.config.level,
                format_type=self.config.format,
                propagate=False
            )
            self._debug("应用日志器创建成功，处理器数量: %d", len(self.app_logger.handlers))
        except Exception as e:
            self._error("创建应用日志器失败: %s", e)
            import traceback
            traceback.print_exc()
            raise

        if self.config.error_file:
            self._debug("添加错误日志处理器: %s", self.config.error_file)
            try:
                error_handler = self._create_file_handler(
                    filename=self.config.error_file,
                    level=LogLevel.ERROR,
                    format_type=self.config.format
                )
                self.app_logger.addHandler(error_handler)
                self._debug("错误日志处理器添加成功")
            except Exception as e:
                self._error("添加错误日志处理器失败: %s", e)
                raise

        self._debug("=" * 15)

    def _init_access_logger(self) -> None:
        """初始化访问日志记录器"""
        self._debug("初始化访问日志记录器")
        self.access_logger = self._init_logger(
            name=f'{self._app_name}.access',
            filename=self.config.access_log_file,
            level=LogLevel.INFO,
            format_type=self.config.format,
            propagate=False
        )

        self.access_logger.info("访问日志记录器初始化完成")

    def _init_audit_logger(self) -> None:
        """初始化审计日志记录器"""
        self._debug("初始化审计日志记录器")
        format_type = LogFormat.JSON if self.config.format == LogFormat.BOTH else self.config.format

        self.audit_logger = self._init_logger(
            name=f'{self._app_name}.audit',
            filename=self.config.audit_log_file,
            level=LogLevel.INFO,
            format_type=format_type,
            propagate=False
        )

        self.audit_logger.info("审计日志记录器初始化完成")

    def _init_performance_logger(self) -> None:
        """初始化性能日志记录器"""
        self._debug("初始化性能日志记录器")
        format_type = LogFormat.JSON if self.config.format == LogFormat.BOTH else self.config.format

        self.performance_logger = self._init_logger(
            name=f'{self._app_name}.performance',
            filename=self.config.performance_log_file,
            level=LogLevel.INFO,
            format_type=format_type,
            propagate=False
        )

        self.performance_logger.info("性能日志记录器初始化完成")

    def _init_logger(self, name: str, filename: str, level: LogLevel,
                     format_type: LogFormat, propagate: bool = False) -> logging.Logger:
        """初始化 logger

        参数:
            name: logger名称
            filename: 日志文件名
            level: 日志级别
            format_type: 日志格式类型
            propagate: 是否传播到父logger

        返回:
            配置好的logger实例
        """
        logger = logging.getLogger(name)
        logger.setLevel(level.value)
        logger.propagate = propagate

        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        try:
            handler = self._create_file_handler(
                filename=filename,
                level=level,
                format_type=format_type
            )
            logger.addHandler(handler)
            self._debug("成功添加处理器到 logger %s", name)
        except Exception as e:
            self._error("创建处理器失败 for %s: %s", name, e)
            raise

        return logger

    def _create_file_handler(self, filename: str, level: LogLevel,
                             format_type: LogFormat) -> logging.Handler:
        """创建文件处理器

        参数:
            filename: 文件名
            level: 日志级别
            format_type: 日志格式类型

        返回:
            文件处理器实例
        """
        log_path = Path(self.config.log_dir) / filename

        self._debug(f"🔧 创建文件处理器:")
        self._debug(f"   - config.log_dir: '{self.config.log_dir}'")
        self._debug(f"   - filename: '{filename}'")
        self._debug(f"   - log_path: '{log_path}'")
        self._debug(f"   - log_path 绝对路径: '{log_path.absolute()}'")
        self._debug(f"   - 目录是否存在: {log_path.parent.exists()}")

        # 确保目录存在
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._debug(f"   - 已确保目录存在: {log_path.parent}")

        # 测试写入权限
        try:
            test_file = log_path.parent / ".write_test"
            test_file.touch()
            test_file.unlink()
            self._debug(f"   - 目录可写: 是")
        except Exception as e:
            self._debug(f"   - 目录可写: 否, 错误: {e}")

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
            from concurrent_log_handler import ConcurrentRotatingFileHandler
            handler = ConcurrentRotatingFileHandler(**kwargs)
        else:
            handler = handler_class(**kwargs)

        handler.setLevel(level.value)

        if format_type == LogFormat.JSON:
            formatter = CustomJsonFormatter(self.config)
        else:
            formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        handler.addFilter(self.request_id_filter)
        handler.addFilter(self.sensitive_filter)
        handler.addFilter(self.sampling_filter)

        self._debug(f"   - 处理器创建成功: {type(handler).__name__}")
        if hasattr(handler, 'baseFilename'):
            self._debug(f"   - 处理器文件路径: {handler.baseFilename}")

        if self.config.use_async:
            async_handler = AsyncLogHandler(self.config, handler)
            async_handler.setLevel(level.value)
            async_handler.addFilter(self.request_id_filter)
            async_handler.addFilter(self.sensitive_filter)
            async_handler.addFilter(self.sampling_filter)
            self._debug(f"   - 已包装为异步处理器")
            return async_handler

        return handler

    def _create_console_handler(self) -> Optional[logging.Handler]:
        """创建控制台处理器

        返回:
            控制台处理器实例，如果控制台输出被禁用则返回 None
        """
        if not self.config.console_output:
            return None

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(self.config.console_level.value)

        formatter = CustomTextFormatter(self.config)
        handler.setFormatter(formatter)

        return handler

    def _log_startup_info(self) -> None:
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

    def log_access(self, method: str = "GET", path: str = "/", status: int = 200,
                   duration_ms: float = 0.0, ip: str = "", user_agent: str = "",
                   **kwargs: Any) -> None:
        """记录访问日志

        参数:
            method: HTTP 方法
            path: 请求路径
            status: HTTP 状态码
            duration_ms: 请求耗时（毫秒）
            ip: 客户端 IP
            user_agent: User-Agent
            **kwargs: 额外的日志字段
        """
        request_id = self.get_request_id()

        extra = {
            'request_id': request_id,
            'method': method,
            'path': path,
            'status': status,
            'duration_ms': duration_ms,
            'ip': ip,
            'user_agent': user_agent,
        }
        extra.update(kwargs)
        extra = {k: v for k, v in extra.items() if v is not None}

        if not hasattr(self, 'access_logger') or not self.access_logger:
            self._fallback_log("access", extra, {
                'method': method,
                'path': path,
                'status': status,
                'duration_ms': duration_ms
            })
            return

        self.access_logger.info("访问日志", extra=extra)
        self._stats['logs_processed'] += 1

    def log_audit(self, action: str, user_id: str, target_user: str = None,
                  role: str = None, ip_address: str = None, **kwargs: Any) -> None:
        """记录审计日志

        参数:
            action: 操作类型
            user_id: 操作用户 ID
            target_user: 目标用户 ID
            role: 角色
            ip_address: IP 地址
            **kwargs: 额外的日志字段
        """
        request_id = self.get_request_id()

        extra = {
            'request_id': request_id,
            'action': action,
            'user_id': user_id,
            'target_user': target_user,
            'role': role,
            'ip_address': ip_address,
        }
        extra.update(kwargs)
        extra = {k: v for k, v in extra.items() if v is not None}

        if not hasattr(self, 'audit_logger') or not self.audit_logger:
            self._fallback_log("audit", extra, {
                'action': action,
                'user_id': user_id
            })
            return

        self.audit_logger.info("审计日志", extra=extra)
        self._stats['logs_processed'] += 1

    def log_performance(self, operation: str, duration_ms: float, query: str = None,
                        rows: int = None, database: str = None, **kwargs: Any) -> None:
        """记录性能日志

        参数:
            operation: 操作名称
            duration_ms: 耗时（毫秒）
            query: 查询语句
            rows: 影响行数
            database: 数据库名称
            **kwargs: 额外的日志字段
        """
        request_id = self.get_request_id()

        extra = {
            'request_id': request_id,
            'operation': operation,
            'duration_ms': duration_ms,
            'query': query,
            'rows': rows,
            'database': database,
        }
        extra.update(kwargs)
        extra = {k: v for k, v in extra.items() if v is not None}

        if not hasattr(self, 'performance_logger') or not self.performance_logger:
            self._fallback_log("performance", extra, {
                'operation': operation,
                'duration_ms': duration_ms
            })
            return

        self.performance_logger.info("性能日志", extra=extra)
        self._stats['logs_processed'] += 1

    def _fallback_log(self, log_type: str, extra: Dict[str, Any],
                      essential_info: Dict[str, Any]) -> None:
        """Fallback 日志记录方法

        参数:
            log_type: 日志类型 ('access', 'audit', 'performance')
            extra: 完整的额外信息
            essential_info: 关键信息，用于生成简短的日志消息
        """
        try:
            fallback_logger = logging.getLogger()

            if log_type == "access":
                msg = (f"[FALLBACK ACCESS] {essential_info.get('method', 'UNKNOWN')} "
                       f"{essential_info.get('path', '/')} - {essential_info.get('status', 0)} "
                       f"({essential_info.get('duration_ms', 0):.2f}ms)")
            elif log_type == "audit":
                msg = (f"[FALLBACK AUDIT] action={essential_info.get('action', 'UNKNOWN')}, "
                       f"user={essential_info.get('user_id', 'N/A')}")
            elif log_type == "performance":
                msg = (f"[FALLBACK PERFORMANCE] {essential_info.get('operation', 'UNKNOWN')} - "
                       f"{essential_info.get('duration_ms', 0):.2f}ms")
            else:
                msg = f"[FALLBACK {log_type.upper()}]"

            if 'request_id' not in extra:
                extra['request_id'] = self.get_request_id()

            extra['_fallback'] = True
            extra['_log_type'] = log_type

            fallback_logger.warning(msg, extra=extra)
            self._stats['warnings'] += 1
            self._stats['logs_processed'] += 1

        except Exception as e:
            self._error("Fallback 日志记录失败: %s", e)
            try:
                print(f"CRITICAL: [{log_type.upper()}] {essential_info}", file=sys.stderr)
            except:
                pass

    def set_request_id(self, request_id: str) -> None:
        """设置当前请求ID

        参数:
            request_id: 请求 ID
        """
        from datamind.core.logging.context import set_request_id
        set_request_id(request_id)
        self._debug("设置请求ID: %s", request_id)

    def get_request_id(self) -> str:
        """获取当前请求ID

        返回:
            当前请求 ID
        """
        from datamind.core.logging.context import get_request_id
        request_id = get_request_id()
        return request_id

    def get_current_time(self) -> datetime:
        """获取当前时间（已应用时区）

        返回:
            应用时区后的当前时间
        """
        if self.timezone_formatter:
            return self.timezone_formatter.format_time()
        return datetime.now()

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息

        返回:
            统计信息字典
        """
        return self._stats.copy()

    def reload_config(self, new_config: Optional[LoggingConfig] = None) -> bool:
        """热重载日志配置

        参数:
            new_config: 新的配置对象，如果为 None 则创建新实例

        返回:
            重载是否成功
        """
        with self._lock:
            if not self._initialized:
                raise RuntimeError("日志管理器尚未初始化，请先调用 initialize()")

            self._debug("=" * 50)
            self._debug("开始热重载日志配置")

            old_config = self.config
            old_handlers = self._capture_current_handlers()

            try:
                if new_config is None:
                    new_config = LoggingConfig()

                old_digest = self._config_digest
                new_digest = self._generate_config_digest(new_config)

                if old_digest == new_digest:
                    self._debug("配置无变化，跳过重载")
                    return True

                self._validate_config(new_config)
                self._log_reload_start(old_config, new_config)
                self._apply_new_config(new_config)
                self._cleanup_old_handlers(old_handlers)
                self._log_reload_success()

                self._debug("热重载完成")
                self._debug("=" * 50)
                return True

            except Exception as e:
                self._error("热重载失败: %s", e)
                self._rollback_config(old_config, old_handlers, e)
                raise

    def _capture_current_handlers(self) -> Dict[str, List[logging.Handler]]:
        """捕获当前所有日志器的处理器

        返回:
            处理器映射
        """
        handlers = {}
        for logger_name in self._get_logger_names():
            logger = logging.getLogger(logger_name)
            handlers[logger_name] = logger.handlers[:]
        return handlers

    def _cleanup_old_handlers(self, old_handlers: Dict[str, List[logging.Handler]]) -> None:
        """清理旧的处理器

        参数:
            old_handlers: 旧处理器映射
        """
        total_handlers = 0
        for handlers in old_handlers.values():
            for handler in handlers:
                try:
                    if hasattr(handler, 'stop'):
                        handler.stop()
                    handler.close()
                    total_handlers += 1
                except Exception as e:
                    self._debug("关闭处理器失败: %s", e)
        self._debug("已清理 %d 个旧处理器", total_handlers)

    def _log_reload_start(self, old_config: LoggingConfig, new_config: LoggingConfig) -> None:
        """记录重载开始"""
        logger = logging.getLogger()
        logger.info(
            "开始热重载日志配置",
            extra={
                "old_timezone": old_config.timezone.value,
                "new_timezone": new_config.timezone.value,
                "old_format": old_config.format.value,
                "new_format": new_config.format.value,
                "event": "config_reload_start"
            }
        )

    def _log_reload_success(self) -> None:
        """记录重载成功"""
        logging.getLogger().info(
            "日志配置热重载成功",
            extra={
                "timezone": self.config.timezone.value,
                "format": self.config.format.value,
                "event": "config_reload_success"
            }
        )

    def _apply_new_config(self, new_config: LoggingConfig) -> None:
        """应用新配置

        参数:
            new_config: 新配置对象
        """
        self._debug("开始应用新配置")

        request_id_filter = self.request_id_filter

        self._initialized = False
        self.config = new_config

        self._init_timezone_formatter()
        self._config_digest = self._generate_config_digest(new_config)

        self.sensitive_filter = SensitiveDataFilter(new_config)
        self.sampling_filter = SamplingFilter(new_config)
        self.request_id_filter = request_id_filter

        self.cleanup_manager = CleanupManager(new_config, self.timezone_formatter)
        self.cleanup_manager.start()

        for logger_name in self._get_logger_names():
            logger = logging.getLogger(logger_name)
            for h in logger.handlers[:]:
                h.close()
                logger.removeHandler(h)

        self._init_root_logger()
        self._init_app_logger()
        if self.config.enable_access_log:
            self._init_access_logger()
        if self.config.enable_audit_log:
            self._init_audit_logger()
        if self.config.enable_performance_log:
            self._init_performance_logger()

        self._initialized = True
        self._debug("新配置应用完成")

    def _rollback_config(self, old_config: LoggingConfig,
                         old_handlers: Dict[str, List[logging.Handler]],
                         error: Exception) -> None:
        """回滚到旧配置

        参数:
            old_config: 旧配置对象
            old_handlers: 旧处理器映射
            error: 导致回滚的异常
        """
        self._debug("开始回滚到旧配置")
        try:
            for logger_name in self._get_logger_names():
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers[:]:
                    try:
                        if hasattr(handler, 'stop'):
                            handler.stop()
                        handler.close()
                    except:
                        pass
                    logger.removeHandler(handler)

            restored = 0
            for logger_name, handlers in old_handlers.items():
                logger = logging.getLogger(logger_name)
                for handler in handlers:
                    logger.addHandler(handler)
                    restored += 1
            self._debug("已恢复 %d 个旧处理器", restored)

            self.config = old_config
            self.timezone_formatter = TimezoneFormatter(old_config)
            self._config_digest = self._generate_config_digest(old_config)
            self._initialized = True

            logging.getLogger().error(
                f"配置重载失败，已回滚: {error}",
                exc_info=True,
                extra={"event": "config_reload_failed"}
            )

        except Exception as rollback_error:
            self._error("回滚过程中发生错误: %s", rollback_error)

    def watch_config_changes(self, interval: int = 5) -> threading.Thread:
        """监控配置文件变化并自动重载

        参数:
            interval: 检查间隔（秒）

        返回:
            监控线程
        """

        def watch_worker() -> None:
            last_mtimes = {}
            env_files = ['.env', f'.env.{os.getenv("DATAMIND_ENV", "development")}']

            for env_file in env_files:
                env_path = Path(env_file)
                if env_path.exists():
                    try:
                        last_mtimes[env_file] = env_path.stat().st_mtime
                    except Exception as e:
                        self._debug("无法获取文件 %s 的修改时间: %s", env_file, e)

            while self._initialized:
                try:
                    time.sleep(interval)

                    need_reload = False
                    changed_files = []

                    for env_file in env_files:
                        env_path = Path(env_file)
                        if env_path.exists():
                            try:
                                current_mtime = env_path.stat().st_mtime
                                if env_file in last_mtimes and current_mtime > last_mtimes[env_file]:
                                    need_reload = True
                                    changed_files.append(env_file)
                                last_mtimes[env_file] = current_mtime
                            except Exception as e:
                                self._debug("检查文件 %s 时出错: %s", env_file, e)

                    if need_reload:
                        self._debug("检测到配置文件变化: %s", changed_files)
                        logging.getLogger().info(f"检测到配置文件变化: {changed_files}")
                        new_config = LoggingConfig()
                        self.reload_config(new_config)

                except Exception as e:
                    self._error("配置监控失败: %s", e)

        self._watch_thread = threading.Thread(target=watch_worker, daemon=True, name="ConfigWatcher")
        self._watch_thread.start()
        self._debug("配置监控线程已启动，间隔: %d秒", interval)
        return self._watch_thread

    def cleanup(self) -> None:
        """清理资源"""
        if self._shutdown_called:
            return
        self._shutdown_called = True

        self._debug("开始清理资源")
        with self._lock:
            for logger_name in self._get_logger_names():
                logger = logging.getLogger(logger_name)
                for handler in logger.handlers:
                    try:
                        if isinstance(handler, AsyncLogHandler):
                            handler.flush()
                        handler.flush()
                    except Exception as e:
                        self._debug(f"刷新处理器失败: {e}")

            if self.cleanup_manager:
                self.cleanup_manager.stop()

            total_closed = 0
            for logger_name in self._get_logger_names():
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

            self._initialized = False
            self._debug("清理完成，统计信息: 处理日志=%d, 警告=%d, 错误=%d",
                        self._stats['logs_processed'],
                        self._stats['warnings'],
                        self._stats['errors'])


# 全局日志管理器实例
log_manager = LogManager()