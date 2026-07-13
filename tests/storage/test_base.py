# tests/storage/test_base.py

"""存储后端抽象基类测试

验证抽象接口约束以及完整存储后端实现的基本行为。

核心功能：
  - test_base_storage_backend_is_abstract:
    验证存储后端基类不能直接实例化
  - test_base_storage_backend_declares_required_abstract_methods:
    验证基类声明完整抽象接口
  - test_complete_backend_is_concrete:
    验证完整实现可以实例化
  - test_complete_backend_supports_object_operations:
    验证完整实现支持对象操作
  - test_delete_missing_object_is_idempotent:
    验证删除不存在对象保持幂等
"""

import inspect

from datamind.storage.base import BaseStorageBackend


ABSTRACT_METHOD_NAMES = (
    "put_object",
    "get_object",
    "delete_object",
    "object_exists",
    "list_objects",
)


class MemoryStorageBackend(BaseStorageBackend):
    """完整实现抽象接口的内存存储后端"""

    def __init__(
            self,
    ) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(
            self,
            key: str,
            data: bytes,
    ) -> None:
        """存储对象"""
        self.objects[key] = data

    def get_object(
            self,
            key: str,
    ) -> bytes:
        """读取对象"""
        return self.objects[key]

    def delete_object(
            self,
            key: str,
    ) -> None:
        """删除对象"""
        self.objects.pop(
            key,
            None,
        )

    def object_exists(
            self,
            key: str,
    ) -> bool:
        """检查对象是否存在"""
        return key in self.objects

    def list_objects(
            self,
            prefix: str,
    ) -> list[str]:
        """列出指定前缀下的对象"""
        return sorted(
            key
            for key in self.objects
            if key.startswith(prefix)
        )


def test_base_storage_backend_is_abstract() -> None:
    """测试存储后端基类是抽象类"""
    assert inspect.isabstract(
        BaseStorageBackend
    )


def test_base_storage_backend_declares_required_abstract_methods() -> None:
    """测试五个存储接口均声明为抽象方法"""
    for method_name in ABSTRACT_METHOD_NAMES:
        method = inspect.getattr_static(
            BaseStorageBackend,
            method_name,
        )

        assert getattr(
            method,
            "__isabstractmethod__",
            False,
        )


def test_complete_backend_is_concrete() -> None:
    """测试完整实现所有接口后可以实例化"""
    assert not inspect.isabstract(
        MemoryStorageBackend
    )

    backend = MemoryStorageBackend()

    assert isinstance(
        backend,
        BaseStorageBackend,
    )


def test_complete_backend_supports_object_operations() -> None:
    """测试完整后端实现支持统一对象操作"""
    backend = MemoryStorageBackend()

    backend.put_object(
        "models/mdl_001/1.0.0/model.pkl",
        b"model data",
    )
    backend.put_object(
        "models/mdl_001/2.0.0/model.pkl",
        b"model data v2",
    )
    backend.put_object(
        "reports/report.txt",
        b"report",
    )

    assert backend.object_exists(
        "models/mdl_001/1.0.0/model.pkl"
    )
    assert backend.get_object(
        "models/mdl_001/1.0.0/model.pkl"
    ) == b"model data"
    assert backend.list_objects(
        "models/mdl_001/"
    ) == [
        "models/mdl_001/1.0.0/model.pkl",
        "models/mdl_001/2.0.0/model.pkl",
    ]

    backend.delete_object(
        "models/mdl_001/1.0.0/model.pkl"
    )

    assert not backend.object_exists(
        "models/mdl_001/1.0.0/model.pkl"
    )


def test_delete_missing_object_is_idempotent() -> None:
    """测试完整后端实现可提供幂等删除行为"""
    backend = MemoryStorageBackend()

    backend.delete_object(
        "models/missing.pkl"
    )

    assert not backend.object_exists(
        "models/missing.pkl"
    )
