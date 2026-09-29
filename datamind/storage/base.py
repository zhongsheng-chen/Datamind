"""存储后端抽象基类.

定义统一的存储接口，支持多种存储后端实现。

核心功能：
  - put_object: 将数据存储到指定键
  - get_object: 从指定键读取数据
  - delete_object: 删除指定键的数据
  - object_exists: 检查指定键是否存在
  - list_objects: 列出指定前缀下的所有键

使用示例：
  from datamind.storage.base import BaseStorageBackend

  class CustomStorageBackend(BaseStorageBackend):
      def put_object(
              self,
              key: str,
              data: bytes,
      ) -> None:
          ...
"""

from abc import ABC, abstractmethod


class BaseStorageBackend(ABC):
    """存储后端抽象类.

    仅定义底层 I/O 操作，不包含业务语义。
    """

    @abstractmethod
    def put_object(
            self,
            key: str,
            data: bytes,
    ) -> None:
        """存储对象.

        参数：
            key: 存储键
            data: 二进制数据
        """
        pass

    @abstractmethod
    def get_object(
            self,
            key: str,
    ) -> bytes:
        """读取对象.

        参数：
            key: 存储键

        返回：
            二进制数据
        """
        pass

    @abstractmethod
    def delete_object(
            self,
            key: str,
    ) -> None:
        """删除对象.

        参数：
            key: 存储键
        """
        pass

    @abstractmethod
    def object_exists(
            self,
            key: str,
    ) -> bool:
        """检查对象是否存在.

        参数：
            key: 存储键

        返回：
            存在返回 True，否则返回 False
        """
        pass

    @abstractmethod
    def list_objects(
            self,
            prefix: str,
    ) -> list[str]:
        """列出指定前缀下的所有对象.

        参数：
            prefix: 存储键前缀

        返回：
            匹配前缀的完整存储键列表
        """
        pass
