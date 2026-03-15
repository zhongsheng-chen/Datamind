import logging
import time
from core.logging import log_manager
from config.logging_config import LoggingConfig
from core.logging.bootstrap import (
    install_bootstrap_logger,
    bootstrap_info,
    set_debug_mode,
    debug_print_cache
)

# 启用调试模式（开发环境使用）
set_debug_mode(True)

install_bootstrap_logger()

# 设置默认的 request_id 为 '-'
old_factory = logging.getLogRecordFactory()


def record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    if not hasattr(record, 'request_id'):
        record.request_id = '-'
    return record


logging.setLogRecordFactory(record_factory)


def main():
    bootstrap_info("开始初始化应用...")

    # 查看当前缓存状态
    debug_print_cache()

    # 加载配置
    config = LoggingConfig.load()

    # 再次查看缓存状态
    debug_print_cache()

    # 初始化日志管理器
    file_handlers_ready = log_manager.initialize(config)

    if file_handlers_ready:
        print("\n✅ 文件处理器已就绪，启动日志已刷新")
    else:
        print("\n⚠️ 文件处理器未创建")

    # 获取应用日志器
    app_logger = log_manager.app_logger
    access_logger = log_manager.access_logger
    audit_logger = log_manager.audit_logger
    performance_logger = log_manager.performance_logger

    # 模拟普通程序日志
    app_logger.info("程序启动")
    app_logger.warning("程序警告示例")

    # 模拟处理请求日志
    for req_id in ["req-12345", "req-67890"]:
        log_manager.set_request_id(req_id)
        app_logger.info(f"处理请求 {req_id} - 应用日志")
        access_logger.info(f"请求 {req_id} 已访问")
        audit_logger.info(f"请求 {req_id} 审计事件记录")
        performance_logger.info(f"请求 {req_id} 性能数据记录")
        time.sleep(0.1)  # 模拟处理延迟

    # 清除 request_id
    log_manager.set_request_id("-")
    app_logger.info("所有请求处理完成")

    print("测试完成，日志应分别写入应用、access、audit、performance 文件")


if __name__ == "__main__":
    main()
