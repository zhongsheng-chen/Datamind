# datamind/core/logging/__init__.py

"""日志模块

提供完整的日志管理功能，包括日志初始化、格式化、过滤、处理和清理。

核心功能：
  - get_logger: 安全获取日志记录器
  - log_audit: 记录审计日志
  - log_access: 记录API访问日志
  - log_performance: 记录性能指标
  - log_manager: 全局日志管理器实例

日志类型使用场景：
  - get_logger: 业务逻辑日志、调试信息、错误追踪
  - log_audit: 模型注册/激活/停用、A/B测试操作、用户登录、配置变更
  - log_access: HTTP请求日志、API调用统计
  - log_performance: 模型推理耗时、数据库查询耗时、缓存命中率

特性：
  - 单例模式：全局唯一日志管理器
  - 配置热重载：支持运行时动态刷新
  - 多格式支持：JSON 和文本格式
  - 异步日志：队列缓冲，非阻塞写入
  - 敏感脱敏：自动识别并脱敏敏感字段
  - 链路追踪：完整的 request_id/trace_id/span_id
  - 启动缓存：缓存初始化前的日志
  - 日志轮转：按大小或按时间
  - 自动清理：按保留天数清理过期日志
  - 日志归档：自动压缩归档
  - 懒加载：避免循环导入

使用示例：
    from datamind.core.logging import get_logger, log_audit, log_access, log_performance, log_manager
    from datamind.config import get_logging_config
    from datamind.core.domain.enums import AuditAction, PerformanceOperation

    # 初始化日志系统
    config = get_logging_config()
    log_manager.initialize(config)

    # 业务日志
    logger = get_logger(__name__)
    logger.info("模型加载成功: %s", model_id)

    # 审计日志
    log_audit(
        action=AuditAction.MODEL_ACTIVATE.value,
        user_id="admin",
        ip_address="192.168.1.100",
        resource_type="model",
        resource_id=model_id
    )

    # 访问日志
    log_access(
        request_id="req-12345",
        user_id="user_001",
        endpoint="/v1/predict",
        method="POST",
        status_code=200,
        duration_ms=45.2
    )

    # 性能日志
    log_performance(
        operation=PerformanceOperation.MODEL_INFERENCE,
        duration_ms=12.5,
        model_id=model_id
    )
"""

import importlib
import logging
import sys
from typing import TYPE_CHECKING, Dict, Any, Optional

from datamind.core.logging.manager import log_manager

if TYPE_CHECKING:
    from datamind.core.logging.manager import LogManager
    from datamind.core.logging.formatters import TimezoneFormatter, CustomJsonFormatter, CustomTextFormatter
    from datamind.core.logging.filters import RequestIdFilter, SensitiveDataFilter, SamplingFilter
    from datamind.core.logging.handlers import TimeRotatingFileHandlerWithTimezone, AsyncLogHandler
    from datamind.core.logging.cleanup import CleanupManager
    from datamind.core.domain.enums import PerformanceOperation


# ==================== 全局 fallback logger ====================

_fallback_logger = logging.getLogger("datamind.fallback")
_fallback_logger.propagate = False
_fallback_logger.setLevel(logging.WARNING)

if not _fallback_logger.handlers:
    _console_handler = logging.StreamHandler(sys.stderr)
    _console_handler.setLevel(logging.WARNING)
    _fallback_logger.addHandler(_console_handler)


# ==================== 业务日志 ====================

def get_logger(name: str = None) -> logging.Logger:
    """获取日志记录器

    使用场景：
        - 业务逻辑日志（模型加载成功/失败）
        - 调试信息（变量值、状态检查）
        - 一般性信息（服务启动、配置加载）
        - 错误追踪（异常详情、堆栈信息）

    示例：
        logger = get_logger(__name__)
        logger.info("模型加载成功: %s", model_id)
        logger.debug("特征值: %s", features)
        logger.error("推理失败: %s", str(e), exc_info=True)

    参数:
        name: 日志记录器名称（可选）

    返回:
        日志记录器实例
    """
    try:
        logger = log_manager.logger
        if logger is not None:
            if name is None:
                return logger
            return logger.getChild(name)
    except Exception as e:
        _fallback_logger.debug("日志管理器初始化失败，降级使用标准日志记录器: %s", e)

    return logging.getLogger(name or __name__)


