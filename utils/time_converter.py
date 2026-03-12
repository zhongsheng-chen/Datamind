# utils/time_converter.py
from datetime import datetime
import time
import pytz


class TimeFormatConverter:
    """时间格式转换工具"""

    @staticmethod
    def text_to_json(text_time: str) -> str:
        """
        将文本时间转换为ISO8601
        输入: "2024-01-15 10:30:25.123"
        输出: "2024-01-15T10:30:25.123+08:00"
        """
        # 解析文本时间
        dt = datetime.strptime(text_time, "%Y-%m-%d %H:%M:%S.%f")

        # 添加时区（假设是东八区）
        tz = pytz.timezone('Asia/Shanghai')
        dt_tz = tz.localize(dt)

        # 转换为ISO8601
        return dt_tz.isoformat()

    @staticmethod
    def json_to_text(iso_time: str) -> str:
        """
        将ISO8601转换为文本时间
        输入: "2024-01-15T10:30:25.123+08:00"
        输出: "2024-01-15 10:30:25.123"
        """
        # 解析ISO8601
        dt = datetime.fromisoformat(iso_time)

        # 转换为本地时间（去掉时区信息）
        dt_local = dt.astimezone().replace(tzinfo=None)

        # 格式化为文本
        return dt_local.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # 保留毫秒

    @staticmethod
    def epoch_to_iso(timestamp_ms: int, tz_str: str = "+08:00") -> str:
        """
        将时间戳转换为ISO8601
        输入: 1644825025123
        输出: "2024-01-15T10:30:25.123+08:00"
        """
        dt = datetime.fromtimestamp(timestamp_ms / 1000)
        tz = pytz.timezone('Asia/Shanghai')
        dt_tz = tz.localize(dt)
        return dt_tz.isoformat()