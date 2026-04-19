from datamind.config import get_settings
from datamind.logging import setup_logging, get_logger, request_context, set_context

# 初始化
settings = get_settings()
setup_logging(settings.logging)

# 设置上下文
# set_context(trace_id="trace-123", request_id="req-456")

# 获取 logger
logger = get_logger(__name__)

# 记录日志
logger.info("服务启动")
logger.info("用户登录成功", user_id=12345, action="login", password="fefett5t5w3434tt35")
logger.error("数据库连接失败", error="Connection refused", retry_count=3)
logger.debug("这是调试日志")
logger.warning("这是警告日志")
logger.critical("这是关键日志")
logger.error("这是失败日志")

with request_context(trace_id="trace-123", request_id="req-456"):
    logger.debug("自动注入")