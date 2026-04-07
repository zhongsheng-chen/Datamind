# datamind/config/storage_config.py

"""存储配置模块

定义 Datamind 系统的存储配置，支持本地存储、MinIO、AWS S3 等多种存储后端。

核心功能：
  - is_cloud_storage: 判断是否为云存储
  - get_effective_cache_ttl: 获取有效的缓存过期时间
  - get_effective_cache_size: 获取有效的缓存大小
  - get_compression_library_module: 获取压缩库对应的模块对象
  - get_encryption_key_hash: 获取加密密钥的 SHA256 哈希值
  - to_summary_dict: 获取配置摘要（用于调试和监控）

特性：
  - 多存储支持：本地文件系统、MinIO、AWS S3
  - 自动调整：chunk_size 与 multipart_threshold 比例自动优化
  - 压缩支持：zlib/gzip/lz4/zstd 多种压缩库
  - 加密支持：AES 加密，密钥强度校验
  - 缓存控制：可配置缓存大小和过期时间
  - 分块上传：支持大文件分块上传，阈值可配置
  - 端点验证：支持 IPv6 和子域名格式
  - 跨平台：Windows/Linux/macOS 路径兼容
  - 完整验证：类型、范围、格式、依赖关系全面校验
  - 生产安全：生产环境强制校验凭证和桶名
  - 配置摘要：提供 summary 方法便于调试和监控
  - 环境变量支持：支持 DATAMIND_STORAGE_* 前缀的环境变量
"""

import os
import re
import hashlib
import importlib
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator

from datamind import PROJECT_ROOT
from .base import BaseConfig, _debug, _mask_sensitive


# ==================== 常量定义 ====================

class StorageConstants:
    """存储常量定义

    定义存储系统使用的所有常量，包括大小单位、限制值和默认值。
    """

    # 大小常量
    KB: int = 1024
    MB: int = 1024 * KB
    GB: int = 1024 * MB

    # 默认值
    DEFAULT_MAX_FILE_SIZE: int = 1 * GB
    DEFAULT_CHUNK_SIZE: int = 8 * MB
    DEFAULT_MULTIPART_THRESHOLD: int = 100 * MB
    DEFAULT_CACHE_SIZE: int = 100
    DEFAULT_CACHE_TTL: int = 300
    DEFAULT_DEFAULT_TTL: int = 86400
    DEFAULT_COMPRESSION_LEVEL: int = 6
    DEFAULT_CHUNK_RATIO: int = 10

    # 限制值
    MIN_CACHE_SIZE: int = 1
    MAX_CACHE_SIZE: int = 10000
    MIN_CACHE_TTL: int = 60
    MAX_CACHE_TTL: int = 86400
    MIN_ENCRYPTION_KEY_LEN: int = 32
    MIN_COMPRESSION_LEVEL: int = 1
    MAX_COMPRESSION_LEVEL: int = 9
    MIN_MAX_FILE_SIZE: int = 1 * MB
    MAX_MAX_FILE_SIZE: int = 10 * GB
    MIN_CHUNK_SIZE: int = 1 * MB
    MAX_CHUNK_SIZE: int = 100 * MB
    MIN_MULTIPART_THRESHOLD: int = 5 * MB
    MAX_MULTIPART_THRESHOLD: int = 5 * GB
    MIN_CHUNK_RATIO: int = 2
    MAX_CHUNK_RATIO: int = 100

    # 默认存储桶名称
    DEFAULT_BUCKET_NAME: str = "datamind-storage"

    # 脱敏保留字符数
    MASK_PREFIX_LEN: int = 3
    MASK_SUFFIX_LEN: int = 3

    # 压缩库推荐级别范围
    COMPRESSION_LIBRARY_RANGES: Dict[str, Tuple[int, int]] = {
        "zlib": (1, 9),
        "gzip": (1, 9),
        "lz4": (1, 3),
        "zstd": (1, 9),
    }

    # 加密密钥安全字符正则
    ENCRYPTION_KEY_PATTERN: re.Pattern = re.compile(r'^[a-zA-Z0-9!@#$%^&*()_+=\-]{32,}$')


