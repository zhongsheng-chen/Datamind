import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import os

# 全局唯一 logger
_logger = None

def get_logger():
    """
    获取全局 logger，支持多脚本和多进程写同一个日志文件
    """
    global _logger
    if _logger:
        return _logger

    # 延迟导入 config 避免循环导入
    try:
        from src.config_parser import config
        log_conf = config.get("logging")
    except Exception:
        log_conf = {}

    # 环境变量优先
    logger_name = os.getenv("DATAMIND_LOG_NAME", log_conf.get("name", "DatamindLogger"))
    log_file = Path(os.getenv("DATAMIND_LOG_FILE", log_conf.get("file", "logs/Datamind.log")))
    log_level = getattr(logging, os.getenv("DATAMIND_LOG_LEVEL", log_conf.get("level", "INFO")).upper(), logging.INFO)
    max_bytes = int(os.getenv("DATAMIND_LOG_MAX_BYTES", log_conf.get("max_bytes", 10 * 1024 * 1024)))
    backup_count = int(os.getenv("DATAMIND_LOG_BACKUP_COUNT", log_conf.get("backup_count", 5)))
    use_concurrent = str(os.getenv("DATAMIND_LOG_USE_CONCURRENT", log_conf.get("use_concurrent", False))).lower() in ("1", "true", "yes")

    # 确保日志目录存在
    root = Path(__file__).resolve().parent.parent
    if not log_file.is_absolute():
        log_file = root / log_file
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # 获取 logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # 如果 handler 已存在，直接返回全局 logger
    if _logger:
        return _logger

    # 日志格式
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(module)s - %(filename)s - %(message)s")

    # 添加 handler 的封装函数
    def add_handler(handler):
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # 控制台 handler
    add_handler(logging.StreamHandler())

    # 文件 handler
    if use_concurrent:
        try:
            from concurrent_log_handler import ConcurrentRotatingFileHandler
            fh = ConcurrentRotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        except ImportError:
            raise ImportError("use_concurrent=True requires 'concurrent-log-handler' package")
    else:
        fh = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    add_handler(fh)

    # 保存全局 logger
    _logger = logger
    return _logger
