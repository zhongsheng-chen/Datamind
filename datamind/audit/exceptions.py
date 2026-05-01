# datamind/audit/exceptions.py

"""审计异常定义

定义审计模块的异常类型。

核心功能：
  - AuditError: 审计模块基础异常
  - AuditValidationError: 审计事件校验失败
  - AuditDispatchError: 审计事件分发失败
  - AuditWriteError: 审计事件写入失败

使用示例：
  from datamind.audit.exceptions import AuditValidationError

  try:
      do_something()
  except AuditValidationError:
    do_something_else()
"""


class AuditError(Exception):
    """审计模块基础异常"""
    pass


class AuditValidationError(AuditError):
    """审计事件校验失败"""
    def __init__(self, message: str = "审计事件校验失败"):
        super().__init__(message)


class AuditDispatchError(AuditError):
    """审计事件分发失败"""
    def __init__(self, message: str = "审计事件分发失败"):
        super().__init__(message)


class AuditWriteError(AuditError):
    """审计事件写入失败"""
    def __init__(self, message: str = "审计事件写入失败"):
        super().__init__(message)