class StorageType(str, Enum):
    """存储类型枚举

    定义支持的存储后端类型。

    - LOCAL: 本地文件系统
    - MINIO: MinIO 对象存储
    - S3: AWS S3 对象存储
    """

    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"


class CompressionLibrary(str, Enum):
    """压缩库枚举

    定义支持的压缩库类型。

    - ZLIB: zlib 压缩（默认）
    - GZIP: gzip 压缩
    - LZ4: lz4 压缩（高性能）
    - ZSTD: zstd 压缩（高压缩比）
    """

    ZLIB = "zlib"
    GZIP = "gzip"
    LZ4 = "lz4"
    ZSTD = "zstd"


def normalize_prefix(prefix: str) -> str:
    """规范化对象前缀（确保以单个斜杠结尾）

    参数:
        prefix: 原始前缀字符串

    返回:
        规范化后的前缀（以单个斜杠结尾，如为空则返回空字符串）
    """
    if not prefix:
        return ""
    prefix = prefix.strip()
    prefix = prefix.rstrip('/') + '/'
    return prefix


def validate_endpoint(endpoint: Optional[str]) -> Optional[str]:
    """验证端点格式并规范化（支持 IPv6 和子域名）

    参数:
        endpoint: 端点字符串

    返回:
        规范化后的端点字符串

    抛出:
        ValueError: 端点格式无效时抛出
    """
    if endpoint is None:
        return endpoint

    endpoint = endpoint.rstrip('/')

    clean_v = endpoint
    if endpoint.startswith(('http://', 'https://')):
        match = re.match(r'https?://(.+)', endpoint)
        if match:
            clean_v = match.group(1)

    endpoint_pattern = re.compile(
        r'^(\[[0-9a-fA-F:]+]|([a-zA-Z0-9\-_]+\.)*[a-zA-Z0-9\-_]+)(:[0-9]{1,5})?$'
    )

    if not endpoint_pattern.match(clean_v):
        raise ValueError(f"端点格式无效: {endpoint}，应为 host:port 或 http(s)://host:port 格式")

    return endpoint


def ensure_directory(path: Path) -> Path:
    """确保目录存在，如果不存在则创建

    参数:
        path: 目录路径

    返回:
        解析后的 Path 对象

    抛出:
        OSError: 目录创建失败时抛出
    """
    resolved_path = path.expanduser().resolve()
    resolved_path.mkdir(parents=True, exist_ok=True)

    if not os.access(resolved_path, os.W_OK):
        raise OSError(f"目录不可写: {resolved_path}")

    return resolved_path


class LocalStorageConfig(BaseModel):
    """本地存储配置

    定义本地文件系统存储的路径。

    - models_path: 模型存储路径（相对于项目根目录）
    - get_resolved_models_path: 获取解析后的模型存储路径
    """

    models_path: str = Field(default="models", description="模型存储路径（相对于项目根目录）")

    model_config = {"validate_assignment": True}

    def get_resolved_models_path(self) -> Path:
        """获取解析后的模型存储路径（确保目录存在且可写）

        返回:
            模型存储目录的 Path 对象
        """
        return ensure_directory(PROJECT_ROOT / self.models_path)


