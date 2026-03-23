# tests/storage/test_local_storage.py

"""本地存储测试

测试 LocalStorage 的各项功能，包括文件保存、加载、删除、复制、移动等操作。
"""

import io
import tempfile
import shutil
import pytest
from pathlib import Path

from datamind.storage.local_storage import LocalStorage


class TestLocalStorage:
    """本地存储测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def storage(self, temp_dir):
        """创建本地存储实例"""
        return LocalStorage(root_path=temp_dir)

    @pytest.fixture
    def test_content(self):
        """测试文件内容"""
        return b"Hello, World! This is a test file."

    @pytest.mark.asyncio
    async def test_save_and_load(self, storage, test_content):
        """测试保存和加载文件"""
        path = "test/file.txt"

        # 保存文件
        with io.BytesIO(test_content) as f:
            result = await storage.save(path, f)

        assert result['path'] == path
        assert result['size'] == len(test_content)
        assert result['hash'] is not None

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
            'description': '测试文件'
        }

        with io.BytesIO(test_content) as f:
            result = await storage.save(path, f, metadata)

        assert result['metadata'] is not None

        # 验证元数据
        file_metadata = await storage.get_metadata(path)
        assert file_metadata['custom'] is not None

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

        # 列出所有文件（空前缀列出根目录下的所有文件）
        all_files = await storage.list()
        assert len(all_files) == len(files)

        # 列出指定目录下的文件
        dir1_files = await storage.list(prefix="dir1")
        assert len(dir1_files) == 2

        # 列出另一个目录下的文件
        dir2_files = await storage.list(prefix="dir2")
        assert len(dir2_files) == 1

        # 列出根目录下的文件
        root_files = [f for f in all_files if f['path'] == "root.txt"]
        assert len(root_files) == 1

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
        assert url.startswith("file://")
        assert path in url

    @pytest.mark.asyncio
    async def test_file_not_found(self, storage):
        """测试文件不存在时的错误处理"""
        path = "nonexistent.txt"

        assert await storage.exists(path) is False

        with pytest.raises(FileNotFoundError):
            await storage.load(path)

        result = await storage.delete(path)
        assert result is False

    @pytest.mark.asyncio
    async def test_list_files_with_nested_structure(self, storage, test_content):
        """测试嵌套目录结构列出文件"""
        # 保存嵌套目录中的文件
        nested_files = [
            "project/src/main.py",
            "project/src/utils.py",
            "project/tests/test_main.py",
            "project/README.md",
            "docs/guide.md"
        ]

        for file_path in nested_files:
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)

        # 列出所有文件
        all_files = await storage.list()
        assert len(all_files) == len(nested_files)

        # 列出 project 目录下的所有文件
        project_files = await storage.list(prefix="project")
        assert len(project_files) == 4

        # 列出 project/src 目录下的文件
        src_files = await storage.list(prefix="project/src")
        assert len(src_files) == 2

        # 列出 docs 目录下的文件
        docs_files = await storage.list(prefix="docs")
        assert len(docs_files) == 1


class TestLocalStorageBasePath:
    """本地存储基础路径测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def storage(self, temp_dir):
        """创建带基础路径的本地存储"""
        return LocalStorage(root_path=temp_dir, base_path="models")

    @pytest.fixture
    def test_content(self):
        """测试文件内容"""
        return b"Test content"

    @pytest.mark.asyncio
    async def test_save_with_base_path(self, storage, test_content):
        """测试带基础路径的保存"""
        path = "model_v1.pkl"

        with io.BytesIO(test_content) as f:
            result = await storage.save(path, f)

        # 完整路径应该包含 base_path
        assert "models" in result['path']
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
        # 由于 base_path 存在，所有文件路径都会包含 "models/" 前缀
        assert len(all_files) == len(files)

        # 验证路径包含 base_path
        for f in all_files:
            assert f['path'].startswith("models/")

        # 列出指定目录（相对于 base_path）
        dir1_files = await storage.list(prefix="dir1")
        assert len(dir1_files) == 2
        for f in dir1_files:
            assert f['path'].startswith("models/dir1/")