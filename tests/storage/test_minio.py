# tests/storage/test_minio.py

"""MinIO 对象存储后端测试

验证客户端初始化、基础前缀、对象操作、键校验和异常映射。

核心功能：
  - test_init_passes_client_options_and_normalizes_values:
    验证客户端参数传递和配置规范化
  - test_init_creates_missing_bucket:
    验证自动创建不存在的存储桶
  - test_init_rejects_invalid_bucket:
    验证拒绝非法存储桶
  - test_init_wraps_client_creation_error:
    验证客户端初始化异常映射
  - test_put_object_adds_base_prefix_and_uploads_bytes:
    验证添加基础前缀并上传字节
  - test_get_object_returns_data_and_closes_response:
    验证读取数据并关闭响应资源
  - test_get_object_rejects_empty_response_data:
    验证拒绝空响应内容
  - test_delete_object_is_idempotent_for_missing_object:
    验证删除不存在对象保持幂等
  - test_object_exists_returns_expected_value:
    验证对象存在判断
  - test_list_objects_removes_base_prefix_and_sorts:
    验证列表移除基础前缀并排序
  - test_list_objects_with_empty_prefix_uses_base_prefix:
    验证空逻辑前缀使用基础前缀
  - test_object_operations_reject_invalid_keys:
    验证对象操作拒绝非法键和绝对键
  - test_list_objects_rejects_invalid_prefix:
    验证列表拒绝非法前缀和绝对前缀
  - test_s3_errors_are_mapped_to_storage_errors:
    验证 S3 异常映射为标准存储异常
  - test_unexpected_client_errors_are_wrapped:
    验证未知客户端异常被统一包装
"""

from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pytest
from minio.error import S3Error

from datamind.storage import minio as minio_module
from datamind.storage.errors import (
    StorageBackendError,
    StorageConnectionError,
    StorageKeyError,
    StorageNotFoundError,
    StoragePermissionError,
)
from datamind.storage.minio import MinIOStorageBackend


class FakeS3Error(S3Error):
    """仅提供测试所需字段的 S3Error"""

    def __init__(
        self,
        code: str,
        message: str,
    ) -> None:
        Exception.__init__(
            self,
            message,
        )
        self._test_code = code
        self._test_message = message

    @property
    def code(self) -> str:
        """返回测试错误码"""
        return self._test_code

    @property
    def message(self) -> str:
        """返回测试错误消息"""
        return self._test_message

    def __str__(self) -> str:
        """返回简化错误文本"""
        return (
            f"code={self.code}, "
            f"message={self.message}"
        )


@dataclass
class ObjectItem:
    """模拟 MinIO 列表结果项"""

    object_name: str | None


class FakeResponse:
    """模拟 MinIO 下载响应"""

    def __init__(
        self,
        data: bytes | None,
        *,
        read_error: Exception | None = None,
    ) -> None:
        self.data = data
        self.read_error = read_error
        self.close_count = 0
        self.release_count = 0

    def read(self) -> bytes | None:
        """读取响应内容"""
        if self.read_error is not None:
            raise self.read_error

        return self.data

    def close(self) -> None:
        """记录关闭调用"""
        self.close_count += 1

    def release_conn(self) -> None:
        """记录连接释放调用"""
        self.release_count += 1


