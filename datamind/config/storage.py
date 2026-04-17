# datamind/config/storage.py

"""存储配置

定义模型文件的存储后端和连接参数，支持本地存储和MinIO对象存储。

两种存储方式互斥，通过 storage_type 选择：

- local: 本地文件系统存储
- minio: MinIO/S3 兼容对象存储

配置示例：

    # 本地存储
    DATAMIND_STORAGE_STORAGE_TYPE=local
    DATAMIND_STORAGE_LOCAL_BASE_DIR=/var/datamind/data
    DATAMIND_STORAGE_MODEL_DIR=models

    # MinIO存储
    DATAMIND_STORAGE_STORAGE_TYPE=minio
    DATAMIND_STORAGE_MINIO_ENDPOINT=minio.example.com:9000
    DATAMIND_STORAGE_MINIO_BUCKET=datamind-models
    DATAMIND_STORAGE_MINIO_ACCESS_KEY=your_access_key
    DATAMIND_STORAGE_MINIO_SECRET_KEY=your_secret_key
    DATAMIND_STORAGE_MINIO_BASE_PREFIX=production
    DATAMIND_STORAGE_MINIO_CHUNK_SIZE=16777216
    DATAMIND_STORAGE_MINIO_MULTIPART_THRESHOLD=67108864
    DATAMIND_STORAGE_MINIO_MAX_CONCURRENCY=4

属性说明：

通用属性：
  - storage_type: 存储类型，local 或 minio
  - max_file_size: 单个模型文件最大字节数，默认 200MB
  - model_dir: 模型存放的子目录名，统一抽象层使用

本地存储（local）：
  - base_dir: 数据根目录，模型实际路径为 {base_dir}/{model_dir}

MinIO存储（minio）：
  - endpoint: MinIO服务地址
  - bucket: 存储桶名称
  - access_key / secret_key: 认证凭证
  - secure: 是否启用 TLS/SSL
  - region: S3兼容区域（可选）
  - base_prefix: 对象存储顶层前缀
  - chunk_size: 分块上传的块大小
  - multipart_threshold: 触发分段上传的文件大小阈值
  - max_concurrency: 分段上传的最大并发数
  - connect_timeout / read_timeout / write_timeout: 网络超时控制
  - max_retries: 操作失败最大重试次数

环境变量：

通用：
  - DATAMIND_STORAGE_STORAGE_TYPE: 存储类型，默认 local
  - DATAMIND_STORAGE_MAX_FILE_SIZE: 文件大小上限，默认 209715200
  - DATAMIND_STORAGE_MODEL_DIR: 模型目录，默认 models

本地存储：
  - DATAMIND_STORAGE_LOCAL_BASE_DIR: 本地基础目录，默认 ./data

MinIO存储：
  - DATAMIND_STORAGE_MINIO_ENDPOINT: 服务端点，默认 localhost:9000
  - DATAMIND_STORAGE_MINIO_BUCKET: 存储桶，默认 datamind
  - DATAMIND_STORAGE_MINIO_ACCESS_KEY: 访问密钥，默认空
  - DATAMIND_STORAGE_MINIO_SECRET_KEY: 秘密密钥，默认空
  - DATAMIND_STORAGE_MINIO_SECURE: 启用TLS，默认 false
  - DATAMIND_STORAGE_MINIO_REGION: 区域，默认 None
  - DATAMIND_STORAGE_MINIO_BASE_PREFIX: 基础前缀，默认 datamind
  - DATAMIND_STORAGE_MINIO_CHUNK_SIZE: 分块大小，默认 16777216
  - DATAMIND_STORAGE_MINIO_MULTIPART_THRESHOLD: 分段阈值，默认 67108864
  - DATAMIND_STORAGE_MINIO_MAX_CONCURRENCY: 最大并发，默认 4
  - DATAMIND_STORAGE_MINIO_CONNECT_TIMEOUT: 连接超时，默认 5
  - DATAMIND_STORAGE_MINIO_READ_TIMEOUT: 读取超时，默认 60
  - DATAMIND_STORAGE_MINIO_WRITE_TIMEOUT: 写入超时，默认 60
  - DATAMIND_STORAGE_MINIO_MAX_RETRIES: 最大重试，默认 3
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from datamind.constants.size import MB


class LocalStorageConfig(BaseSettings):
    """本地存储配置"""

    base_dir: str = "./data"

    @field_validator("base_dir")
    @classmethod
    def make_absolute(cls, v: str) -> str:
        """转换为绝对路径，跨系统兼容"""
        return str(Path(v).expanduser().resolve())

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_STORAGE_LOCAL_",
        env_file=".env",
        extra="ignore",
    )


class MinIOStorageConfig(BaseSettings):
    """MinIO存储配置"""

    endpoint: str = "localhost:9000"
    bucket: str = "datamind"
    access_key: str = ""
    secret_key: str = ""
    secure: bool = False
    region: str | None = None
    base_prefix: str = "datamind"
    chunk_size: int = 16 * MB
    multipart_threshold: int = 64 * MB
    max_concurrency: int = 4
    connect_timeout: int = 5
    read_timeout: int = 60
    write_timeout: int = 60
    max_retries: int = 3

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_STORAGE_MINIO_",
        env_file=".env",
        extra="ignore",
    )


class StorageConfig(BaseSettings):
    """存储配置类"""

    storage_type: Literal["local", "minio"] = "local"
    max_file_size: int = 200 * MB
    model_dir: str = "models"

    local: LocalStorageConfig = Field(default_factory=LocalStorageConfig)
    minio: MinIOStorageConfig = Field(default_factory=MinIOStorageConfig)

    model_config = SettingsConfigDict(
        env_prefix="DATAMIND_STORAGE_",
        env_file=".env",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate(self):
        if self.storage_type == "minio":
            if not self.minio.endpoint:
                raise ValueError("使用 minio 存储时，endpoint 不能为空")
            if not self.minio.bucket:
                raise ValueError("使用 minio 存储时，bucket 不能为空")
        return self

    @property
    def local_model_path(self) -> str:
        """本地模型根路径"""
        return str(Path(self.local.base_dir) / self.model_dir)

    @property
    def minio_model_prefix(self) -> str:
        """MinIO模型前缀（自动去除首尾斜杠，避免空前缀问题）"""
        prefix = self.minio.base_prefix.strip("/")
        model_dir = self.model_dir.strip("/")

        if prefix:
            return f"{prefix}/{model_dir}"
        return model_dir

    def get_local_model_path(self, model_id: str, filename: str) -> str:
        """获取本地模型文件完整路径，并自动创建目录

        Args:
            model_id: 模型ID
            filename: 模型文件名

        Returns:
            本地完整路径，格式: {local_model_path}/{model_id}/{filename}
        """
        path = Path(self.local_model_path) / model_id
        path.mkdir(parents=True, exist_ok=True)
        return str(path / filename)

    def get_model_key(self, model_id: str, filename: str) -> str:
        """获取MinIO模型对象key

        Args:
            model_id: 模型ID
            filename: 模型文件名

        Returns:
            MinIO对象key，格式: {minio_model_prefix}/{model_id}/{filename}
        """
        return f"{self.minio_model_prefix}/{model_id}/{filename}"