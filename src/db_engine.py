from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from src.config_parser import config
from src.logger import get_logger

logger = get_logger()

# 引擎缓存池
_engines: dict[str, Engine] = {}


def make_connection_url(db_name: str, db_config: dict) -> URL:
    """根据数据库配置构造 SQLAlchemy URL"""
    host = db_config.get("host", "localhost")
    port = db_config.get("port")
    user = db_config.get("user", "")
    password = db_config.get("password", "")

    if port is None:
        raise ValueError(f"数据库 {db_name} 配置缺少 port")

    if db_name.lower() == "oracle":
        service_name = db_config.get("service_name", "")
        return URL.create(
            drivername="oracle+cx_oracle",
            username=user,
            password=password,
            host=host,
            port=port,
            query={"service_name": service_name},
        )
    elif db_name.lower() == "postgres":
        database = db_config.get("database", "")
        return URL.create(
            drivername="postgresql+psycopg2",
            username=user,
            password=password,
            host=host,
            port=port,
            database=database,
        )
    else:
        raise ValueError(f"不支持的数据库类型: {db_name}")


def create_db_engine(db_name: str) -> Engine:
    """根据配置创建数据库引擎"""
    try:
        db_config = config.get_database(db_name)
        if not db_config:
            raise ValueError(f"没有找到数据库配置: {db_name}")

        db_url = make_connection_url(db_name, db_config)

        engine = create_engine(
            db_url,
            pool_size=db_config.get("pool_size", 5),
            max_overflow=db_config.get("max_overflow", 10),
            pool_timeout=db_config.get("pool_timeout", 30),
            pool_recycle=db_config.get("pool_recycle", 3600),
        )

        logger.info(f"{db_name.capitalize()} 数据库引擎创建成功")
        return engine

    except Exception as e:
        logger.exception(f"{db_name.capitalize()} 数据库引擎创建失败: {e}")
        raise


def get_engine(db_name: str) -> Engine:
    """获取数据库引擎（自动复用缓存）"""
    if db_name not in _engines:
        _engines[db_name] = create_db_engine(db_name)
    return _engines[db_name]

# 示例初始化数据库
oracle_engine = get_engine("oracle")
postgres_engine = get_engine("postgres")