class MinIOStorageConfig(BaseModel):
    """MinIO存储配置

    定义 MinIO 对象存储的连接参数。

    - endpoint: MinIO服务端点
    - access_key: MinIO访问密钥
    - secret_key: MinIO秘密密钥
    - bucket: MinIO存储桶名称
    - secure: 是否使用HTTPS连接
    - region: MinIO区域（可选）
    - models_prefix: 模型对象前缀
    - timeout: 超时时间（秒）
    - max_connections: 最大连接数
    """

    endpoint: str = Field(default="localhost:9000", description="MinIO服务端点")
    access_key: str = Field(default="", description="MinIO访问密钥")
    secret_key: str = Field(default="", description="MinIO秘密密钥")
    bucket: str = Field(default=StorageConstants.DEFAULT_BUCKET_NAME, description="MinIO存储桶名称")
    secure: bool = Field(default=False, description="是否使用HTTPS连接")
    region: Optional[str] = Field(default=None, description="MinIO区域（可选）")
    models_prefix: str = Field(default="models/", description="模型对象前缀")
    timeout: int = Field(default=30, description="超时时间（秒）")
    max_connections: int = Field(default=10, description="最大连接数")

    model_config = {"validate_assignment": True}

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """验证端点格式"""
        result = validate_endpoint(v)
        return result if result is not None else v

    def get_models_prefix(self) -> str:
        """获取模型对象前缀（确保以斜杠结尾）"""
        return normalize_prefix(self.models_prefix)


class S3StorageConfig(BaseModel):
    """AWS S3存储配置

    定义 AWS S3 对象存储的连接参数。

    - endpoint: S3自定义端点（可选）
    - access_key_id: AWS访问密钥ID
    - secret_access_key: AWS秘密访问密钥
    - bucket: S3存储桶名称
    - region: AWS区域
    - prefix: S3对象键前缀
    - acl: S3对象ACL
    - use_ssl: 是否使用SSL连接
    - verify_ssl: 是否验证SSL证书
    - addressing_style: S3寻址风格
    - max_pool_connections: 连接池最大连接数
    - timeout: 请求超时时间（秒）
    - retries: 请求重试次数
    """

    endpoint: Optional[str] = Field(default=None, description="S3自定义端点（用于兼容S3的其他服务）")
    access_key_id: str = Field(default="", description="AWS访问密钥ID")
    secret_access_key: str = Field(default="", description="AWS秘密访问密钥")
    bucket: str = Field(default=StorageConstants.DEFAULT_BUCKET_NAME, description="S3存储桶名称")
    region: str = Field(default="us-east-1", description="AWS区域")
    prefix: str = Field(default="models/", description="S3对象键前缀")
    acl: Optional[str] = Field(default=None, description="S3对象ACL（如 'private', 'public-read'）")
    use_ssl: bool = Field(default=True, description="是否使用SSL连接S3")
    verify_ssl: bool = Field(default=True, description="是否验证SSL证书")
    addressing_style: str = Field(default="auto", description="S3寻址风格: auto/virtual/path")
    max_pool_connections: int = Field(default=10, description="S3连接池最大连接数")
    timeout: int = Field(default=30, description="S3请求超时时间（秒）")
    retries: int = Field(default=3, description="S3请求重试次数")

    model_config = {"validate_assignment": True}

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: Optional[str]) -> Optional[str]:
        """验证端点格式"""
        return validate_endpoint(v)

    def get_prefix(self) -> str:
        """获取对象前缀（确保以斜杠结尾）"""
        return normalize_prefix(self.prefix)