class FakeMinioClient:
    """模拟 MinIO 客户端"""

    def __init__(
        self,
        endpoint: str,
        *,
        access_key: str,
        secret_key: str,
        secure: bool,
        region: str | None,
    ) -> None:
        self.endpoint = endpoint
        self.access_key = access_key
        self.secret_key = secret_key
        self.secure = secure
        self.region = region

        self.bucket_exists_result = True
        self.bucket_exists_error: Exception | None = None
        self.make_bucket_error: Exception | None = None
        self.put_error: Exception | None = None
        self.get_error: Exception | None = None
        self.remove_error: Exception | None = None
        self.stat_error: Exception | None = None
        self.list_error: Exception | None = None

        self.response = FakeResponse(b"model data")
        self.listed_objects: list[ObjectItem] = []

        self.bucket_exists_calls: list[str] = []
        self.make_bucket_calls: list[str] = []
        self.put_calls: list[
            tuple[str, str, bytes, int]
        ] = []
        self.get_calls: list[tuple[str, str]] = []
        self.remove_calls: list[tuple[str, str]] = []
        self.stat_calls: list[tuple[str, str]] = []
        self.list_calls: list[
            tuple[str, str, bool]
        ] = []

    def bucket_exists(
        self,
        bucket: str,
    ) -> bool:
        """模拟检查存储桶"""
        self.bucket_exists_calls.append(bucket)

        if self.bucket_exists_error is not None:
            raise self.bucket_exists_error

        return self.bucket_exists_result

    def make_bucket(
        self,
        bucket: str,
    ) -> None:
        """模拟创建存储桶"""
        self.make_bucket_calls.append(bucket)

        if self.make_bucket_error is not None:
            raise self.make_bucket_error

    def put_object(
        self,
        bucket: str,
        object_name: str,
        data: BytesIO,
        *,
        length: int,
    ) -> None:
        """模拟上传对象"""
        payload = data.read()
        self.put_calls.append(
            (
                bucket,
                object_name,
                payload,
                length,
            )
        )

        if self.put_error is not None:
            raise self.put_error

    def get_object(
        self,
        bucket: str,
        object_name: str,
    ) -> FakeResponse:
        """模拟下载对象"""
        self.get_calls.append(
            (
                bucket,
                object_name,
            )
        )

        if self.get_error is not None:
            raise self.get_error

        return self.response

    def remove_object(
        self,
        bucket: str,
        object_name: str,
    ) -> None:
        """模拟删除对象"""
        self.remove_calls.append(
            (
                bucket,
                object_name,
            )
        )

        if self.remove_error is not None:
            raise self.remove_error

    def stat_object(
        self,
        bucket: str,
        object_name: str,
    ) -> object:
        """模拟读取对象元数据"""
        self.stat_calls.append(
            (
                bucket,
                object_name,
            )
        )

        if self.stat_error is not None:
            raise self.stat_error

        return object()

    def list_objects(
        self,
        bucket: str,
        *,
        prefix: str,
        recursive: bool,
    ) -> list[ObjectItem]:
        """模拟列出对象"""
        self.list_calls.append(
            (
                bucket,
                prefix,
                recursive,
            )
        )

        if self.list_error is not None:
            raise self.list_error

        return self.listed_objects


def make_s3_error(
    code: str,
    message: str = "storage error",
) -> S3Error:
    """创建 MinIO S3Error 测试对象"""
    return FakeS3Error(
        code,
        message,
    )


def install_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bucket_exists_result: bool = True,
) -> tuple[
    list[FakeMinioClient],
    dict[str, Any],
]:
    """替换 Minio 构造器并记录客户端和参数"""
    clients: list[FakeMinioClient] = []
    options: dict[str, Any] = {}

    def fake_minio(
        endpoint: str,
        *,
        access_key: str,
        secret_key: str,
        secure: bool,
        region: str | None,
    ) -> FakeMinioClient:
        options.update(
            {
                "endpoint": endpoint,
                "access_key": access_key,
                "secret_key": secret_key,
                "secure": secure,
                "region": region,
            }
        )
        client = FakeMinioClient(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region,
        )
        client.bucket_exists_result = bucket_exists_result
        clients.append(client)
        return client

    monkeypatch.setitem(
        vars(minio_module),
        "Minio",
        fake_minio,
    )

    return clients, options


def create_backend(
    monkeypatch: pytest.MonkeyPatch,
    *,
    bucket: str = "datamind",
    base_prefix: str = "artifacts",
) -> tuple[
    MinIOStorageBackend,
    FakeMinioClient,
]:
    """创建使用模拟客户端的 MinIO 后端"""
    clients, _ = install_client(monkeypatch)

    backend = MinIOStorageBackend(
        endpoint="minio.internal:9000",
        access_key="access-key",
        secret_key="secret-key",
        bucket=bucket,
        secure=False,
        base_prefix=base_prefix,
        region="cn-north-1",
    )

    return backend, clients[0]


