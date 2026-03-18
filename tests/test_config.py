# tests/test_config.py
import os
import unittest
from unittest.mock import patch, mock_open

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


class TestAppConfig(unittest.TestCase):
    """测试应用配置"""

    def test_default_values(self):
        """测试默认值"""
        config = AppConfig()
        self.assertEqual(config.app_name, "Datamind")
        self.assertEqual(config.version, "1.0.0")
        self.assertEqual(config.env, "development")
        self.assertFalse(config.debug)

    def test_env_validation(self):
        """测试环境验证"""
        # 通过环境变量设置值
        with patch.dict(os.environ, {"DATAMIND_ENV": "testing"}):
            config = AppConfig()
            self.assertEqual(config.env, "testing")

        with patch.dict(os.environ, {"DATAMIND_ENV": "production"}):
            config = AppConfig()
            self.assertEqual(config.env, "production")

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_ENV": "invalid_env"}):
            with self.assertRaises(ValueError):
                AppConfig()

    @patch.dict(os.environ, {
        "DATAMIND_APP_NAME": "TestApp",
        "DATAMIND_ENV": "production",
        "DATAMIND_DEBUG": "true"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = AppConfig()
        self.assertEqual(config.app_name, "TestApp")
        self.assertEqual(config.env, "production")
        self.assertTrue(config.debug)


class TestApiConfig(unittest.TestCase):
    """测试API配置"""

    def test_default_values(self):
        """测试默认值"""
        config = ApiConfig()
        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 8000)
        self.assertEqual(config.prefix, "/api/v1")
        self.assertEqual(config.root_path, "")

    @patch.dict(os.environ, {
        "DATAMIND_API_HOST": "127.0.0.1",
        "DATAMIND_API_PORT": "9000",
        "DATAMIND_API_PREFIX": "/api/v2"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = ApiConfig()
        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 9000)
        self.assertEqual(config.prefix, "/api/v2")


class TestDatabaseConfig(unittest.TestCase):
    """测试数据库配置"""

    def test_default_values(self):
        """测试默认值"""

        with patch.dict(os.environ, {}, clear=True):
            config = DatabaseConfig(_env_file=None)
            self.assertEqual(config.url, "postgresql://postgres:postgres@localhost:5432/datamind")
            self.assertIsNone(config.readonly_url)
            self.assertEqual(config.pool_size, 20)
            self.assertEqual(config.max_overflow, 40)
            self.assertEqual(config.pool_timeout, 30)
            self.assertEqual(config.pool_recycle, 3600)
            self.assertFalse(config.echo)

    @patch.dict(os.environ, {
        "DATAMIND_DATABASE_URL": "postgresql://user:pass@remote:5432/testdb",
        "DATAMIND_DB_POOL_SIZE": "50",
        "DATAMIND_DB_ECHO": "true"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = DatabaseConfig()
        self.assertEqual(config.url, "postgresql://user:pass@remote:5432/testdb")
        self.assertEqual(config.pool_size, 50)
        self.assertTrue(config.echo)


class TestRedisConfig(unittest.TestCase):
    """测试Redis配置"""

    def test_default_values(self):
        """测试默认值"""
        config = RedisConfig()
        self.assertEqual(config.url, "redis://localhost:6379/0")
        self.assertIsNone(config.password)
        self.assertEqual(config.max_connections, 50)
        self.assertEqual(config.socket_timeout, 5)

    @patch.dict(os.environ, {
        "DATAMIND_REDIS_URL": "redis://:password@remote:6380/1",
        "DATAMIND_REDIS_MAX_CONNECTIONS": "100"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = RedisConfig()
        self.assertEqual(config.url, "redis://:password@remote:6380/1")
        self.assertEqual(config.max_connections, 100)


class TestAuthConfig(unittest.TestCase):
    """测试认证配置"""

    def test_default_values(self):
        """测试默认值"""
        config = AuthConfig()
        self.assertTrue(config.api_key_enabled)
        self.assertEqual(config.api_key_header, "X-API-Key")
        self.assertEqual(config.jwt_secret_key, "your-secret-key-change-in-production")
        self.assertEqual(config.jwt_algorithm, "HS256")
        self.assertEqual(config.jwt_expire_minutes, 30)

    @patch.dict(os.environ, {
        "DATAMIND_API_KEY_ENABLED": "false",
        "DATAMIND_JWT_SECRET_KEY": "my-secret-key",
        "DATAMIND_JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = AuthConfig()
        self.assertFalse(config.api_key_enabled)
        self.assertEqual(config.jwt_secret_key, "my-secret-key")
        self.assertEqual(config.jwt_expire_minutes, 60)


class TestModelConfig(unittest.TestCase):
    """测试模型配置"""

    def test_default_values(self):
        """测试默认值"""
        config = ModelConfig()
        self.assertEqual(config.models_path, "./models")
        self.assertEqual(config.max_size, 1024 * 1024 * 1024)
        self.assertIn(".pkl", config.allowed_extensions)
        self.assertTrue(config.xgboost_use_json)

    @patch.dict(os.environ, {
        "DATAMIND_MODELS_PATH": "/custom/models",
        "DATAMIND_XGBOOST_USE_JSON": "false"
    })
    def test_env_override(self):
        """测试环境变量覆盖"""
        config = ModelConfig()
        self.assertEqual(config.models_path, "/custom/models")
        self.assertFalse(config.xgboost_use_json)


class TestInferenceConfig(unittest.TestCase):
    """测试推理配置"""

    def test_default_values(self):
        """测试默认值"""
        config = InferenceConfig()
        self.assertEqual(config.timeout, 30)
        self.assertEqual(config.cache_size, 10)
        self.assertEqual(config.cache_ttl, 3600)


class TestFeatureStoreConfig(unittest.TestCase):
    """测试特征存储配置"""

    def test_default_values(self):
        """测试默认值"""
        config = FeatureStoreConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.cache_size, 1000)
        self.assertEqual(config.cache_ttl, 300)


class TestABTestConfig(unittest.TestCase):
    """测试A/B测试配置"""

    def test_default_values(self):
        """测试默认值"""
        config = ABTestConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.redis_key_prefix, "ab_test:")
        self.assertEqual(config.assignment_expiry, 86400)


class TestBatchConfig(unittest.TestCase):
    """测试批处理配置"""

    def test_default_values(self):
        """测试默认值"""
        config = BatchConfig()
        self.assertEqual(config.batch_size, 100)
        self.assertEqual(config.max_workers, 10)


class TestMonitoringConfig(unittest.TestCase):
    """测试监控配置"""

    def test_default_values(self):
        """测试默认值"""
        config = MonitoringConfig()
        self.assertTrue(config.enabled)
        self.assertEqual(config.prometheus_port, 9090)
        self.assertEqual(config.path, "/metrics")


class TestAlertConfig(unittest.TestCase):
    """测试告警配置"""

    def test_default_values(self):
        """测试默认值"""
        config = AlertConfig()
        self.assertFalse(config.enabled)
        self.assertIsNone(config.webhook_url)
        self.assertTrue(config.on_error)
        self.assertTrue(config.on_model_degradation)


class TestSecurityConfig(unittest.TestCase):
    """测试安全配置"""

    def test_default_values(self):
        """测试默认值"""
        config = SecurityConfig()
        self.assertEqual(config.cors_origins, ["*"])
        self.assertEqual(config.trusted_proxies, [])
        self.assertTrue(config.rate_limit_enabled)
        self.assertEqual(config.rate_limit_requests, 100)
        self.assertEqual(config.rate_limit_period, 60)


class TestLoggingConfig(unittest.TestCase):
    """测试日志配置"""

    def test_default_values(self):
        """测试默认值"""
        with patch.dict(os.environ, {
            "DATAMIND_LOG_FORMAT": "json",
            "DATAMIND_LOG_TIMEZONE":"UTC",

        }, clear=True):
            config = LoggingConfig()
            self.assertEqual(config.name, "datamind")
            self.assertEqual(config.level, LogLevel.INFO)
            self.assertEqual(config.format, LogFormat.JSON)
            self.assertEqual(config.encoding, "utf-8")
            self.assertEqual(config.log_dir, "logs")
            self.assertEqual(config.file, "datamind.log")
            self.assertEqual(config.max_bytes, 104857600)
            self.assertEqual(config.backup_count, 30)
            self.assertEqual(config.retention_days, 90)
            self.assertEqual(config.timezone, TimeZone.UTC)
            self.assertEqual(config.sampling_rate, 1.0)

    def test_sampling_rate_validation(self):
        """测试采样率验证"""
        # 通过环境变量设置采样率
        with patch.dict(os.environ, {"DATAMIND_LOG_SAMPLING_RATE": "0.5"}):
            config = LoggingConfig()
            self.assertEqual(config.sampling_rate, 0.5)

        with patch.dict(os.environ, {"DATAMIND_LOG_SAMPLING_RATE": "0.8"}):
            config = LoggingConfig()
            self.assertEqual(config.sampling_rate, 0.8)

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_LOG_SAMPLING_RATE": "1.5"}):
            with self.assertRaises(ValueError):
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
        self.assertEqual(config.level, LogLevel.DEBUG)
        self.assertEqual(config.format, LogFormat.TEXT)
        self.assertEqual(config.file, "custom.log")
        self.assertEqual(config.max_bytes, 52428800)
        self.assertEqual(config.timezone, TimeZone.CST)
        self.assertEqual(config.sampling_rate, 0.3)


class TestStorageConfig(unittest.TestCase):
    """测试存储配置"""

    def test_default_values(self):
        """测试默认值"""
        config = StorageConfig()
        self.assertEqual(config.storage_type, StorageType.LOCAL)
        self.assertEqual(config.default_ttl, 86400)
        self.assertTrue(config.enable_cache)
        self.assertEqual(config.cache_size, 100)
        self.assertEqual(config.cache_ttl, 300)
        self.assertFalse(config.enable_compression)
        self.assertEqual(config.compression_level, 6)
        self.assertFalse(config.enable_encryption)
        self.assertEqual(config.max_file_size, 1024 * 1024 * 1024)

    def test_local_config_defaults(self):
        """测试本地存储子配置"""
        config = StorageConfig()
        self.assertEqual(config.local.base_path, "./models")
        self.assertEqual(config.local.models_subpath, "models")

    def test_minio_config_defaults(self):
        """测试MinIO存储子配置"""
        config = StorageConfig()
        self.assertEqual(config.minio.endpoint, "localhost:9000")
        self.assertEqual(config.minio.bucket, "datamind-storage")
        self.assertFalse(config.minio.secure)

    def test_s3_config_defaults(self):
        """测试S3存储子配置"""
        config = StorageConfig()
        self.assertEqual(config.s3.region, "us-east-1")
        self.assertEqual(config.s3.bucket, "datamind-storage")
        self.assertTrue(config.s3.use_ssl)

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
        self.assertEqual(config.storage_type, StorageType.MINIO)
        self.assertEqual(config.minio.endpoint, "minio.example.com:9000")
        self.assertEqual(config.minio.access_key, "testkey")
        self.assertEqual(config.minio.secret_key, "testsecret")
        self.assertEqual(config.minio.bucket, "test-bucket")

    def test_compression_level_validation(self):
        """测试压缩级别验证"""
        # 通过环境变量设置压缩级别
        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "5"}):
            config = StorageConfig()
            self.assertEqual(config.compression_level, 5)

        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "3"}):
            config = StorageConfig()
            self.assertEqual(config.compression_level, 3)

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "0"}):
            with self.assertRaises(ValueError):
                StorageConfig()

        with patch.dict(os.environ, {"DATAMIND_STORAGE_COMPRESSION_LEVEL": "10"}):
            with self.assertRaises(ValueError):
                StorageConfig()

    def test_max_file_size_validation(self):
        """测试最大文件大小验证"""
        # 通过环境变量设置文件大小
        test_size = 1024 * 1024 * 2  # 2MB
        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(test_size)}):
            config = StorageConfig()
            self.assertEqual(config.max_file_size, test_size)

        test_size = 1024 * 1024 * 50  # 50MB
        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(test_size)}):
            config = StorageConfig()
            self.assertEqual(config.max_file_size, test_size)

        # 无效值应该抛出异常
        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(1024 * 500)}):  # 500KB
            with self.assertRaises(ValueError):
                StorageConfig()

        with patch.dict(os.environ, {"DATAMIND_STORAGE_MAX_FILE_SIZE": str(1024 * 1024 * 1024 * 11)}):  # 11GB
            with self.assertRaises(ValueError):
                StorageConfig()


