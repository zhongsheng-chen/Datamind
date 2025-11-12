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

# 默认 Engine 参数
DEFAULT_ENGINE_PARAMS = {
    "pool_size": 5,
    "max_overflow": 10,
    "pool_timeout": 30,
    "pool_recycle": 3600,
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
    database = db_config.get("database") or None
    query = {}

    if db_key == "oracle":
        service_name = db_config.get("service_name")
        sid = db_config.get("sid")
        if service_name:
            dsn = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})(PORT={port}))(CONNECT_DATA=(SERVICE_NAME={service_name})))"
        elif sid:
            dsn = f"(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST={host})(PORT={port}))(CONNECT_DATA=(SID={sid})))"
        else:
            raise ValueError("Oracle 连接缺少 service_name 或 sid")
        database = None
        query["dsn"] = dsn
    elif db_key == "mysql":
        query["charset"] = db_config.get("charset", "utf8mb4")
    elif db_key == "mssql":
        query["driver"] = db_config.get("driver", "ODBC Driver 18 for SQL Server")

    return URL.create(
        drivername=drivername,
        username=user,
        password=password,
        host=host,
        port=port,
        database=database,
        query=query,
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
            **{k: int(db_config.get(k, v)) for k, v in DEFAULT_ENGINE_PARAMS.items()}
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


class LazyEngine:
    """惰性加载 Engine，仅在首次访问时初始化"""
    def __init__(self, name: str):
        self._name = name
        self._engine: Engine | None = None
        self._lock = Lock()

    def __getattr__(self, item):
        if self._engine is None:
            with self._lock:
                if self._engine is None:
                    logger.info(f"正在延迟加载 {self._name} 数据库引擎...")
                    self._engine = get_engine(self._name)
        return getattr(self._engine, item)

    def dispose(self):
        """手动释放连接池资源"""
        if self._engine:
            logger.info(f"释放 {self._name} 数据库引擎连接池资源")
            self._engine.dispose()


def close_all_engines():
    """关闭所有缓存的数据库引擎"""
    with _lock:
        for name, engine in _engines.items():
            logger.info(f"关闭数据库引擎：{name}")
            engine.dispose()
        _engines.clear()


oracle_engine = LazyEngine("oracle")
postgres_engine = LazyEngine("postgres")
