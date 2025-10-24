import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from src.config_parser import config

def setup_logger():
    """
    初始化 logger，支持多脚本和多进程同时写日志
    """
    log_conf = config.get("logging")

    logger_name = log_conf.get("name", "Datamind")
    log_file = Path(log_conf.get("file", "logs/Datamind.log"))
    log_level = getattr(logging, log_conf.get("level", "INFO").upper(), logging.INFO)
    max_bytes = log_conf.get("max_bytes", 10*1024*1024)
    backup_count = log_conf.get("backup_count", 5)
    use_concurrent = log_conf.get("use_concurrent", False)

    # 处理日志文件路径
    root = Path(__file__).resolve().parent.parent
    if not log_file.is_absolute():
        log_file = root / log_file
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # 获取 logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(log_level)

    # 避免重复添加 handler
    if logger.hasHandlers():
        return logger

    # 日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(module)s - %(filename)s - %(message)s"
    )

    # 内部函数封装添加 handler
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
            fh = ConcurrentRotatingFileHandler(
                log_file, maxBytes=max_bytes, backupCount=backup_count
            )
        except ImportError:
            raise ImportError("use_concurrent=True requires 'concurrent-log-handler' package")
    else:
        fh = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
    add_handler(fh)

    return logger
