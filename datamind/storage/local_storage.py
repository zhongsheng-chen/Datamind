# datamind/storage/local_storage.py

"""本地文件系统存储

提供基于本地文件系统的存储后端，支持文件的保存、加载、删除、复制、移动等操作。

功能特性：
  - 文件保存：支持自定义元数据存储
  - 文件加载：支持版本控制
  - 文件删除：同时删除对应的元数据文件
  - 文件复制/移动：支持完整复制元数据
  - 文件列表：递归列出目录下的所有文件
  - 元数据管理：独立的 .meta.json 文件存储元数据
  - 完整审计：记录所有存储操作到审计日志
  - 链路追踪：完整的 trace_id, span_id, parent_span_id

使用示例：
    storage = LocalStorage(root_path="/data/models")

    # 保存文件
    with open("model.pkl", "rb") as f:
        result = await storage.save("models/v1/model.pkl", f)

    # 加载文件
    content = await storage.load("models/v1/model.pkl")

    # 列出文件
    files = await storage.list("models/")

    # 复制文件
    await storage.copy("models/v1/model.pkl", "models/v2/model.pkl")

    # 获取元数据
    metadata = await storage.get_metadata("models/v1/model.pkl")
"""


import json
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Union, List, Dict, Any
from datetime import datetime

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.storage.base import StorageBackend

_logger = get_logger(__name__)


