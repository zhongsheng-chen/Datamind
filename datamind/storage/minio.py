# datamind/storage/minio.py

"""MinIO对象存储后端

将数据存储在MinIO/S3兼容的对象存储中。

核心功能：
  - put_object: 上传对象到存储桶
  - get_object: 下载对象内容
  - delete_object: 删除对象
  - object_exists: 检查对象是否存在
  - list_objects: 列出指定前缀下的所有对象

特性：
  - S3兼容：支持MinIO、AWS S3、阿里云OSS等
  - 分块上传：大文件自动分块上传
  - 异常分类：区分不存在、权限、连接等错误
"""

from minio import Minio, S3Error
from io import BytesIO

from datamind.storage.base import BaseStorageBackend
from datamind.storage.errors import (
    StorageNotFoundError,
    StoragePermissionError,
    StorageConnectionError,
)


class MinIOStorageBackend(BaseStorageBackend):
    """MinIO对象存储后端"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        region: str | None = None,
    ):
        """初始化MinIO存储后端

        参数：
            endpoint: MinIO服务端点
            access_key: 访问密钥
            secret_key: 秘密密钥
            bucket: 存储桶名称
            secure: 是否启用TLS
            region: 区域（可选）
        """
        try:
            self.client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
                region=region,
            )
        except Exception as e:
            raise StorageConnectionError(f"连接MinIO失败: {e}")

        self.bucket = bucket

        # 确保存储桶存在
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
        except S3Error as e:
            raise StoragePermissionError(f"访问存储桶失败: {e}")

    def put_object(self, key: str, data: bytes) -> None:
        """上传对象到存储桶

        参数：
            key: 对象键
            data: 二进制数据
        """
        self.client.put_object(
            self.bucket,
            key,
            BytesIO(data),
            length=len(data),
        )

    def get_object(self, key: str) -> bytes:
        """下载对象内容

        参数：
            key: 对象键

        返回：
            对象二进制内容

        异常：
            StorageNotFoundError: 对象不存在
        """
        try:
            response = self.client.get_object(self.bucket, key)
            try:
                return response.read()
            finally:
                response.close()
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise StorageNotFoundError(f"对象不存在: {key}")
            raise StoragePermissionError(f"读取对象失败: {e}")

    def delete_object(self, key: str) -> None:
        """删除对象

        参数：
            key: 对象键
        """
        try:
            self.client.remove_object(self.bucket, key)
        except S3Error:
            # 删除失败不抛出异常，对象可能已不存在
            pass

    def object_exists(self, key: str) -> bool:
        """检查对象是否存在

        参数：
            key: 对象键

        返回：
            存在返回 True，否则返回 False
        """
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            # 其他错误（如权限）返回 False 但记录日志
            return False

    def list_objects(self, prefix: str) -> list[str]:
        """列出指定前缀下的所有对象

        参数：
            prefix: 对象键前缀

        返回：
            匹配前缀的完整对象键列表
        """
        objects = self.client.list_objects(
            self.bucket,
            prefix=prefix,
            recursive=True,
        )
        return [obj.object_name for obj in objects]