# tests/storage/test_model_storage.py

"""模型存储测试

测试 ModelStorage 的各项功能，包括模型保存、加载、删除、列表等操作。
"""

import io
import tempfile
import shutil
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from datamind.storage.models.model_storage import ModelStorage
from datamind.storage.local_storage import LocalStorage
from datamind.core.domain.enums import AuditAction


class TestModelStorage:
    """模型存储测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def storage_backend(self, temp_dir):
        """创建存储后端"""
        return LocalStorage(root_path=temp_dir)

    @pytest.fixture
    def model_storage(self, storage_backend):
        """创建模型存储实例"""
        return ModelStorage(storage_backend=storage_backend)

    @pytest.fixture
    def model_content(self):
        """测试模型文件内容"""
        return b"Mock model binary content"

    @pytest.mark.asyncio
    async def test_save_model(self, model_storage, model_content):
        """测试保存模型"""
        model_id = "test_model"
        version = "1.0.0"
        framework = "sklearn"

        with io.BytesIO(model_content) as f:
            result = await model_storage.save_model(
                model_id=model_id,
                version=version,
                model_file=f,
                framework=framework,
                metadata={"description": "测试模型"}
            )

        assert result['path'] is not None
        assert result['size'] == len(model_content)
        assert model_id in result['path']
        assert version in result['path']

    @pytest.mark.asyncio
    async def test_load_model_by_version(self, model_storage, model_content):
        """测试按版本加载模型"""
        model_id = "test_model"
        version = "1.0.0"

        # 保存模型
        with io.BytesIO(model_content) as f:
            await model_storage.save_model(
                model_id=model_id,
                version=version,
                model_file=f,
                framework="sklearn"
            )

        # 加载模型
        content = await model_storage.load_model(model_id, version=version)
        assert content == model_content

    @pytest.mark.asyncio
    async def test_load_model_latest(self, model_storage, model_content):
        """测试加载最新版本模型"""
        model_id = "test_model"

        # 保存多个版本
        versions = ["1.0.0", "1.1.0", "2.0.0"]
        for version in versions:
            with io.BytesIO(model_content) as f:
                await model_storage.save_model(
                    model_id=model_id,
                    version=version,
                    model_file=f,
                    framework="sklearn"
                )

        # 加载最新版本
        content = await model_storage.load_model(model_id)
        assert content == model_content

    @pytest.mark.asyncio
    async def test_delete_model_version(self, model_storage, model_content):
        """测试删除指定版本"""
        model_id = "test_model"
        version = "1.0.0"

        # 保存模型
        with io.BytesIO(model_content) as f:
            await model_storage.save_model(
                model_id=model_id,
                version=version,
                model_file=f,
                framework="sklearn"
            )

        # 删除版本
        result = await model_storage.delete_model(model_id, version=version)
        assert result is True

        # 验证版本已删除
        with pytest.raises(Exception):
            await model_storage.load_model(model_id, version=version)

    @pytest.mark.asyncio
    async def test_delete_all_versions(self, model_storage, model_content):
        """测试删除所有版本"""
        model_id = "test_model"
        versions = ["1.0.0", "1.1.0", "2.0.0"]

        # 保存多个版本
        for version in versions:
            with io.BytesIO(model_content) as f:
                await model_storage.save_model(
                    model_id=model_id,
                    version=version,
                    model_file=f,
                    framework="sklearn"
                )

        # 删除所有版本
        result = await model_storage.delete_model(model_id)
        assert result is True

        # 验证所有版本已删除
        with pytest.raises(Exception):
            await model_storage.load_model(model_id)

    @pytest.mark.asyncio
    async def test_list_models(self, model_storage, model_content):
        """测试列出模型"""
        models = [
            ("model_a", "1.0.0"),
            ("model_a", "1.1.0"),
            ("model_b", "1.0.0"),
        ]

        for model_id, version in models:
            with io.BytesIO(model_content) as f:
                await model_storage.save_model(
                    model_id=model_id,
                    version=version,
                    model_file=f,
                    framework="sklearn"
                )

        # 列出所有模型
        model_list = await model_storage.list_models()
        assert len(model_list) == 2  # model_a 和 model_b

        # 验证模型信息
        model_a = next(m for m in model_list if m['model_id'] == "model_a")
        assert len(model_a['versions']) == 2

    @pytest.mark.asyncio
    async def test_get_model_info(self, model_storage, model_content):
        """测试获取模型信息"""
        model_id = "test_model"
        versions = ["1.0.0", "1.1.0"]

        for version in versions:
            with io.BytesIO(model_content) as f:
                await model_storage.save_model(
                    model_id=model_id,
                    version=version,
                    model_file=f,
                    framework="sklearn"
                )

        info = await model_storage.get_model_info(model_id)
        assert info['model_id'] == model_id
        assert info['version_count'] == 2
        assert len(info['versions']) == 2

    @pytest.mark.asyncio
    async def test_get_signed_url(self, model_storage, model_content):
        """测试获取模型签名URL"""
        model_id = "test_model"
        version = "1.0.0"

        with io.BytesIO(model_content) as f:
            await model_storage.save_model(
                model_id=model_id,
                version=version,
                model_file=f,
                framework="sklearn"
            )

        url = await model_storage.get_signed_url(model_id, version=version)
        assert url.startswith("file://")
        assert model_id in url
        assert version in url