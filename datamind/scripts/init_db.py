#!/usr/bin/env python3
# datamind/scripts/init_db.py
"""
数据库初始化脚本
用于创建数据库表、初始化枚举类型和基础数据
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy_utils import database_exists, create_database, drop_database

from datamind.core import Base
from datamind.core import (
    TaskType, ModelType, Framework, ModelStatus,
    AuditAction, DeploymentEnvironment, ABTestStatus
)
from datamind.config import settings
from datamind.config import LoggingConfig
from datamind.core import log_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_enums(conn):
    """创建PostgreSQL枚举类型"""
    logger.info("创建枚举类型...")

    enums = [
        ("task_type_enum", TaskType),
        ("model_type_enum", ModelType),
        ("framework_enum", Framework),
        ("model_status_enum", ModelStatus),
        ("audit_action_enum", AuditAction),
        ("deployment_env_enum", DeploymentEnvironment),
        ("abtest_status_enum", ABTestStatus),
    ]

    for enum_name, enum_class in enums:
        try:
            # 检查枚举是否已存在
            result = conn.execute(
                text(f"SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{enum_name}')")
            ).scalar()

            if not result:
                enum_values = [f"'{e.value}'" for e in enum_class]
                conn.execute(text(f"CREATE TYPE {enum_name} AS ENUM ({','.join(enum_values)})"))
                logger.info(f"创建枚举类型: {enum_name}")
            else:
                logger.info(f"枚举类型已存在: {enum_name}")

        except Exception as e:
            logger.error(f"创建枚举类型 {enum_name} 失败: {e}")
            raise


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
            logger.info(f"创建扩展: {ext}")
        except Exception as e:
            logger.error(f"创建扩展 {ext} 失败: {e}")
            # 继续执行，不中断


def create_tables(engine):
    """创建数据库表"""
    logger.info("创建数据库表...")
    Base.metadata.create_all(engine)
    logger.info("数据库表创建完成")


def create_indexes(engine):
    """创建额外索引"""
    logger.info("创建索引...")

    with engine.connect() as conn:
        # 创建GIN索引用于JSONB字段
        indexes = [
            """
            CREATE INDEX IF NOT EXISTS idx_model_metadata_gin
                ON model_metadata USING gin (metadata_json)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_api_call_logs_request_data_gin
                ON api_call_logs USING gin (request_data)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_details_gin
                ON audit_logs USING gin (details)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_model_metadata_search
                ON model_metadata USING gin (
                to_tsvector('english',
                coalesce (model_name,'') || ' ' ||
                coalesce (description,'')
                )
                )
            """
        ]

        for idx in indexes:
            try:
                conn.execute(text(idx))
                conn.commit()
            except Exception as e:
                logger.error(f"创建索引失败: {e}")

    logger.info("索引创建完成")


def init_base_data(engine):
    """初始化基础数据"""
    logger.info("初始化基础数据...")

    with engine.connect() as conn:
        # 检查是否已有系统配置
        result = conn.execute(
            text("SELECT COUNT(*) FROM system_configs")
        ).scalar()

        if result == 0:
            # 插入默认系统配置
            conn.execute(
                text("""
                     INSERT INTO system_configs
                     (config_key, config_value, description, category, updated_by, created_at)
                     VALUES ('system.version', :version, '系统版本', 'system', 'system', NOW()),
                            ('system.maintenance_mode', 'false', '维护模式', 'system', 'system', NOW()),
                            ('api.rate_limit.default', '{"requests": 100, "period": 60}',
                             '默认速率限制', 'api', 'system', NOW()),
                            ('model.default_timeout', '30', '默认模型超时时间', 'model', 'system', NOW())
                     """),
                {"version": settings.VERSION}
            )
            conn.commit()
            logger.info("基础数据初始化完成")
        else:
            logger.info("基础数据已存在，跳过初始化")


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始初始化数据库")
    logger.info(f"数据库URL: {settings.DATABASE_URL.split('@')[-1]}")

    # 确认操作
    if "--force" not in sys.argv:
        response = input("此操作将创建数据库表，确定要继续吗？ (yes/no): ")
        if response.lower() != 'yes':
            logger.info("操作已取消")
            return

    try:
        # 创建数据库引擎
        engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            connect_args={'connect_timeout': 10}
        )

        # 创建数据库（如果不存在）
        if not database_exists(engine.url):
            create_database(engine.url)
            logger.info(f"创建数据库: {engine.url.database}")

        # 创建扩展
        with engine.connect() as conn:
            create_extensions(conn)
            conn.commit()

        # 创建枚举
        with engine.connect() as conn:
            create_enums(conn)
            conn.commit()

        # 创建表
        create_tables(engine)

        # 创建索引
        create_indexes(engine)

        # 初始化基础数据
        init_base_data(engine)

        logger.info("=" * 50)
        logger.info("数据库初始化完成！")

        # 记录审计日志
        log_config = LoggingConfig.load()
        log_manager.initialize(log_config)
        log_manager.log_audit(
            action="DB_INIT",
            user_id="system",
            ip_address="localhost",
            details={"database": str(engine.url)},
            result="SUCCESS"
        )

    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()