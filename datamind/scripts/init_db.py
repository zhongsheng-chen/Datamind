# Datamind/datamind/scripts/init_db.py

"""数据库初始化脚本

用于创建数据库、扩展和基础数据，表结构和枚举由 Alembic 统一管理
"""

import sys
import logging
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine.url import make_url

from datamind.config import get_settings, BASE_DIR

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 获取配置
settings = get_settings()


def database_exists(url):
    """检查数据库是否存在"""
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False


def create_database(url):
    """创建数据库（使用 make_url 安全处理）"""
    db_url = make_url(str(url))
    default_db = db_url.set(database="postgres")
    engine = create_engine(default_db, isolation_level="AUTOCOMMIT")

    with engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{db_url.database}"'))
        logger.info(f"创建数据库: {db_url.database}")


def create_extensions(conn):
    """创建PostgreSQL扩展"""
    logger.info("创建数据库扩展...")

    extensions = [
        "uuid-ossp",
        "pgcrypto",
        "btree_gin",
        "pg_stat_statements"
    ]

    for ext in extensions:
        try:
            conn.execute(text(f'CREATE EXTENSION IF NOT EXISTS "{ext}"'))
            logger.info(f"  创建扩展: {ext}")
        except Exception as e:
            logger.error(f"  创建扩展 {ext} 失败: {e}")


def is_initialized(engine):
    """判断数据库是否已初始化（是否存在 alembic_version 表）"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM alembic_version"))
            return True
    except Exception:
        return False


def run_alembic_upgrade():
    """运行 Alembic 迁移创建表结构和枚举"""
    logger.info("运行 Alembic 迁移...")

    project_root = BASE_DIR.parent

    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )

        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    logger.info(f"  {line}")

        logger.info("Alembic 迁移完成")
        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"Alembic 迁移失败 (返回码: {e.returncode})")
        if e.stderr:
            logger.error(f"  错误输出: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"运行 Alembic 失败: {e}")
        return False


def init_base_data(engine):
    """初始化基础数据"""
    logger.info("初始化基础数据...")

    with engine.begin() as conn:
        # 检查是否已有系统配置
        result = conn.execute(
            text("SELECT COUNT(*) FROM system_configs")
        ).scalar()

        if result == 0:
            conn.execute(
                text("""
                     INSERT INTO system_configs
                     (config_key, config_value, description, category, version, updated_by, created_at)
                     VALUES ('system.version', '"1.0.0"', '系统版本', 'system', 1, 'system', NOW()),
                            ('system.maintenance_mode', 'false', '维护模式', 'system', 1, 'system', NOW()),
                            ('api.rate_limit.default', '{"requests": 100, "period": 60}',
                             '默认速率限制', 'api', 1, 'system', NOW()),
                            ('model.default_timeout', '30', '默认模型超时时间', 'model', 1, 'system', NOW())
                     """)
            )
            logger.info("基础数据初始化完成")
        else:
            logger.info("基础数据已存在，跳过初始化")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始初始化数据库")
    logger.info(f"数据库URL: {settings.database.url.split('@')[-1]}")
    logger.info(f"项目根目录: {BASE_DIR.parent}")

    if "--force" not in sys.argv:
        response = input("此操作将创建数据库表，确定要继续吗？ (yes/no): ")
        if response.lower() != 'yes':
            logger.info("操作已取消")
            return

    try:
        # 创建数据库引擎
        engine = create_engine(
            settings.database.url,
            pool_pre_ping=True,
            connect_args={'connect_timeout': 10}
        )

        # 创建数据库（如果不存在）
        if not database_exists(engine.url):
            create_database(engine.url)
            logger.info(f"创建数据库: {engine.url.database}")

        # 重新连接
        engine = create_engine(
            settings.database.url,
            pool_pre_ping=True,
            connect_args={'connect_timeout': 10}
        )

        # 创建扩展
        with engine.begin() as conn:
            create_extensions(conn)

        # 运行 Alembic 迁移（幂等，如果已初始化会自动跳过已执行的部分）
        if not run_alembic_upgrade():
            logger.error("Alembic 迁移失败，数据库初始化中止")
            sys.exit(1)

        # 初始化基础数据
        init_base_data(engine)

        logger.info("=" * 50)
        logger.info("数据库初始化完成！")

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()