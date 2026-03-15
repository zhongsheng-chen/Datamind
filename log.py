# import logging
# from core.logging import log_manager
# from config.logging_config import LoggingConfig
#
#
# def main():
#     config = LoggingConfig.load()
#     log_manager.initialize(config)
#
#     print(f"主日志文件: {config.file}")
#     print(f"日志格式: {config.format}")
#     print(f"控制台输出: {config.console_output}")
#
#     logger = logging.getLogger(__name__)
#     logger.info("Hello", extra={"user_id": 123})
#
#     log_manager.log_access(
#         method="GET",
#         path="/api/users",
#         status=200,
#         duration_ms=45.6
#     )
# if __name__ == "__main__":
#     main()

# # log.py
# import logging
# from core.logging import log_manager
# from config.logging_config import LoggingConfig
#
# # ========== 添加：为所有日志记录添加默认的 request_id 字段 ==========
# old_factory = logging.getLogRecordFactory()
#
# def record_factory(*args, **kwargs):
#     record = old_factory(*args, **kwargs)
#     if not hasattr(record, 'request_id'):
#         record.request_id = '-'
#     return record
#
# logging.setLogRecordFactory(record_factory)
# # ================================================================
#
# def main():
#     config = LoggingConfig.load()
#     log_manager.initialize(config)
#
#     print(f"主日志文件: {config.file}")
#     print(f"日志格式: {config.format}")
#     print(f"控制台输出: {config.console_output}")
#
#     logger = logging.getLogger(__name__)
#     logger.info("Hello", extra={"user_id": 123})
#
#     log_manager.log_access(
#         method="GET",
#         path="/api/users",
#         status=200,
#         duration_ms=45.6
#     )
#
# if __name__ == "__main__":
#     main()

# log.py

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

# 直接指定 bootstrap logger 名称
# BOOTSTRAP_LOGGER_NAME = "Datamind.bootstrap"

# 安装启动日志缓存，直接传入名称
# install_bootstrap_logger(name=BOOTSTRAP_LOGGER_NAME)
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

    # 加载配置（这些日志会被缓存）
    config = LoggingConfig.load()

    # 再次查看缓存状态
    debug_print_cache()

    # 初始化日志管理器（内部会刷新启动日志，不需要再手动调用）
    file_handlers_ready = log_manager.initialize(config)

    if file_handlers_ready:
        print("\n✅ 文件处理器已就绪，启动日志已在 manager 中刷新")
    else:
        print("\n⚠️ 警告: 文件处理器未创建")

    # 这是主程序，不是请求处理，所以 request_id 会是 '-'
    logger = logging.getLogger(__name__)
    logger.info("程序启动")

    # 模拟处理一个请求
    log_manager.set_request_id("req-12345")
    logger.info("处理用户请求")

    # 模拟另一个请求
    log_manager.set_request_id("req-67890")
    logger.info("处理另一个请求")

    # 请求结束，清除
    log_manager.set_request_id("-")
    logger.info("所有请求处理完成")


if __name__ == "__main__":
    main()

