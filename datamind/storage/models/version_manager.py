# datamind/storage/models/version_manager.py

"""模型版本管理器

管理模型的版本控制、版本比较、版本回滚等功能，遵循语义化版本规范 (Semantic Versioning)。

功能特性：
  - 版本管理：添加、删除、查询版本
  - 生产版本管理：设置和获取生产版本
  - 版本比较：比较两个版本的差异
  - 版本回滚：回滚到指定版本
  - 版本标签：给版本打标签，便于分类
  - 版本统计：获取版本统计信息
  - 版本清理：清理旧版本，释放存储空间
  - 完整审计：记录所有版本操作到审计日志
  - 链路追踪：完整的 trace_id, span_id, parent_span_id

使用示例：
    version_manager = VersionManager(storage, model_id="model_001")

    # 添加版本
    await version_manager.add_version("1.0.0", "models/model_001/versions/model_1.0.0.pkl")

    # 设置生产版本
    await version_manager.set_production_version("1.0.0")

    # 回滚到指定版本
    await version_manager.rollback_to_version("0.9.0")

    # 清理旧版本
    await version_manager.cleanup_old_versions(keep_count=5)
"""


import io
import json
import semver
from datetime import datetime
from typing import Dict, Any, Optional, List, BinaryIO


from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.storage.base import StorageBackend

logger = get_logger(__name__)


