"""本地文件存储后端测试

验证本地对象的写入、读取、删除、存在判断、列表和路径安全。

核心功能：
  - test_init_resolves_base_directory:
    验证基础目录解析为绝对路径
  - test_put_object_creates_parent_directories_and_writes_data:
    验证写入时创建父目录
  - test_put_object_overwrites_existing_file:
    验证重复写入原子覆盖文件
  - test_put_object_preserves_existing_file_when_replace_fails:
    验证替换失败时保留旧文件并清理临时文件
  - test_put_object_retries_transient_windows_replace_error:
    验证 Windows 短暂占用后重试原子替换
  - test_put_object_normalizes_windows_separator:
    验证标准化 Windows 分隔符
  - test_get_object_returns_file_data:
    验证读取已有文件
  - test_get_object_raises_when_file_does_not_exist:
    验证读取不存在文件抛出异常
  - test_get_object_rejects_directory:
    验证读取操作拒绝目录
  - test_delete_object_removes_existing_file:
    验证删除已有文件
  - test_delete_object_is_idempotent_for_missing_file:
    验证删除不存在文件保持幂等
  - test_object_exists_returns_expected_values:
    验证文件存在判断
  - test_object_exists_returns_false_for_directory:
    验证目录不被视为对象
  - test_list_objects_returns_sorted_recursive_keys:
    验证递归列出并排序对象键
  - test_list_objects_with_empty_prefix_lists_all_files:
    验证空前缀列出全部文件
  - test_list_objects_returns_empty_for_missing_prefix:
    验证不存在前缀返回空列表
  - test_list_objects_returns_empty_when_prefix_is_file:
    验证文件前缀返回空列表
  - test_public_operations_reject_unsafe_keys:
    验证公开操作拒绝不安全键和逻辑路径遍历
  - test_public_operations_reject_non_string_keys:
    验证公开操作拒绝非字符串键
  - test_public_operations_reject_null_character:
    验证公开操作拒绝空字符
  - test_list_objects_rejects_unsafe_prefix:
    验证列表操作拒绝不安全前缀
"""

from pathlib import Path
from typing import Any

import pytest

import datamind.storage.local as local_module
from datamind.storage.errors import (
    StorageKeyError,
    StorageNotFoundError,
)
from datamind.storage.local import LocalStorageBackend


def create_backend(
    tmp_path: Path,
) -> LocalStorageBackend:
    """创建使用临时目录的本地存储后端"""
    return LocalStorageBackend(
        base_dir=tmp_path / "storage"
    )


def test_init_resolves_base_directory(
    tmp_path: Path,
) -> None:
    """测试初始化时将基础目录转换为绝对路径"""
    base_dir = tmp_path / "data" / ".." / "storage"

    backend = LocalStorageBackend(
        base_dir=base_dir
    )

    assert backend.base_dir == base_dir.resolve()
    assert backend.base_dir.is_absolute()


def test_put_object_creates_parent_directories_and_writes_data(
    tmp_path: Path,
) -> None:
    """测试写入对象时自动创建父目录"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    data = b"model data"

    backend.put_object(
        key,
        data,
    )

    path = backend.base_dir / key

    assert path.is_file()
    assert path.read_bytes() == data


def test_put_object_overwrites_existing_file(
    tmp_path: Path,
) -> None:
    """测试重复写入时覆盖已有文件"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"

    backend.put_object(
        key,
        b"old data",
    )
    backend.put_object(
        key,
        b"new data",
    )

    assert backend.get_object(key) == b"new data"


