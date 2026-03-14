# datamind/storage/local_storage.py
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Union, List, Dict, Any
from datetime import datetime
import hashlib
import json
import mimetypes

from storage.base import StorageBackend
from core.logging import log_manager, get_request_id, debug_print


class LocalStorage(StorageBackend):
    """本地文件系统存储"""

    def __init__(self, root_path: Union[str, Path], base_path: str = ""):
        """
        初始化本地存储

        Args:
            root_path: 根目录路径
            base_path: 基础路径
        """
        super().__init__(base_path=base_path)
        self.root_path = Path(root_path)
        self.root_path.mkdir(parents=True, exist_ok=True)
        debug_print("LocalStorage", f"本地存储根目录: {self.root_path}")

    async def save(self, path: str, content: BinaryIO,
                   metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """保存文件到本地"""
        full_path = self.root_path / self._get_full_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # 计算哈希
        file_hash = self._calculate_hash(content)

        # 保存文件
        content.seek(0)
        with open(full_path, 'wb') as f:
            shutil.copyfileobj(content, f)

        file_size = full_path.stat().st_size

        # 保存元数据
        if metadata:
            meta_path = full_path.with_suffix('.meta.json')
            metadata.update({
                'saved_at': datetime.now().isoformat(),
                'hash': file_hash,
                'size': file_size
            })
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)

        debug_print("LocalStorage", f"文件保存成功: {full_path}")

        return {
            'path': str(full_path.relative_to(self.root_path)),
            'full_path': str(full_path),
            'size': file_size,
            'hash': file_hash,
            'metadata': metadata
        }

    async def load(self, path: str, version: Optional[str] = None) -> bytes:
        """加载文件"""
        if version:
            # 版本控制（简化版）
            full_path = self.root_path / self._get_full_path(f"{path}.{version}")
        else:
            full_path = self.root_path / self._get_full_path(path)

        if not full_path.exists():
            raise FileNotFoundError(f"文件不存在: {full_path}")

        with open(full_path, 'rb') as f:
            content = f.read()

        debug_print("LocalStorage", f"文件加载成功: {full_path}")
        return content

    async def delete(self, path: str, version: Optional[str] = None) -> bool:
        """删除文件"""
        if version:
            full_path = self.root_path / self._get_full_path(f"{path}.{version}")
        else:
            full_path = self.root_path / self._get_full_path(path)

        if not full_path.exists():
            return False

        # 删除文件
        full_path.unlink()

        # 删除对应的元数据文件
        meta_path = full_path.with_suffix('.meta.json')
        if meta_path.exists():
            meta_path.unlink()

        debug_print("LocalStorage", f"文件删除成功: {full_path}")
        return True

    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        full_path = self.root_path / self._get_full_path(path)
        return full_path.exists()

    async def list(self, prefix: str = "") -> List[Dict[str, Any]]:
        """列出文件"""
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

        return files

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """获取文件元数据"""
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

        return metadata

    async def copy(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """复制文件"""
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

        debug_print("LocalStorage", f"文件复制成功: {source_full} -> {dest_full}")

        return {
            'source': source_path,
            'destination': dest_path,
            'size': dest_full.stat().st_size
        }

    async def move(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """移动文件"""
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

        debug_print("LocalStorage", f"文件移动成功: {source_full} -> {dest_full}")

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