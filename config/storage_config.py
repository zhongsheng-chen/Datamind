# datamind/config/storage_config.py
"""
存储配置模块

用于管理不同存储类型的配置和客户端初始化
"""
import os
import time
import json
import logging
import threading
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Union, Literal, ClassVar, List, Callable
from enum import Enum
from datetime import datetime
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator, ConfigDict

# 基础应用名称
APP_NAME = os.getenv("DATAMIND_APP_NAME", "datamind").lower()

# 设置日志层级
logger = logging.getLogger(f"{APP_NAME}.storage")

BASE_DIR = Path(
    os.getenv(
        "DATAMIND_HOME",
        Path(__file__).resolve().parent.parent
    )
).resolve()


class StorageType(str, Enum):
    """存储类型枚举"""
    LOCAL = "local"
    MINIO = "minio"
    S3 = "s3"


class LocalStorageConfig(BaseModel):
    """本地存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    base_path: Path = Field(..., description="本地存储基础路径")
    models_subpath: str = Field(default="models", description="模型子路径")

    @property
    def models_path(self) -> Path:
        """获取模型存储路径"""
        return self.base_path / self.models_subpath

    def ensure_directories(self):
        """确保目录存在"""
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.models_path.mkdir(parents=True, exist_ok=True)
        return self


class MinIOStorageConfig(BaseModel):
    """MinIO存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    endpoint: str = Field(..., description="MinIO服务端点")
    access_key: str = Field(..., description="访问密钥")
    secret_key: str = Field(..., description="秘密密钥")
    bucket: str = Field(..., description="存储桶名称")
    secure: bool = Field(default=False, description="是否使用HTTPS")
    region: Optional[str] = Field(default=None, description="区域")
    location: str = Field(default="us-east-1", description="存储桶位置")
    models_prefix: str = Field(default="models/", description="模型对象前缀")

    # 客户端配置
    timeout: int = Field(default=30, description="超时时间（秒）")
    max_connections: int = Field(default=10, description="最大连接数")

    @property
    def models_path(self) -> str:
        """获取模型存储路径（bucket/prefix格式）"""
        return f"{self.bucket}/{self.models_prefix.rstrip('/')}"

    @property
    def connection_params(self) -> Dict[str, Any]:
        """获取连接参数"""
        return {
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": self.secret_key,
            "secure": self.secure,
            "region": self.region,
            "timeout": self.timeout,
            "max_connections": self.max_connections,
        }


