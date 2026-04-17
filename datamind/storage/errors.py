# datamind/storage/errors.py

"""存储异常定义

定义存储层的标准异常类型。

特性：
  - 语义清晰：区分不同类型的存储错误
  - 可恢复性：调用方可根据异常类型决定重试策略
"""


class StorageBackendError(Exception):
    """存储后端基础异常"""
    pass


class StorageKeyError(StorageBackendError):
    """存储键错误（如路径遍历攻击）"""
    pass


class StorageNotFoundError(StorageBackendError):
    """对象不存在异常"""
    pass


class StoragePermissionError(StorageBackendError):
    """权限错误异常"""
    pass


class StorageConnectionError(StorageBackendError):
    """连接错误异常"""
    pass