def test_init_passes_client_options_and_normalizes_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试初始化参数传递和名称规范化"""
    clients, options = install_client(
        monkeypatch
    )

    backend = MinIOStorageBackend(
        endpoint="minio.internal:9000",
        access_key="access-key",
        secret_key="secret-key",
        bucket=" datamind ",
        secure=True,
        base_prefix=r"\artifacts\models/",
        region="cn-north-1",
    )

    assert len(clients) == 1
    assert backend.client is clients[0]
    assert backend.bucket == "datamind"
    assert backend.base_prefix == "artifacts/models"
    assert options == {
        "endpoint": "minio.internal:9000",
        "access_key": "access-key",
        "secret_key": "secret-key",
        "secure": True,
        "region": "cn-north-1",
    }
    assert clients[0].bucket_exists_calls == [
        "datamind",
    ]
    assert clients[0].make_bucket_calls == []


def test_init_creates_missing_bucket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试存储桶不存在时自动创建"""
    clients, _ = install_client(
        monkeypatch,
        bucket_exists_result=False,
    )

    MinIOStorageBackend(
        endpoint="minio.internal:9000",
        access_key="access-key",
        secret_key="secret-key",
        bucket="datamind",
        secure=False,
    )

    assert clients[0].make_bucket_calls == [
        "datamind",
    ]


@pytest.mark.parametrize(
    "bucket",
    [
        "",
        "   ",
        "data/mind",
        r"data\mind",
    ],
)
def test_init_rejects_invalid_bucket(
    monkeypatch: pytest.MonkeyPatch,
    bucket: str,
) -> None:
    """测试拒绝空桶名和包含分隔符的桶名"""
    clients, _ = install_client(
        monkeypatch
    )

    with pytest.raises(
        ValueError,
        match="非法的 MinIO 存储桶名称",
    ):
        MinIOStorageBackend(
            endpoint="minio.internal:9000",
            access_key="access-key",
            secret_key="secret-key",
            bucket=bucket,
            secure=False,
        )

    assert clients == []


def test_init_wraps_client_creation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试客户端构造异常包装为连接异常"""
    original_error = RuntimeError(
        "invalid endpoint"
    )

    def failing_minio(
        _endpoint: str,
        *,
        access_key: str,
        secret_key: str,
        secure: bool,
        region: str | None,
    ) -> None:
        assert access_key == "access-key"
        assert secret_key == "secret-key"
        assert secure is False
        assert region is None
        raise original_error

    monkeypatch.setitem(
        vars(minio_module),
        "Minio",
        failing_minio,
    )

    with pytest.raises(
        StorageConnectionError,
        match=(
            "初始化 MinIO 客户端失败: "
            "invalid endpoint"
        ),
    ) as exc_info:
        MinIOStorageBackend(
            endpoint="invalid",
            access_key="access-key",
            secret_key="secret-key",
            bucket="datamind",
            secure=False,
        )

    assert exc_info.value.__cause__ is original_error


def test_put_object_adds_base_prefix_and_uploads_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试上传对象时加入基础前缀"""
    backend, client = create_backend(
        monkeypatch
    )
    data = b"model data"

    backend.put_object(
        r"models\mdl_0123456789abcdef\1.0.0\model.pkl",
        data,
    )

    assert client.put_calls == [
        (
            "datamind",
            (
                "artifacts/models/mdl_0123456789abcdef/"
                "1.0.0/model.pkl"
            ),
            data,
            len(data),
        ),
    ]


