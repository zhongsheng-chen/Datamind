# core/database.py
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from core.db.models import Base
from config.settings import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """PostgreSQL数据库管理器"""

    def __init__(self):
        self._engines = {}
        self._session_factories = {}
        self._scoped_sessions = {}
        self._initialized = False

    def initialize(
        self,
        database_url: str = None,
        pool_size: int = 20,
        max_overflow: int = 40,
        pool_timeout: int = 30,
        pool_recycle: int = 3600,
        echo: bool = False
    ):
        if self._initialized:
            return

        self.database_url = database_url or settings.DATABASE_URL
        self.pool_size = pool_size or settings.DB_POOL_SIZE
        self.max_overflow = max_overflow or settings.DB_MAX_OVERFLOW
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.echo = echo or settings.DB_ECHO

        if not self.database_url.startswith('postgresql'):
            raise ValueError("只支持PostgreSQL数据库")

        self._create_engine(
            'default',
            self.database_url,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            echo=self.echo
        )

        if settings.READONLY_DATABASE_URL:
            self._create_engine(
                'readonly',
                settings.READONLY_DATABASE_URL,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                echo=self.echo
            )

        self._initialized = True
        logger.info(f"数据库连接初始化完成")

    def _create_engine(self, name: str, url: str, **kwargs):
        engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_pre_ping=True,
            connect_args={
                'connect_timeout': 10,
                'keepalives': 1,
                'keepalives_idle': 30,
                'keepalives_interval': 10,
                'keepalives_count': 5,
            },
            **kwargs
        )

        self._add_engine_events(engine)

        self._engines[name] = engine
        self._session_factories[name] = sessionmaker(bind=engine)
        self._scoped_sessions[name] = scoped_session(self._session_factories[name])

    def _add_engine_events(self, engine: Engine):
        @event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            logger.debug("数据库连接已建立")

        @event.listens_for(engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            logger.debug("从连接池取出连接")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(OperationalError)
    )
    def get_session(self, engine_name: str = 'default') -> Session:
        try:
            if engine_name not in self._scoped_sessions:
                engine_name = 'default'

            session = self._scoped_sessions[engine_name]()
            self._health_check(session)
            return session
        except OperationalError as e:
            logger.error(f"获取数据库会话失败: {e}")
            self.reconnect(engine_name)
            raise

    def _health_check(self, session: Session):
        try:
            session.execute("SELECT 1")
        except Exception as e:
            logger.warning(f"数据库健康检查失败: {e}")
            raise

    @contextmanager
    def session_scope(self, engine_name: str = 'default', commit: bool = True) -> Generator[Session, None, None]:
        session = self.get_session(engine_name)
        try:
            yield session
            if commit:
                session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"事务回滚: {e}")
            raise
        finally:
            session.close()

    @contextmanager
    def transaction(self, engine_name: str = 'default') -> Generator[Session, None, None]:
        session = self.get_session(engine_name)
        try:
            yield session
        except Exception as e:
            session.rollback()
            logger.error(f"事务回滚: {e}")
            raise

    def reconnect(self, engine_name: str = 'default'):
        try:
            if engine_name in self._engines:
                self._engines[engine_name].dispose()
                logger.info(f"数据库引擎已释放: {engine_name}")

            if engine_name == 'default':
                self._create_engine(engine_name, self.database_url)
            elif engine_name == 'readonly' and settings.READONLY_DATABASE_URL:
                self._create_engine(engine_name, settings.READONLY_DATABASE_URL)

            logger.info(f"数据库重新连接成功: {engine_name}")
        except Exception as e:
            logger.error(f"数据库重新连接失败: {e}")
            raise

    def dispose_all(self):
        for name, engine in self._engines.items():
            engine.dispose()
            logger.info(f"数据库引擎已释放: {name}")

    def check_health(self) -> dict:
        health_status = {'status': 'healthy', 'engines': {}}
        for name, engine in self._engines.items():
            try:
                with engine.connect() as conn:
                    conn.execute("SELECT 1")
                    health_status['engines'][name] = {'status': 'healthy'}
            except Exception as e:
                health_status['status'] = 'unhealthy'
                health_status['engines'][name] = {'status': 'unhealthy', 'error': str(e)}
        return health_status


# 全局数据库管理器实例
db_manager = DatabaseManager()


def get_db_session(engine_name: str = 'default') -> Session:
    """获取数据库会话"""
    return db_manager.get_session(engine_name)


@contextmanager
def get_db(engine_name: str = 'default') -> Generator[Session, None, None]:
    """获取数据库会话的上下文管理器"""
    with db_manager.session_scope(engine_name) as session:
        yield session


def init_db(database_url: str = None):
    """初始化数据库（创建表）"""
    if not database_url:
        database_url = settings.DATABASE_URL

    engine = create_engine(database_url)

    with engine.connect() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
        conn.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";")
        conn.commit()

    Base.metadata.create_all(engine)
    logger.info("数据库表创建完成")