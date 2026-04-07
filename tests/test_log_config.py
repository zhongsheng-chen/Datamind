# # demo_basic.py
# """基础日志使用示例"""
#
# import sys
# import os
# from pathlib import Path
#
# # 添加项目根目录到路径
# sys.path.insert(0, str(Path(__file__).parent))
#
# from datamind.config import get_logging_config, get_settings
# from datamind.core.logging import get_logger, log_manager, context
#
#
# def main():
#     """主函数"""
#     # 1. 获取日志配置
#     config = get_logging_config()
#     print(f"日志配置摘要: {config.to_summary_dict()}")
#
#     # 2. 初始化日志系统
#     success = log_manager.initialize(config)
#     if not success:
#         print("日志系统初始化失败")
#         return
#
#     # 3. 获取日志记录器
#     logger = get_logger(__name__)
#
#     # 4. 记录日志
#     logger.info("应用启动成功")
#     logger.debug("调试信息（可能不会显示）")
#     logger.warning("这是一个警告")
#     logger.error("这是一个错误")
#
#     # 5. 设置请求ID
#     context.set_request_id("req-20240409-001")
#     logger.info("带请求ID的日志")
#
#     # 6. 使用上下文管理器
#     with context.RequestIdContext("req-temp-001"):
#         logger.info("临时请求ID上下文中的日志")
#
#     logger.info("恢复原请求ID的日志")
#
#     # 7. 使用 Span 追踪
#     with context.SpanContext("user_login"):
#         logger.info("用户登录处理中...")
#
#         with context.SpanContext("password_verify"):
#             logger.info("验证密码")
#
#         with context.SpanContext("token_generate"):
#             logger.info("生成令牌")
#
#     # 8. 记录带额外字段的日志
#     logger.info("用户操作", extra={
#         "user_id": "user-12345",
#         "action": "login",
#         "ip": "192.168.1.100"
#     })
#
#     # 9. 记录异常
#     try:
#         raise ValueError("这是一个测试异常")
#     except Exception as e:
#         logger.exception("捕获到异常: %s", e)
#
#     print("日志记录完成，请查看 logs/ 目录")
#
#
# if __name__ == "__main__":
#     main()

# test_log_config.py
import os
from dotenv import load_dotenv

# 加载 .env
load_dotenv()

print("=" * 60)
print("1. 环境变量检查")
print("=" * 60)
for key, value in os.environ.items():
    if key.startswith("DATAMIND_LOG"):
        print(f"  {key} = {value}")

print("\n" + "=" * 60)
print("2. LoggingConfig.from_env() 调试")
print("=" * 60)

from datamind.config.logging_config import LoggingConfig

# 手动模拟 from_env 过程
prefix = "DATAMIND_LOG_"
fields = LoggingConfig.model_fields

print("字段映射检查:")
for field_name, field_info in fields.items():
    alias = field_info.alias
    if alias:
        env_name = f"{prefix}{alias}"
    else:
        env_name = f"{prefix}{field_name.upper()}"
    env_value = os.environ.get(env_name)
    print(f"  {field_name} -> alias={alias} -> env={env_name} -> value={env_value}")

print("\n" + "=" * 60)
print("3. LoggingConfig.from_env() 测试")
print("=" * 60)

config = LoggingConfig.from_env()
print(f"  log_dir: {config.log_dir}")
print(f"  log_file: {config.log_file}")
print(f"  format: {config.format}")
print(f"  level: {config.level}")
print(f"  file_name_timestamp: {config.file_name_timestamp}")