def test_get_object_returns_data_and_closes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试下载对象并释放响应连接"""
    backend, client = create_backend(
        monkeypatch
    )
    response = FakeResponse(
        b"model data"
    )
    client.response = response

    data = backend.get_object(
        "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    )

    assert data == b"model data"
    assert client.get_calls == [
        (
            "datamind",
            (
                "artifacts/models/mdl_0123456789abcdef/"
                "1.0.0/model.pkl"
            ),
        ),
    ]
    assert response.close_count == 1
    assert response.release_count == 1


def test_get_object_rejects_empty_response_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试响应内容为 None 时抛出后端异常"""
    backend, client = create_backend(
        monkeypatch
    )
    response = FakeResponse(None)
    client.response = response

    with pytest.raises(
        StorageBackendError,
        match="读取对象失败，响应内容为空",
    ):
        backend.get_object(
            "models/mdl_0123456789abcdef/1.0.0/model.pkl"
        )

    assert response.close_count == 1
    assert response.release_count == 1


def test_delete_object_is_idempotent_for_missing_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试删除不存在对象时保持幂等"""
    backend, client = create_backend(
        monkeypatch
    )
    client.remove_error = make_s3_error(
        "NoSuchKey"
    )

    backend.delete_object(
        "models/mdl_missing/1.0.0/model.pkl"
    )

    assert client.remove_calls == [
        (
            "datamind",
            (
                "artifacts/models/mdl_missing/"
                "1.0.0/model.pkl"
            ),
        ),
    ]


@pytest.mark.parametrize(
    (
        "error_code",
        "expected",
    ),
    [
        (
            None,
            True,
        ),
        (
            "NoSuchKey",
            False,
        ),
        (
            "NotFound",
            False,
        ),
    ],
)
def test_object_exists_returns_expected_value(
    monkeypatch: pytest.MonkeyPatch,
    error_code: str | None,
    expected: bool,
) -> None:
    """测试对象存在和不存在判断"""
    backend, client = create_backend(
        monkeypatch
    )

    if error_code is not None:
        client.stat_error = make_s3_error(
            error_code
        )

    result = backend.object_exists(
        "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    )

    assert result is expected


def test_list_objects_removes_base_prefix_and_sorts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试列表结果移除基础前缀并排序"""
    backend, client = create_backend(
        monkeypatch
    )
    client.listed_objects = [
        ObjectItem(
            "artifacts/models/mdl_a/2.0.0/model.pkl"
        ),
        ObjectItem(None),
        ObjectItem(
            "artifacts/models/mdl_a/1.0.0/model.pkl"
        ),
    ]

    keys = backend.list_objects(
        "models/mdl_a"
    )

    assert client.list_calls == [
        (
            "datamind",
            "artifacts/models/mdl_a",
            True,
        ),
    ]
    assert keys == [
        "models/mdl_a/1.0.0/model.pkl",
        "models/mdl_a/2.0.0/model.pkl",
    ]


