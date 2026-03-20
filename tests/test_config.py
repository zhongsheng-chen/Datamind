# tests/test_config.py
"""配置模块测试

测试配置加载、环境变量覆盖、配置验证等功能。
"""

import os
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path

from datamind.config import get_settings
from datamind.config import (
    AppConfig,
    ApiConfig,
    DatabaseConfig,
    RedisConfig,
    AuthConfig,
    ModelConfig,
    InferenceConfig,
    FeatureStoreConfig,
    ABTestConfig,
    BatchConfig,
    MonitoringConfig,
    AlertConfig,
    SecurityConfig,
    Settings,
    BASE_DIR
)
from datamind.config import (
    LoggingConfig,
    LogLevel,
    LogFormat,
    TimeZone
)
from datamind.config import (
    StorageConfig,
    StorageType
)


class TestAppConfig:
    """测试应用配置"""

    def test_default_values(self):
        """测试默认值"""
        config = AppConfig()
        assert config.app_name == "Datamind"
        assert config.version == "1.0.0"
        assert config.env == "development"
        assert not config.debug

    def test_env_validation(self):
        """测试环境验证"""
        with patch.dict(os.environ, {"DATAMIND_ENV": "testing"}):
            config = AppConfig()
            assert config.env == "testing"

        with patch.dict(os.environ, {"DATAMIND_ENV": "production"}):
            config = AppConfig()
            assert config.env == "production"

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_ENV": "invalid_env"}):
            with pytest.raises(ValueError):
                AppConfig()

    @patch.dict(os.environ, {
        "DATAMIND_APP_NAME": "TestApp",
        "DATAMIND_ENV": "production",
        "DATAMIND_DEBUG": "true"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = AppConfig()
        assert config.app_name == "TestApp"
        assert config.env == "production"
        assert config.debug


class TestApiConfig:
    """测试API配置"""

    def test_default_values(self):
        """测试默认值"""
        config = ApiConfig()
        assert config.host == "0.0.0.0"
        assert config.port == 8000
        assert config.prefix == "/api/v1"
        assert config.root_path == ""

    @patch.dict(os.environ, {
        "DATAMIND_API_HOST": "127.0.0.1",
        "DATAMIND_API_PORT": "9000",
        "DATAMIND_API_PREFIX": "/api/v2"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = ApiConfig()
        assert config.host == "127.0.0.1"
        assert config.port == 9000
        assert config.prefix == "/api/v2"


class TestDatabaseConfig:
    """测试数据库配置"""

    def test_default_values(self):
        """测试默认值"""
        with patch.dict(os.environ, {}, clear=True):
            config = DatabaseConfig(_env_file=None)
            assert config.url == "postgresql://postgres:postgres@localhost:5432/datamind"
            assert config.readonly_url is None
            assert config.pool_size == 20
            assert config.max_overflow == 40
            assert config.pool_timeout == 30
            assert config.pool_recycle == 3600
            assert not config.echo

    @patch.dict(os.environ, {
        "DATAMIND_DATABASE_URL": "postgresql://user:pass@remote:5432/testdb",
        "DATAMIND_DB_POOL_SIZE": "50",
        "DATAMIND_DB_ECHO": "true"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = DatabaseConfig()
        assert config.url == "postgresql://user:pass@remote:5432/testdb"
        assert config.pool_size == 50
        assert config.echo


class TestRedisConfig:
    """测试Redis配置"""

    def test_default_values(self):
        """测试默认值"""
        config = RedisConfig()
        assert config.url == "redis://localhost:6379/0"
        assert config.password is None
        assert config.max_connections == 50
        assert config.socket_timeout == 5

    @patch.dict(os.environ, {
        "DATAMIND_REDIS_URL": "redis://:password@remote:6380/1",
        "DATAMIND_REDIS_MAX_CONNECTIONS": "100"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = RedisConfig()
        assert config.url == "redis://:password@remote:6380/1"
        assert config.max_connections == 100


class TestAuthConfig:
    """测试认证配置"""

    def test_default_values(self):
        """测试默认值"""
        config = AuthConfig()
        assert config.api_key_enabled
        assert config.api_key_header == "X-API-Key"
        assert config.jwt_secret_key == "your-secret-key-change-in-production"
        assert config.jwt_algorithm == "HS256"
        assert config.jwt_expire_minutes == 30

    @patch.dict(os.environ, {
        "DATAMIND_API_KEY_ENABLED": "false",
        "DATAMIND_JWT_SECRET_KEY": "my-secret-key",
        "DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = AuthConfig()
        assert not config.api_key_enabled
        assert config.jwt_secret_key == "my-secret-key"
        assert config.jwt_expire_minutes == 60


class TestModelConfig:
    """测试模型配置"""

    def test_default_values(self):
        """测试默认值"""
        config = ModelConfig()
        assert config.models_path == "./models"
        assert config.max_size == 1024 * 1024 * 1024
        assert ".pkl" in config.allowed_extensions
        assert config.xgboost_use_json

    @patch.dict(os.environ, {
        "DATAMIND_MODELS_PATH": "/custom/models",
        "DATAMIND_XGBOOST_USE_JSON": "false"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = ModelConfig()
        assert config.models_path == "/custom/models"
        assert not config.xgboost_use_json


class TestInferenceConfig:
    """测试推理配置"""

    def test_default_values(self):
        """测试默认值"""
        config = InferenceConfig()
        assert config.timeout == 30
        assert config.cache_size == 10
        assert config.cache_ttl == 3600


class TestFeatureStoreConfig:
    """测试特征存储配置"""

    def test_default_values(self):
        """测试默认值"""
        config = FeatureStoreConfig()
        assert config.enabled
        assert config.cache_size == 1000
        assert config.cache_ttl == 300


class TestABTestConfig:
    """测试A/B测试配置"""

    def test_default_values(self):
        """测试默认值"""
        config = ABTestConfig()
        assert config.enabled
        assert config.redis_key_prefix == "ab_test:"
        assert config.assignment_expiry == 86400


class TestBatchConfig:
    """测试批处理配置"""

    def test_default_values(self):
        """测试默认值"""
        config = BatchConfig()
        assert config.batch_size == 100
        assert config.max_workers == 10


class TestMonitoringConfig:
    """测试监控配置"""

    def test_default_values(self):
        """测试默认值"""
        config = MonitoringConfig()
        assert config.enabled
        assert config.prometheus_port == 9090
        assert config.path == "/metrics"


class TestAlertConfig:
    """测试告警配置"""

    def test_default_values(self):
        """测试默认值"""
        config = AlertConfig()
        assert not config.enabled
        assert config.webhook_url is None
        assert config.on_error
        assert config.on_model_degradation


class TestSecurityConfig:
    """测试安全配置"""

    def test_default_values(self):
        """测试默认值"""
        config = SecurityConfig()
        assert config.cors_origins == ["*"]
        assert config.trusted_proxies == []
        assert config.rate_limit_enabled
        assert config.rate_limit_requests == 100
        assert config.rate_limit_period == 60


class TestLoggingConfig:
    """测试日志配置"""

    def test_default_values(self):
        """测试默认值"""
        with patch.dict(os.environ, {
            "DATAMIND_LOG_FORMAT": "json",
            "DATAMIND_LOG_TIMEZONE": "UTC",
        }, clear=True):
            config = LoggingConfig()
            assert config.name == "datamind"
            assert config.level == LogLevel.INFO
            assert config.format == LogFormat.JSON
            assert config.encoding == "utf-8"
            assert config.log_dir == "logs"
            assert config.file == "datamind.log"
            assert config.max_bytes == 104857600
            assert config.backup_count == 30
            assert config.retention_days == 90
            assert config.timezone == TimeZone.UTC
            assert config.sampling_rate == 1.0

    def test_sampling_rate_validation(self):
        """测试采样率验证"""
        with patch.dict(os.environ, {"DATAMIND_LOG_SAMPLING_RATE": "0.5"}):
            config = LoggingConfig()
            assert config.sampling_rate == 0.5

        with patch.dict(os.environ, {"DATAMIND_LOG_SAMPLING_RATE": "0.8"}):
            config = LoggingConfig()
            assert config.sampling_rate == 0.8

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_LOG_SAMPLING_RATE": "1.5"}):
            with pytest.raises(ValueError):
                LoggingConfig()

    @patch.dict(os.environ, {
        "DATAMIND_LOG_LEVEL": "DEBUG",
        "DATAMIND_LOG_FORMAT": "text",
        "DATAMIND_LOG_FILE": "custom.log",
        "DATAMIND_LOG_MAX_BYTES": "52428800",
        "DATAMIND_LOG_TIMEZONE": "CST",
        "DATAMIND_LOG_SAMPLING_RATE": "0.3"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = LoggingConfig()
        assert config.level == LogLevel.DEBUG
        assert config.format == LogFormat.TEXT
        assert config.file == "custom.log"
        assert config.max_bytes == 52428800
        assert config.timezone == TimeZone.CST
        assert config.sampling_rate == 0.3


class TestStorageConfig:
    """测试存储配置"""

    def test_default_values(self):
        """测试默认值"""
        config = StorageConfig()
        assert config.storage_type == StorageType.LOCAL
        assert config.default_ttl == 86400
        assert config.enable_cache
        assert config.cache_size == 100
        assert config.cache_ttl == 300
        assert not config.enable_compression
        assert config.compression_level == 6
        assert not config.enable_encryption
        assert config.max_file_size == 1024 * 1024 * 1024

    def test_local_config_defaults(self):
        """测试本地存储子配置"""
        config = StorageConfig()
        assert config.local.base_path == "./models"
        assert config.local.models_subpath == "models"

    def test_minio_config_defaults(self):
        """测试MinIO存储子配置"""
        config = StorageConfig()
        assert config.minio.endpoint == "localhost:9000"
        assert config.minio.bucket == "datamind-storage"
        assert not config.minio.secure

    def test_s3_config_defaults(self):
        """测试S3存储子配置"""
        config = StorageConfig()
        assert config.s3.region == "us-east-1"
        assert config.s3.bucket == "datamind-storage"
        assert config.s3.use_ssl

    @patch.dict(os.environ, {
        "DATAMIND_STORAGE_TYPE": "minio",
        "MINIO_ENDPOINT": "minio.example.com:9000",
        "MINIO_ACCESS_KEY": "testkey",
        "MINIO_SECRET_KEY": "testsecret",
        "MINIO_BUCKET": "test-bucket"
    })
    def test_minio_config_override(self):
        """测试MinIO环境变量覆盖"""
        config = StorageConfig()
        assert config.storage_type == StorageType.MINIO
        assert config.minio.endpoint == "minio.example.com:9000"
        assert config.minio.access_key == "testkey"
        assert config.minio.secret_key == "testsecret"
        assert config.minio.bucket == "test-bucket"

    def test_compression_level_validation(self):
        """测试压缩级别验证"""
        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "5"}):
            config = StorageConfig()
            assert config.compression_level == 5

        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "3"}):
            config = StorageConfig()
            assert config.compression_level == 3

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "0"}):
            with pytest.raises(ValueError):
                StorageConfig()

        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "10"}):
            with pytest.raises(ValueError):
                StorageConfig()

    def test_max_file_size_validation(self):
        """测试最大文件大小验证"""
        test_size = 1024 * 1024 * 2
        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(test_size)}):
            config = StorageConfig()
            assert config.max_file_size == test_size

        test_size = 1024 * 1024 * 50
        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(test_size)}):
            config = StorageConfig()
            assert config.max_file_size == test_size

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(1024 * 500)}):
            with pytest.raises(ValueError):
                StorageConfig()

        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(1024 * 1024 * 1024 * 11)}):
            with pytest.raises(ValueError):
                StorageConfig()