# ==================== 审计日志 ====================

def log_audit(
    action: str,
    user_id: str,
    ip_address: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    request_id: Optional[str] = None
) -> None:
    """记录审计日志

    使用场景：
        - 模型注册、激活、停用、归档
        - 模型版本切换、生产环境提升
        - A/B测试创建、启动、暂停、完成
        - 用户登录、登出、权限变更
        - API密钥创建、吊销
        - 系统配置变更
        - 数据导出、导入

    示例：
        from datamind.core.domain.enums import AuditAction

        log_audit(
            action=AuditAction.MODEL_ACTIVATE.value,
            user_id="admin",
            ip_address="192.168.1.100",
            resource_type="model",
            resource_id=model_id,
            details={"before_status": "inactive", "after_status": "active"}
        )

    参数:
        action: 操作类型（AuditAction 枚举值）
        user_id: 操作用户ID
        ip_address: 操作IP地址
        resource_type: 资源类型（model/ab_test/user/api_key/config等）
        resource_id: 资源ID
        resource_name: 资源名称
        details: 操作详情
        reason: 操作原因（失败时）
        request_id: 请求ID
    """
    logger = get_logger("audit")
    extra = {
        "action": action,
        "user_id": user_id,
        "ip_address": ip_address,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "resource_name": resource_name,
        "details": details,
        "reason": reason,
        "request_id": request_id,
    }
    extra = {k: v for k, v in extra.items() if v is not None}

    if reason:
        logger.warning(f"审计失败: {action}", extra=extra)
    else:
        logger.info(f"审计成功: {action}", extra=extra)


# ==================== 访问日志 ====================

def log_access(
    request_id: str,
    user_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    duration_ms: float,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    **kwargs
) -> None:
    """记录API访问日志

    使用场景：
        - 所有HTTP请求（入口/出口）
        - API调用统计
        - 流量分析
        - 安全审计（异常请求模式）

    示例：
        log_access(
            request_id="req-12345",
            user_id="api_user_001",
            endpoint="/v1/predict/model_001",
            method="POST",
            status_code=200,
            duration_ms=45.2,
            ip_address="10.0.0.1",
            user_agent="python-requests/2.28.0"
        )

    参数:
        request_id: 请求ID
        user_id: 用户ID
        endpoint: 访问端点
        method: HTTP方法
        status_code: 状态码
        duration_ms: 耗时（毫秒）
        ip_address: IP地址（可选）
        user_agent: User-Agent（可选）
        **kwargs: 其他信息（如 body_size、query_params等）
    """
    logger = get_logger("access")
    extra = {
        "request_id": request_id,
        "user_id": user_id,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "ip_address": ip_address,
        "user_agent": user_agent,
        **kwargs
    }
    extra = {k: v for k, v in extra.items() if v is not None}

    if status_code >= 400:
        logger.warning(f"访问失败: {method} {endpoint} -> {status_code}", extra=extra)
    else:
        logger.info(f"访问成功: {method} {endpoint} -> {status_code}", extra=extra)


# ==================== 性能日志 ====================