class TestSettingsRoot(unittest.TestCase):
    """测试根配置"""

    def test_default_values(self):
        """测试默认值"""
        with patch.dict(os.environ, {
            "DATAMIND_LOG_FORMAT": "json",
            "DATAMIND_LOG_TIMEZONE": "UTC",
        }, clear=True):
            settings = Settings()
            self.assertEqual(settings.app.app_name, "Datamind")
            self.assertEqual(settings.api.port, 8000)
            self.assertEqual(settings.database.pool_size, 20)
            self.assertEqual(settings.redis.max_connections, 50)
            self.assertEqual(settings.logging.level, LogLevel.INFO)
            self.assertEqual(settings.logging.format, LogFormat.JSON)
            self.assertEqual(settings.logging.timezone, TimeZone.UTC)
            self.assertEqual(settings.logging.sampling_rate, 1.0)
            self.assertEqual(settings.storage.storage_type, StorageType.LOCAL)
            self.assertEqual(settings.storage.compression_level, 6)
            self.assertEqual(settings.storage.max_file_size, 1024 * 1024 * 1024)

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
        self.assertEqual(settings.app.app_name, "TestApp")
        self.assertEqual(settings.api.port, 9000)
        self.assertEqual(settings.redis.max_connections, 100)
        self.assertEqual(settings.logging.level, LogLevel.DEBUG)
        self.assertEqual(settings.logging.format, LogFormat.TEXT)
        self.assertEqual(settings.logging.timezone, TimeZone.CST)
        self.assertEqual(settings.logging.sampling_rate, 0.3)
        self.assertEqual(settings.storage.storage_type, StorageType.S3)
        self.assertEqual(settings.storage.s3.access_key_id, "test-access-key")
        self.assertEqual(settings.storage.s3.secret_access_key, "test-secret-key")
        self.assertEqual(settings.storage.s3.bucket, "test-bucket")
        self.assertEqual(settings.storage.compression_level, 5)
        self.assertEqual(settings.storage.max_file_size, 2097152)

    def test_get_settings_cached(self):
        """测试配置缓存"""
        settings1 = get_settings()
        settings2 = get_settings()
        self.assertIs(settings1, settings2)

    @patch('builtins.open', new_callable=mock_open, read_data="""
DATAMIND_APP_NAME=EnvFileApp
DATAMIND_API_PORT=8888
    """)
    def test_env_file_loading(self, mock_file):
        """测试.env文件加载"""
        with patch('pathlib.Path.exists', return_value=True):
            settings = Settings(_env_file=".env")
            self.assertIsInstance(settings, Settings)


class TestConfigIntegration(unittest.TestCase):
    """集成测试"""

    def test_real_config_creation(self):
        """测试真实配置创建"""
        try:
            settings = get_settings()
            self.assertIsNotNone(settings)
            self.assertIsNotNone(settings.app)
            self.assertIsNotNone(settings.database)
            self.assertIsNotNone(settings.redis)
            self.assertIsNotNone(settings.logging)
            self.assertIsNotNone(settings.storage)
        except Exception as e:
            self.fail(f"配置创建失败: {e}")

    def test_base_dir_exists(self):
        """测试基础目录"""
        self.assertTrue(BASE_DIR.exists())
        self.assertTrue(BASE_DIR.is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)