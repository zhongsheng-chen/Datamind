"""本地存储组件验证测试 - 兼容 Windows 和 Linux"""

import asyncio
import tempfile
import json
from pathlib import Path
from io import BytesIO

from datamind.storage.local_storage import LocalStorage
from datamind.storage.base import ProgressCallback


def normalize_path(path: str) -> str:
    """统一路径分隔符为正斜杠，用于跨平台断言"""
    return path.replace('\\', '/')


class SimpleProgressCallback(ProgressCallback):
    """简单的进度回调实现"""
    def __init__(self):
        self.calls = []

    async def __call__(self, current: int, total: int, phase: str = "upload"):
        self.calls.append((current, total, phase))
        print(f"  进度: {phase} - {current}/{total} 字节 ({current*100/total:.1f}%)")


async def test_save_and_load():
    """测试保存和加载文件"""
    print("\n测试 1: 保存和加载文件")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        test_content = b"Hello, DataMind! This is a test file."
        content_io = BytesIO(test_content)

        result = await storage.save("hello.txt", content_io, metadata={"author": "test_user"})
        normalized_path = normalize_path(result.path)
        print(f"  保存结果: path={normalized_path}, size={result.size}")

        assert normalized_path == "test/hello.txt"
        assert result.size == len(test_content)

        loaded = await storage.load("hello.txt")
        print(f"  加载内容: {loaded.decode('utf-8')}")
        assert loaded == test_content

        print("  通过")


async def test_exists():
    """测试文件存在性检查"""
    print("\n测试 2: 文件存在性检查")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        await storage.save("exists_test.txt", BytesIO(b"test content"))

        exists = await storage.exists("exists_test.txt")
        print(f"  存在文件检查: {exists}")
        assert exists is True

        not_exists = await storage.exists("not_exists.txt")
        print(f"  不存在文件检查: {not_exists}")
        assert not_exists is False

        print("  通过")


async def test_delete():
    """测试删除文件"""
    print("\n测试 3: 删除文件")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        await storage.save("delete_me.txt", BytesIO(b"to be deleted"))

        result = await storage.delete("delete_me.txt")
        print(f"  删除结果: {result}")
        assert result is True

        exists = await storage.exists("delete_me.txt")
        print(f"  删除后存在: {exists}")
        assert exists is False

        result2 = await storage.delete("not_exists.txt")
        print(f"  删除不存在文件: {result2}")
        assert result2 is False

        print("  通过")


async def test_list():
    """测试列出文件"""
    print("\n测试 4: 列出文件")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        files = ["file1.txt", "file2.txt", "subdir/file3.txt"]
        for f in files:
            await storage.save(f, BytesIO(b"content"))

        all_files = [normalize_path(f.path) for f in await storage.list()]
        print(f"  所有文件: {all_files}")
        assert len(all_files) == 3

        prefixed = [normalize_path(f.path) for f in await storage.list(prefix="subdir/")]
        print(f"  subdir/ 下文件: {prefixed}")
        assert len(prefixed) == 1

        print("  通过")


async def test_get_metadata():
    """测试获取元数据"""
    print("\n测试 5: 获取元数据")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        test_content = b"metadata test content"
        await storage.save("meta_test.txt", BytesIO(test_content), metadata={
            "description": "测试元数据",
            "version": "1.0.0"
        })

        metadata = await storage.get_metadata("meta_test.txt")
        normalized_path = normalize_path(metadata.path)
        print(f"  元数据路径: {normalized_path}")

        assert normalized_path == "test/meta_test.txt"
        assert metadata.size == len(test_content)
        assert metadata.metadata["description"] == "测试元数据"

        print("  通过")


async def test_copy():
    """测试复制文件"""
    print("\n测试 6: 复制文件")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        test_content = b"copy test content"
        await storage.save("source.txt", BytesIO(test_content))

        result = await storage.copy("source.txt", "destination.txt")
        normalized_path = normalize_path(result.path)
        print(f"  复制结果: {normalized_path}")

        exists = await storage.exists("destination.txt")
        print(f"  目标文件存在: {exists}")
        assert exists is True

        loaded = await storage.load("destination.txt")
        assert loaded == test_content

        print("  通过")


async def test_move():
    """测试移动文件"""
    print("\n测试 7: 移动文件")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        test_content = b"move test content"
        await storage.save("to_move.txt", BytesIO(test_content))

        result = await storage.move("to_move.txt", "moved.txt")
        normalized_path = normalize_path(result.path)
        print(f"  移动结果: {normalized_path}")

        source_exists = await storage.exists("to_move.txt")
        print(f"  源文件存在: {source_exists}")
        assert source_exists is False

        target_exists = await storage.exists("moved.txt")
        print(f"  目标文件存在: {target_exists}")
        assert target_exists is True

        print("  通过")


async def test_get_signed_url():
    """测试获取签名URL"""
    print("\n测试 8: 获取签名URL")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        await storage.save("url_test.txt", BytesIO(b"content"))

        url = await storage.get_signed_url("url_test.txt")
        print(f"  签名URL: {url[:80]}...")

        assert url.startswith("file://")

        print("  通过")


