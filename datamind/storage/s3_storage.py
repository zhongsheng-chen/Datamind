# Datamind/datamind/storage/s3_storage.py
import boto3
import botocore
from typing import BinaryIO, Optional, List, Dict, Any
import mimetypes
import os

from datamind.storage.base import StorageBackend
from datamind.core.logging import debug_print


class S3Storage(StorageBackend):
    """AWS S3存储"""

    def __init__(self, bucket_name: str, aws_access_key_id: str = None,
                 aws_secret_access_key: str = None, region_name: str = 'us-east-1',
                 endpoint_url: str = None, base_path: str = ""):
        """
        初始化S3存储

        参数:
            bucket_name: S3桶名称
            aws_access_key_id: AWS访问密钥ID
            aws_secret_access_key: AWS秘密访问密钥
            region_name: 区域名称
            endpoint_url: 自定义端点URL（用于MinIO等）
            base_path: 基础路径
        """
        super().__init__(bucket_name, base_path)

        self.session = boto3.Session(
            aws_access_key_id=aws_access_key_id or os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=aws_secret_access_key or os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=region_name
        )

        self.s3_client = self.session.client(
            's3',
            endpoint_url=endpoint_url,
            config=botocore.client.Config(signature_version='s3v4')
        )

        # 确保桶存在
        try:
            self.s3_client.head_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError:
            # 桶不存在，创建桶
            self.s3_client.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={'LocationConstraint': region_name}
            )

        debug_print("S3Storage", f"S3存储初始化完成: {bucket_name}")

    async def save(self, path: str, content: BinaryIO,
                   metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """保存文件到S3"""
        full_path = self._get_full_path(path)

        # 检测内容类型
        content_type, _ = mimetypes.guess_type(path)
        if not content_type:
            content_type = 'application/octet-stream'

        # 准备元数据
        s3_metadata = {}
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, str):
                    s3_metadata[key] = value

        # 计算哈希
        file_hash = self._calculate_hash(content)
        content.seek(0)

        # 上传文件
        self.s3_client.upload_fileobj(
            content,
            self.bucket_name,
            full_path,
            ExtraArgs={
                'ContentType': content_type,
                'Metadata': s3_metadata
            }
        )

        # 获取文件信息
        response = self.s3_client.head_object(
            Bucket=self.bucket_name,
            Key=full_path
        )

        debug_print("S3Storage", f"文件上传成功: s3://{self.bucket_name}/{full_path}")

        return {
            'path': full_path,
            'bucket': self.bucket_name,
            'size': response['ContentLength'],
            'hash': file_hash,
            'etag': response['ETag'].strip('"'),
            'last_modified': response['LastModified'].isoformat(),
            'metadata': metadata
        }

    async def load(self, path: str, version: Optional[str] = None) -> bytes:
        """从S3加载文件"""
        full_path = self._get_full_path(path)
        if version:
            # S3版本控制
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=full_path,
                VersionId=version
            )
        else:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=full_path
            )

        content = response['Body'].read()
        debug_print("S3Storage", f"文件下载成功: s3://{self.bucket_name}/{full_path}")
        return content

    async def delete(self, path: str, version: Optional[str] = None) -> bool:
        """从S3删除文件"""
        full_path = self._get_full_path(path)

        if version:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=full_path,
                VersionId=version
            )
        else:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=full_path
            )

        debug_print("S3Storage", f"文件删除成功: s3://{self.bucket_name}/{full_path}")
        return True

    async def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        full_path = self._get_full_path(path)

        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=full_path
            )
            return True
        except botocore.exceptions.ClientError:
            return False

    async def list(self, prefix: str = "") -> List[Dict[str, Any]]:
        """列出S3文件"""
        full_prefix = self._get_full_path(prefix)

        paginator = self.s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(
            Bucket=self.bucket_name,
            Prefix=full_prefix
        )

        files = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    # 获取元数据
                    try:
                        head = self.s3_client.head_object(
                            Bucket=self.bucket_name,
                            Key=obj['Key']
                        )
                        metadata = head.get('Metadata', {})
                    except:
                        metadata = {}

                    files.append({
                        'path': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'etag': obj['ETag'].strip('"'),
                        'metadata': metadata
                    })

        return files

    async def get_metadata(self, path: str) -> Dict[str, Any]:
        """获取文件元数据"""
        full_path = self._get_full_path(path)

        response = self.s3_client.head_object(
            Bucket=self.bucket_name,
            Key=full_path
        )

        return {
            'path': full_path,
            'size': response['ContentLength'],
            'last_modified': response['LastModified'].isoformat(),
            'etag': response['ETag'].strip('"'),
            'content_type': response.get('ContentType'),
            'metadata': response.get('Metadata', {})
        }

    async def copy(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """复制S3文件"""
        source_full = self._get_full_path(source_path)
        dest_full = self._get_full_path(dest_path)

        copy_source = {
            'Bucket': self.bucket_name,
            'Key': source_full
        }

        response = self.s3_client.copy_object(
            Bucket=self.bucket_name,
            Key=dest_full,
            CopySource=copy_source
        )

        debug_print("S3Storage", f"文件复制成功: {source_full} -> {dest_full}")

        return {
            'source': source_path,
            'destination': dest_path,
            'etag': response['CopyObjectResult']['ETag'].strip('"')
        }

    async def move(self, source_path: str, dest_path: str) -> Dict[str, Any]:
        """移动S3文件"""
        # 先复制
        result = await self.copy(source_path, dest_path)
        # 再删除原文件
        await self.delete(source_path)

        debug_print("S3Storage", f"文件移动成功: {source_path} -> {dest_path}")

        return result

    async def get_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """获取S3签名URL"""
        full_path = self._get_full_path(path)

        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self.bucket_name,
                'Key': full_path
            },
            ExpiresIn=expires_in
        )

        return url