def log_performance(
    operation: "PerformanceOperation",
    duration_ms: float,
    model_id: Optional[str] = None,
    request_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """记录性能日志

    使用场景：
        - 模型推理耗时
        - 数据库查询耗时
        - 外部API调用耗时
        - 缓存命中/未命中统计
        - 批量处理耗时

    示例：
        from datamind.core.domain.enums import PerformanceOperation

        log_performance(
            operation=PerformanceOperation.MODEL_INFERENCE,
            duration_ms=12.5,
            model_id=model_id,
            extra={"batch_size": 1, "framework": "sklearn"}
        )

        log_performance(
            operation=PerformanceOperation.DB_QUERY,
            duration_ms=5.2,
            extra={"query_type": "select", "table": "model_metadata"}
        )

    参数:
        operation: 操作类型（PerformanceOperation 枚举值）
        duration_ms: 耗时（毫秒）
        model_id: 模型ID（可选）
        request_id: 请求ID（可选）
        extra: 额外信息（可选）
    """
    logger = get_logger("performance")
    log_extra = {
        "operation": operation.value,
        "duration_ms": round(duration_ms, 2),
        "model_id": model_id,
        "request_id": request_id,
    }
    if extra:
        log_extra.update(extra)
    log_extra = {k: v for k, v in log_extra.items() if v is not None}

    logger.info(f"性能指标: {operation.value} 耗时 {duration_ms:.2f}ms", extra=log_extra)


# ==================== 懒加载缓存 ====================

_LAZY_CACHE = {}


def _lazy_import(module_name: str, attr_name: str = None):
    """安全的懒导入，带缓存"""
    cache_key = f"{module_name}:{attr_name}" if attr_name else module_name
    if cache_key in _LAZY_CACHE:
        return _LAZY_CACHE[cache_key]

    try:
        module = importlib.import_module(module_name)
        if attr_name:
            result = getattr(module, attr_name)
        else:
            result = module
        _LAZY_CACHE[cache_key] = result
        return result
    except ImportError as e:
        _fallback_logger.debug("懒导入失败: %s, 错误: %s", cache_key, e)
        raise


def __getattr__(name: str):
    if name == "LogManager":
        from datamind.core.logging.manager import LogManager
        return LogManager

    elif name in {"TimezoneFormatter", "CustomJsonFormatter", "CustomTextFormatter"}:
        return _lazy_import("datamind.core.logging.formatters", name)

    elif name in {"RequestIdFilter", "SensitiveDataFilter", "SamplingFilter"}:
        return _lazy_import("datamind.core.logging.filters", name)

    elif name in {"TimeRotatingFileHandlerWithTimezone", "AsyncLogHandler"}:
        return _lazy_import("datamind.core.logging.handlers", name)

    elif name == "CleanupManager":
        return _lazy_import("datamind.core.logging.cleanup", "CleanupManager")

    elif name == "context":
        return _lazy_import("datamind.core.logging.context")

    elif name in {
        "get_request_id", "set_request_id", "clear_request_id", "has_request_id",
        "get_trace_id", "set_trace_id", "clear_trace_id", "has_trace_id",
        "get_span_id", "set_span_id", "clear_span_id", "has_span_id",
        "get_parent_span_id", "set_parent_span_id", "clear_parent_span_id", "has_parent_span_id",
        "ensure_request", "ensure_trace", "ensure_span",
        "with_request_id", "with_span",
        "RequestIdContext", "SpanContext", "RequestContext"
    }:
        context_mod = _lazy_import("datamind.core.logging.context")
        return getattr(context_mod, name)

    elif name in {
        "install_bootstrap_logger",
        "flush_bootstrap_logs",
        "get_bootstrap_logger",
        "bootstrap_info",
        "bootstrap_debug",
        "bootstrap_warning",
        "bootstrap_error",
        "bootstrap_critical",
    }:
        return _lazy_import("datamind.core.logging.bootstrap", name)

    raise AttributeError(f"模块 'datamind.core.logging' 没有属性 '{name}'")


__all__ = [
    'LogManager',
    'log_manager',
    'get_logger',
    'log_audit',
    'log_access',
    'log_performance',
    'TimezoneFormatter',
    'CustomJsonFormatter',
    'CustomTextFormatter',
    'RequestIdFilter',
    'SensitiveDataFilter',
    'SamplingFilter',
    'TimeRotatingFileHandlerWithTimezone',
    'AsyncLogHandler',
    'CleanupManager',
    'context',
]