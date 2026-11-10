"""接入 CVXPY 和 Python warnings，保留原始 LogRecord 与警告语义."""

import logging
import os
import warnings
from collections.abc import Sequence

from structlog.typing import EventDict, Processor, WrappedLogger
from structlog.stdlib import ExtraAdder


class _ForwardHandler(logging.Handler):
    """复用应用输出通道，不重新发出或重新命名第三方日志."""

    def __init__(self, handlers: Sequence[logging.Handler]) -> None:
        super().__init__()
        self.handlers = tuple(handlers)

    def emit(self, record: logging.LogRecord) -> None:
        """交给原有 handler；保留消息参数、级别、异常与堆栈信息."""
        for handler in self.handlers:
            if record.levelno >= handler.level:
                handler.handle(record)


class _HandlerGuard(logging.Filter):
    """适配 CVXPY 延迟导入时自行追加的默认 handler."""

    def __init__(self, logger: logging.Logger, handler: logging.Handler) -> None:
        super().__init__()
        self.logger = logger
        self.handler = handler
        self.original_handlers = list(logger.handlers)
        self.original_propagate = logger.propagate
        self.original_level = logger.level
        self.warning_level_owned = logger.name == "py.warnings" and logger.level == logging.NOTSET
        if self.warning_level_owned:
            # warnings 原本不受 root 的阈值控制；不要因接入而静默丢失。
            logger.setLevel(logging.WARNING)
        self._remember_handlers()
        logger.handlers = [handler]
        logger.propagate = False

    def _remember_handlers(self) -> None:
        for handler in self.logger.handlers:
            if handler is not self.handler and handler not in self.original_handlers:
                self.original_handlers.append(handler)

    def filter(self, record: logging.LogRecord) -> bool:
        """在派发前收敛默认输出通道，保留每一条真实事件."""
        self._remember_handlers()
        self.logger.handlers = [self.handler]
        self.logger.propagate = False
        return True

    def restore(self) -> None:
        """恢复已有通道，不关闭由第三方持有的 handler."""
        self._remember_handlers()
        self.logger.handlers = self.original_handlers
        self.logger.propagate = self.original_propagate
        if self.warning_level_owned and self.logger.level == logging.WARNING:
            self.logger.setLevel(self.original_level)
        self.logger.removeFilter(self)


class ForeignLogging:
    """管理本进程内两个明确来源的接入与清理."""

    def __init__(self, handlers: Sequence[logging.Handler]) -> None:
        self.handler = _ForwardHandler(handlers)
        self.guards = []
        for name in ("__cvxpy__", "py.warnings"):
            logger = logging.getLogger(name)
            guard = _HandlerGuard(logger, self.handler)
            logger.addFilter(guard)
            self.guards.append(guard)
        previous = warnings.showwarning
        logging.captureWarnings(True)
        self.showwarning = warnings.showwarning
        self.owns_warning_capture = self.showwarning is not previous

    def close(self) -> None:
        """只撤销本实例拥有的配置，不改 warnings 过滤规则."""
        for guard in self.guards:
            guard.restore()
        if self.owns_warning_capture and warnings.showwarning is self.showwarning:
            logging.captureWarnings(False)
        self.handler.close()


def foreign_context(
    *,
    worker_id: str | None = None,
    service_id: str | None = None,
) -> Processor:
    """添加记录发出进程的来源，防止 fork 后误用父 Worker 身份."""
    configured_pid = os.getpid()
    add_extras = ExtraAdder()

    def processor(_: WrappedLogger, __: str, event: EventDict) -> EventDict:
        record = event["_record"]
        original_message = event["event"]
        add_extras(_, __, event)
        event["_foreign"] = True
        # Formatter-generated attributes are not user extras; keep the original
        # message and source authoritative even when another handler ran first.
        event.pop("message", None)
        event.pop("asctime", None)
        event["event"] = original_message
        event["logger"] = record.name
        event["level"] = record.levelname.lower()
        event["pid"] = record.process
        if record.process == configured_pid:
            if worker_id is not None:
                event.setdefault("worker_id", worker_id)
            if service_id is not None:
                event.setdefault("service_id", service_id)
        if record.stack_info:
            event["stack"] = record.stack_info
            event.pop("stack_info", None)
        if record.exc_text and not record.exc_info:
            event["exception"] = record.exc_text
        return event

    return processor
