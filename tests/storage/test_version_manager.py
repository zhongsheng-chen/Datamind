# tests/storage/test_version_manager.py

"""版本管理器测试

测试 VersionManager 的各项功能，包括版本添加、删除、查询、回滚等操作。
"""

import io
import tempfile
import shutil
import pytest

from datamind.storage.models.version_manager import VersionManager
from datamind.storage.local_storage import LocalStorage


class TestVersionManager:
    """版本管理器测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def storage(self, temp_dir):
        """创建存储后端"""
        return LocalStorage(root_path=temp_dir)

    @pytest.fixture
    def version_manager(self, storage):
        """创建版本管理器"""
        return VersionManager(storage=storage, model_id="test_model")

    @pytest.fixture
    def test_content(self):
        """测试文件内容"""
        return b"Mock model binary content"

    @pytest.mark.asyncio
    async def test_init_versions(self, version_manager):
        """测试初始化版本记录"""
        versions_data = await version_manager.init_versions()

        assert versions_data['model_id'] == "test_model"
        assert versions_data['total_versions'] == 0
        assert versions_data['latest_version'] is None
        assert versions_data['versions'] == []

    @pytest.mark.asyncio
    async def test_add_version(self, version_manager, storage, test_content):
        """测试添加版本"""
        version = "1.0.0"
        file_path = "models/test_model/versions/model_1.0.0.pkl"

        # 先保存文件
        with io.BytesIO(test_content) as f:
            await storage.save(file_path, f)

        # 添加版本
        version_info = await version_manager.add_version(
            version=version,
            file_path=file_path,
            metadata={"description": "初始版本"},
            is_production=True
        )

        assert version_info['version'] == version
        assert version_info['is_production'] is True
        assert version_info['file_size'] == len(test_content)

        # 验证版本已添加
        versions_data = await version_manager._get_versions()
        assert versions_data['total_versions'] == 1
        assert versions_data['latest_version'] == version

    @pytest.mark.asyncio
    async def test_get_version(self, version_manager, storage, test_content):
        """测试获取版本信息"""
        version = "1.0.0"
        file_path = "models/test_model/versions/model_1.0.0.pkl"

        with io.BytesIO(test_content) as f:
            await storage.save(file_path, f)

        await version_manager.add_version(version, file_path)

        # 获取指定版本
        version_info = await version_manager.get_version(version)
        assert version_info['version'] == version

        # 获取最新版本
        latest_info = await version_manager.get_version()
        assert latest_info['version'] == version

    @pytest.mark.asyncio
    async def test_list_versions(self, version_manager, storage, test_content):
        """测试列出所有版本"""
        versions = ["1.0.0", "1.1.0", "2.0.0"]

        for v in versions:
            file_path = f"models/test_model/versions/model_{v}.pkl"
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)
            await version_manager.add_version(v, file_path)

        # 列出版本（精简信息）
        version_list = await version_manager.list_versions()
        assert len(version_list) == 3

        # 列出版本（包含元数据）
        full_list = await version_manager.list_versions(include_metadata=True)
        assert len(full_list) == 3
        assert 'file_hash' in full_list[0]

    @pytest.mark.asyncio
    async def test_delete_version(self, version_manager, storage, test_content):
        """测试删除版本"""
        version = "1.0.0"
        file_path = f"models/test_model/versions/model_{version}.pkl"

        with io.BytesIO(test_content) as f:
            await storage.save(file_path, f)

        await version_manager.add_version(version, file_path)

        # 删除版本
        result = await version_manager.delete_version(version)
        assert result is True

        # 验证版本已删除
        with pytest.raises(ValueError):
            await version_manager.get_version(version)

    @pytest.mark.asyncio
    async def test_set_production_version(self, version_manager, storage, test_content):
        """测试设置生产版本"""
        versions = ["1.0.0", "1.1.0", "2.0.0"]

        for v in versions:
            file_path = f"models/test_model/versions/model_{v}.pkl"
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)
            await version_manager.add_version(v, file_path)

        # 设置生产版本
        prod_version = await version_manager.set_production_version("1.1.0")
        assert prod_version['is_production'] is True

        # 验证其他版本不是生产版本
        v1 = await version_manager.get_version("1.0.0")
        assert v1['is_production'] is False

        v2 = await version_manager.get_version("2.0.0")
        assert v2['is_production'] is False

    @pytest.mark.asyncio
    async def test_get_production_version(self, version_manager, storage, test_content):
        """测试获取生产版本"""
        versions = ["1.0.0", "1.1.0"]

        for v in versions:
            file_path = f"models/test_model/versions/model_{v}.pkl"
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)
            await version_manager.add_version(v, file_path)

        # 初始时没有生产版本
        prod_version = await version_manager.get_production_version()
        assert prod_version is None

        # 设置生产版本
        await version_manager.set_production_version("1.1.0")

        # 获取生产版本
        prod_version = await version_manager.get_production_version()
        assert prod_version['version'] == "1.1.0"

    @pytest.mark.asyncio
    async def test_compare_versions(self, version_manager):
        """测试版本比较"""
        result = await version_manager.compare_versions("1.0.0", "1.1.0")
        assert result['v1_lt_v2'] is True
        assert result['major_diff'] == 0
        assert result['minor_diff'] == -1

        result = await version_manager.compare_versions("2.0.0", "1.9.9")
        assert result['v1_gt_v2'] is True
        assert result['major_diff'] == 1

    @pytest.mark.asyncio
    async def test_rollback_to_version(self, version_manager, storage, test_content):
        """测试版本回滚"""
        versions = ["1.0.0", "1.1.0", "1.2.0"]

        for v in versions:
            file_path = f"models/test_model/versions/model_{v}.pkl"
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)
            await version_manager.add_version(v, file_path)

        # 获取当前版本数
        before_count = len(await version_manager.list_versions())

        # 回滚到 1.0.0
        rollback_info = await version_manager.rollback_to_version("1.0.0")
        assert rollback_info['version'].endswith("-rollback")

        # 验证新版本已添加
        after_count = len(await version_manager.list_versions())
        assert after_count == before_count + 1

    @pytest.mark.asyncio
    async def test_tag_version(self, version_manager, storage, test_content):
        """测试版本标签"""
        version = "1.0.0"
        file_path = f"models/test_model/versions/model_{version}.pkl"

        with io.BytesIO(test_content) as f:
            await storage.save(file_path, f)

        await version_manager.add_version(version, file_path)

        # 添加标签
        await version_manager.tag_version(version, "stable")
        await version_manager.tag_version(version, "release")

        # 验证标签
        version_info = await version_manager.get_version(version)
        assert "stable" in version_info['tags']
        assert "release" in version_info['tags']

    @pytest.mark.asyncio
    async def test_get_versions_by_tag(self, version_manager, storage, test_content):
        """测试根据标签获取版本"""
        versions = ["1.0.0", "1.1.0", "2.0.0"]

        for v in versions:
            file_path = f"models/test_model/versions/model_{v}.pkl"
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)
            await version_manager.add_version(v, file_path)

        # 添加标签
        await version_manager.tag_version("1.0.0", "stable")
        await version_manager.tag_version("1.1.0", "stable")

        # 根据标签获取版本
        tagged_versions = await version_manager.get_versions_by_tag("stable")
        assert len(tagged_versions) == 2

    @pytest.mark.asyncio
    async def test_increment_download_count(self, version_manager, storage, test_content):
        """测试增加下载计数"""
        version = "1.0.0"
        file_path = f"models/test_model/versions/model_{version}.pkl"

        with io.BytesIO(test_content) as f:
            await storage.save(file_path, f)

        await version_manager.add_version(version, file_path)

        # 增加下载计数
        count = await version_manager.increment_download_count(version)
        assert count == 1

        count = await version_manager.increment_download_count(version)
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_version_stats(self, version_manager, storage, test_content):
        """测试获取版本统计信息"""
        versions = ["1.0.0", "1.1.0", "2.0.0"]

        for v in versions:
            file_path = f"models/test_model/versions/model_{v}.pkl"
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)
            await version_manager.add_version(v, file_path)

        # 增加下载计数
        await version_manager.increment_download_count("1.0.0")
        await version_manager.increment_download_count("1.0.0")
        await version_manager.increment_download_count("1.1.0")

        # 获取统计信息
        stats = await version_manager.get_version_stats()
        assert stats['total_versions'] == 3
        assert stats['latest_version'] == "2.0.0"
        assert stats['total_downloads'] == 3
        assert stats['major_version_distribution']['1'] == 2
        assert stats['major_version_distribution']['2'] == 1

    @pytest.mark.asyncio
    async def test_cleanup_old_versions(self, version_manager, storage, test_content):
        """测试清理旧版本"""
        versions = ["1.0.0", "1.1.0", "1.2.0", "1.3.0", "1.4.0"]

        for v in versions:
            file_path = f"models/test_model/versions/model_{v}.pkl"
            with io.BytesIO(test_content) as f:
                await storage.save(file_path, f)
            await version_manager.add_version(v, file_path)

        # 清理旧版本，保留最近2个
        deleted = await version_manager.cleanup_old_versions(keep_count=2)
        assert len(deleted) == 3  # 1.0.0, 1.1.0, 1.2.0 被删除

        # 验证剩余版本
        remaining = await version_manager.list_versions()
        assert len(remaining) == 2
        assert remaining[0]['version'] == "1.4.0"
        assert remaining[1]['version'] == "1.3.0"