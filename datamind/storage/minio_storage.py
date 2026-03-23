# datamind/storage/minio_storage.py

"""MinIO对象存储

提供基于 MinIO 的对象存储后端，支持文件的保存、加载、删除、复制、移动等操作。

功能特性：
  - 文件保存：支持自定义元数据存储
  - 文件加载：支持版本控制
  - 文件删除：支持指定版本删除
  - 文件复制/移动：支持完整的对象复制
  - 文件列表：递归列出指定前缀下的所有对象
  - 元数据管理：支持获取和设置对象元数据、标签
  - 存储桶管理：支持创建/删除存储桶、设置存储桶策略
  - 签名URL：支持生成预签名上传/下载URL
  - 完整审计：记录所有存储操作到审计日志
  - 链路追踪：完整的 trace_id, span_id, parent_span_id
"""

import os
import hashlib
import mimetypes
import json
from typing import BinaryIO, Optional, List, Dict, Any
from datetime import timedelta
from minio import Minio
from minio.api import CopySource  # 正确的导入路径
from minio.error import S3Error

from datamind.storage.base import StorageBackend
from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.core.domain.enums import AuditAction


class MinIOStorage(StorageBackend):
    """MinIO对象存储"""

    def __init__(self, endpoint: str, bucket_name: str,
                 access_key: str = None, secret_key: str = None,
                 secure: bool = True, region: str = None,
                 base_path: str = ""):
        """
        初始化MinIO存储

        Args:
            endpoint: MinIO服务器地址 (例如: "localhost:9000")
            bucket_name: 存储桶名称
            access_key: 访问密钥
            secret_key: 秘密密钥
            secure: 是否使用HTTPS
            region: 区域
            base_path: 基础路径
        """
        super().__init__(bucket_name, base_path)

        # 从环境变量获取密钥（如果没有提供）
        access_key = access_key or os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
        secret_key = secret_key or os.getenv('MINIO_SECRET_KEY', 'minioadmin')

        # 初始化MinIO客户端
        self.client = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
            region=region
        )

        # 确保存储桶存在
        self._ensure_bucket_exists(bucket_name)

        debug_print("MinIOStorage", f"MinIO存储初始化完成: {endpoint}/{bucket_name}")

    def _ensure_bucket_exists(self, bucket_name: str):
        """确保存储桶存在，不存在则创建"""
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
                debug_print("MinIOStorage", f"创建存储桶: {bucket_name}")

                # 设置存储桶策略（公开读）- 需要转换为 JSON 字符串
                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": "*"},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                        }
                    ]
                }
                # 将字典转换为 JSON 字符串
                self.client.set_bucket_policy(bucket_name, json.dumps(policy))
        except S3Error as e:
            debug_print("MinIOStorage", f"存储桶操作失败: {e}")
            raise

    async def save(self, path: str, content: BinaryIO,
                   metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """保存文件到MinIO"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self._get_full_path(path)

        try:
            # 检测内容类型
            content_type, _ = mimetypes.guess_type(path)
            if not content_type:
                content_type = 'application/octet-stream'

            # 计算文件大小和哈希
            content.seek(0, 2)
            size = content.tell()
            content.seek(0)

            # 计算MD5哈希
            md5_hash = hashlib.md5()
            for chunk in iter(lambda: content.read(8192), b''):
                md5_hash.update(chunk)
            content.seek(0)

            # 准备元数据 - 只支持 ASCII 字符
            minio_metadata = {}
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, str):
                        # 只保留 ASCII 字符的元数据
                        try:
                            value.encode('ascii')
                            minio_metadata[key] = value
                        except UnicodeEncodeError:
                            # 跳过非 ASCII 字符
                            debug_print("MinIOStorage", f"跳过非 ASCII 元数据: {key}={value}")
                    elif isinstance(value, (int, float, bool)):
                        minio_metadata[key] = str(value)
                    else:
                        minio_metadata[key] = str(value)

            # 上传文件
            result = self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=full_path,
                data=content,
                length=size,
                content_type=content_type,
                metadata=minio_metadata
            )

            log_audit(
                action=AuditAction.FILE_UPLOAD.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "size": size,
                    "etag": result.etag,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"文件上传成功: {self.bucket_name}/{full_path}")

            return {
                'path': full_path,
                'bucket': self.bucket_name,
                'size': size,
                'etag': result.etag,
                'version_id': result.version_id,
                'metadata': metadata,
                'location': f"minio://{self.bucket_name}/{full_path}"
            }

        except S3Error as e:
            log_audit(
                action=AuditAction.FILE_UPLOAD.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            debug_print("MinIOStorage", f"文件上传失败: {e}")
            raise

    async def load(self, path: str, version: Optional[str] = None) -> bytes:
        """从MinIO加载文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self._get_full_path(path)

        try:
            # 获取对象
            if version:
                response = self.client.get_object(
                    bucket_name=self.bucket_name,
                    object_name=full_path,
                    version_id=version
                )
            else:
                response = self.client.get_object(
                    bucket_name=self.bucket_name,
                    object_name=full_path
                )

            # 读取内容
            content = response.read()
            response.close()
            response.release_conn()

            log_audit(
                action=AuditAction.FILE_DOWNLOAD.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "size": len(content),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"文件下载成功: {self.bucket_name}/{full_path}")
            return content

        except S3Error as e:
            log_audit(
                action=AuditAction.FILE_DOWNLOAD.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            debug_print("MinIOStorage", f"文件下载失败: {e}")
            raise

    async def delete(self, path: str, version: Optional[str] = None) -> bool:
        """从MinIO删除文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self._get_full_path(path)

        try:
            # 先检查文件是否存在
            if not await self.exists(path):
                return False

            if version:
                self.client.remove_object(
                    bucket_name=self.bucket_name,
                    object_name=full_path,
                    version_id=version
                )
            else:
                self.client.remove_object(
                    bucket_name=self.bucket_name,
                    object_name=full_path
                )

            log_audit(
                action=AuditAction.FILE_DELETE.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"文件删除成功: {self.bucket_name}/{full_path}")
            return True

        except S3Error as e:
            log_audit(
                action=AuditAction.FILE_DELETE.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            debug_print("MinIOStorage", f"文件删除失败: {e}")
            return False

    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        full_path = self._get_full_path(path)

        try:
            self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=full_path
            )
            return True
        except S3Error:
            return False

    async def list(self, prefix: str = "") -> List[Dict[str, Any]]:
        """列出MinIO文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_prefix = self._get_full_path(prefix)

        try:
            objects = self.client.list_objects(
                bucket_name=self.bucket_name,
                prefix=full_prefix,
                recursive=True
            )

            files = []
            for obj in objects:
                # 跳过目录条目（以 '/' 结尾的对象）
                if obj.object_name.endswith('/'):
                    continue

                # 获取对象元数据
                try:
                    stat = self.client.stat_object(
                        bucket_name=self.bucket_name,
                        object_name=obj.object_name
                    )
                    metadata = stat.metadata
                except:
                    metadata = {}

                files.append({
                    'path': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified.isoformat() if obj.last_modified else None,
                    'etag': obj.etag.strip('"') if obj.etag else None,
                    'is_dir': obj.is_dir,
                    'metadata': metadata
                })

            log_audit(
                action=AuditAction.FILE_LIST.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "prefix": prefix,
                    "file_count": len(files),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"列出文件成功: {full_prefix}, 共 {len(files)} 个文件")
            return files

        except S3Error as e:
            debug_print("MinIOStorage", f"列出文件失败: {e}")
            return []

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self._get_full_path(path)

        try:
            stat = self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=full_path
            )

            log_audit(
                action=AuditAction.FILE_METADATA.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "size": stat.size,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            return {
                'path': full_path,
                'size': stat.size,
                'last_modified': stat.last_modified.isoformat() if stat.last_modified else None,
                'etag': stat.etag.strip('"') if stat.etag else None,
                'content_type': stat.content_type,
                'metadata': stat.metadata or {}
            }

        except S3Error as e:
            debug_print("MinIOStorage", f"获取元数据失败: {e}")
            raise

    async def copy(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """复制MinIO文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        source_full = self._get_full_path(source_path)
        dest_full = self._get_full_path(dest_path)

        try:
            # 使用 CopySource 对象
            copy_source = CopySource(self.bucket_name, source_full)

            # 复制对象
            result = self.client.copy_object(
                bucket_name=self.bucket_name,
                object_name=dest_full,
                source=copy_source
            )

            log_audit(
                action=AuditAction.FILE_COPY.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "source": source_full,
                    "destination": dest_full,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"文件复制成功: {source_full} -> {dest_full}")

            return {
                'source': source_path,
                'destination': dest_path,
                'etag': result.etag,
                'version_id': result.version_id
            }

        except S3Error as e:
            log_audit(
                action=AuditAction.FILE_COPY.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "source": source_full,
                    "destination": dest_full,
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            debug_print("MinIOStorage", f"文件复制失败: {e}")
            raise

    async def move(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """移动MinIO文件"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        source_full = self._get_full_path(source_path)
        dest_full = self._get_full_path(dest_path)

        # 先复制
        result = await self.copy(source_path, dest_path)
        # 再删除原文件
        await self.delete(source_path)

        log_audit(
            action=AuditAction.FILE_MOVE.value,
            user_id="system",
            ip_address=None,
            details={
                "storage_type": "minio",
                "bucket": self.bucket_name,
                "source": source_full,
                "destination": dest_full,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        debug_print("MinIOStorage", f"文件移动成功: {source_path} -> {dest_path}")

        return result

    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """获取MinIO签名URL"""
        full_path = self._get_full_path(path)

        try:
            # 生成签名URL
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=full_path,
                expires=timedelta(seconds=expires_in)
            )

            return url

        except S3Error as e:
            debug_print("MinIOStorage", f"生成签名URL失败: {e}")
            raise

    async def get_upload_url(self, path: str, expires_in: int = 3600) -> str:
        """获取上传签名URL"""
        full_path = self._get_full_path(path)

        try:
            # 生成上传签名URL
            url = self.client.presigned_put_object(
                bucket_name=self.bucket_name,
                object_name=full_path,
                expires=timedelta(seconds=expires_in)
            )

            return url

        except S3Error as e:
            debug_print("MinIOStorage", f"生成上传URL失败: {e}")
            raise

    async def get_object_info(self, path: str) -> Dict[str, Any]:
        """获取对象详细信息"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self._get_full_path(path)

        try:
            # 获取对象信息
            stat = self.client.stat_object(
                bucket_name=self.bucket_name,
                object_name=full_path
            )

            # 获取对象标签
            try:
                tags = self.client.get_object_tags(
                    bucket_name=self.bucket_name,
                    object_name=full_path
                )
            except:
                tags = {}

            # 获取对象保留配置
            try:
                retention = self.client.get_object_retention(
                    bucket_name=self.bucket_name,
                    object_name=full_path
                )
            except:
                retention = None

            log_audit(
                action=AuditAction.FILE_METADATA.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "size": stat.size,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            return {
                'path': full_path,
                'bucket': self.bucket_name,
                'size': stat.size,
                'etag': stat.etag.strip('"') if stat.etag else None,
                'last_modified': stat.last_modified.isoformat() if stat.last_modified else None,
                'content_type': stat.content_type,
                'metadata': stat.metadata or {},
                'tags': tags,
                'retention': retention,
                'version_id': stat.version_id
            }

        except S3Error as e:
            debug_print("MinIOStorage", f"获取对象信息失败: {e}")
            raise

    async def set_object_tags(self, path: str, tags: Dict[str, str]) -> bool:
        """设置对象标签"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        full_path = self._get_full_path(path)

        try:
            self.client.set_object_tags(
                bucket_name=self.bucket_name,
                object_name=full_path,
                tags=tags
            )

            log_audit(
                action=AuditAction.FILE_METADATA.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "bucket": self.bucket_name,
                    "path": full_path,
                    "operation": "set_tags",
                    "tags": list(tags.keys()),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"设置对象标签成功: {full_path}")
            return True

        except S3Error as e:
            debug_print("MinIOStorage", f"设置对象标签失败: {e}")
            return False

    async def list_buckets(self) -> List[str]:
        """列出所有存储桶"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            buckets = self.client.list_buckets()
            bucket_names = [b.name for b in buckets]

            log_audit(
                action=AuditAction.FILE_LIST.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "operation": "list_buckets",
                    "bucket_count": len(bucket_names),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            return bucket_names
        except S3Error as e:
            debug_print("MinIOStorage", f"列出存储桶失败: {e}")
            return []

    async def create_bucket(self, bucket_name: str) -> bool:
        """创建存储桶"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)

                log_audit(
                    action=AuditAction.FILE_UPLOAD.value,
                    user_id="system",
                    ip_address=None,
                    details={
                        "storage_type": "minio",
                        "operation": "create_bucket",
                        "bucket": bucket_name,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                debug_print("MinIOStorage", f"创建存储桶成功: {bucket_name}")
                return True
            return False
        except S3Error as e:
            debug_print("MinIOStorage", f"创建存储桶失败: {e}")
            return False

    async def delete_bucket(self, bucket_name: str) -> bool:
        """删除存储桶"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            # 检查存储桶是否为空
            objects = list(self.client.list_objects(bucket_name, recursive=True))
            if objects:
                # 删除所有对象
                for obj in objects:
                    self.client.remove_object(bucket_name, obj.object_name)

            # 删除存储桶
            self.client.remove_bucket(bucket_name)

            log_audit(
                action=AuditAction.FILE_DELETE.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "operation": "delete_bucket",
                    "bucket": bucket_name,
                    "objects_deleted": len(objects),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"删除存储桶成功: {bucket_name}")
            return True
        except S3Error as e:
            debug_print("MinIOStorage", f"删除存储桶失败: {e}")
            return False

    async def get_bucket_policy(self, bucket_name: str) -> str:
        """获取存储桶策略"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            policy = self.client.get_bucket_policy(bucket_name)

            log_audit(
                action=AuditAction.FILE_METADATA.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "operation": "get_bucket_policy",
                    "bucket": bucket_name,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            return policy
        except S3Error as e:
            debug_print("MinIOStorage", f"获取存储桶策略失败: {e}")
            raise

    async def set_bucket_policy(self, bucket_name: str, policy: dict) -> bool:
        """设置存储桶策略"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            self.client.set_bucket_policy(bucket_name, json.dumps(policy))

            log_audit(
                action=AuditAction.FILE_METADATA.value,
                user_id="system",
                ip_address=None,
                details={
                    "storage_type": "minio",
                    "operation": "set_bucket_policy",
                    "bucket": bucket_name,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("MinIOStorage", f"设置存储桶策略成功: {bucket_name}")
            return True
        except S3Error as e:
            debug_print("MinIOStorage", f"设置存储桶策略失败: {e}")
            return False