class TestSettingsRoot:
    """测试根配置"""

    def test_default_values(self):
        """测试默认值"""
        with patch.dict(os.environ, {
            "DATAMIND_LOG_FORMAT": "json",
            "DATAMIND_LOG_TIMEZONE": "UTC",
        }, clear=True):
            settings = Settings()
            assert settings.app.app_name == "Datamind"
            assert settings.api.port == 8000
            assert settings.database.pool_size == 20
            assert settings.redis.max_connections == 50
            assert settings.logging.level == LogLevel.INFO
            assert settings.logging.format == LogFormat.JSON
            assert settings.logging.timezone == TimeZone.UTC
            assert settings.logging.sampling_rate == 1.0
            assert settings.storage.storage_type == StorageType.LOCAL
            assert settings.storage.compression_level == 6
            assert settings.storage.max_file_size == 1024 * 1024 * 1024

    @patch.dict(os.environ, {
        "DATAMIND_APP_NAME": "TestApp",
        "DATAMIND_API_PORT": "9000",
        "DATAMIND_REDIS_MAX_CONNECTIONS": "100",
        "DATAMIND_LOG_LEVEL": "DEBUG",
        "DATAMIND_LOG_FORMAT": "text",
        "DATAMIND_LOG_TIMEZONE": "CST",
        "DATAMIND_LOG_SAMPLING_RATE": "0.3",
        "DATAMIND_STORAGE_TYPE": "s3",
        "AWS_ACCESS_KEY_ID": "test-access-key",
        "AWS_SECRET_ACCESS_KEY": "test-secret-key",
        "S3_BUCKET": "test-bucket",
        "DATAMIND_STORAGE_COMPRESSION_LEVEL": "5",
        "DATAMIND_STORAGE_MAX_FILE_SIZE": "2097152"
    })
    def test_env_override_all(self):
        """测试所有环境变量覆盖"""
        settings = Settings()
        assert settings.app.app_name == "TestApp"
        assert settings.api.port == 9000
        assert settings.redis.max_connections == 100
        assert settings.logging.level == LogLevel.DEBUG
        assert settings.logging.format == LogFormat.TEXT
        assert settings.logging.timezone == TimeZone.CST
        assert settings.logging.sampling_rate == 0.3
        assert settings.storage.storage_type == StorageType.S3
        assert settings.storage.s3.access_key_id == "test-access-key"
        assert settings.storage.s3.secret_access_key == "test-secret-key"
        assert settings.storage.s3.bucket == "test-bucket"
        assert settings.storage.compression_level == 5
        assert settings.storage.max_file_size == 2097152

    def test_get_settings_cached(self):
        """测试配置缓存"""
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    @patch('builtins.open', new_callable=mock_open, read_data="""
DATAMIND_APP_NAME=EnvFileApp
DATAMIND_API_PORT=8888
    """)
    def test_env_file_loading(self, mock_file):
        """测试.env文件加载"""
        with patch('pathlib.Path.exists', return_value=True):
            settings = Settings(_env_file=".env")
            assert isinstance(settings, Settings)


class TestConfigIntegration:
    """集成测试"""

    def test_real_config_creation(self):
        """测试真实配置创建"""
        try:
            settings = get_settings()
            assert settings is not None
            assert settings.app is not None
            assert settings.database is not None
            assert settings.redis is not None
            assert settings.logging is not None
            assert settings.storage is not None
        except Exception as e:
            pytest.fail(f"配置创建失败: {e}")

    def test_base_dir_exists(self):
        """测试基础目录"""
        assert BASE_DIR.exists()
        assert BASE_DIR.is_dir()