class S3StorageConfig(BaseModel):
    """AWS S3存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    endpoint: Optional[str] = Field(default=None, description="自定义端点")
    access_key_id: str = Field(..., description="访问密钥ID")
    secret_access_key: str = Field(..., description="秘密访问密钥")
    bucket: str = Field(..., description="存储桶名称")
    region: str = Field(default="us-east-1", description="区域")
    prefix: str = Field(default="models/", description="对象键前缀")
    acl: Optional[str] = Field(default=None, description="对象ACL")

    # 连接配置
    use_ssl: bool = Field(default=True, description="是否使用SSL")
    verify_ssl: bool = Field(default=True, description="是否验证SSL证书")
    addressing_style: Literal["auto", "virtual", "path"] = Field(default="auto", description="寻址风格")
    max_pool_connections: int = Field(default=10, description="连接池最大连接数")
    timeout: int = Field(default=30, description="请求超时时间（秒）")
    retries: int = Field(default=3, description="重试次数")

    @property
    def models_path(self) -> str:
        """获取模型存储路径（bucket/prefix格式）"""
        return f"{self.bucket}/{self.prefix.rstrip('/')}"

    @property
    def connection_params(self) -> Dict[str, Any]:
        """获取连接参数"""
        return {
            "endpoint_url": self.endpoint,
            "aws_access_key_id": self.access_key_id,
            "aws_secret_access_key": self.secret_access_key,
            "region_name": self.region,
            "use_ssl": self.use_ssl,
            "verify": self.verify_ssl,
            "config": {
                "addressing_style": self.addressing_style,
                "max_pool_connections": self.max_pool_connections,
                "connect_timeout": self.timeout,
                "read_timeout": self.timeout,
                "retries": {"max_attempts": self.retries},
            }
        }


@dataclass
class ConfigChangeEvent:
    """配置变更事件"""
    old_config: 'StorageConfig'
    new_config: 'StorageConfig'
    changes: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class StorageConfig(BaseModel):
    """统一存储配置"""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # 存储类型
    type: StorageType = Field(default=StorageType.LOCAL, description="存储类型")

    # 存储配置
    local: Optional[LocalStorageConfig] = Field(default=None, description="本地存储配置")
    minio: Optional[MinIOStorageConfig] = Field(default=None, description="MinIO存储配置")
    s3: Optional[S3StorageConfig] = Field(default=None, description="S3存储配置")

    # 通用配置
    default_ttl: int = Field(default=86400, description="默认过期时间（秒）")
    enable_cache: bool = Field(default=True, description="是否启用缓存")
    cache_size: int = Field(default=100, description="缓存大小（对象数量）")
    cache_ttl: int = Field(default=300, description="缓存过期时间（秒）")
    enable_compression: bool = Field(default=False, description="是否启用压缩")
    compression_level: int = Field(default=6, description="压缩级别 (1-9)")
    enable_encryption: bool = Field(default=False, description="是否启用加密")
    encryption_key: Optional[str] = Field(default=None, description="加密密钥")
    max_file_size: int = Field(default=1024 * 1024 * 1024, description="最大文件大小（字节）")
    allowed_extensions: list[str] = Field(
        default=[".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin", ".joblib", ".npy"],
        description="允许的文件扩展名"
    )
    chunk_size: int = Field(default=1024 * 1024 * 8, description="分块大小（字节）")
    multipart_threshold: int = Field(default=1024 * 1024 * 100, description="分片上传阈值（字节）")

    # 私有属性
    _env: Optional[str] = None
    _base_dir: Optional[Path] = None
    _last_modified: Optional[datetime] = None
    _config_source: Optional[str] = None
    _change_listeners: ClassVar[List[Callable[[ConfigChangeEvent], None]]] = []
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()
    _instance_cache: ClassVar[Dict[str, 'StorageConfig']] = {}

    @field_validator("compression_level")
    @classmethod
    def validate_compression_level(cls, v):
        """验证压缩级别"""
        if v < 1 or v > 9:
            raise ValueError("压缩级别必须在 1 到 9 之间")
        return v

    @field_validator("max_file_size")
    @classmethod
    def validate_max_file_size(cls, v):
        """验证最大文件大小"""
        if v < 1024 * 1024:
            raise ValueError("文件大小不能小于1MB")
        return v

    @property
    def active_config(self) -> Union[LocalStorageConfig, MinIOStorageConfig, S3StorageConfig]:
        """获取当前激活的存储配置"""
        if self.type == StorageType.LOCAL:
            if self.local is None:
                raise ValueError("本地存储配置未设置")
            return self.local
        elif self.type == StorageType.MINIO:
            if self.minio is None:
                raise ValueError("MinIO存储配置未设置")
            return self.minio
        elif self.type == StorageType.S3:
            if self.s3 is None:
                raise ValueError("S3存储配置未设置")
            return self.s3
        else:
            raise ValueError(f"不支持的存储类型: {self.type}")

    @property
    def models_path(self) -> str:
        """获取模型存储路径"""
        return self.active_config.models_path

    @property
    def models_path_local(self) -> Path:
        """获取本地缓存路径"""
        if self.type == StorageType.LOCAL:
            return self.active_config.models_path
        else:
            cache_dir = Path("/tmp/datamind/models_cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
            return cache_dir

    @classmethod
    def get_cached(cls, env: Optional[str] = None, base_dir: Optional[Path] = None) -> 'StorageConfig':
        """获取缓存的配置实例"""
        cache_key = f"{env or 'default'}_{str(base_dir or '')}"

        with cls._cache_lock:
            if cache_key not in cls._instance_cache:
                cls._instance_cache[cache_key] = cls.load(env=env, base_dir=base_dir)
            return cls._instance_cache[cache_key]

    def invalidate_cache(self):
        """使配置缓存失效"""
        with self.__class__._cache_lock:
            cache_key = f"{self._env or 'default'}_{str(self._base_dir or '')}"
            if cache_key in self.__class__._instance_cache:
                del self.__class__._instance_cache[cache_key]

    @classmethod
    def add_change_listener(cls, listener: Callable[[ConfigChangeEvent], None]):
        """添加配置变更监听器"""
        if listener not in cls._change_listeners:
            cls._change_listeners.append(listener)

    @classmethod
    def remove_change_listener(cls, listener: Callable[[ConfigChangeEvent], None]):
        """移除配置变更监听器"""
        if listener in cls._change_listeners:
            cls._change_listeners.remove(listener)

    def _notify_change(self, old_config: 'StorageConfig'):
        """通知配置变更"""
        changes = self._get_changes(old_config)
        if not changes:
            return

        event = ConfigChangeEvent(
            old_config=old_config,
            new_config=self,
            changes=changes
        )

        for listener in self.__class__._change_listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"配置变更监听器执行失败: {e}")

    def _get_changes(self, old_config: 'StorageConfig') -> Dict[str, Any]:
        """获取配置变更详情"""
        changes = {}
        # 使用 model_dump 替代 dict() (Pydantic v2 推荐)
        old_dict = old_config.model_dump()
        new_dict = self.model_dump()

        for key in set(old_dict.keys()) | set(new_dict.keys()):
            old_value = old_dict.get(key)
            new_value = new_dict.get(key)
            if old_value != new_value:
                changes[key] = {
                    'old': old_value,
                    'new': new_value
                }

        return changes

    @classmethod
    def load(cls, env: Optional[str] = None, base_dir: Optional[Path] = None) -> 'StorageConfig':
        """
        加载存储配置

        Args:
            env: 环境名称，如 development/production
            base_dir: 基础目录（项目根目录）

        Returns:
            StorageConfig: 存储配置对象
        """
        # 导入settings（延迟导入，避免循环依赖）
        from config.settings import settings as app_settings

        # 确定环境
        if env is None:
            env = app_settings.ENV

        # 确定基础目录
        base_dir = (base_dir or BASE_DIR).resolve()

        # 创建配置实例
        config = StorageConfigFactory.create_from_settings(app_settings, base_dir=base_dir)

        # 保存环境信息
        config._env = env
        config._base_dir = base_dir
        config._last_modified = datetime.now()
        config._config_source = "settings"

        # 确保目录存在
        config.ensure_directories()

        return config

    def reload(self) -> 'StorageConfig':
        """
        重新加载配置

        Returns:
            StorageConfig: 新的存储配置对象
        """
        old_config = self.model_copy()  # 使用 model_copy 替代 copy() (Pydantic v2)
        new_config = self.__class__.load(env=self._env, base_dir=self._base_dir)
        self._notify_change(old_config)
        return new_config

    def get_config_digest(self) -> str:
        """
        获取配置摘要，用于判断配置是否变化
        """
        # 使用 model_dump_json 替代手动 JSON 序列化
        config_str = self.model_dump_json(sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def get_config_metadata(self) -> Dict[str, Any]:
        """获取配置元数据"""
        return {
            'env': self._env,
            'base_dir': str(self._base_dir) if self._base_dir else None,
            'last_modified': self._last_modified.isoformat() if self._last_modified else None,
            'source': self._config_source,
            'digest': self.get_config_digest()[:8]
        }

    async def validate_connection(self) -> Dict[str, Any]:
        """验证存储连接是否可用"""
        result = {'success': False, 'details': {}, 'error': None}

        try:
            if self.type == StorageType.LOCAL:
                # 测试本地写入
                test_file = self.models_path_local / '.connection_test'
                test_file.write_text('test')
                test_file.unlink()
                result['success'] = True
                result['details']['path'] = str(self.models_path_local)

            elif self.type == StorageType.MINIO:
                # 测试 MinIO 连接
                from minio import Minio
                client = Minio(**self.active_config.connection_params)
                result['success'] = client.bucket_exists(self.active_config.bucket)
                result['details']['bucket'] = self.active_config.bucket
                result['details']['endpoint'] = self.active_config.endpoint

            elif self.type == StorageType.S3:
                # 测试 S3 连接
                import boto3
                from botocore.config import Config

                config = Config(**self.active_config.connection_params['config'])
                session = boto3.Session(
                    aws_access_key_id=self.active_config.access_key_id,
                    aws_secret_access_key=self.active_config.secret_access_key,
                    region_name=self.active_config.region
                )
                s3 = session.client('s3', config=config,
                                    endpoint_url=self.active_config.endpoint)
                # 尝试列出桶中的对象来验证连接
                s3.list_objects_v2(Bucket=self.active_config.bucket, MaxKeys=1)
                result['success'] = True
                result['details']['bucket'] = self.active_config.bucket
                result['details']['region'] = self.active_config.region

        except ImportError as e:
            result['error'] = f"缺少必要的库: {e}"
        except Exception as e:
            result['error'] = str(e)

        return result

    def validate_all(self) -> Dict[str, Any]:
        """
        全面验证配置，返回验证报告
        """
        report = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'info': {
                'type': self.type.value,
                'models_path': self.models_path,
                'config_digest': self.get_config_digest()[:8],
                'metadata': self.get_config_metadata()
            }
        }

        # 检查目录权限
        try:
            if self.type == StorageType.LOCAL:
                if not os.access(self.models_path_local, os.W_OK):
                    report['errors'].append(f"存储目录不可写: {self.models_path_local}")
                    report['valid'] = False
        except Exception as e:
            report['errors'].append(f"检查存储目录失败: {e}")
            report['valid'] = False

        # 检查加密配置
        if self.enable_encryption and not self.encryption_key:
            report['errors'].append("启用加密时必须提供 encryption_key")
            report['valid'] = False

        # 检查压缩级别
        if self.compression_level < 1 or self.compression_level > 9:
            report['errors'].append("compression_level 必须在 1-9 之间")
            report['valid'] = False

        # 检查文件大小
        if self.max_file_size < 1024 * 1024:
            report['warnings'].append(f"max_file_size 设置过小 ({self.max_file_size} < 1MB)")

        # 检查存储类型特定配置
        if self.type == StorageType.MINIO and self.minio:
            if not self.minio.endpoint:
                report['errors'].append("MinIO endpoint 不能为空")
                report['valid'] = False
            if not self.minio.bucket:
                report['errors'].append("MinIO bucket 不能为空")
                report['valid'] = False

        elif self.type == StorageType.S3 and self.s3:
            if not self.s3.access_key_id:
                report['warnings'].append("S3 access_key_id 未设置")
            if not self.s3.bucket:
                report['errors'].append("S3 bucket 不能为空")
                report['valid'] = False

        return report

    def to_dict(self, exclude_sensitive: bool = True) -> Dict[str, Any]:
        """
        导出配置为字典
        """
        data = self.model_dump()

        if exclude_sensitive:
            sensitive_keys = ['access_key', 'secret_key', 'access_key_id', 'secret_access_key', 'encryption_key']

            def mask_sensitive_values(d):
                if isinstance(d, dict):
                    for key, value in list(d.items()):
                        if key in sensitive_keys and value:
                            d[key] = '***'
                        elif isinstance(value, (dict, list)):
                            mask_sensitive_values(value)
                elif isinstance(d, list):
                    for item in d:
                        mask_sensitive_values(item)
                return d

            data = mask_sensitive_values(data)

        return data

    def is_equivalent_to(self, other: 'StorageConfig') -> bool:
        """
        判断两个配置是否等效
        """
        return self.get_config_digest() == other.get_config_digest()

    def get_client_config(self) -> Dict[str, Any]:
        """获取客户端配置"""
        config = {
            "type": self.type.value,
            "default_ttl": self.default_ttl,
            "enable_cache": self.enable_cache,
            "cache_size": self.cache_size,
            "cache_ttl": self.cache_ttl,
            "enable_compression": self.enable_compression,
            "compression_level": self.compression_level,
            "enable_encryption": self.enable_encryption,
            "encryption_key": self.encryption_key,
            "max_file_size": self.max_file_size,
            "allowed_extensions": self.allowed_extensions,
            "chunk_size": self.chunk_size,
            "multipart_threshold": self.multipart_threshold,
        }

        if hasattr(self.active_config, 'connection_params'):
            config.update(self.active_config.connection_params)

        return config

    def ensure_directories(self):
        """确保必要的目录存在"""
        if self.type == StorageType.LOCAL:
            self.active_config.ensure_directories()
        else:
            self.models_path_local.mkdir(parents=True, exist_ok=True)
        return self

    def to_readable(self, as_string: bool = False) -> Union[Dict[str, Any], str]:
        """返回人类可读的配置信息

        Args:
            as_string: 是否返回JSON字符串格式

        Returns:
            Union[Dict[str, Any], str]: 字典或JSON字符串
        """
        data = {
            "type": self.type.value,
            "models_path": self.models_path,
            "models_path_local": str(self.models_path_local),
            "config": self.get_client_config(),
            "metadata": self.get_config_metadata()
        }

        if as_string:
            return json.dumps(data, indent=2, default=str, ensure_ascii=False)
        return data

    def to_json(self) -> str:
        """转换为JSON字符串"""
        return self.model_dump_json(indent=2)

    def export_to_file(self, filepath: Union[str, Path], format: Literal['json', 'yaml'] = 'json'):
        """导出配置到文件"""
        filepath = Path(filepath)
        data = self.to_dict(exclude_sensitive=True)

        if format == 'json':
            filepath.write_text(json.dumps(data, indent=2, default=str))
        elif format == 'yaml':
            try:
                import yaml
                filepath.write_text(yaml.dump(data, default_flow_style=False))
            except ImportError:
                raise ImportError("导出YAML格式需要安装PyYAML: pip install pyyaml")
        else:
            raise ValueError(f"不支持的格式: {format}")

        logger.info(f"配置已导出到: {filepath}")

    @classmethod
    def import_from_file(cls, filepath: Union[str, Path]) -> 'StorageConfig':
        """从文件导入配置"""
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"配置文件不存在: {filepath}")

        if filepath.suffix == '.json':
            data = json.loads(filepath.read_text())
        elif filepath.suffix in ['.yaml', '.yml']:
            try:
                import yaml
                data = yaml.safe_load(filepath.read_text())
            except ImportError:
                raise ImportError("导入YAML格式需要安装PyYAML: pip install pyyaml")
        else:
            raise ValueError(f"不支持的文件格式: {filepath.suffix}")

        config = StorageConfigFactory.create_from_dict(data)
        config._config_source = str(filepath)
        config._last_modified = datetime.fromtimestamp(filepath.stat().st_mtime)

        return config


class StorageConfigFactory:
    """存储配置工厂类"""

    @classmethod
    def create_from_settings(cls, settings, base_dir: Optional[Path] = None) -> StorageConfig:
        """
        从settings创建存储配置

        Args:
            settings: settings模块的实例
            base_dir: 基础目录（项目根目录）

        Returns:
            StorageConfig: 存储配置对象
        """
        storage_type = StorageType(settings.STORAGE_TYPE)

        if storage_type == StorageType.LOCAL:
            # 本地存储路径处理
            local_path = Path(settings.LOCAL_STORAGE_PATH)
            if not local_path.is_absolute() and base_dir:
                local_path = base_dir / local_path

            local_config = LocalStorageConfig(
                base_path=local_path,
                models_subpath="models"
            )
            minio_config = None
            s3_config = None

        elif storage_type == StorageType.MINIO:
            local_config = None
            minio_config = MinIOStorageConfig(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                bucket=settings.MINIO_BUCKET,
                secure=settings.MINIO_SECURE,
                region=settings.MINIO_REGION,
                location=settings.MINIO_LOCATION,
                models_prefix="models/",
                timeout=getattr(settings, 'STORAGE_TIMEOUT', 30),
                max_connections=getattr(settings, 'S3_MAX_POOL_CONNECTIONS', 10)
            )
            s3_config = None

        elif storage_type == StorageType.S3:
            local_config = None
            minio_config = None
            s3_config = S3StorageConfig(
                endpoint=settings.S3_ENDPOINT,
                access_key_id=settings.S3_ACCESS_KEY_ID,
                secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                bucket=settings.S3_BUCKET,
                region=settings.S3_REGION,
                prefix=settings.S3_PREFIX,
                acl=settings.S3_ACL,
                use_ssl=settings.S3_USE_SSL,
                verify_ssl=settings.S3_VERIFY_SSL,
                addressing_style=settings.S3_ADDRESSING_STYLE,
                max_pool_connections=settings.S3_MAX_POOL_CONNECTIONS,
                timeout=settings.S3_TIMEOUT,
                retries=settings.S3_RETRIES
            )

        else:
            raise ValueError(f"不支持的存储类型: {storage_type}")

        return StorageConfig(
            type=storage_type,
            local=local_config,
            minio=minio_config,
            s3=s3_config,
            default_ttl=settings.STORAGE_DEFAULT_TTL,
            enable_cache=settings.STORAGE_ENABLE_CACHE,
            cache_size=settings.STORAGE_CACHE_SIZE,
            cache_ttl=settings.STORAGE_CACHE_TTL,
            enable_compression=settings.STORAGE_ENABLE_COMPRESSION,
            compression_level=settings.STORAGE_COMPRESSION_LEVEL,
            enable_encryption=settings.STORAGE_ENABLE_ENCRYPTION,
            encryption_key=settings.STORAGE_ENCRYPTION_KEY,
            max_file_size=settings.STORAGE_MAX_FILE_SIZE,
            allowed_extensions=settings.STORAGE_ALLOWED_EXTENSIONS,
            chunk_size=settings.STORAGE_CHUNK_SIZE,
            multipart_threshold=settings.STORAGE_MULTIPART_THRESHOLD
        )

    @classmethod
    def create_from_dict(cls, config_dict: Dict[str, Any]) -> StorageConfig:
        """
        从字典创建存储配置

        Args:
            config_dict: 配置字典

        Returns:
            StorageConfig: 存储配置对象
        """
        storage_type = StorageType(config_dict.get("type", "local"))

        local_config = None
        minio_config = None
        s3_config = None

        if storage_type == StorageType.LOCAL:
            local_config = LocalStorageConfig(
                base_path=Path(config_dict.get("local", {}).get("base_path", "./models")),
                models_subpath=config_dict.get("local", {}).get("models_subpath", "models")
            )
        elif storage_type == StorageType.MINIO:
            minio_config_dict = config_dict.get("minio", {})
            minio_config = MinIOStorageConfig(
                endpoint=minio_config_dict.get("endpoint", "localhost:9000"),
                access_key=minio_config_dict.get("access_key", "minioadmin"),
                secret_key=minio_config_dict.get("secret_key", "minioadmin"),
                bucket=minio_config_dict.get("bucket", "datamind-storage"),
                secure=minio_config_dict.get("secure", False),
                region=minio_config_dict.get("region"),
                location=minio_config_dict.get("location", "us-east-1"),
                models_prefix=minio_config_dict.get("models_prefix", "models/"),
                timeout=minio_config_dict.get("timeout", 30),
                max_connections=minio_config_dict.get("max_connections", 10)
            )
        elif storage_type == StorageType.S3:
            s3_config_dict = config_dict.get("s3", {})
            s3_config = S3StorageConfig(
                endpoint=s3_config_dict.get("endpoint"),
                access_key_id=s3_config_dict.get("access_key_id", ""),
                secret_access_key=s3_config_dict.get("secret_access_key", ""),
                bucket=s3_config_dict.get("bucket", "datamind-storage"),
                region=s3_config_dict.get("region", "us-east-1"),
                prefix=s3_config_dict.get("prefix", "models/"),
                acl=s3_config_dict.get("acl"),
                use_ssl=s3_config_dict.get("use_ssl", True),
                verify_ssl=s3_config_dict.get("verify_ssl", True),
                addressing_style=s3_config_dict.get("addressing_style", "auto"),
                max_pool_connections=s3_config_dict.get("max_pool_connections", 10),
                timeout=s3_config_dict.get("timeout", 30),
                retries=s3_config_dict.get("retries", 3)
            )

        return StorageConfig(
            type=storage_type,
            local=local_config,
            minio=minio_config,
            s3=s3_config,
            default_ttl=config_dict.get("default_ttl", 86400),
            enable_cache=config_dict.get("enable_cache", True),
            cache_size=config_dict.get("cache_size", 100),
            cache_ttl=config_dict.get("cache_ttl", 300),
            enable_compression=config_dict.get("enable_compression", False),
            compression_level=config_dict.get("compression_level", 6),
            enable_encryption=config_dict.get("enable_encryption", False),
            encryption_key=config_dict.get("encryption_key"),
            max_file_size=config_dict.get("max_file_size", 1024 * 1024 * 1024),
            allowed_extensions=config_dict.get("allowed_extensions",
                                               [".pkl", ".json", ".txt", ".pt", ".h5", ".onnx", ".cbm", ".bin",
                                                ".joblib", ".npy"]),
            chunk_size=config_dict.get("chunk_size", 1024 * 1024 * 8),
            multipart_threshold=config_dict.get("multipart_threshold", 1024 * 1024 * 100)
        )

    @classmethod
    def create_from_env(cls) -> StorageConfig:
        """从环境变量创建配置"""
        config_dict = {
            'type': os.getenv('STORAGE_TYPE', 'local'),
            'default_ttl': int(os.getenv('STORAGE_DEFAULT_TTL', '86400')),
            'enable_cache': os.getenv('STORAGE_ENABLE_CACHE', 'true').lower() == 'true',
            'cache_size': int(os.getenv('STORAGE_CACHE_SIZE', '100')),
            'cache_ttl': int(os.getenv('STORAGE_CACHE_TTL', '300')),
            'enable_compression': os.getenv('STORAGE_ENABLE_COMPRESSION', 'false').lower() == 'true',
            'compression_level': int(os.getenv('STORAGE_COMPRESSION_LEVEL', '6')),
            'enable_encryption': os.getenv('STORAGE_ENABLE_ENCRYPTION', 'false').lower() == 'true',
            'encryption_key': os.getenv('STORAGE_ENCRYPTION_KEY'),
            'max_file_size': int(os.getenv('STORAGE_MAX_FILE_SIZE', str(1024 * 1024 * 1024))),
        }

        # 根据类型添加特定配置
        if config_dict['type'] == 'minio':
            config_dict['minio'] = {
                'endpoint': os.getenv('MINIO_ENDPOINT', 'localhost:9000'),
                'access_key': os.getenv('MINIO_ACCESS_KEY', ''),
                'secret_key': os.getenv('MINIO_SECRET_KEY', ''),
                'bucket': os.getenv('MINIO_BUCKET', 'datamind'),
                'secure': os.getenv('MINIO_SECURE', 'false').lower() == 'true',
                'region': os.getenv('MINIO_REGION'),
                'models_prefix': os.getenv('MINIO_MODELS_PREFIX', 'models/'),
            }
        elif config_dict['type'] == 's3':
            config_dict['s3'] = {
                'access_key_id': os.getenv('AWS_ACCESS_KEY_ID', ''),
                'secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY', ''),
                'bucket': os.getenv('S3_BUCKET', 'datamind'),
                'region': os.getenv('AWS_REGION', 'us-east-1'),
                'endpoint': os.getenv('S3_ENDPOINT'),
                'prefix': os.getenv('S3_PREFIX', 'models/'),
            }
        elif config_dict['type'] == 'local':
            config_dict['local'] = {
                'base_path': os.getenv('LOCAL_STORAGE_PATH', './models'),
            }

        return cls.create_from_dict(config_dict)


# 便捷函数
def get_storage_config(settings=None, use_cache: bool = True) -> StorageConfig:
    """
    获取存储配置的便捷函数

    Args:
        settings: settings模块的实例（可选）
        use_cache: 是否使用缓存

    Returns:
        StorageConfig: 存储配置对象
    """
    if settings is None:
        from config.settings import settings as app_settings
        settings = app_settings

    if use_cache:
        return StorageConfig.get_cached(env=getattr(settings, 'ENV', None))
    else:
        return StorageConfigFactory.create_from_settings(settings)


def get_storage_client_config(settings=None, use_cache: bool = True) -> Dict[str, Any]:
    """
    获取存储客户端配置的便捷函数

    Args:
        settings: settings模块的实例（可选）
        use_cache: 是否使用缓存

    Returns:
        Dict[str, Any]: 客户端配置字典
    """
    storage_config = get_storage_config(settings, use_cache)
    return storage_config.get_client_config()