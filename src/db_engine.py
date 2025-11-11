from threading import Lock
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from src.config_parser import config
from src.logger import get_logger

logger = get_logger()

# 引擎缓存池
_engines: dict[str, Engine] = {}
_lock = Lock()

# 数据库类型到 SQLAlchemy driver 映射
DRIVER_MAP = {
    "oracle": "oracle+cx_oracle",
    "postgres": "postgresql+psycopg2",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
}

def make_connection_url(db_name: str, db_config: dict) -> URL:
    """根据数据库配置构造 SQLAlchemy URL"""
    db_key = db_name.lower()
    drivername = DRIVER_MAP.get(db_key)
    if not drivername:
        raise ValueError(f"不支持的数据库类型: {db_name}")

    host = db_config.get("host", "localhost")
    port = int(db_config.get("port"))
    user = db_config.get("user", "")
    password = db_config.get("password", "")

    query = {}
    database = db_config.get("database", None)

    if db_key == "oracle":
        # Oracle 需要 service_name
        query["service_name"] = db_config.get("service_name", "")
        database = None
    elif db_key == "mysql":
        # MySQL 可选字符集
        query["charset"] = db_config.get("charset", "utf8mb4")
    elif db_key == "mssql":
        # SQL Server 可通过 DSN 或 query 配置其他参数
        query["driver"] = db_config.get("driver", "ODBC Driver 18 for SQL Server")

    return URL.create(
        drivername=drivername,
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
        query=query
    )


def create_db_engine(db_name: str) -> Engine:
    """根据配置创建数据库引擎"""
    try:
        db_config = config.get_database(db_name)
        if not db_config:
            raise ValueError(f"没有找到数据库配置: {db_name}")

        db_url = make_connection_url(db_name, db_config)

        engine = create_engine(
            db_url,
            pool_size=int(db_config.get("pool_size", 5)),
            max_overflow=int(db_config.get("max_overflow", 10)),
            pool_timeout=int(db_config.get("pool_timeout", 30)),
            pool_recycle=int(db_config.get("pool_recycle", 3600)),
        )

        logger.info(f"{db_name.capitalize()} 数据库引擎创建成功")
        return engine

    except Exception as e:
        logger.exception(f"{db_name.capitalize()} 数据库引擎创建失败: {e}")
        raise


def get_engine(db_name: str) -> Engine:
    """获取数据库引擎（线程安全、自动复用缓存）"""
    with _lock:
        if db_name not in _engines:
            logger.info(f"{db_name.capitalize()} 数据库引擎尚未创建，正在初始化...")
            _engines[db_name] = create_db_engine(db_name)
        return _engines[db_name]


# 示例初始化数据库
oracle_engine = get_engine("oracle")
postgres_engine = get_engine("postgres")