class StorageConfig(BaseConfig):
    """存储配置

    聚合所有存储后端配置，提供统一的存储配置入口。

    环境变量前缀：DATAMIND_STORAGE_
    例如：DATAMIND_STORAGE_STORAGE_TYPE=minio, DATAMIND_STORAGE_ENABLE_CACHE=true

    - storage_type: 存储类型
    - enable_cache: 是否启用存储缓存
    - enable_compression: 是否启用存储压缩
    - enable_encryption: 是否启用存储加密
    - chunk_size: 存储分块大小
    - multipart_threshold: 分片上传阈值
    - chunk_ratio: chunk_size 与 multipart_threshold 的推荐比例
    - local: 本地存储配置
    - minio: MinIO存储配置
    - s3: S3存储配置
    """

    __env_prefix__ = "DATAMIND_STORAGE_"

    __enum_mappings__ = {
        "storage_type": StorageType,
        "compression_library": CompressionLibrary,
    }

    # 存储类型
    storage_type: StorageType = Field(default=StorageType.LOCAL, alias="STORAGE_TYPE", description="存储类型: local/minio/s3")

    # 存储通用配置
    default_ttl: int = Field(default=StorageConstants.DEFAULT_DEFAULT_TTL, alias="DEFAULT_TTL", description="存储对象默认过期时间（秒）")
    enable_cache: bool = Field(default=True, alias="ENABLE_CACHE", description="是否启用存储缓存")
    cache_size: int = Field(default=StorageConstants.DEFAULT_CACHE_SIZE, alias="CACHE_SIZE", description="存储缓存大小（对象数量）")
    cache_ttl: int = Field(default=StorageConstants.DEFAULT_CACHE_TTL, alias="CACHE_TTL", description="存储缓存过期时间（秒）")
    enable_compression: bool = Field(default=False, alias="ENABLE_COMPRESSION", description="是否启用存储压缩")
    compression_level: int = Field(default=StorageConstants.DEFAULT_COMPRESSION_LEVEL, alias="COMPRESSION_LEVEL", description="存储压缩级别 (1-9)")
    compression_library: CompressionLibrary = Field(default=CompressionLibrary.ZLIB, alias="COMPRESSION_LIBRARY", description="压缩库类型: zlib/gzip/lz4/zstd")
    enable_encryption: bool = Field(default=False, alias="ENABLE_ENCRYPTION", description="是否启用存储加密")
    encryption_key: Optional[str] = Field(default=None, alias="ENCRYPTION_KEY", description="存储加密密钥")
    max_file_size: int = Field(default=StorageConstants.DEFAULT_MAX_FILE_SIZE, alias="MAX_FILE_SIZE", description="存储最大文件大小（字节）")
    allowed_extensions: List[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin", ".joblib", ".npy"],
        alias="ALLOWED_EXTENSIONS",
        description="允许存储的文件扩展名"
    )
    chunk_size: int = Field(default=StorageConstants.DEFAULT_CHUNK_SIZE, alias="CHUNK_SIZE", description="存储分块大小（用于大文件上传）")
    multipart_threshold: int = Field(default=StorageConstants.DEFAULT_MULTIPART_THRESHOLD, alias="MULTIPART_THRESHOLD", description="启用分片上传的阈值")
    chunk_ratio: int = Field(
        default=StorageConstants.DEFAULT_CHUNK_RATIO,
        ge=StorageConstants.MIN_CHUNK_RATIO,
        le=StorageConstants.MAX_CHUNK_RATIO,
        alias="CHUNK_RATIO",
        description="chunk_size 与 multipart_threshold 的推荐比例"
    )

    # 存储后端配置
    local: LocalStorageConfig = Field(default_factory=LocalStorageConfig, description="本地存储配置")
    minio: MinIOStorageConfig = Field(default_factory=MinIOStorageConfig, description="MinIO存储配置")
    s3: S3StorageConfig = Field(default_factory=S3StorageConfig, description="S3存储配置")

    # 运行环境
    env: str = Field(default="development", alias="ENV", description="运行环境: development/testing/staging/production")

    # ==================== 字段验证器 ====================

    @field_validator("compression_level")
    @classmethod
    def validate_compression_level(cls, v: int) -> int:
        """验证压缩级别在有效范围内"""
        if v < StorageConstants.MIN_COMPRESSION_LEVEL or v > StorageConstants.MAX_COMPRESSION_LEVEL:
            raise ValueError(
                f"compression_level 必须在 {StorageConstants.MIN_COMPRESSION_LEVEL} 到 "
                f"{StorageConstants.MAX_COMPRESSION_LEVEL} 之间"
            )
        return v

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v: int) -> int:
        """验证最大文件大小在有效范围内"""
        if v < StorageConstants.MIN_MAX_FILE_SIZE:
            raise ValueError(f"max_file_size 不能小于 {StorageConstants.MIN_MAX_FILE_SIZE // StorageConstants.MB}MB")
        if v > StorageConstants.MAX_MAX_FILE_SIZE:
            raise ValueError(f"max_file_size 不能大于 {StorageConstants.MAX_MAX_FILE_SIZE // StorageConstants.GB}GB")
        return v

    @field_validator("chunk_size")
    @classmethod
    def validate_chunk_size(cls, v: int) -> int:
        """验证分块大小在有效范围内"""
        if v < StorageConstants.MIN_CHUNK_SIZE:
            raise ValueError(f"chunk_size 不能小于 {StorageConstants.MIN_CHUNK_SIZE // StorageConstants.MB}MB")
        if v > StorageConstants.MAX_CHUNK_SIZE:
            raise ValueError(f"chunk_size 不能大于 {StorageConstants.MAX_CHUNK_SIZE // StorageConstants.MB}MB")
        return v

    @field_validator("multipart_threshold")
    @classmethod
    def validate_multipart_threshold(cls, v: int) -> int:
        """验证分片上传阈值在有效范围内"""
        if v < StorageConstants.MIN_MULTIPART_THRESHOLD:
            raise ValueError(
                f"multipart_threshold 不能小于 {StorageConstants.MIN_MULTIPART_THRESHOLD // StorageConstants.MB}MB"
            )
        if v > StorageConstants.MAX_MULTIPART_THRESHOLD:
            raise ValueError(
                f"multipart_threshold 不能大于 {StorageConstants.MAX_MULTIPART_THRESHOLD // StorageConstants.GB}GB"
            )
        return v

    @field_validator("cache_size")
    @classmethod
    def validate_cache_size(cls, v: int) -> int:
        """验证缓存大小在有效范围内"""
        if v < StorageConstants.MIN_CACHE_SIZE:
            raise ValueError(f"cache_size 必须大于等于 {StorageConstants.MIN_CACHE_SIZE}")
        if v > StorageConstants.MAX_CACHE_SIZE:
            raise ValueError(f"cache_size 不得超过 {StorageConstants.MAX_CACHE_SIZE}")
        return v

    @field_validator("cache_ttl")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        """验证缓存过期时间在有效范围内"""
        if v < StorageConstants.MIN_CACHE_TTL:
            raise ValueError(f"cache_ttl 必须大于等于 {StorageConstants.MIN_CACHE_TTL} 秒")
        if v > StorageConstants.MAX_CACHE_TTL:
            raise ValueError(f"cache_ttl 不得超过 {StorageConstants.MAX_CACHE_TTL // 3600} 小时")
        return v

    @field_validator("default_ttl")
    @classmethod
    def validate_default_ttl(cls, v: int) -> int:
        """验证默认过期时间有效"""
        if v < 0:
            raise ValueError("default_ttl 不能为负数")
        if v > 30 * 24 * 3600:
            raise ValueError("default_ttl 不能超过30天")
        return v

    @field_validator("allowed_extensions")
    @classmethod
    def validate_allowed_extensions(cls, v: List[str]) -> List[str]:
        """验证文件扩展名格式"""
        for ext in v:
            if not ext.startswith('.'):
                raise ValueError(f"文件扩展名必须以点开头: {ext}")
            if not re.match(r'^\.[a-zA-Z0-9_]+$', ext):
                raise ValueError(f"文件扩展名格式无效: {ext}，只允许字母、数字和下划线")
        return v

    @field_validator("chunk_ratio")
    @classmethod
    def validate_chunk_ratio(cls, v: int) -> int:
        """验证分块比例在有效范围内"""
        if v < StorageConstants.MIN_CHUNK_RATIO or v > StorageConstants.MAX_CHUNK_RATIO:
            raise ValueError(
                f"chunk_ratio 必须在 {StorageConstants.MIN_CHUNK_RATIO} 到 "
                f"{StorageConstants.MAX_CHUNK_RATIO} 之间"
            )
        return v

    # ==================== 存储类型特定验证方法 ====================

    def _validate_minio(self) -> None:
        """验证 MinIO 配置"""
        minio = self.minio

        if not minio.endpoint:
            raise ValueError("使用MinIO存储时必须提供 minio.endpoint")

        validate_endpoint(minio.endpoint)

        if not minio.access_key:
            raise ValueError("使用MinIO存储时必须提供 minio.access_key")
        if not minio.secret_key:
            raise ValueError("使用MinIO存储时必须提供 minio.secret_key")
        if not minio.bucket:
            raise ValueError("使用MinIO存储时必须提供 minio.bucket")

        if self.env == "production":
            if minio.access_key == "" or minio.secret_key == "":
                raise ValueError("生产环境使用MinIO时必须设置有效的 access_key 和 secret_key")
            if minio.bucket == StorageConstants.DEFAULT_BUCKET_NAME:
                _debug("生产环境建议修改MinIO默认存储桶名称")

    def _validate_s3(self) -> None:
        """验证 S3 配置"""
        s3 = self.s3

        if not s3.access_key_id:
            raise ValueError("使用S3存储时必须提供 s3.access_key_id")
        if not s3.secret_access_key:
            raise ValueError("使用S3存储时必须提供 s3.secret_access_key")
        if not s3.bucket:
            raise ValueError("使用S3存储时必须提供 s3.bucket")

        if s3.endpoint:
            validate_endpoint(s3.endpoint)

        if self.env == "production":
            if s3.access_key_id == "" or s3.secret_access_key == "":
                raise ValueError("生产环境使用S3时必须设置有效的 access_key_id 和 secret_access_key")
            if s3.bucket == StorageConstants.DEFAULT_BUCKET_NAME:
                _debug("生产环境建议修改S3默认存储桶名称")

    def _validate_local(self) -> None:
        """验证本地存储配置"""
        _debug("本地存储路径: %s", self.local.models_path)
        self.local.get_resolved_models_path()

    # ==================== 通用配置验证 ====================

    def _validate_encryption(self) -> None:
        """验证加密配置"""
        if not self.enable_encryption:
            return

        if not self.encryption_key:
            raise ValueError("启用加密时必须提供 encryption_key")

        if len(self.encryption_key) < StorageConstants.MIN_ENCRYPTION_KEY_LEN:
            raise ValueError(
                f"encryption_key 长度必须至少为 {StorageConstants.MIN_ENCRYPTION_KEY_LEN} 位"
            )

        if not StorageConstants.ENCRYPTION_KEY_PATTERN.match(self.encryption_key):
            raise ValueError(
                "encryption_key 必须至少32位且只包含字母、数字和特殊字符 !@#$%^&*()_+=-"
            )

    def _validate_cache(self) -> None:
        """验证缓存配置"""
        if not self.enable_cache:
            return

        if self.cache_size < StorageConstants.MIN_CACHE_SIZE:
            raise ValueError(f"enable_cache=True 时 cache_size 必须大于 {StorageConstants.MIN_CACHE_SIZE}")
        if self.cache_ttl < StorageConstants.MIN_CACHE_TTL:
            raise ValueError(f"enable_cache=True 时 cache_ttl 必须大于 {StorageConstants.MIN_CACHE_TTL}")

    def _validate_compression(self) -> None:
        """验证压缩配置"""
        if not self.enable_compression:
            return

        if self.compression_level < StorageConstants.MIN_COMPRESSION_LEVEL or \
           self.compression_level > StorageConstants.MAX_COMPRESSION_LEVEL:
            raise ValueError(
                f"enable_compression=True 时 compression_level 必须在 "
                f"{StorageConstants.MIN_COMPRESSION_LEVEL}-{StorageConstants.MAX_COMPRESSION_LEVEL} 之间"
            )

        lib_key = self.compression_library.value
        if lib_key not in StorageConstants.COMPRESSION_LIBRARY_RANGES:
            _debug("未知压缩库类型: %s，将使用默认行为", lib_key)
        else:
            min_recommended, max_recommended = StorageConstants.COMPRESSION_LIBRARY_RANGES[lib_key]
            if self.compression_level < min_recommended or self.compression_level > max_recommended:
                _debug(
                    "%s 压缩级别建议范围 %d-%d，当前使用级别 %d",
                    lib_key.upper(), min_recommended, max_recommended, self.compression_level
                )

    def _validate_chunk_upload(self) -> None:
        """验证分块上传配置并自动调整"""
        if self.chunk_size <= 0:
            raise ValueError("chunk_size 必须大于0")

        if self.multipart_threshold <= 0:
            raise ValueError("multipart_threshold 必须大于0")

        self._auto_adjust_chunk_params()

        optimal_chunk_size = self.multipart_threshold // self.chunk_ratio
        if self.chunk_size * self.chunk_ratio > self.multipart_threshold:
            _debug(
                "chunk_size (%s) 接近 multipart_threshold (%s)，建议 chunk_size ≤ %s 以获得更好性能",
                self.chunk_size, self.multipart_threshold, optimal_chunk_size
            )

    def _auto_adjust_chunk_params(self) -> bool:
        """自动调整分块参数"""
        adjustments = []
        adjusted = False

        if self.chunk_size > self.multipart_threshold:
            old_chunk = self.chunk_size
            self.chunk_size = self.multipart_threshold // self.chunk_ratio
            if self.chunk_size < StorageConstants.MIN_CHUNK_SIZE:
                self.chunk_size = StorageConstants.MIN_CHUNK_SIZE
            adjustments.append(f"chunk_size: {old_chunk} -> {self.chunk_size} (超过 multipart_threshold)")
            adjusted = True

        if self.chunk_size < StorageConstants.MIN_CHUNK_SIZE:
            old_chunk = self.chunk_size
            self.chunk_size = StorageConstants.MIN_CHUNK_SIZE
            adjustments.append(f"chunk_size: {old_chunk} -> {self.chunk_size} (低于最小值)")
            adjusted = True

        if self.multipart_threshold > StorageConstants.MAX_MULTIPART_THRESHOLD:
            old_threshold = self.multipart_threshold
            self.multipart_threshold = StorageConstants.MAX_MULTIPART_THRESHOLD
            adjustments.append(f"multipart_threshold: {old_threshold} -> {self.multipart_threshold} (超过最大值)")
            adjusted = True

        if self.chunk_size * self.chunk_ratio > self.multipart_threshold:
            old_chunk = self.chunk_size
            recommended_chunk = self.multipart_threshold // self.chunk_ratio
            if recommended_chunk >= StorageConstants.MIN_CHUNK_SIZE:
                self.chunk_size = recommended_chunk
                adjustments.append(f"chunk_size: {old_chunk} -> {self.chunk_size} (比例不合理)")
                adjusted = True

        if adjustments:
            _debug("分块参数已自动调整: %s", '; '.join(adjustments))

        return adjusted

    @model_validator(mode='after')
    def validate_storage_config(self):
        """验证存储配置的完整性和一致性"""
        _debug("存储配置验证通过，当前使用存储类型: %s", self.storage_type.value)

        if self.storage_type == StorageType.MINIO:
            self._validate_minio()
        elif self.storage_type == StorageType.S3:
            self._validate_s3()
        else:
            self._validate_local()

        self._validate_encryption()
        self._validate_cache()
        self._validate_compression()
        self._validate_chunk_upload()

        return self

    # ==================== 公共方法 ====================

    def is_cloud_storage(self) -> bool:
        """判断是否为云存储

        返回:
            True 表示云存储（MinIO 或 S3），False 表示本地存储
        """
        return self.storage_type in (StorageType.MINIO, StorageType.S3)

    def get_effective_cache_ttl(self) -> Optional[int]:
        """获取有效的缓存过期时间

        当缓存禁用时返回 None，避免业务代码误用

        返回:
            缓存过期时间（秒），缓存禁用时返回 None
        """
        return self.cache_ttl if self.enable_cache else None

    def get_effective_cache_size(self) -> Optional[int]:
        """获取有效的缓存大小

        当缓存禁用时返回 None，避免业务代码误用

        返回:
            缓存大小（对象数量），缓存禁用时返回 None
        """
        return self.cache_size if self.enable_cache else None

    def get_compression_library_module(self):
        """获取压缩库对应的模块对象

        返回:
            压缩库模块对象
        """
        module_name = self.get_compression_library_module_name()
        return importlib.import_module(module_name)

    def get_compression_library_module_name(self) -> str:
        """获取压缩库对应的模块名

        返回:
            压缩库模块名
        """
        library_map = {
            CompressionLibrary.ZLIB: "zlib",
            CompressionLibrary.GZIP: "gzip",
            CompressionLibrary.LZ4: "lz4.frame",
            CompressionLibrary.ZSTD: "zstandard",
        }
        return library_map.get(self.compression_library, "zlib")

    def get_encryption_key_hash(self) -> Optional[str]:
        """获取加密密钥的 SHA256 哈希值（用于调试，不暴露原始密钥）

        返回:
            密钥的 SHA256 哈希值，未启用加密时返回 None
        """
        if not self.enable_encryption or not self.encryption_key:
            return None
        return hashlib.sha256(self.encryption_key.encode()).hexdigest()[:16]

    def to_summary_dict(self) -> Dict[str, Any]:
        """获取存储配置摘要（用于调试和监控）

        返回:
            配置摘要字典，包含关键配置项
        """
        summary: Dict[str, Any] = {
            "storage_type": self.storage_type.value,
            "enable_cache": self.enable_cache,
            "cache_size": self.cache_size if self.enable_cache else None,
            "cache_ttl": self.cache_ttl if self.enable_cache else None,
            "enable_compression": self.enable_compression,
            "compression_library": self.compression_library.value if self.enable_compression else None,
            "compression_level": self.compression_level if self.enable_compression else None,
            "enable_encryption": self.enable_encryption,
            "encryption_key_hash": self.get_encryption_key_hash(),
            "max_file_size_mb": self.max_file_size // StorageConstants.MB,
            "chunk_size_mb": self.chunk_size // StorageConstants.MB,
            "multipart_threshold_mb": self.multipart_threshold // StorageConstants.MB,
            "chunk_ratio": self.chunk_ratio,
        }

        if self.storage_type == StorageType.MINIO:
            summary["minio"] = {
                "endpoint": self.minio.endpoint,
                "bucket": self.minio.bucket,
                "secure": self.minio.secure,
                "region": self.minio.region,
                "access_key": _mask_sensitive(self.minio.access_key, "access_key") if self.minio.access_key else None,
                "secret_key": "***" if self.minio.secret_key else None,
            }
        elif self.storage_type == StorageType.S3:
            summary["s3"] = {
                "bucket": self.s3.bucket,
                "region": self.s3.region,
                "use_ssl": self.s3.use_ssl,
                "verify_ssl": self.s3.verify_ssl,
                "endpoint": self.s3.endpoint,
                "access_key_id": _mask_sensitive(self.s3.access_key_id, "access_key_id") if self.s3.access_key_id else None,
                "secret_access_key": "***" if self.s3.secret_access_key else None,
            }
        else:
            summary["local"] = {
                "models_path": self.local.models_path,
                "resolved_models_path": str(self.local.get_resolved_models_path()),
            }

        return summary


__all__ = [
    "StorageConfig",
    "StorageType",
    "CompressionLibrary",
    "LocalStorageConfig",
    "MinIOStorageConfig",
    "S3StorageConfig",
    "StorageConstants",
    "validate_endpoint",
    "normalize_prefix",
    "ensure_directory",
]