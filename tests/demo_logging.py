#!/usr/bin/env python
# -*- coding: utf-8 -*-
# tests/demo_logging.py

"""日志组件使用示例

演示 Datamind 日志系统的所有核心功能：
  - 基础日志记录
  - 请求上下文和链路追踪
  - 结构化日志
  - 敏感数据脱敏
  - 异步日志
  - 上下文变量传递
  - 配置热重载
  - 统计信息查看
"""

import sys
import time
import logging
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datamind.core.logging import log_manager, get_logger, context
from datamind.core.logging.bootstrap import (
    install_bootstrap_logger,
    bootstrap_info,
    bootstrap_debug,
    bootstrap_warning,
    bootstrap_error,
    is_initialized,
    is_flushed
)
from datamind.config import get_settings

_logging_initialized = False


def init_logging():
    """初始化日志系统"""
    global _logging_initialized
    if _logging_initialized:
        return

    print("\n" + "=" * 60)
    print("初始化日志系统")
    print("=" * 60)

    # 获取应用配置
    settings = get_settings()
    app_config = settings.app

    print(f"应用名称: {app_config.name}")
    print(f"应用版本: {app_config.version}")
    print(f"运行环境: {app_config.environment}")
    print(f"日志级别: {logging.getLevelName(settings.logging.level)}")
    print(f"日志格式: {settings.logging.format.value}")

    # 安装启动日志缓存
    result = install_bootstrap_logger(level=logging.DEBUG)
    print(f"install_bootstrap_logger: {result}")

    # 记录启动日志（这些日志会被缓存）
    bootstrap_info(f"应用 {app_config.name} 正在启动...")
    bootstrap_info(f"应用版本: {app_config.version}")
    bootstrap_info(f"运行环境: {app_config.environment}")
    bootstrap_info("加载配置文件中...")
    bootstrap_debug("调试信息也会被缓存")

    # 模拟启动过程中的警告
    bootstrap_warning("配置文件中的某些可选参数缺失，使用默认值")

    # 模拟启动过程中的错误
    bootstrap_error("配置管理器初始化错误")

    print(f"bootstrap 已初始化: {is_initialized()}")

    # 初始化正式日志系统
    log_manager.initialize()

    print(f"bootstrap 已刷新: {is_flushed()}")
    if log_manager.config:
        print(
            f"日志配置: level={log_manager.config.level}, format={log_manager.config.format}, log_dir={log_manager.config.log_dir}")
    else:
        print("警告: 日志配置未正确初始化")

    # 记录初始化完成的日志
    logger = get_logger(__name__)
    logger.info("日志系统初始化完成", extra={
        "app_name": app_config.name,
        "app_version": app_config.version,
        "app_environment": app_config.environment.value if hasattr(app_config.environment, 'value') else str(
            app_config.environment),
    })

    _logging_initialized = True


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def demo_basic_logging():
    """基础日志记录示例"""
    print_section("基础日志记录示例")

    logger = get_logger(__name__)

    logger.debug("这是 DEBUG 级别日志")
    logger.info("这是 INFO 级别日志")
    logger.warning("这是 WARNING 级别日志")
    logger.error("这是 ERROR 级别日志")

    try:
        raise ValueError("这是一个测试异常")
    except ValueError as e:
        logger.exception("捕获到异常: %s", e)


def demo_request_context():
    """请求上下文示例"""
    print_section("请求上下文示例")

    logger = get_logger(__name__)

    # 设置请求ID和追踪ID
    context.set_request_id("req-001")
    context.set_trace_id("trace-001")
    logger.info("请求1: 处理用户登录")

    # 使用上下文管理器临时覆盖请求ID
    with context.RequestIdContext("req-002"):
        logger.info("请求2: 创建订单开始")

        # 使用 Span 追踪嵌套调用
        with context.SpanContext("validate_order"):
            logger.info("验证订单信息...")

        with context.SpanContext("process_payment"):
            logger.info("处理支付中...")
            logger.info("支付完成")

        logger.info("请求2: 订单创建完成")

    # 恢复原请求ID
    logger.info("请求1: 继续处理其他业务")

    # 使用装饰器自动管理请求ID和Span
    @context.with_request_id("req-003")
    @context.with_span("api_handler")
    def handle_api_request():
        logger.info("处理 API 请求")
        return "success"

    handle_api_request()


