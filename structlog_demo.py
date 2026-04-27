from datamind.config import get_settings
from datamind.logging import setup_logging, get_logger
from datamind.context import context_scope

# 初始化
settings = get_settings()
setup_logging(settings.logging)

# 获取 logger
logger = get_logger(__name__)

# 记录日志（无上下文）
logger.info("服务启动")

logger.info(
    "用户登录成功",
    user_id=12345,
    action="login"
)

logger.error(
    "数据库连接失败",
    error="Connection refused",
    retry_count=3
)

logger.debug("这是调试日志")
logger.warning("这是警告日志")
logger.critical("这是关键日志")
logger.error("这是失败日志")

# 上下文作用域（统一语义）
with context_scope(trace_id="trace-123", request_id="req-456", user="admin", ip="127.0.0.1"):
    logger.debug("自动注入上下文")