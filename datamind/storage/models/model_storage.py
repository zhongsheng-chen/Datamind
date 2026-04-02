# datamind/storage/models/model_storage.py

"""模型存储管理器

统一管理模型文件的存储、版本和元数据，提供模型文件的上传、下载、删除、迁移等功能。

功能特性：
  - 模型保存：自动按框架确定文件扩展名，支持自定义元数据
  - 模型加载：支持按版本加载或加载最新版本
  - 模型删除：支持删除指定版本或删除所有版本
  - 模型列表：按模型ID分组列出所有模型及其版本
  - 模型信息：获取模型的版本列表和最新版本信息
  - 签名URL：生成模型下载的签名URL
  - 模型迁移：将模型从一个存储后端迁移到另一个存储后端
  - 完整审计：记录所有模型存储操作到审计日志
  - 链路追踪：完整的 trace_id, span_id, parent_span_id

使用示例：
    storage = ModelStorage()

    # 保存模型
    with open("model.pkl", "rb") as f:
        result = await storage.save_model(
            model_id="model_001",
            version="1.0.0",
            model_file=f,
            framework="sklearn",
            metadata={"description": "测试模型"}
        )

    # 加载模型
    content = await storage.load_model("model_001", version="1.0.0")

    # 获取签名URL
    url = await storage.get_signed_url("model_001")
"""


import tempfile
from typing import Optional, Dict, Any, List, BinaryIO
from datetime import datetime

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.storage.base import StorageBackend
from datamind.storage.local_storage import LocalStorage
from datamind.config import get_settings

logger = get_logger(__name__)


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
        settings = get_settings()

        if storage_backend:
            self.storage = storage_backend
        else:
            # 默认使用本地存储
            self.storage = LocalStorage(
                root_path=settings.model.models_path,
                base_path="models"
            )

        logger.debug("模型存储初始化完成")

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
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

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

        log_audit(
            action=AuditAction.MODEL_SAVE.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": model_id,
                "version": version,
                "framework": framework,
                "storage_type": type(self.storage).__name__,
                "path": path,
                "size": result.get('size', 0),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger.debug("模型保存成功: %s v%s", model_id, version)

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
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            if version:
                # 查找指定版本
                files = await self.storage.list(prefix=f"{model_id}/versions/")
                for f in files:
                    # 从路径中提取文件名
                    file_name = f['path'].split('/')[-1]

                    # 检查文件名是否以 model_{version} 开头（可能有扩展名）
                    if file_name.startswith(f"model_{version}"):
                        content = await self.storage.load(f['path'])

                        log_audit(
                            action=AuditAction.MODEL_LOAD.value,
                            user_id="system",
                            ip_address=None,
                            details={
                                "model_id": model_id,
                                "version": version,
                                "storage_type": type(self.storage).__name__,
                                "path": f['path'],
                                "size": len(content),
                                "trace_id": trace_id,
                                "span_id": span_id,
                                "parent_span_id": parent_span_id
                            },
                            request_id=request_id
                        )

                        return content
                raise FileNotFoundError(f"未找到模型 {model_id} 版本 {version}")
            else:
                # 加载最新版本
                files = await self.storage.list(prefix=f"{model_id}/")

                # 查找 latest 文件（可能是软链接或实际文件）
                latest_files = [f for f in files if 'latest' in f['path']]
                if latest_files:
                    content = await self.storage.load(latest_files[0]['path'])

                    log_audit(
                        action=AuditAction.MODEL_LOAD.value,
                        user_id="system",
                        ip_address=None,
                        details={
                            "model_id": model_id,
                            "version": "latest",
                            "storage_type": type(self.storage).__name__,
                            "path": latest_files[0]['path'],
                            "size": len(content),
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )

                    return content
                raise FileNotFoundError(f"未找到模型 {model_id}")

        except FileNotFoundError as e:
            log_audit(
                action=AuditAction.MODEL_LOAD.value,
                user_id="system",
                ip_address=None,
                details={
                    "model_id": model_id,
                    "version": version or "latest",
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    async def delete_model(self, model_id: str, version: Optional[str] = None) -> bool:
        """
        删除模型

        Args:
            model_id: 模型ID
            version: 版本号，None表示删除所有版本
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        if version:
            # 删除指定版本
            files = await self.storage.list(prefix=f"{model_id}/versions/")
            for f in files:
                # 从路径中提取文件名
                file_name = f['path'].split('/')[-1]

                # 检查文件名是否以 model_{version} 开头（可能有扩展名）
                if file_name.startswith(f"model_{version}"):
                    result = await self.storage.delete(f['path'])

                    log_audit(
                        action=AuditAction.MODEL_DELETE.value,
                        user_id="system",
                        ip_address=None,
                        details={
                            "model_id": model_id,
                            "version": version,
                            "storage_type": type(self.storage).__name__,
                            "path": f['path'],
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )

                    logger.debug("删除模型版本: %s v%s", model_id, version)
                    return result
            return False
        else:
            # 删除所有版本
            files = await self.storage.list(prefix=f"{model_id}/")
            deleted_count = 0
            for f in files:
                if await self.storage.delete(f['path']):
                    deleted_count += 1

            log_audit(
                action=AuditAction.MODEL_DELETE.value,
                user_id="system",
                ip_address=None,
                details={
                    "model_id": model_id,
                    "version": "all",
                    "storage_type": type(self.storage).__name__,
                    "deleted_count": deleted_count,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.debug("删除所有模型版本: %s", model_id)
            return True

    async def list_models(self, prefix: str = "") -> List[Dict[str, Any]]:
        """列出所有模型"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

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

        result = list(models.values())

        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id="system",
            ip_address=None,
            details={
                "prefix": prefix,
                "model_count": len(result),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return result

    async def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """获取模型信息"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        files = await self.storage.list(prefix=f"{model_id}/")

        versions = []
        latest = None

        for f in files:
            if 'versions' in f['path']:
                versions.append(f)
            elif 'latest' in f['path']:
                latest = f

        result = {
            'model_id': model_id,
            'versions': versions,
            'latest': latest,
            'version_count': len(versions)
        }

        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": model_id,
                "version_count": len(versions),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return result

    async def get_signed_url(self, model_id: str, version: Optional[str] = None) -> str:
        """获取模型下载签名URL"""
        if version:
            # 查找指定版本的文件
            files = await self.storage.list(prefix=f"{model_id}/versions/")
            for f in files:
                file_name = f['path'].split('/')[-1]
                if file_name.startswith(f"model_{version}"):
                    return await self.storage.get_signed_url(f['path'])
            raise FileNotFoundError(f"未找到模型 {model_id} 版本 {version}")
        else:
            # 查找最新版本
            files = await self.storage.list(prefix=f"{model_id}/")
            latest_files = [f for f in files if 'latest' in f['path']]
            if latest_files:
                return await self.storage.get_signed_url(latest_files[0]['path'])
            raise FileNotFoundError(f"未找到模型 {model_id}")

    async def migrate_model(self, model_id: str, target_storage: StorageBackend) -> Dict[str, Any]:
        """
        迁移模型到其他存储后端

        Args:
            model_id: 模型ID
            target_storage: 目标存储后端
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

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

        log_audit(
            action=AuditAction.MODEL_MIGRATE.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": model_id,
                "source_storage": type(self.storage).__name__,
                "target_storage": type(target_storage).__name__,
                "migrated_count": len(migrated),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger.debug("模型迁移成功: %s, %d个版本", model_id, len(migrated))

        return {
            'model_id': model_id,
            'migrated_versions': migrated
        }