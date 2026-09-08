"""审计异常定义

定义审计模块的异常类型。

核心功能：
  - AuditError: 审计模块基础异常
  - AuditValidationError: 审计事件校验失败
  - AuditWriteError: 审计事件写入失败

使用示例：
  from datamind.audit.errors import AuditValidationError

  try:
      do_something()
  except AuditValidationError:
      do_something_else()
"""


class AuditError(Exception):
    """审计模块基础异常"""


class AuditValidationError(AuditError):
    """审计事件校验失败"""

    def __init__(self, message: str = "审计事件校验失败") -> None:
        super().__init__(message)


class AuditWriteError(AuditError):
    """审计事件写入失败"""

    def __init__(self, message: str = "审计事件写入失败") -> None:
        super().__init__(message)
