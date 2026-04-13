"""MinIO存储组件验证测试"""

import asyncio
import os
from io import BytesIO

from datamind.storage.minio_storage import MinIOStorage
from datamind.storage.base import ProgressCallback
from datamind.core.common import StorageNotFoundException, StorageConnectionException


class SimpleProgressCallback(ProgressCallback):
    def __init__(self):
        self.calls = []

    async def __call__(self, current: int, total: int, phase: str = "upload"):
        self.calls.append((current, total, phase))
        if total > 0 and (current == 0 or current == total or current % 25000 == 0):
            print(f"  进度: {phase} - {current}/{total} 字节 ({current*100/total:.1f}%)")


async def get_minio_storage():
    endpoint = os.getenv('MINIO_ENDPOINT', '100.92.47.128:9000')
    access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    bucket_name = os.getenv('MINIO_BUCKET', 'test-bucket')
    secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'

    print(f"  MinIO配置: endpoint={endpoint}, bucket={bucket_name}")

    return MinIOStorage(
        endpoint=endpoint,
        bucket_name=bucket_name,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
        base_path="test"
    )


async def test_save_and_load():
    print("\n测试 1: 保存和加载文件")
    print("-" * 40)

    storage = await get_minio_storage()
    test_content = b"Hello, DataMind! This is a MinIO test file."

    result = await storage.save("hello.txt", BytesIO(test_content))
    print(f"  保存结果: size={result.size}")
    assert result.size == len(test_content)

    loaded = await storage.load("hello.txt")
    print(f"  加载内容: {loaded.decode('utf-8')[:50]}...")
    assert loaded == test_content

    print("  通过")


async def test_exists():
    print("\n测试 2: 文件存在性检查")
    print("-" * 40)

    storage = await get_minio_storage()

    await storage.save("exists_test.txt", BytesIO(b"test content"))

    exists = await storage.exists("exists_test.txt")
    print(f"  存在文件检查: {exists}")
    assert exists is True

    not_exists = await storage.exists("not_exists.txt")
    print(f"  不存在文件检查: {not_exists}")
    assert not_exists is False

    print("  通过")


async def test_delete():
    print("\n测试 3: 删除文件")
    print("-" * 40)

    storage = await get_minio_storage()

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
    print("\n测试 4: 列出文件")
    print("-" * 40)

    storage = await get_minio_storage()

    files = ["list1.txt", "list2.txt", "subdir/list3.txt"]
    for f in files:
        await storage.save(f, BytesIO(b"content"))

    all_files = [f.path for f in await storage.list()]
    print(f"  所有文件: {all_files}")
    assert len(all_files) >= 3

    prefixed = [f.path for f in await storage.list(prefix="subdir/")]
    print(f"  subdir/ 下文件: {prefixed}")
    assert len(prefixed) >= 1

    print("  通过")


async def test_get_metadata():
    print("\n测试 5: 获取元数据")
    print("-" * 40)

    storage = await get_minio_storage()

    # 使用英文元数据（MinIO 不支持中文）
    test_content = b"metadata test content"
    await storage.save("meta_test.txt", BytesIO(test_content), metadata={
        "description": "test metadata",
        "version": "1.0.0"
    })

    metadata = await storage.get_metadata("meta_test.txt")
    print(f"  元数据路径: {metadata.path}")
    print(f"  元数据内容: {metadata.metadata}")

    assert metadata.size == len(test_content)

    # MinIO 返回的元数据键名会添加 x-amz-meta- 前缀
    description = metadata.metadata.get('x-amz-meta-description') or metadata.metadata.get('description')
    version = metadata.metadata.get('x-amz-meta-version') or metadata.metadata.get('version')

    print(f"  提取的 description: {description}")
    print(f"  提取的 version: {version}")

    assert description == "test metadata"
    assert version == "1.0.0"

    print("  通过")


async def test_copy():
    print("\n测试 6: 复制文件")
    print("-" * 40)

    storage = await get_minio_storage()

    test_content = b"copy test content"
    await storage.save("source.txt", BytesIO(test_content))

    result = await storage.copy("source.txt", "destination.txt")
    print(f"  复制结果: {result.path}")

    exists = await storage.exists("destination.txt")
    print(f"  目标文件存在: {exists}")
    assert exists is True

    loaded = await storage.load("destination.txt")
    assert loaded == test_content

    print("  通过")


async def test_move():
    print("\n测试 7: 移动文件")
    print("-" * 40)

    storage = await get_minio_storage()

    test_content = b"move test content"
    await storage.save("to_move.txt", BytesIO(test_content))

    result = await storage.move("to_move.txt", "moved.txt")
    print(f"  移动结果: {result.path}")

    source_exists = await storage.exists("to_move.txt")
    print(f"  源文件存在: {source_exists}")
    assert source_exists is False

    target_exists = await storage.exists("moved.txt")
    print(f"  目标文件存在: {target_exists}")
    assert target_exists is True

    print("  通过")


async def test_get_signed_url():
    print("\n测试 8: 获取签名URL")
    print("-" * 40)

    storage = await get_minio_storage()

    await storage.save("url_test.txt", BytesIO(b"content"))

    url = await storage.get_signed_url("url_test.txt")
    print(f"  签名URL: {url[:80]}...")

    assert url.startswith("http")

    print("  通过")


async def test_progress_callback():
    print("\n测试 9: 进度回调")
    print("-" * 40)

    storage = await get_minio_storage()

    progress = SimpleProgressCallback()
    large_content = b"X" * 50000
    await storage.save("large.bin", BytesIO(large_content), progress_callback=progress)

    print(f"  上传回调次数: {len(progress.calls)}")
    assert len(progress.calls) > 0

    print("  通过")


async def test_batch_operations():
    print("\n测试 10: 批量操作")
    print("-" * 40)

    storage = await get_minio_storage()

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


async def test_error_handling():
    print("\n测试 11: 错误处理")
    print("-" * 40)

    storage = await get_minio_storage()

    try:
        await storage.load("not_exist.txt")
        print("  错误: 应该抛出异常")
    except StorageNotFoundException as e:
        print(f"  正确抛出异常: {e.message[:60]}...")

    try:
        await storage.copy("not_exist.txt", "dest.txt")
        print("  错误: 应该抛出异常")
    except StorageNotFoundException as e:
        print(f"  正确抛出异常: {e.message[:60]}...")

    print("  通过")


async def main():
    print("\n" + "=" * 50)
    print("开始验证 MinIO 存储组件")
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
        test_error_handling,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            await test()
            passed += 1
        except StorageConnectionException as e:
            print(f"  跳过: MinIO服务未连接 - {e.message}")
        except AssertionError as e:
            failed += 1
            print(f"  断言失败: {e}")
        except Exception as e:
            failed += 1
            print(f"  异常: {type(e).__name__}: {e}")

    print("\n" + "=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 50)

    if failed == 0:
        print("\nMinIO 存储组件验证成功！")
    else:
        print(f"\n有 {failed} 个测试失败，请检查。")


if __name__ == "__main__":
    asyncio.run(main())