def test_list_objects_with_empty_prefix_uses_base_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试空逻辑前缀列出基础前缀下全部对象"""
    backend, client = create_backend(
        monkeypatch
    )
    client.listed_objects = []

    assert backend.list_objects("") == []
    assert client.list_calls == [
        (
            "datamind",
            "artifacts/",
            True,
        ),
    ]


@pytest.mark.parametrize(
    "key",
    [
        "",
        ".",
        "..",
        "../model.pkl",
        "models//model.pkl",
        "models/./model.pkl",
        "models/../model.pkl",
        "/models/model.pkl",
        r"\models\model.pkl",
        "models/model.pkl/",
        "models/model\x00.pkl",
    ],
)
def test_object_operations_reject_invalid_keys(
    monkeypatch: pytest.MonkeyPatch,
    key: str,
) -> None:
    """测试对象操作拒绝空键、空字符和非法路径段"""
    backend, client = create_backend(
        monkeypatch
    )

    operations = [
        lambda: backend.put_object(
            key,
            b"data",
        ),
        lambda: backend.get_object(key),
        lambda: backend.delete_object(key),
        lambda: backend.object_exists(key),
    ]

    for operation in operations:
        with pytest.raises(StorageKeyError):
            operation()

    assert client.put_calls == []
    assert client.get_calls == []
    assert client.remove_calls == []
    assert client.stat_calls == []


@pytest.mark.parametrize(
    "prefix",
    [
        ".",
        "..",
        "../models",
        "models//mdl_a",
        "models/./mdl_a",
        "models/../mdl_a",
        "/models/mdl_a",
        r"\models\mdl_a",
        "models\x00",
    ],
)
def test_list_objects_rejects_invalid_prefix(
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
) -> None:
    """测试列表操作拒绝非法逻辑前缀"""
    backend, client = create_backend(
        monkeypatch
    )

    with pytest.raises(StorageKeyError):
        backend.list_objects(prefix)

    assert client.list_calls == []


@pytest.mark.parametrize(
    (
        "method_name",
        "error_code",
        "error_type",
    ),
    [
        (
            "get",
            "NoSuchKey",
            StorageNotFoundError,
        ),
        (
            "get",
            "AccessDenied",
            StoragePermissionError,
        ),
        (
            "put",
            "InternalError",
            StorageBackendError,
        ),
        (
            "delete",
            "AccessDenied",
            StoragePermissionError,
        ),
        (
            "exists",
            "SignatureDoesNotMatch",
            StoragePermissionError,
        ),
        (
            "list",
            "NoSuchBucket",
            StorageNotFoundError,
        ),
    ],
)
def test_s3_errors_are_mapped_to_storage_errors(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    error_code: str,
    error_type: type[StorageBackendError],
) -> None:
    """测试不同 S3 错误码映射为标准存储异常"""
    backend, client = create_backend(
        monkeypatch
    )
    error = make_s3_error(
        error_code,
        "operation failed",
    )

    if method_name == "get":
        client.get_error = error
        operation = lambda: backend.get_object(
            "models/mdl_a/1.0.0/model.pkl"
        )
    elif method_name == "put":
        client.put_error = error
        operation = lambda: backend.put_object(
            "models/mdl_a/1.0.0/model.pkl",
            b"data",
        )
    elif method_name == "delete":
        client.remove_error = error
        operation = lambda: backend.delete_object(
            "models/mdl_a/1.0.0/model.pkl"
        )
    elif method_name == "exists":
        client.stat_error = error
        operation = lambda: backend.object_exists(
            "models/mdl_a/1.0.0/model.pkl"
        )
    else:
        client.list_error = error
        operation = lambda: backend.list_objects(
            "models/mdl_a"
        )

    with pytest.raises(
        error_type,
    ) as exc_info:
        operation()

    assert exc_info.value.__cause__ is error


@pytest.mark.parametrize(
    (
        "method_name",
        "message",
    ),
    [
        (
            "put",
            "上传对象失败",
        ),
        (
            "get",
            "读取对象失败",
        ),
        (
            "delete",
            "删除对象失败",
        ),
        (
            "exists",
            "检查对象失败",
        ),
        (
            "list",
            "列出对象失败",
        ),
    ],
)
def test_unexpected_client_errors_are_wrapped(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
    message: str,
) -> None:
    """测试非 S3 客户端异常包装为连接异常"""
    backend, client = create_backend(
        monkeypatch
    )
    original_error = RuntimeError(
        "connection lost"
    )

    if method_name == "put":
        client.put_error = original_error
        operation = lambda: backend.put_object(
            "models/mdl_a/1.0.0/model.pkl",
            b"data",
        )
    elif method_name == "get":
        client.get_error = original_error
        operation = lambda: backend.get_object(
            "models/mdl_a/1.0.0/model.pkl"
        )
    elif method_name == "delete":
        client.remove_error = original_error
        operation = lambda: backend.delete_object(
            "models/mdl_a/1.0.0/model.pkl"
        )
    elif method_name == "exists":
        client.stat_error = original_error
        operation = lambda: backend.object_exists(
            "models/mdl_a/1.0.0/model.pkl"
        )
    else:
        client.list_error = original_error
        operation = lambda: backend.list_objects(
            "models/mdl_a"
        )

    with pytest.raises(
        StorageConnectionError,
        match=message,
    ) as exc_info:
        operation()

    assert exc_info.value.__cause__ is original_error