class VersionManager:
    """
    模型版本管理器

    管理模型的版本控制、版本比较、版本回滚等功能
    遵循语义化版本规范 (Semantic Versioning)
    """

    def __init__(self, storage: StorageBackend, model_id: str):
        """
        初始化版本管理器

        Args:
            storage: 存储后端
            model_id: 模型ID
        """
        self.storage = storage
        self.model_id = model_id
        self.metadata_file = f"{model_id}/versions.json"
        self._versions_cache = None
        logger.debug("初始化版本管理器: %s", model_id)

    async def init_versions(self) -> Dict[str, Any]:
        """初始化版本记录文件"""
        versions_data = {
            'model_id': self.model_id,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'versions': [],
            'latest_version': None,
            'total_versions': 0
        }

        # 创建空的版本记录文件
        await self._save_versions(versions_data)
        logger.debug("初始化版本记录: %s", self.model_id)
        return versions_data

    async def add_version(self, version: str, file_path: str,
                          metadata: Optional[Dict] = None,
                          is_production: bool = False) -> Dict[str, Any]:
        """
        添加新版本

        Args:
            version: 版本号 (遵循语义化版本，如 1.0.0)
            file_path: 模型文件路径
            metadata: 版本元数据
            is_production: 是否为生产版本

        Returns:
            版本信息
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        # 验证版本号格式
        if not self._validate_version(version):
            raise ValueError(f"无效的版本号格式: {version}，应为 x.y.z 格式")

        # 获取现有版本
        versions_data = await self._get_versions()

        # 检查版本是否已存在
        existing = self._find_version(versions_data, version)
        if existing:
            raise ValueError(f"版本 {version} 已存在")

        # 获取文件信息
        file_info = await self.storage.get_metadata(file_path)

        # 创建版本记录
        version_info = {
            'version': version,
            'file_path': file_path,
            'file_hash': file_info.get('hash') or file_info.get('etag', ''),
            'file_size': file_info['size'],
            'added_at': datetime.now().isoformat(),
            'is_production': is_production,
            'metadata': metadata or {},
            'download_count': 0,
            'tags': []
        }

        # 如果是生产版本，将其他版本的生产标记设为False
        if is_production:
            for v in versions_data['versions']:
                v['is_production'] = False

        # 添加新版本
        versions_data['versions'].append(version_info)

        # 按版本号排序（降序）
        versions_data['versions'].sort(
            key=lambda x: semver.VersionInfo.parse(x['version']),
            reverse=True
        )

        # 更新最新版本
        versions_data['latest_version'] = versions_data['versions'][0]['version']
        versions_data['total_versions'] = len(versions_data['versions'])
        versions_data['updated_at'] = datetime.now().isoformat()

        # 保存
        await self._save_versions(versions_data)

        # 审计日志
        log_audit(
            action=AuditAction.MODEL_VERSION_ADD.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "version": version,
                "is_production": is_production,
                "file_size": file_info['size'],
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger.debug("添加版本成功: %s v%s", self.model_id, version)
        return version_info

    async def get_version(self, version: Optional[str] = None) -> Dict[str, Any]:
        """
        获取版本信息

        Args:
            version: 版本号，None表示最新版本

        Returns:
            版本信息
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        if version is None:
            # 返回最新版本
            latest = versions_data.get('latest_version')
            if not latest:
                raise ValueError(f"模型 {self.model_id} 没有版本")
            version_info = self._find_version(versions_data, latest)
        else:
            # 返回指定版本
            version_info = self._find_version(versions_data, version)
            if not version_info:
                raise ValueError(f"版本 {version} 不存在")

        # 审计日志（查询操作）
        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "version": version or "latest",
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return version_info

    async def list_versions(self, include_metadata: bool = False) -> List[Dict[str, Any]]:
        """
        列出所有版本

        Args:
            include_metadata: 是否包含详细元数据

        Returns:
            版本列表
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        if include_metadata:
            result = versions_data['versions']
        else:
            # 返回精简信息
            result = [{
                'version': v['version'],
                'added_at': v['added_at'],
                'is_production': v['is_production'],
                'file_size': v['file_size'],
                'tags': v.get('tags', [])
            } for v in versions_data['versions']]

        # 审计日志（查询操作）
        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "total_versions": len(result),
                "include_metadata": include_metadata,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return result

    async def delete_version(self, version: str) -> bool:
        """
        删除版本

        Args:
            version: 版本号

        Returns:
            是否删除成功
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        # 查找版本
        version_info = self._find_version(versions_data, version)
        if not version_info:
            raise ValueError(f"版本 {version} 不存在")

        # 如果是生产版本，不允许删除
        if version_info.get('is_production'):
            raise ValueError(f"生产版本 {version} 不能删除")

        # 删除文件
        try:
            await self.storage.delete(version_info['file_path'])
        except Exception as e:
            logger.debug("删除文件失败: %s", e)

        # 从列表中移除
        versions_data['versions'] = [
            v for v in versions_data['versions']
            if v['version'] != version
        ]

        # 更新最新版本
        if versions_data['versions']:
            versions_data['versions'].sort(
                key=lambda x: semver.VersionInfo.parse(x['version']),
                reverse=True
            )
            versions_data['latest_version'] = versions_data['versions'][0]['version']
        else:
            versions_data['latest_version'] = None

        versions_data['total_versions'] = len(versions_data['versions'])
        versions_data['updated_at'] = datetime.now().isoformat()

        # 保存
        await self._save_versions(versions_data)

        # 审计日志
        log_audit(
            action=AuditAction.MODEL_VERSION_DELETE.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "version": version,
                "was_production": version_info.get('is_production', False),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger.debug("删除版本成功: %s v%s", self.model_id, version)
        return True

    async def set_production_version(self, version: str) -> Dict[str, Any]:
        """
        设置生产版本

        Args:
            version: 版本号

        Returns:
            更新后的版本信息
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        # 查找版本
        version_info = self._find_version(versions_data, version)
        if not version_info:
            raise ValueError(f"版本 {version} 不存在")

        # 将其他版本的生产标记设为False
        for v in versions_data['versions']:
            v['is_production'] = False

        # 设置当前版本为生产
        version_info['is_production'] = True
        versions_data['updated_at'] = datetime.now().isoformat()

        # 保存
        await self._save_versions(versions_data)

        # 审计日志
        log_audit(
            action=AuditAction.MODEL_PROMOTE.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "version": version,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger.debug("设置生产版本: %s v%s", self.model_id, version)
        return version_info

    async def get_production_version(self) -> Optional[Dict[str, Any]]:
        """获取生产版本"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        for v in versions_data['versions']:
            if v.get('is_production'):
                # 审计日志（查询操作）
                log_audit(
                    action=AuditAction.MODEL_QUERY.value,
                    user_id="system",
                    ip_address=None,
                    details={
                        "model_id": self.model_id,
                        "production_version": v['version'],
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                return v

        return None

    async def compare_versions(self, version1: str, version2: str) -> Dict[str, Any]:
        """
        比较两个版本

        Args:
            version1: 第一个版本号
            version2: 第二个版本号

        Returns:
            比较结果
        """
        v1 = semver.VersionInfo.parse(version1)
        v2 = semver.VersionInfo.parse(version2)

        return {
            'version1': version1,
            'version2': version2,
            'v1_gt_v2': v1 > v2,
            'v1_lt_v2': v1 < v2,
            'v1_eq_v2': v1 == v2,
            'major_diff': v1.major - v2.major,
            'minor_diff': v1.minor - v2.minor,
            'patch_diff': v1.patch - v2.patch
        }

    async def get_version_diff(self, version1: str, version2: str) -> Dict[str, Any]:
        """
        获取两个版本的差异

        Args:
            version1: 第一个版本号
            version2: 第二个版本号

        Returns:
            版本差异
        """
        v1_info = await self.get_version(version1)
        v2_info = await self.get_version(version2)

        # 比较元数据
        metadata1 = v1_info.get('metadata', {})
        metadata2 = v2_info.get('metadata', {})

        added_keys = set(metadata2.keys()) - set(metadata1.keys())
        removed_keys = set(metadata1.keys()) - set(metadata2.keys())
        changed_keys = {
            k for k in set(metadata1.keys()) & set(metadata2.keys())
            if metadata1[k] != metadata2[k]
        }

        return {
            'version1': version1,
            'version2': version2,
            'file_size_diff': v2_info['file_size'] - v1_info['file_size'],
            'metadata_changes': {
                'added': list(added_keys),
                'removed': list(removed_keys),
                'changed': list(changed_keys)
            },
            'hash_changed': v1_info['file_hash'] != v2_info['file_hash']
        }

    async def rollback_to_version(self, version: str) -> Dict[str, Any]:
        """
        回滚到指定版本

        Args:
            version: 目标版本号

        Returns:
            回滚后的版本信息
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        # 获取目标版本信息
        target_version = await self.get_version(version)

        # 创建回滚记录
        rollback_version = self._generate_rollback_version(version)

        # 复制文件
        new_path = target_version['file_path'].replace(
            target_version['version'],
            rollback_version
        )

        await self.storage.copy(target_version['file_path'], new_path)

        # 添加为新版本
        metadata = target_version.get('metadata', {}).copy()
        metadata['rollback_from'] = version
        metadata['rollback_reason'] = '版本回滚'

        version_info = await self.add_version(
            version=rollback_version,
            file_path=new_path,
            metadata=metadata
        )

        # 审计日志
        log_audit(
            action=AuditAction.MODEL_ROLLBACK.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "from_version": version,
                "to_version": rollback_version,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger.debug("回滚到版本: %s v%s -> v%s", self.model_id, version, rollback_version)
        return version_info

    async def tag_version(self, version: str, tag: str) -> Dict[str, Any]:
        """
        给版本打标签

        Args:
            version: 版本号
            tag: 标签名

        Returns:
            更新后的版本信息
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        version_info = self._find_version(versions_data, version)
        if not version_info:
            raise ValueError(f"版本 {version} 不存在")

        if 'tags' not in version_info:
            version_info['tags'] = []

        if tag not in version_info['tags']:
            version_info['tags'].append(tag)
            await self._save_versions(versions_data)

            # 审计日志
            log_audit(
                action=AuditAction.MODEL_UPDATE.value,
                user_id="system",
                ip_address=None,
                details={
                    "model_id": self.model_id,
                    "version": version,
                    "tag": tag,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.debug("添加标签: %s v%s -> %s", self.model_id, version, tag)

        return version_info

    async def get_versions_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        根据标签获取版本

        Args:
            tag: 标签名

        Returns:
            版本列表
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        result = [
            v for v in versions_data['versions']
            if tag in v.get('tags', [])
        ]

        # 审计日志（查询操作）
        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "tag": tag,
                "found_count": len(result),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return result

    async def increment_download_count(self, version: str) -> int:
        """
        增加版本下载计数

        Args:
            version: 版本号

        Returns:
            更新后的下载计数
        """
        versions_data = await self._get_versions()

        version_info = self._find_version(versions_data, version)
        if not version_info:
            raise ValueError(f"版本 {version} 不存在")

        version_info['download_count'] = version_info.get('download_count', 0) + 1
        await self._save_versions(versions_data)

        return version_info['download_count']

    async def get_version_stats(self) -> Dict[str, Any]:
        """获取版本统计信息"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        versions = versions_data['versions']
        total_downloads = sum(v.get('download_count', 0) for v in versions)

        # 计算版本分布
        major_versions = {}
        for v in versions:
            major = v['version'].split('.')[0]
            if major not in major_versions:
                major_versions[major] = 0
            major_versions[major] += 1

        result = {
            'model_id': self.model_id,
            'total_versions': versions_data['total_versions'],
            'latest_version': versions_data['latest_version'],
            'total_downloads': total_downloads,
            'production_version': (await self.get_production_version() or {}).get('version'),
            'major_version_distribution': major_versions,
            'created_at': versions_data['created_at'],
            'updated_at': versions_data['updated_at']
        }

        # 审计日志（查询操作）
        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id="system",
            ip_address=None,
            details={
                "model_id": self.model_id,
                "total_versions": result['total_versions'],
                "total_downloads": total_downloads,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return result

    async def cleanup_old_versions(self, keep_count: int = 10) -> List[str]:
        """
        清理旧版本，只保留最近的N个版本

        Args:
            keep_count: 保留的版本数量

        Returns:
            被删除的版本列表
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        versions_data = await self._get_versions()

        if len(versions_data['versions']) <= keep_count:
            return []

        # 按版本号排序（降序）
        sorted_versions = sorted(
            versions_data['versions'],
            key=lambda x: semver.VersionInfo.parse(x['version']),
            reverse=True
        )

        # 保留前keep_count个
        keep_versions = sorted_versions[:keep_count]
        delete_versions = sorted_versions[keep_count:]

        deleted = []
        for v in delete_versions:
            # 跳过生产版本
            if v.get('is_production'):
                continue

            try:
                await self.storage.delete(v['file_path'])
                versions_data['versions'].remove(v)
                deleted.append(v['version'])
                logger.debug("清理旧版本: %s v%s", self.model_id, v['version'])
            except Exception as e:
                logger.debug("清理失败: %s", e)

        # 更新
        versions_data['total_versions'] = len(versions_data['versions'])
        versions_data['updated_at'] = datetime.now().isoformat()
        await self._save_versions(versions_data)

        # 审计日志
        if deleted:
            log_audit(
                action=AuditAction.MODEL_VERSION_DELETE.value,
                user_id="system",
                ip_address=None,
                details={
                    "model_id": self.model_id,
                    "deleted_versions": deleted,
                    "deleted_count": len(deleted),
                    "keep_count": keep_count,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

        return deleted

    async def _get_versions(self) -> Dict[str, Any]:
        """获取版本数据"""
        if self._versions_cache:
            return self._versions_cache

        try:
            # 尝试读取版本文件
            content = await self.storage.load(self.metadata_file)
            self._versions_cache = json.loads(content.decode())
        except FileNotFoundError:
            # 文件不存在，初始化
            self._versions_cache = await self.init_versions()
        except Exception as e:
            logger.debug("读取版本文件失败: %s", e)
            self._versions_cache = await self.init_versions()

        return self._versions_cache

    async def _save_versions(self, versions_data: Dict[str, Any]):
        """保存版本数据"""
        content = json.dumps(versions_data, indent=2).encode()

        # 创建内存文件对象
        file_obj = io.BytesIO(content)

        await self.storage.save(
            self.metadata_file,
            file_obj,
            metadata={'content_type': 'application/json'}
        )

        self._versions_cache = versions_data
        logger.debug("保存版本文件: %s", self.metadata_file)

    def _find_version(self, versions_data: Dict, version: str) -> Optional[Dict]:
        """查找版本"""
        for v in versions_data['versions']:
            if v['version'] == version:
                return v
        return None

    def _validate_version(self, version: str) -> bool:
        """
        验证版本号格式

        支持:
        - 1.0.0
        - 2.1.3
        - 1.0.0-beta
        - 2.0.0-alpha.1
        """
        try:
            semver.VersionInfo.parse(version)
            return True
        except ValueError:
            return False

    def _generate_rollback_version(self, from_version: str) -> str:
        """生成回滚版本号"""
        try:
            v = semver.VersionInfo.parse(from_version)
            # 增加补丁版本号
            new_version = f"{v.major}.{v.minor}.{v.patch + 1}"
            # 添加回滚标记
            return f"{new_version}-rollback"
        except:
            # 如果解析失败，使用时间戳
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            return f"0.0.0-rollback-{timestamp}"