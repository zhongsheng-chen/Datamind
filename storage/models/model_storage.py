# datamind/storage/models/model_storage.py
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
from datetime import datetime
import json
import tempfile

from storage.base import StorageBackend
from storage.local_storage import LocalStorage
from core.logging import log_manager, get_request_id, debug_print
from config.settings import settings


class ModelStorage:
    """
    模型存储管理器

    统一管理模型文件的存储、版本和元数据
    """

    def __init__(self, storage_backend: Optional[StorageBackend] = None):
        """
        初始化模型存储

        Args:
            storage_backend: 存储后端，默认为本地存储
        """
        if storage_backend:
            self.storage = storage_backend
        else:
            # 默认使用本地存储
            self.storage = LocalStorage(
                root_path=settings.MODELS_PATH,
                base_path="models"
            )

        debug_print("ModelStorage", f"模型存储初始化完成")

    async def save_model(self, model_id: str, version: str,
                         model_file: BinaryIO, framework: str,
                         metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        保存模型文件

        Args:
            model_id: 模型ID
            version: 版本号
            model_file: 模型文件
            framework: 框架类型
            metadata: 元数据

        Returns:
            保存结果
        """
        # 确定文件扩展名
        ext_map = {
            'sklearn': '.pkl',
            'xgboost': '.json',
            'lightgbm': '.txt',
            'torch': '.pt',
            'tensorflow': '.h5',
            'onnx': '.onnx',
            'catboost': '.cbm'
        }
        ext = ext_map.get(framework, '.bin')

        # 构建存储路径
        path = f"{model_id}/versions/model_{version}{ext}"

        # 准备元数据
        if not metadata:
            metadata = {}
        metadata.update({
            'model_id': model_id,
            'version': version,
            'framework': framework,
            'saved_at': datetime.now().isoformat()
        })

        # 保存文件
        result = await self.storage.save(path, model_file, metadata)

        # 更新latest符号链接
        latest_path = f"{model_id}/latest{ext}"
        await self.storage.copy(path, latest_path)

        debug_print("ModelStorage", f"模型保存成功: {model_id} v{version}")

        return result

    async def load_model(self, model_id: str, version: Optional[str] = None) -> bytes:
        """
        加载模型文件

        Args:
            model_id: 模型ID
            version: 版本号，None表示最新版本

        Returns:
            模型文件内容
        """
        if version:
            # 查找指定版本
            files = await self.storage.list(prefix=f"{model_id}/versions/")
            for f in files:
                if f['path'].endswith(f"model_{version}"):
                    return await self.storage.load(f['path'])
            raise FileNotFoundError(f"未找到模型 {model_id} 版本 {version}")
        else:
            # 加载最新版本
            files = await self.storage.list(prefix=f"{model_id}/")
            latest_files = [f for f in files if 'latest' in f['path']]
            if latest_files:
                return await self.storage.load(latest_files[0]['path'])
            raise FileNotFoundError(f"未找到模型 {model_id}")

    async def delete_model(self, model_id: str, version: Optional[str] = None) -> bool:
        """
        删除模型

        Args:
            model_id: 模型ID
            version: 版本号，None表示删除所有版本
        """
        if version:
            # 删除指定版本
            files = await self.storage.list(prefix=f"{model_id}/versions/")
            for f in files:
                if f['path'].endswith(f"model_{version}"):
                    await self.storage.delete(f['path'])
                    debug_print("ModelStorage", f"删除模型版本: {model_id} v{version}")
                    return True
            return False
        else:
            # 删除所有版本
            files = await self.storage.list(prefix=f"{model_id}/")
            for f in files:
                await self.storage.delete(f['path'])
            debug_print("ModelStorage", f"删除所有模型版本: {model_id}")
            return True

    async def list_models(self, prefix: str = "") -> List[Dict[str, Any]]:
        """列出所有模型"""
        files = await self.storage.list(prefix=prefix)

        # 按模型分组
        models = {}
        for f in files:
            parts = f['path'].split('/')
            if len(parts) >= 1:
                model_id = parts[0]
                if model_id not in models:
                    models[model_id] = {
                        'model_id': model_id,
                        'versions': [],
                        'latest': None
                    }

                if 'versions' in f['path']:
                    models[model_id]['versions'].append(f)
                elif 'latest' in f['path']:
                    models[model_id]['latest'] = f

        return list(models.values())

    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """获取模型信息"""
        files = await self.storage.list(prefix=f"{model_id}/")

        versions = []
        latest = None

        for f in files:
            if 'versions' in f['path']:
                versions.append(f)
            elif 'latest' in f['path']:
                latest = f

        return {
            'model_id': model_id,
            'versions': versions,
            'latest': latest,
            'version_count': len(versions)
        }

    async def get_signed_url(self, model_id: str, version: Optional[str] = None) -> str:
        """获取模型下载签名URL"""
        if version:
            path = f"{model_id}/versions/model_{version}"
        else:
            path = f"{model_id}/latest"

        # 查找实际文件
        files = await self.storage.list(prefix=path)
        if not files:
            raise FileNotFoundError(f"未找到模型: {model_id}")

        return await self.storage.get_signed_url(files[0]['path'])

    async def migrate_model(self, model_id: str, target_storage: StorageBackend) -> Dict[str, Any]:
        """
        迁移模型到其他存储后端

        Args:
            model_id: 模型ID
            target_storage: 目标存储后端
        """
        # 获取所有版本
        info = await self.get_model_info(model_id)

        migrated = []
        for version in info['versions']:
            # 下载文件
            content = await self.storage.load(version['path'])

            # 创建临时文件
            with tempfile.NamedTemporaryFile() as tmp:
                tmp.write(content)
                tmp.flush()

                # 上传到目标存储
                with open(tmp.name, 'rb') as f:
                    result = await target_storage.save(
                        version['path'],
                        f,
                        version.get('metadata')
                    )
                    migrated.append(result)

        debug_print("ModelStorage", f"模型迁移成功: {model_id}, {len(migrated)}个版本")

        return {
            'model_id': model_id,
            'migrated_versions': migrated
        }