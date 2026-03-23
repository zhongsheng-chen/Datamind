# tests/storage/test_minio_storage.py

"""MinIO 存储测试

测试 MinIOStorage 的各项功能，包括文件保存、加载、删除、复制、移动等操作。
使用 testcontainers 启动真实的 MinIO 容器进行测试，需要 Docker 环境支持。
"""

import io
import pytest
from testcontainers.minio import MinioContainer

from datamind.storage.minio_storage import MinIOStorage


class TestMinIOStorageReal:
    """MinIO真实存储测试类"""

    @pytest.fixture(scope="module")
    def minio_container(self):
        """启动 MinIO 容器"""
        with MinioContainer() as minio:
            yield minio

    @pytest.fixture
    def storage(self, minio_container):
        """创建 MinIO 存储实例"""
        host = minio_container.get_container_host_ip()
        port = minio_container.get_exposed_port(9000)
        endpoint = f"{host}:{port}"

        return MinIOStorage(
            endpoint=endpoint,
            bucket_name="test-bucket",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False,
            base_path=""
        )

    @pytest.fixture
    def test_content(self):
        """测试文件内容"""
        return b"Hello, MinIO! This is a test file."

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
            'description': 'test_file'  # 使用 ASCII 字符
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
        # 保存多个文件
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
            assert expected_file in file_paths, f"Expected file {expected_file} not found"

        # 验证文件数量至少包含预期文件（可能还有目录条目）
        assert len(all_files) >= len(files)

        # 列出指定目录下的文件
        dir1_files = await storage.list(prefix="dir1")
        dir1_paths = [f['path'] for f in dir1_files]

        # 验证目录下的文件
        assert "dir1/file1.txt" in dir1_paths
        assert "dir1/file2.txt" in dir1_paths
        assert len(dir1_files) >= 2

        # 列出另一个目录下的文件
        dir2_files = await storage.list(prefix="dir2")
        dir2_paths = [f['path'] for f in dir2_files]

        assert "dir2/file3.txt" in dir2_paths
        assert len(dir2_files) >= 1

        # 列出根目录下的文件
        root_files = await storage.list(prefix="")
        root_paths = [f['path'] for f in root_files]

        # 验证根目录下的文件存在
        assert "root.txt" in root_paths

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
        assert "X-Amz" in url or "AWSAccessKeyId" in url

    @pytest.mark.asyncio
    async def test_get_upload_url(self, storage, test_content):
        """测试获取上传签名URL"""
        path = "test/upload.txt"

        # 获取上传URL
        url = await storage.get_upload_url(path)
        assert url is not None
        assert "X-Amz" in url or "AWSAccessKeyId" in url

    @pytest.mark.asyncio
    async def test_get_object_info(self, storage, test_content):
        """测试获取对象详细信息"""
        path = "test/info.txt"

        with io.BytesIO(test_content) as f:
            await storage.save(path, f)

        info = await storage.get_object_info(path)
        assert info['path'] == path
        assert info['size'] == len(test_content)
        assert info['bucket'] == storage.bucket_name
        assert info['etag'] is not None

    @pytest.mark.asyncio
    async def test_file_not_found(self, storage):
        """测试文件不存在时的错误处理"""
        path = "nonexistent.txt"

        assert await storage.exists(path) is False

        with pytest.raises(Exception):
            await storage.load(path)

        result = await storage.delete(path)
        assert result is False


class TestMinIOStorageWithBasePath:
    """MinIO存储基础路径测试"""

    @pytest.fixture(scope="module")
    def minio_container(self):
        """启动 MinIO 容器"""
        with MinioContainer() as minio:
            yield minio

    @pytest.fixture
    def storage(self, minio_container):
        """创建带基础路径的 MinIO 存储"""
        host = minio_container.get_container_host_ip()
        port = minio_container.get_exposed_port(9000)
        endpoint = f"{host}:{port}"

        return MinIOStorage(
            endpoint=endpoint,
            bucket_name="test-bucket",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False,
            base_path="models"
        )

    @pytest.fixture
    def test_content(self):
        """测试文件内容"""
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
            assert expected in actual_paths, f"Expected file {expected} not found"

        # 验证文件数量至少包含预期文件
        assert len(all_files) >= len(files)

        # 列出指定目录（相对于 base_path）
        dir1_files = await storage.list(prefix="dir1")
        dir1_expected = [f"models/dir1/file1.txt", f"models/dir1/file2.txt"]
        dir1_actual = [f['path'] for f in dir1_files]

        for expected in dir1_expected:
            assert expected in dir1_actual, f"Expected {expected} not found in dir1"
        assert len(dir1_files) >= 2

        # 验证路径格式
        for f in dir1_files:
            assert f['path'].startswith("models/dir1/")