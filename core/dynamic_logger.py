# core/dynamic_logger.py
class DynamicLogger:
    """支持动态切换日志格式的日志器"""

    def __init__(self, config: LoggingConfig):
        self.config = config
        self.current_format = config.format
        self.handlers = {}

    def switch_format(self, new_format: LogFormat):
        """动态切换日志格式"""
        if new_format == self.current_format:
            return

        # 移除旧格式的处理器
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 添加新格式的处理器
        if new_format == LogFormat.TEXT:
            self._add_text_handlers()
        elif new_format == LogFormat.JSON:
            self._add_json_handlers()
        elif new_format == LogFormat.BOTH:
            self._add_both_handlers()

        self.current_format = new_format
        logging.info(f"日志格式已切换为: {new_format.value}")