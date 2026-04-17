# datamind/storage/base.py

"""存储后端抽象基类

定义统一的存储接口，支持多种存储后端实现。

核心功能：
  - put_object: 存储数据到指定key
  - get_object: 从指定key读取数据
  - delete_object: 删除指定key的数据
  - object_exists: 检查指定key是否存在
  - list_objects: 列出指定前缀下的所有key

特性：
  - 统一抽象：屏蔽不同存储后端的实现差异
  - 字节流操作：统一使用 bytes 类型进行数据传输
  - 扩展友好：新增存储后端只需实现此接口
  - 命名约束：使用 *_object 命名避免业务语义误导
"""

from abc import ABC, abstractmethod


class BaseStorageBackend(ABC):
    """存储后端抽象类（纯IO层，不理解业务）"""

    @abstractmethod
    def put_object(self, key: str, data: bytes) -> None:
        """存储对象

        参数：
            key: 存储键
            data: 二进制数据
        """
        pass

    @abstractmethod
    def get_object(self, key: str) -> bytes:
        """读取对象

        参数：
            key: 存储键

        返回：
            二进制数据
        """
        pass

    @abstractmethod
    def delete_object(self, key: str) -> None:
        """删除对象

        参数：
            key: 存储键
        """
        pass

    @abstractmethod
    def object_exists(self, key: str) -> bool:
        """检查对象是否存在

        参数：
            key: 存储键

        返回：
            存在返回 True，否则返回 False
        """
        pass

    @abstractmethod
    def list_objects(self, prefix: str) -> list[str]:
        """列出指定前缀下的所有key

        参数：
            prefix: 键前缀

        返回：
            匹配前缀的完整key列表
        """
        pass