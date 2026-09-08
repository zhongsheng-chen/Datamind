"""审计失败策略

核心功能：
  - AuditFailureMode: 定义审计失败是否影响业务操作
"""

from enum import Enum


class AuditFailureMode(str, Enum):
    """审计失败处理模式"""

    OPEN = "open"
    CLOSED = "closed"

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value
