# datamind/audit/enums.py

"""审计枚举

定义审计事件来源和执行状态枚举。

核心功能：
  - BaseEnum: 字符串枚举基类
  - AuditSource: 审计事件来源
  - AuditStatus: 审计执行状态

使用示例：
  from datamind.audit.enums import (
      AuditSource,
      AuditStatus,
  )

  source = AuditSource.CLI
  status = AuditStatus.SUCCESS

  print(
      str(
          source
      )
  )
  print(
      str(
          status
      )
  )
"""

from enum import Enum


class BaseEnum(str, Enum):
    """字符串枚举基类"""

    def __str__(
            self,
    ) -> str:
        """返回枚举值字符串"""
        return self.value


class AuditSource(BaseEnum):
    """审计事件来源

    属性：
        HTTP: HTTP 请求
        CLI: 命令行操作
        SYSTEM: 系统内部操作
        WORKER: 后台 Worker 操作
        SCHEDULER: 调度器操作
    """

    HTTP = "http"
    CLI = "cli"
    SYSTEM = "system"
    WORKER = "worker"
    SCHEDULER = "scheduler"


class AuditStatus(BaseEnum):
    """审计执行状态

    属性：
        SUCCESS: 操作成功
        FAILED: 操作失败
    """

    SUCCESS = "success"
    FAILED = "failed"


__all__ = [
    "BaseEnum",
    "AuditSource",
    "AuditStatus",
]