def demo_structured_logging():
    """结构化日志示例"""
    print_section("结构化日志示例")

    logger = get_logger(__name__)
    settings = get_settings()

    # 业务操作日志
    logger.info("用户操作", extra={
        "app_name": settings.app.name,
        "app_version": settings.app.version,
        "user_id": "user-12345",
        "action": "login",
        "ip": "192.168.1.100",
        "duration_ms": 123.45,
        "user_agent": "Mozilla/5.0"
    })

    # 性能告警日志
    logger.warning("慢查询告警", extra={
        "app_name": settings.app.name,
        "environment": settings.app.environment.value if hasattr(settings.app.environment, 'value') else str(
            settings.app.environment),
        "query": "SELECT * FROM users WHERE ...",
        "duration_ms": 5200,
        "threshold_ms": 1000,
        "database": "postgres"
    })

    # 业务错误日志
    logger.error("业务错误", extra={
        "app_name": settings.app.name,
        "app_version": settings.app.version,
        "error_code": "E10001",
        "error_msg": "余额不足",
        "user_id": "user-12345",
        "amount": 100.00
    })


def demo_sensitive_data_masking():
    """敏感数据脱敏示例"""
    print_section("敏感数据脱敏示例")

    logger = get_logger(__name__)

    # 敏感字段会自动脱敏
    logger.info("用户登录", extra={
        "user_id": "user-12345",
        "password": "my_secret_password_123",
        "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "credit_card": "1234-5678-9012-3456",
        "id_number": "11010119900307663X"
    })

    # 日志消息中的敏感信息也会被脱敏
    logger.info("登录信息: password=%s, token=%s", "secret123", "abc123token456")

    # 嵌套结构中的敏感字段也会被脱敏
    logger.info("用户注册", extra={
        "user": {
            "name": "张三",
            "password": "user_password_123",
            "email": "zhangsan@example.com"
        },
        "api_key": "sk-1234567890abcdef"
    })


def demo_async_logging():
    """异步日志示例"""
    print_section("异步日志示例")

    # 检查是否启用异步模式
    async_enabled = log_manager.config and log_manager.config.use_async

    if not async_enabled:
        print("当前未启用异步模式")
        print("可以通过设置环境变量 DATAMIND_LOG_USE_ASYNC=true 启用")
        return

    handler = log_manager.logger.handlers[0] if log_manager.logger else None

    if handler and hasattr(handler, 'get_stats'):
        stats = handler.get_stats()
        print(f"异步模式: {stats.get('is_running', False)}")
        print(f"队列大小: {stats.get('queue_size', 0)}/{stats.get('max_queue_size', 'N/A')}")
        print(f"队列使用率: {stats.get('queue_usage_percent', 0):.1f}%")

        logger = get_logger(__name__)

        print("\n开始记录 1000 条日志...")
        start = time.time()

        for i in range(1000):
            logger.info(f"异步日志测试 #{i}", extra={"index": i})

        elapsed = time.time() - start
        print(f"记录完成，耗时: {elapsed:.3f} 秒")

        # 等待队列处理完成
        print("等待队列处理...")

        # 刷新处理器，确保所有日志被处理
        if hasattr(handler, 'flush'):
            handler.flush()

        # 额外等待统计更新
        time.sleep(10)

        stats = handler.get_stats()
        print(f"处理完成，已处理: {stats.get('processed_count', 0)}")
        print(f"丢弃: {stats.get('dropped_count', 0)}")

        # 显示队列状态
        if stats.get('queue_size', 0) > 0:
            print(f"队列中还有 {stats.get('queue_size', 0)} 条日志未处理")


def demo_context_variables():
    """上下文变量传递示例"""
    print_section("上下文变量传递示例")

    import asyncio
    import threading

    logger = get_logger(__name__)

    # 设置主线程的请求上下文
    context.set_request_id("req-multi-001")
    context.set_trace_id("trace-multi-001")

    logger.info("主线程开始")

    # 子线程自动继承上下文
    def thread_worker():
        logger.info("子线程执行中")
        logger.info(f"子线程中的 request_id: {context.get_request_id()}")
        logger.info(f"子线程中的 trace_id: {context.get_trace_id()}")

    print("\n启动子线程（自动继承上下文）...")
    thread = context.run_in_thread(thread_worker)
    thread.start()
    thread.join()

    # 异步任务也支持上下文传递
    async def async_worker():
        logger.info("异步任务执行中")
        logger.info(f"异步任务中的 request_id: {context.get_request_id()}")
        logger.info(f"异步任务中的 trace_id: {context.get_trace_id()}")
        return "done"

    print("\n运行异步任务（自动继承上下文）...")
    try:
        asyncio.run(async_worker())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(async_worker())
        loop.close()

    logger.info("主线程结束")


