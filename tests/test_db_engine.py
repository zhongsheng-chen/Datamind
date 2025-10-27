import unittest
from unittest.mock import patch
from sqlalchemy.engine import Engine
from src import db_engine


class TestDBEngine(unittest.TestCase):
    @patch("src.db_engine.config")
    def test_create_oracle_engine(self, mock_config):
        """测试 Oracle 引擎创建"""
        mock_config.get_databases.side_effect = lambda db_name: {
            "oracle": {
                "user": "test_user",
                "password": "test_pass",
                "host": "localhost",
                "port": 1521,
                "service_name": "TESTPDB",
                "pool_size": 2,
                "max_overflow": 5,
                "pool_timeout": 10,
                "pool_recycle": 100,
            }
        }.get(db_name)

        engine = db_engine.create_db_engine("oracle")
        self.assertIsInstance(engine, Engine)

    @patch("src.db_engine.config")
    def test_create_postgres_engine(self, mock_config):
        """测试 Postgres 引擎创建"""
        mock_config.get_databases.side_effect = lambda db_name: {
            "postgres": {
                "user": "pg_user",
                "password": "pg_pass",
                "host": "localhost",
                "port": 5432,
                "database": "test_db",
                "pool_size": 3,
                "max_overflow": 7,
                "pool_timeout": 15,
                "pool_recycle": 120,
            }
        }.get(db_name)

        engine = db_engine.create_db_engine("postgres")
        self.assertIsInstance(engine, Engine)

    @patch("src.db_engine.config")
    def test_unsupported_db(self, mock_config):
        """测试不支持的数据库类型"""
        mock_config.get_databases.side_effect = lambda db_name: None
        with self.assertRaises(ValueError):
            db_engine.create_db_engine("sqlite")

    @patch("src.db_engine.config")
    def test_missing_port(self, mock_config):
        """测试缺少 port 配置"""
        mock_config.get_databases.side_effect = lambda db_name: {
            "oracle": {
                "user": "user",
                "password": "pass",
                "host": "localhost"
                # port 故意缺失
            }
        }.get(db_name)

        with self.assertRaises(ValueError):
            db_engine.create_db_engine("oracle")

    @patch("src.db_engine.config")
    def test_missing_port_postgres(self, mock_config):
        """测试 Postgres 缺少 port"""
        mock_config.get_databases.side_effect = lambda db_name: {
            "postgres": {
                "user": "user",
                "password": "pass",
                "host": "localhost",
                "database": "db_test"
                # port 故意缺失
            }
        }.get(db_name)

        with self.assertRaises(ValueError):
            db_engine.create_db_engine("postgres")


if __name__ == "__main__":
    unittest.main()