def test_put_object_preserves_existing_file_when_replace_fails(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试原子替换失败时保留旧文件并清理临时文件"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"

    backend.put_object(
        key,
        b"old data",
    )

    def fail_replace(
            _source: Path,
            _target: Path,
    ) -> None:
        raise OSError(
            "replace failed"
        )

    monkeypatch.setitem(
        vars(local_module.os),
        "replace",
        fail_replace,
    )

    with pytest.raises(
            OSError,
            match="replace failed",
    ):
        backend.put_object(
            key,
            b"new data",
        )

    path = backend.base_dir / key

    assert path.read_bytes() == b"old data"
    assert list(
        path.parent.glob(
            ".model.pkl.*.tmp"
        )
    ) == []


def test_put_object_retries_transient_windows_replace_error(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试 Windows 短暂占用后重试原子替换"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    replace = local_module.os.replace
    call_count = 0

    def transient_replace(
            source: Path,
            target: Path,
    ) -> None:
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            raise PermissionError(
                "file is temporarily busy"
            )

        replace(
            source,
            target,
        )

    monkeypatch.setitem(
        vars(local_module.os),
        "replace",
        transient_replace,
    )
    monkeypatch.setitem(
        vars(local_module),
        "_IS_WINDOWS",
        True,
    )
    monkeypatch.setitem(
        vars(local_module.time),
        "sleep",
        lambda _seconds: None,
    )

    backend.put_object(
        key,
        b"model data",
    )

    assert backend.get_object(key) == b"model data"
    assert call_count == 2


def test_put_object_normalizes_windows_separator(
    tmp_path: Path,
) -> None:
    """测试将 Windows 路径分隔符标准化"""
    backend = create_backend(tmp_path)
    key = r"models\mdl_0123456789abcdef\1.0.0\model.pkl"

    backend.put_object(
        key,
        b"model data",
    )

    expected_path = (
        backend.base_dir
        / "models"
        / "mdl_0123456789abcdef"
        / "1.0.0"
        / "model.pkl"
    )

    assert expected_path.is_file()
    assert expected_path.read_bytes() == b"model data"


def test_get_object_returns_file_data(
    tmp_path: Path,
) -> None:
    """测试读取已存在对象"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"
    data = b"model data"

    backend.put_object(
        key,
        data,
    )

    assert backend.get_object(key) == data


def test_get_object_raises_when_file_does_not_exist(
    tmp_path: Path,
) -> None:
    """测试读取不存在对象时抛出标准异常"""
    backend = create_backend(tmp_path)
    key = "models/mdl_missing/1.0.0/model.pkl"

    with pytest.raises(
        StorageNotFoundError,
        match=f"文件不存在: {key}",
    ):
        backend.get_object(key)


def test_get_object_rejects_directory(
    tmp_path: Path,
) -> None:
    """测试目录不能作为文件对象读取"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef"
    directory = backend.base_dir / key
    directory.mkdir(
        parents=True
    )

    with pytest.raises(
        StorageNotFoundError,
        match=f"文件不存在: {key}",
    ):
        backend.get_object(key)


def test_delete_object_removes_existing_file(
    tmp_path: Path,
) -> None:
    """测试删除已存在对象"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"

    backend.put_object(
        key,
        b"model data",
    )

    backend.delete_object(key)

    assert backend.object_exists(key) is False


def test_delete_object_is_idempotent_for_missing_file(
    tmp_path: Path,
) -> None:
    """测试删除不存在对象时保持幂等"""
    backend = create_backend(tmp_path)
    key = "models/mdl_missing/1.0.0/model.pkl"

    backend.delete_object(key)
    backend.delete_object(key)



def test_object_exists_returns_expected_values(
    tmp_path: Path,
) -> None:
    """测试对象存在判断"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"

    assert backend.object_exists(key) is False

    backend.put_object(
        key,
        b"model data",
    )

    assert backend.object_exists(key) is True

    backend.delete_object(key)

    assert backend.object_exists(key) is False


def test_object_exists_returns_false_for_directory(
    tmp_path: Path,
) -> None:
    """测试目录不被视为文件对象"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef"
    directory = backend.base_dir / key
    directory.mkdir(
        parents=True
    )

    assert backend.object_exists(key) is False


def test_list_objects_returns_sorted_recursive_keys(
    tmp_path: Path,
) -> None:
    """测试递归列出指定前缀下的对象并排序"""
    backend = create_backend(tmp_path)

    backend.put_object(
        "models/mdl_0123456789abcdef/2.0.0/model.pkl",
        b"v2",
    )
    backend.put_object(
        "models/mdl_0123456789abcdef/1.0.0/readme.txt",
        b"readme",
    )
    backend.put_object(
        "models/mdl_0123456789abcdef/1.0.0/model.pkl",
        b"v1",
    )
    backend.put_object(
        "models/mdl_other/1.0.0/model.pkl",
        b"other",
    )

    keys = backend.list_objects(
        "models/mdl_0123456789abcdef"
    )

    assert keys == [
        "models/mdl_0123456789abcdef/1.0.0/model.pkl",
        "models/mdl_0123456789abcdef/1.0.0/readme.txt",
        "models/mdl_0123456789abcdef/2.0.0/model.pkl",
    ]


def test_list_objects_with_empty_prefix_lists_all_files(
    tmp_path: Path,
) -> None:
    """测试空前缀列出基础目录下全部对象"""
    backend = create_backend(tmp_path)

    backend.put_object(
        "models/mdl_a/1.0.0/model.pkl",
        b"a",
    )
    backend.put_object(
        "rules/rule_a/1.0.0/rule.yaml",
        b"b",
    )

    keys = backend.list_objects("")

    assert keys == [
        "models/mdl_a/1.0.0/model.pkl",
        "rules/rule_a/1.0.0/rule.yaml",
    ]


def test_list_objects_returns_empty_for_missing_prefix(
    tmp_path: Path,
) -> None:
    """测试不存在的目录前缀返回空列表"""
    backend = create_backend(tmp_path)

    assert backend.list_objects(
        "models/mdl_missing"
    ) == []


def test_list_objects_returns_empty_when_prefix_is_file(
    tmp_path: Path,
) -> None:
    """测试前缀指向文件时返回空列表"""
    backend = create_backend(tmp_path)
    key = "models/mdl_0123456789abcdef/1.0.0/model.pkl"

    backend.put_object(
        key,
        b"model data",
    )

    assert backend.list_objects(key) == []


@pytest.mark.parametrize(
    "key",
    [
        "",
        ".",
        "..",
        "../outside.pkl",
        "models/../../outside.pkl",
        "models/model_a/../model_b/model.pkl",
        "models//model.pkl",
        "models/./model.pkl",
        "models/model.pkl/",
        "/tmp/outside.pkl",
        r"..\outside.pkl",
        r"models\..\..\outside.pkl",
    ],
)
def test_public_operations_reject_unsafe_keys(
    tmp_path: Path,
    key: str,
) -> None:
    """测试公开对象操作拒绝空键、基础目录和路径越界"""
    backend = create_backend(tmp_path)

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


@pytest.mark.parametrize(
    "key",
    [
        None,
        123,
        b"model.pkl",
    ],
)
def test_public_operations_reject_non_string_keys(
    tmp_path: Path,
    key: Any,
) -> None:
    """测试公开对象操作拒绝非字符串键"""
    backend = create_backend(tmp_path)

    operations = [
        lambda: backend.put_object(
            key,
            b"data",
        ),
        lambda: backend.get_object(key),
        lambda: backend.delete_object(key),
        lambda: backend.object_exists(key),
        lambda: backend.list_objects(key),
    ]

    for operation in operations:
        with pytest.raises(
            StorageKeyError,
            match="存储键必须是字符串",
        ):
            operation()


def test_public_operations_reject_null_character(
    tmp_path: Path,
) -> None:
    """测试公开对象操作拒绝空字符"""
    backend = create_backend(tmp_path)
    key = "models/model\x00.pkl"

    operations = [
        lambda: backend.put_object(
            key,
            b"data",
        ),
        lambda: backend.get_object(key),
        lambda: backend.delete_object(key),
        lambda: backend.object_exists(key),
        lambda: backend.list_objects(key),
    ]

    for operation in operations:
        with pytest.raises(
            StorageKeyError,
            match="存储键不能包含空字符",
        ):
            operation()


@pytest.mark.parametrize(
    "prefix",
    [
        "..",
        "../outside",
        "models/model_a/../model_b",
        "models//model_a",
        "models/./model_a",
        "/tmp",
        r"..\outside",
    ],
)
def test_list_objects_rejects_unsafe_prefix(
    tmp_path: Path,
    prefix: str,
) -> None:
    """测试列表操作拒绝越界目录前缀"""
    backend = create_backend(tmp_path)

    with pytest.raises(StorageKeyError):
        backend.list_objects(prefix)
