# utils/log_converter.py
import json
import re
from datetime import datetime


class LogConverter:
    """日志格式转换工具"""

    @staticmethod
    def text_to_json(text_line: str) -> dict:
        """将文本日志转换为JSON格式"""
        # 解析文本日志格式
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (\w+) - \[(.*?)\] - (.*)'
        match = re.match(pattern, text_line)

        if match:
            return {
                "@timestamp": match.group(1),
                "level": match.group(3),
                "logger": match.group(2),
                "request_id": match.group(4),
                "message": match.group(5)
            }
        return {}

    @staticmethod
    def json_to_text(json_obj: dict) -> str:
        """将JSON日志转换为文本格式"""
        timestamp = json_obj.get("@timestamp", "")
        level = json_obj.get("level", "INFO")
        logger = json_obj.get("logger", "DatamindLogger")
        request_id = json_obj.get("request_id", "-")
        message = json_obj.get("message", "")

        return f"{timestamp} - {logger} - {level} - [{request_id}] - {message}"