class LocalStorage(StorageBackend):
    """本地文件系统存储"""

    def __init__(self, root_path: Union[str, Path], base_path: str = ""):
        """
        初始化本地存储

        参数:
            root_path: 根目录路径
            base_path: 基础路径
        """
        super().__init__(base_path=base_path)
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)
        _logger.info("本地存储初始化完成，根目录: %s", self.root_path)

    async def save(self, path: str, content: BinaryIO,
                   metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """保存文件到本地"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self.root_path / self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        file_hash = self._calculate_hash(content)

        content.seek(0)
        with open(full_path, 'wb') as f:
            shutil.copyfileobj(content, f)

        file_size = full_path.stat().st_size

        if metadata:
            meta_path = full_path.with_suffix('.meta.json')
            metadata.update({
                'saved_at': datetime.now().isoformat(),
                'hash': file_hash,
                'size': file_size
            })
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)

        log_audit(
            action=AuditAction.FILE_UPLOAD.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "path": str(full_path.relative_to(self.root_path)),
                "size": file_size,
                "hash": file_hash[:16],
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("文件保存成功: %s, 大小=%.2fKB", full_path, file_size / 1024)

        return {
            'path': str(full_path.relative_to(self.root_path)),
            'full_path': str(full_path),
            'size': file_size,
            'hash': file_hash,
            'metadata': metadata
        }

    async def load(self, path: str, version: Optional[str] = None) -> bytes:
        """加载文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        if version:
            full_path = self.root_path / self._get_full_path(f"{path}.{version}")
        else:
            full_path = self.root_path / self._get_full_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {full_path}")

        with open(full_path, 'rb') as f:
            content = f.read()

        log_audit(
            action=AuditAction.FILE_DOWNLOAD.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "path": str(full_path.relative_to(self.root_path)),
                "size": len(content),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("文件加载成功: %s, 大小=%.2fKB", full_path, len(content) / 1024)
        return content

    async def delete(self, path: str, version: Optional[str] = None) -> bool:
        """删除文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        if version:
            full_path = self.root_path / self._get_full_path(f"{path}.{version}")
        else:
            full_path = self.root_path / self._get_full_path(path)

        if not full_path.exists():
            return False

        full_path.unlink()

        meta_path = full_path.with_suffix('.meta.json')
        if meta_path.exists():
            meta_path.unlink()

        log_audit(
            action=AuditAction.FILE_DELETE.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "path": str(full_path.relative_to(self.root_path)),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("文件删除成功: %s", full_path)
        return True

    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        full_path = self.root_path / self._get_full_path(path)
        return full_path.exists()

    async def list(self, prefix: str = "") -> List[Dict[str, Any]]:
        """列出文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        search_path = self.root_path / self._get_full_path(prefix)

        if not search_path.exists():
            return []

        files = []
        for path in search_path.rglob('*'):
            if path.is_file() and not path.name.endswith('.meta.json'):
                rel_path = path.relative_to(self.root_path)
                stat = path.stat()

                # 加载元数据
                metadata = None
                meta_path = path.with_suffix('.meta.json')
                if meta_path.exists():
                    with open(meta_path, 'r') as f:
                        metadata = json.load(f)

                files.append({
                    'path': str(rel_path),
                    'size': stat.st_size,
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'metadata': metadata
                })

        log_audit(
            action=AuditAction.FILE_LIST.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "prefix": prefix,
                "file_count": len(files),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("列出文件成功: 路径=%s, 共 %d 个文件", search_path, len(files))
        return files

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self.root_path / self._get_full_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {full_path}")

        stat = full_path.stat()
        metadata = {
            'path': str(full_path.relative_to(self.root_path)),
            'size': stat.st_size,
            'created': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'is_file': full_path.is_file(),
            'is_dir': full_path.is_dir()
        }

        # 加载自定义元数据
        meta_path = full_path.with_suffix('.meta.json')
        if meta_path.exists():
            with open(meta_path, 'r') as f:
                metadata['custom'] = json.load(f)

        log_audit(
            action=AuditAction.FILE_METADATA.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "path": str(full_path.relative_to(self.root_path)),
                "size": stat.st_size,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.debug("获取元数据成功: %s", full_path)
        return metadata

    async def copy(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """复制文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        source_full = self.root_path / self._get_full_path(source_path)
        dest_full = self.root_path / self._get_full_path(dest_path)

        if not source_full.exists():
            raise FileNotFoundError(f"源文件不存在: {source_full}")

        dest_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_full, dest_full)

        # 复制元数据
        source_meta = source_full.with_suffix('.meta.json')
        if source_meta.exists():
            dest_meta = dest_full.with_suffix('.meta.json')
            shutil.copy2(source_meta, dest_meta)

        log_audit(
            action=AuditAction.FILE_COPY.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "source": str(source_full.relative_to(self.root_path)),
                "destination": str(dest_full.relative_to(self.root_path)),
                "size": dest_full.stat().st_size,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("文件复制成功: %s -> %s, 大小=%.2fKB",
                   source_full, dest_full, dest_full.stat().st_size / 1024)

        return {
            'source': source_path,
            'destination': dest_path,
            'size': dest_full.stat().st_size
        }

    async def move(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """移动文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        source_full = self.root_path / self._get_full_path(source_path)
        dest_full = self.root_path / self._get_full_path(dest_path)

        if not source_full.exists():
            raise FileNotFoundError(f"源文件不存在: {source_full}")

        dest_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_full), str(dest_full))

        # 移动元数据
        source_meta = source_full.with_suffix('.meta.json')
        if source_meta.exists():
            dest_meta = dest_full.with_suffix('.meta.json')
            shutil.move(str(source_meta), str(dest_meta))

        log_audit(
            action=AuditAction.FILE_MOVE.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "source": str(source_full.relative_to(self.root_path)),
                "destination": str(dest_full.relative_to(self.root_path)),
                "size": dest_full.stat().st_size,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("文件移动成功: %s -> %s, 大小=%.2fKB",
                   source_full, dest_full, dest_full.stat().st_size / 1024)

        return {
            'source': source_path,
            'destination': dest_path,
            'size': dest_full.stat().st_size
        }

    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """获取签名URL（本地存储返回文件路径）"""
        full_path = self.root_path / self._get_full_path(path)
        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {full_path}")

        # 本地存储返回文件URI
        return f"file://{full_path.absolute()}"