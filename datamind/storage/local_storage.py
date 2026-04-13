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
  - 链路追踪：完整的 span 追踪

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
from typing import BinaryIO, Optional, Union, List, Dict
from datetime import datetime

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.core.common import StorageNotFoundException
from datamind.storage.base import StorageBackend, StorageResult, FileInfo, ProgressCallback

_logger = get_logger(__name__)


def get_meta_path(file_path: Path) -> Path:
    """获取元数据文件路径（保留原扩展名，添加 .meta.json）"""
    return file_path.parent / (file_path.name + '.meta.json')


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
                   metadata: Optional[Dict] = None,
                   progress_callback: Optional[ProgressCallback] = None) -> StorageResult:
        """保存文件到本地"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self.root_path / self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        file_hash = self._calculate_hash(content)

        # 获取文件大小
        content.seek(0, 2)
        file_size = content.tell()
        content.seek(0)

        # 进度回调
        if progress_callback:
            await progress_callback(0, file_size, "upload")

        with open(full_path, 'wb') as f:
            written = 0
            while chunk := content.read(8192):
                f.write(chunk)
                written += len(chunk)
                if progress_callback:
                    await progress_callback(written, file_size, "upload")

        if metadata:
            meta_path = get_meta_path(full_path)
            metadata.update({
                'saved_at': datetime.now().isoformat(),
                'hash': file_hash,
                'size': file_size
            })
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

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

        return StorageResult(
            path=str(full_path.relative_to(self.root_path)),
            size=file_size,
            hash=file_hash,
            metadata=metadata,
            location=f"file://{full_path.absolute()}"
        )

    async def load(self, path: str, version: Optional[str] = None,
                   progress_callback: Optional[ProgressCallback] = None) -> bytes:
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
            raise StorageNotFoundException(path=str(full_path))

        file_size = full_path.stat().st_size

        with open(full_path, 'rb') as f:
            if progress_callback:
                await progress_callback(0, file_size, "download")

            content = bytearray()
            while chunk := f.read(8192):
                content.extend(chunk)
                if progress_callback:
                    await progress_callback(len(content), file_size, "download")

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
        return bytes(content)

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

        meta_path = get_meta_path(full_path)
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

    async def list(self, prefix: str = "", max_keys: int = 1000) -> List[FileInfo]:
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
            if len(files) >= max_keys:
                break
            # 跳过元数据文件
            if path.is_file() and not path.name.endswith('.meta.json'):
                rel_path = path.relative_to(self.root_path)
                stat = path.stat()

                # 加载元数据
                metadata = {}
                meta_path = get_meta_path(path)
                if meta_path.exists():
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                    except (json.JSONDecodeError, IOError) as e:
                        _logger.warning("读取元数据文件失败: %s, 错误=%s", meta_path, e)

                files.append(FileInfo(
                    path=str(rel_path),
                    size=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    metadata=metadata
                ))

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

    async def get_metadata(self, path: str) -> FileInfo:
        """获取文件元数据"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self.root_path / self._get_full_path(path)

        if not full_path.exists():
            raise StorageNotFoundException(path=str(full_path))

        stat = full_path.stat()

        # 加载自定义元数据
        custom_metadata = {}
        meta_path = get_meta_path(full_path)
        if meta_path.exists():
            try:
                with open(meta_path, 'r', encoding='utf-8') as f:
                    custom_metadata = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                _logger.warning("读取元数据文件失败: %s, 错误=%s", meta_path, e)

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

        return FileInfo(
            path=str(full_path.relative_to(self.root_path)),
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            metadata=custom_metadata,
            is_dir=full_path.is_dir()
        )

    async def copy(self, source_path: str, dest_path: str) -> StorageResult:
        """复制文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        source_full = self.root_path / self._get_full_path(source_path)
        dest_full = self.root_path / self._get_full_path(dest_path)

        if not source_full.exists():
            raise StorageNotFoundException(path=str(source_full))

        dest_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_full, dest_full)

        # 复制元数据
        source_meta = get_meta_path(source_full)
        if source_meta.exists():
            dest_meta = get_meta_path(dest_full)
            shutil.copy2(source_meta, dest_meta)

        file_size = dest_full.stat().st_size

        log_audit(
            action=AuditAction.FILE_COPY.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "source": str(source_full.relative_to(self.root_path)),
                "destination": str(dest_full.relative_to(self.root_path)),
                "size": file_size,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("文件复制成功: %s -> %s, 大小=%.2fKB",
                     source_full, dest_full, file_size / 1024)

        return StorageResult(
            path=str(dest_full.relative_to(self.root_path)),
            size=file_size,
            hash="",
            location=f"file://{dest_full.absolute()}"
        )

    async def move(self, source_path: str, dest_path: str) -> StorageResult:
        """移动文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        source_full = self.root_path / self._get_full_path(source_path)
        dest_full = self.root_path / self._get_full_path(dest_path)

        if not source_full.exists():
            raise StorageNotFoundException(path=str(source_full))

        dest_full.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_full), str(dest_full))

        # 移动元数据
        source_meta = get_meta_path(source_full)
        if source_meta.exists():
            dest_meta = get_meta_path(dest_full)
            shutil.move(str(source_meta), str(dest_meta))

        file_size = dest_full.stat().st_size

        log_audit(
            action=AuditAction.FILE_MOVE.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "local",
                "source": str(source_full.relative_to(self.root_path)),
                "destination": str(dest_full.relative_to(self.root_path)),
                "size": file_size,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        _logger.info("文件移动成功: %s -> %s, 大小=%.2fKB",
                     source_full, dest_full, file_size / 1024)

        return StorageResult(
            path=str(dest_full.relative_to(self.root_path)),
            size=file_size,
            hash="",
            location=f"file://{dest_full.absolute()}"
        )

    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """获取签名URL（本地存储返回文件路径）"""
        full_path = self.root_path / self._get_full_path(path)
        if not full_path.exists():
            raise StorageNotFoundException(path=str(full_path))

        # 本地存储返回文件URI
        return f"file://{full_path.absolute()}"