def demo_reload_config():
    """配置热重载示例 - 演示动态修改日志配置"""
    print_section("配置热重载示例")

    logger = get_logger(__name__)

    # 场景1: 动态调整日志级别
    print("场景: 动态调整日志级别")
    print("-" * 40)

    # 保存原始级别
    original_level = log_manager.config.level if log_manager.config else logging.INFO
    original_level_name = logging.getLevelName(original_level)

    # 如果当前是 DEBUG，先改为 INFO 来演示效果
    if original_level == logging.DEBUG:
        os.environ['DATAMIND_LOG_LEVEL'] = 'INFO'
        from datamind.config import reload_logging_config
        new_config = reload_logging_config()
        log_manager.reload_config(new_config)
        print(f"临时将日志级别从 DEBUG 改为 INFO")

    current_level = log_manager.config.level if log_manager.config else logging.INFO
    current_level_name = logging.getLevelName(current_level)
    print(f"当前日志级别: {current_level_name}")

    print("\n使用当前配置记录日志:")
    logger.debug("这条 DEBUG 日志不会输出（级别限制）")
    logger.info("这条 INFO 日志会输出")
    logger.warning("这条 WARNING 日志会输出")

    # 修改配置为 DEBUG 级别
    print("\n切换到 DEBUG 级别...")
    os.environ['DATAMIND_LOG_LEVEL'] = 'DEBUG'
    from datamind.config import reload_logging_config
    new_config = reload_logging_config()
    log_manager.reload_config(new_config)

    print(f"新日志级别: {logging.getLevelName(new_config.level)}")
    print("\n使用新配置记录日志:")
    logger.debug("这条 DEBUG 日志现在应该输出")
    logger.info("这条 INFO 日志仍然输出")
    logger.warning("这条 WARNING 日志仍然输出")

    # 恢复原始级别
    os.environ['DATAMIND_LOG_LEVEL'] = original_level_name
    new_config = reload_logging_config()
    log_manager.reload_config(new_config)
    print(f"\n已恢复原始日志级别: {original_level_name}")

    # 场景2: 动态调整日志格式
    print("\n场景: 动态调整日志格式")
    print("-" * 40)

    original_format = log_manager.config.format.value if log_manager.config else 'text'
    print(f"当前日志格式: {original_format}")

    # 切换到 JSON 格式
    os.environ['DATAMIND_LOG_FORMAT'] = 'json' if original_format == 'text' else 'text'
    print(f"修改环境变量 DATAMIND_LOG_FORMAT: {original_format} -> {os.environ['DATAMIND_LOG_FORMAT']}")
    print("执行热重载...")

    new_config = reload_logging_config()
    log_manager.reload_config(new_config)

    print(f"新日志格式: {log_manager.config.format.value}")
    print("\n使用新格式记录日志（注意输出格式变化）:")
    logger.info("这是一条测试日志，展示格式变化")

    # 恢复原始格式
    os.environ['DATAMIND_LOG_FORMAT'] = original_format
    new_config = reload_logging_config()
    log_manager.reload_config(new_config)
    print(f"\n已恢复原始格式: {log_manager.config.format.value}")

    # 场景3: 热重载不影响已有日志记录器
    print("\n场景: 热重载不影响已有日志记录器")
    print("-" * 40)

    logger1 = get_logger("module1")
    logger2 = get_logger("module2")

    print("重载前记录日志:")
    logger1.info("模块1的日志")
    logger2.info("模块2的日志")

    print("\n执行热重载...")
    reload_logging_config()

    print("重载后记录日志:")
    logger1.info("模块1的日志（重载后）")
    logger2.info("模块2的日志（重载后）")

    print("\n热重载测试完成")


def demo_get_stats():
    """统计信息示例"""
    print_section("统计信息示例")

    # 采样过滤器统计
    if hasattr(log_manager, 'sampling_filter') and log_manager.sampling_filter:
        stats = log_manager.sampling_filter.get_stats()
        print("采样过滤器统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    # 处理器统计 - 遍历所有处理器
    if log_manager.logger and log_manager.logger.handlers:
        for i, handler in enumerate(log_manager.logger.handlers):
            if hasattr(handler, 'get_stats'):
                stats = handler.get_stats()
                handler_type = handler.__class__.__name__
                print(f"\n处理器统计 ({handler_type}):")
                for key, value in stats.items():
                    print(f"  {key}: {value}")

    # 清理管理器统计
    if log_manager.cleanup_manager:
        stats = log_manager.cleanup_manager.get_stats()
        print("\n清理管理器统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        archive_size = log_manager.cleanup_manager.get_archive_size()
        if archive_size > 0:
            size_mb = archive_size / (1024 * 1024)
            print(f"  归档目录大小: {size_mb:.2f} MB")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Datamind 日志组件演示程序")
    print("=" * 60)
    print(f"Python 版本: {sys.version}")
    print(f"操作系统: {sys.platform}")

    # 初始化日志系统
    init_logging()

    # 运行所有演示
    demo_basic_logging()
    demo_request_context()
    demo_structured_logging()
    demo_sensitive_data_masking()
    demo_async_logging()
    demo_context_variables()
    demo_reload_config()
    demo_get_stats()

    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)

    # 清理资源
    log_manager.cleanup()


if __name__ == "__main__":
    main()