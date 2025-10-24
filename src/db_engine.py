from sqlalchemy import create_engine
from src.config_parser import config
from src.setup import setup_logger

logger = setup_logger()


def create_db_engine(db_type: str):
    """创建数据库连接引擎"""
    try:
        db_config = config.get(db_type)

        # 检查是否有配置
        if not db_config:
            raise ValueError(f"没有找到 {db_type} 的配置")

        if db_type == "oracle":
            db_url = (
                f"oracle+cx_oracle://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/?service_name={db_config['service_name']}"
            )
        elif db_type == "postgres":
            db_url = (
                f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}"
                f"@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            )
        else:
            raise ValueError(f"不支持的数据库类型: {db_type}")

        engine = create_engine(
            db_url,
            pool_size=db_config.get("pool_size", 5),
            max_overflow=db_config.get("max_overflow", 10),
            pool_timeout=db_config.get("pool_timeout", 30),
            pool_recycle=db_config.get("pool_recycle", 3600),
        )

        logger.info(f"{db_type.capitalize()} 数据库引擎创建成功")
        return engine

    except Exception as e:
        logger.exception(f"{db_type.capitalize()} 数据库引擎创建失败: {e}")
        raise

oracle_engine = create_db_engine("oracle")
postgres_engine = create_db_engine("postgres")
