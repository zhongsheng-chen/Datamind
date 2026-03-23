# tests/storage/test_s3_storage.py

"""S3存储测试

测试 S3Storage 的各项功能，包括文件保存、加载、删除、复制、移动等操作。
使用 MinIO 容器作为 S3 兼容后端进行测试，需要 Docker 环境支持。
"""

import io
import pytest
from testcontainers.minio import MinioContainer

from datamind.storage.s3_storage import S3Storage


class TestS3Storage:
    """S3存储测试类（使用 MinIO 作为 S3 兼容后端）"""

    @pytest.fixture(scope="module")
    def minio_container(self):
        """启动 MinIO 容器"""
        with MinioContainer() as minio:
            yield minio

    @pytest.fixture
    def storage(self, minio_container):
        """创建 S3 存储实例（使用 MinIO 作为后端）"""
        host = minio_container.get_container_host_ip()
        port = minio_container.get_exposed_port(9000)
        endpoint_url = f"http://{host}:{port}"

        return S3Storage(
            bucket_name="test-bucket",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            region_name="us-east-1",
            endpoint_url=endpoint_url,
            base_path=""
        )

    @pytest.fixture
    def test_content(self):
        """测试文件内容"""
        return b"Hello, S3 via MinIO! This is a test file."

    @pytest.mark.asyncio
    async def test_save_and_load(self, storage, test_content):
        """测试保存和加载文件"""
        path = "test/file.txt"

        # 保存文件
        with io.BytesIO(test_content) as f:
            result = await storage.save(path, f)

        assert result['path'] == path
        assert result['size'] == len(test_content)
        assert result['bucket'] == storage.bucket_name
        assert result['etag'] is not None

        # 加载文件
        content = await storage.load(path)
        assert content == test_content

        # 验证文件存在
        assert await storage.exists(path) is True

    @pytest.mark.asyncio
    async def test_save_with_metadata(self, storage, test_content):
        """测试保存带元数据的文件"""
        path = "test/metadata.txt"
        metadata = {
            'author': 'test_user',
            'version': '1.0.0',
            'description': 'test_file'
        }

        with io.BytesIO(test_content) as f:
            result = await storage.save(path, f, metadata)

        assert result['metadata'] is not None

        # 验证元数据
        file_metadata = await storage.get_metadata(path)
        assert file_metadata['metadata'] is not None

    @pytest.mark.asyncio
    async def test_delete(self, storage, test_content):
        """测试删除文件"""
        path = "test/delete.txt"

        # 保存文件
        with io.BytesIO(test_content) as f:
            await storage.save(path, f)

        assert await storage.exists(path) is True

        # 删除文件
        result = await storage.delete(path)
        assert result is True

        assert await storage.exists(path) is False

    @pytest.mark.asyncio
    async def test_list_files(self, storage, test_content):
        """测试列出文件"""
        files = [
            "dir1/file1.txt",
            "dir1/file2.txt",
            "dir2/file3.txt",
            "root.txt"
        ]

        for file_path in files:
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)

        # 列出所有文件
        all_files = await storage.list()

        # 获取文件路径列表
        file_paths = [f['path'] for f in all_files]

        # 验证所有预期文件都在列表中
        for expected_file in files:
            assert expected_file in file_paths

        # 列出指定目录下的文件
        dir1_files = await storage.list(prefix="dir1")
        dir1_paths = [f['path'] for f in dir1_files]

        assert "dir1/file1.txt" in dir1_paths
        assert "dir1/file2.txt" in dir1_paths

    @pytest.mark.asyncio
    async def test_copy(self, storage, test_content):
        """测试复制文件"""
        source = "source.txt"
        dest = "dest.txt"

        # 保存源文件
        with io.BytesIO(test_content) as f:
            await storage.save(source, f)

        # 复制文件
        result = await storage.copy(source, dest)
        assert result['source'] == source
        assert result['destination'] == dest

        # 验证目标文件存在
        assert await storage.exists(dest) is True

        # 验证内容一致
        content = await storage.load(dest)
        assert content == test_content

    @pytest.mark.asyncio
    async def test_move(self, storage, test_content):
        """测试移动文件"""
        source = "source.txt"
        dest = "dest.txt"

        # 保存源文件
        with io.BytesIO(test_content) as f:
            await storage.save(source, f)

        # 移动文件
        result = await storage.move(source, dest)
        assert result['source'] == source
        assert result['destination'] == dest

        # 验证源文件不存在
        assert await storage.exists(source) is False

        # 验证目标文件存在
        assert await storage.exists(dest) is True

        # 验证内容一致
        content = await storage.load(dest)
        assert content == test_content

    @pytest.mark.asyncio
    async def test_get_signed_url(self, storage, test_content):
        """测试获取签名URL"""
        path = "test/url.txt"

        # 保存文件
        with io.BytesIO(test_content) as f:
            await storage.save(path, f)

        # 获取签名URL
        url = await storage.get_signed_url(path)
        assert url is not None
        # MinIO 签名URL 包含特定参数
        assert "X-Amz" in url or "AWSAccessKeyId" in url

    @pytest.mark.asyncio
    async def test_file_not_found(self, storage):
        """测试文件不存在时的错误处理"""
        path = "nonexistent.txt"

        assert await storage.exists(path) is False

        with pytest.raises(Exception):
            await storage.load(path)

        result = await storage.delete(path)
        assert result is False


class TestS3StorageWithBasePath:
    """S3存储基础路径测试（使用 MinIO）"""

    @pytest.fixture(scope="module")
    def minio_container(self):
        """启动 MinIO 容器"""
        with MinioContainer() as minio:
            yield minio

    @pytest.fixture
    def storage(self, minio_container):
        """创建带基础路径的 S3 存储"""
        host = minio_container.get_container_host_ip()
        port = minio_container.get_exposed_port(9000)
        endpoint_url = f"http://{host}:{port}"

        return S3Storage(
            bucket_name="test-bucket",
            aws_access_key_id="minioadmin",
            aws_secret_access_key="minioadmin",
            region_name="us-east-1",
            endpoint_url=endpoint_url,
            base_path="models"
        )

    @pytest.fixture
    def test_content(self):
        return b"Test content for base path"

    @pytest.mark.asyncio
    async def test_save_with_base_path(self, storage, test_content):
        """测试带基础路径的保存"""
        path = "model_v1.pkl"

        with io.BytesIO(test_content) as f:
            result = await storage.save(path, f)

        # 完整路径应该包含 base_path
        assert result['path'].startswith("models/")
        assert result['path'].endswith(path)

    @pytest.mark.asyncio
    async def test_load_with_base_path(self, storage, test_content):
        """测试带基础路径的加载"""
        path = "model_v1.pkl"

        # 保存
        with io.BytesIO(test_content) as f:
            await storage.save(path, f)

        # 加载（使用相对路径）
        content = await storage.load(path)
        assert content == test_content

    @pytest.mark.asyncio
    async def test_list_with_base_path(self, storage, test_content):
        """测试带基础路径的列出文件"""
        files = [
            "dir1/file1.txt",
            "dir1/file2.txt",
            "dir2/file3.txt",
            "root.txt"
        ]

        for file_path in files:
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)

        # 列出所有文件
        all_files = await storage.list()

        # 验证路径包含 base_path
        for f in all_files:
            assert f['path'].startswith("models/")

        # 验证所有预期文件都在列表中
        expected_paths = [f"models/{file}" for file in files]
        actual_paths = [f['path'] for f in all_files]

        for expected in expected_paths:
            assert expected in actual_paths