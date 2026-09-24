"""存储异常定义.

定义存储层的标准异常类型。

核心功能：
  - StorageBackendError: 存储后端基础异常
  - StorageKeyError: 存储键错误
  - StorageNotFoundError: 存储对象不存在
  - StoragePermissionError: 存储权限错误
  - StorageConnectionError: 存储连接错误

使用示例：
  from datamind.storage.errors import (
      StorageBackendError,
      StorageNotFoundError,
  )

  try:
      data = storage.load_by_key(
          "models/mdl_0123456789abcdef/1.0.0/"
          "artifacts/art_0123456789abcdef/model.pkl"
      )
  except StorageNotFoundError:
      print("存储对象不存在")
  except StorageBackendError as exc:
      print(
          f"存储操作失败: {exc}"
      )
"""


class StorageBackendError(Exception):
    """存储后端基础异常."""

    pass


class StorageKeyError(StorageBackendError):
    """存储键格式非法或存在路径安全风险."""

    pass


class StorageNotFoundError(StorageBackendError):
    """存储对象不存在异常."""

    pass


class StoragePermissionError(StorageBackendError):
    """存储权限错误异常."""

    pass


class StorageConnectionError(StorageBackendError):
    """存储连接错误异常."""

    pass