async def test_progress_callback():
    """测试进度回调"""
    print("\n测试 9: 进度回调")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        progress = SimpleProgressCallback()
        large_content = b"X" * 100000
        await storage.save("large.bin", BytesIO(large_content), progress_callback=progress)

        print(f"  上传回调次数: {len(progress.calls)}")
        assert len(progress.calls) > 0

        progress2 = SimpleProgressCallback()
        await storage.load("large.bin", progress_callback=progress2)

        print(f"  下载回调次数: {len(progress2.calls)}")
        assert len(progress2.calls) > 0

        print("  通过")


async def test_batch_operations():
    """测试批量操作"""
    print("\n测试 10: 批量操作")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        items = [
            ("batch1.txt", BytesIO(b"content1"), None),
            ("batch2.txt", BytesIO(b"content2"), None),
            ("sub/batch3.txt", BytesIO(b"content3"), None),
        ]

        results = await storage.batch_save(items)
        print(f"  批量保存: {len(results)} 个文件")
        assert len(results) == 3

        paths = ["batch1.txt", "batch2.txt", "sub/batch3.txt"]
        delete_results = await storage.batch_delete(paths)
        print(f"  批量删除: {delete_results}")

        for path in paths:
            assert await storage.exists(path) is False

        print("  通过")


async def test_quota():
    """测试配额检查"""
    print("\n测试 11: 配额检查")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        await storage.save("file1.txt", BytesIO(b"a" * 1000))
        await storage.save("file2.txt", BytesIO(b"b" * 2000))

        quota = await storage.get_quota()
        print(f"  总大小: {quota.total_size} 字节, 文件数: {quota.file_count}")

        assert quota.total_size == 3000
        assert quota.file_count == 2

        is_ok = await storage.check_quota(additional_size=1000)
        print(f"  配额检查: {is_ok}")
        assert is_ok is True

        print("  通过")


async def test_stream_operations():
    """测试流式操作"""
    print("\n测试 12: 流式操作")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        async def chunk_generator():
            yield b"Hello "
            yield b"World "
            yield b"from "
            yield b"streaming!"

        result = await storage.stream_save("stream.txt", chunk_generator())
        print(f"  流式保存: {result.size} 字节")

        chunks = []
        async for chunk in storage.stream_load("stream.txt", chunk_size=10):
            chunks.append(chunk)

        full_content = b"".join(chunks)
        print(f"  流式加载内容: {full_content.decode('utf-8')}")
        assert full_content == b"Hello World from streaming!"

        print("  通过")


async def test_error_handling():
    """测试错误处理"""
    print("\n测试 13: 错误处理")
    print("-" * 40)

    from datamind.core.common import StorageNotFoundException

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        try:
            await storage.load("not_exist.txt")
            print("  错误: 应该抛出异常但没有")
        except StorageNotFoundException as e:
            print(f"  正确抛出异常: {e.message}")

        try:
            await storage.copy("not_exist.txt", "dest.txt")
            print("  错误: 应该抛出异常但没有")
        except StorageNotFoundException as e:
            print(f"  正确抛出异常: {e.message}")

        print("  通过")


async def test_metadata_persistence():
    """测试元数据持久化"""
    print("\n测试 14: 元数据持久化")
    print("-" * 40)

    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(root_path=tmpdir, base_path="test")

        custom_metadata = {
            "model_type": "random_forest",
            "accuracy": 0.95,
            "tags": ["production", "v2"]
        }

        await storage.save("model.pkl", BytesIO(b"model data"), metadata=custom_metadata)

        metadata = await storage.get_metadata("model.pkl")
        print(f"  读取的元数据: {metadata.metadata}")

        assert metadata.metadata["model_type"] == "random_forest"
        assert metadata.metadata["accuracy"] == 0.95

        # 元数据文件路径: root_path/base_path/filename.meta.json
        meta_file = Path(tmpdir) / "test" / "model.pkl.meta.json"
        print(f"  元数据文件路径: {meta_file}")
        print(f"  元数据文件存在: {meta_file.exists()}")
        assert meta_file.exists(), f"元数据文件不存在: {meta_file}"

        # 验证元数据文件内容
        with open(meta_file, 'r', encoding='utf-8') as f:
            saved_meta = json.load(f)
            print(f"  文件中的元数据: {saved_meta}")
            assert saved_meta["model_type"] == "random_forest"
            assert saved_meta["accuracy"] == 0.95

        print("  通过")


async def main():
    """运行所有测试"""
    print("\n" + "=" * 50)
    print("开始验证本地存储组件")
    print("=" * 50)

    tests = [
        test_save_and_load,
        test_exists,
        test_delete,
        test_list,
        test_get_metadata,
        test_copy,
        test_move,
        test_get_signed_url,
        test_progress_callback,
        test_batch_operations,
        test_quota,
        test_stream_operations,
        test_error_handling,
        test_metadata_persistence,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n  测试失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 50)

    if failed == 0:
        print("\n所有测试通过，存储组件验证成功。")
    else:
        print(f"\n有 {failed} 个测试失败，请检查。")


if __name__ == "__main__":
    asyncio.run(main())