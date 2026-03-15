# datamind/core/db/database.py

import traceback
import logging
from contextlib import contextmanager
from typing import Generator, Optional
from datetime import datetime
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from core.logging import log_manager, get_request_id
from config.settings import settings
from .models import Base


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
        """初始化数据库连接"""
        if self._initialized:
            return

        start_time = datetime.now()
        request_id = get_request_id()

        try:
            self.database_url = database_url or settings.DATABASE_URL
            self.pool_size = pool_size or settings.DB_POOL_SIZE
            self.max_overflow = max_overflow or settings.DB_MAX_OVERFLOW
            self.pool_timeout = pool_timeout
            self.pool_recycle = pool_recycle
            self.echo = echo or settings.DB_ECHO

            if not self.database_url.startswith('postgresql'):
                raise ValueError("只支持PostgreSQL数据库")

            # 创建主引擎
            self._create_engine(
                'default',
                self.database_url,
                pool_size=self.pool_size,
                max_overflow=self.max_overflow,
                pool_timeout=self.pool_timeout,
                pool_recycle=self.pool_recycle,
                echo=self.echo
            )

            # 如果有只读副本，创建只读引擎
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

            duration = (datetime.now() - start_time).total_seconds() * 1000

            # 记录审计日志
            log_manager.log_audit(
                action="DB_INITIALIZE",
                user_id="system",
                ip_address="localhost",
                details={
                    "database_url": self.database_url.split('@')[-1],
                    "pool_size": pool_size,
                    "duration_ms": round(duration, 2)
                },
                request_id=request_id
            )

            self.logger.info(f"数据库初始化完成: {self.database_url.split('@')[-1]}")

        except Exception as e:
            log_manager.log_audit(
                action="DB_INITIALIZE",
                user_id="system",
                ip_address="localhost",
                details={"error": str(e)},
                request_id=request_id
            )
            self.logger.error(f"数据库初始化失败: {str(e)}")
            raise

    def _create_engine(self, name: str, url: str, **kwargs):
        """创建数据库引擎"""
        try:
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

            self.logger.debug(f"创建数据库引擎: {name}")

        except Exception as e:
            log_manager.log_audit(
                action="DB_CREATE_ENGINE",
                user_id="system",
                ip_address="localhost",
                details={"engine_name": name, "error": str(e)}
            )
            self.logger.error(f"创建数据库引擎失败 {name}: {str(e)}")
            raise

    def _add_engine_events(self, engine: Engine):
        """添加数据库引擎事件监听"""

        @event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            self.logger.debug("数据库连接已建立")

        @event.listens_for(engine, "checkout")
        def checkout(dbapi_connection, connection_record, connection_proxy):
            self.logger.debug("从连接池取出连接")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(OperationalError)
    )
    def get_session(self, engine_name: str = 'default') -> Session:
        """获取数据库会话（带重试机制）"""
        try:
            if engine_name not in self._scoped_sessions:
                engine_name = 'default'

            session = self._scoped_sessions[engine_name]()
            self._health_check(session)

            self.logger.debug(f"获取数据库会话: {engine_name}")
            return session

        except OperationalError as e:
            log_manager.log_audit(
                action="DB_GET_SESSION",
                user_id="system",
                ip_address="localhost",
                details={"engine_name": engine_name, "error": str(e)},
                reason="数据库连接失败"
            )
            self.logger.error(f"获取数据库会话失败 (将重试): {engine_name}, {str(e)}")
            self.reconnect(engine_name)
            raise
        except Exception as e:
            log_manager.log_audit(
                action="DB_GET_SESSION",
                user_id="system",
                ip_address="localhost",
                details={"engine_name": engine_name, "error": str(e)}
            )
            self.logger.error(f"获取数据库会话失败: {engine_name}, {str(e)}")
            raise

    def _health_check(self, session: Session):
        """数据库健康检查"""
        try:
            session.execute("SELECT 1")
        except Exception as e:
            log_manager.log_audit(
                action="DB_HEALTH_CHECK",
                user_id="system",
                ip_address="localhost",
                details={"error": str(e)}
            )
            self.logger.error(f"数据库健康检查失败: {str(e)}")
            raise

    @contextmanager
    def session_scope(self, engine_name: str = 'default', commit: bool = True) -> Generator[Session, None, None]:
        """会话上下文管理器（自动提交/回滚）"""
        session = self.get_session(engine_name)
        start_time = datetime.now()
        request_id = get_request_id()

        try:
            self.logger.debug(f"开始事务: {engine_name}")
            yield session

            if commit:
                session.commit()
                self.logger.debug("事务提交成功")

        except SQLAlchemyError as e:
            session.rollback()
            error_msg = str(e)
            error_trace = traceback.format_exc()

            log_manager.log_audit(
                action="DB_TRANSACTION",
                user_id="system",
                ip_address="localhost",
                details={
                    "engine_name": engine_name,
                    "error": error_msg,
                    "traceback": error_trace
                },
                reason=error_msg,
                request_id=request_id
            )

            self.logger.error(f"事务回滚: {error_msg}")
            raise
        finally:
            session.close()
            self.logger.debug("会话已关闭")

    @contextmanager
    def transaction(self, engine_name: str = 'default') -> Generator[Session, None, None]:
        """事务上下文管理器（需要手动提交）"""
        session = self.get_session(engine_name)

        try:
            self.logger.debug(f"开始手动事务: {engine_name}")
            yield session
        except SQLAlchemyError as e:
            session.rollback()
            self.logger.error(f"手动事务回滚: {str(e)}")
            raise
        finally:
            session.close()

    def reconnect(self, engine_name: str = 'default'):
        """重新连接数据库"""
        try:
            if engine_name in self._engines:
                self._engines[engine_name].dispose()
                self.logger.info(f"数据库引擎已释放: {engine_name}")

            if engine_name == 'default':
                self._create_engine(engine_name, self.database_url)
            elif engine_name == 'readonly' and settings.READONLY_DATABASE_URL:
                self._create_engine(engine_name, settings.READONLY_DATABASE_URL)

            log_manager.log_audit(
                action="DB_RECONNECT",
                user_id="system",
                ip_address="localhost",
                details={"engine_name": engine_name}
            )
            self.logger.info(f"数据库重新连接成功: {engine_name}")

        except Exception as e:
            log_manager.log_audit(
                action="DB_RECONNECT",
                user_id="system",
                ip_address="localhost",
                details={"engine_name": engine_name, "error": str(e)}
            )
            self.logger.error(f"数据库重新连接失败: {engine_name}, {str(e)}")
            raise

    def check_health(self) -> dict:
        """健康检查"""
        health_status = {'status': 'healthy', 'engines': {}}

        for name, engine in self._engines.items():
            try:
                with engine.connect() as conn:
                    conn.execute("SELECT 1")
                    health_status['engines'][name] = {'status': 'healthy'}

                self.logger.debug(f"数据库健康检查通过: {name}")

            except Exception as e:
                health_status['status'] = 'unhealthy'
                health_status['engines'][name] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }

                log_manager.log_audit(
                    action="DB_HEALTH_CHECK",
                    user_id="system",
                    ip_address="localhost",
                    details={"engine_name": name, "error": str(e)}
                )
                self.logger.error(f"数据库健康检查失败: {name}, {str(e)}")

        return health_status


# 全局数据库管理器实例
db_manager = DatabaseManager()


@contextmanager
def get_db(engine_name: str = 'default') -> Generator[Session, None, None]:
    """获取数据库会话的上下文管理器"""
    with db_manager.session_scope(engine_name) as session:
        yield session


def init_db(database_url: str = None):
    """初始化数据库（创建表）"""
    start_time = datetime.now()
    request_id = get_request_id()
    logger = logging.getLogger(f"{settings.name}.database.init")

    try:
        if not database_url:
            database_url = settings.DATABASE_URL

        engine = create_engine(database_url)
        logger.info(f"开始初始化数据库表: {database_url.split('@')[-1]}")

        with engine.connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
            conn.execute("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";")
            conn.commit()

        Base.metadata.create_all(engine)

        duration = (datetime.now() - start_time).total_seconds() * 1000

        log_manager.log_audit(
            action="DB_INIT_SCHEMA",
            user_id="system",
            ip_address="localhost",
            details={
                "database_url": database_url.split('@')[-1],
                "duration_ms": round(duration, 2)
            },
            request_id=request_id
        )

        logger.info(f"数据库表创建完成，耗时: {round(duration, 2)}ms")

    except Exception as e:
        log_manager.log_audit(
            action="DB_INIT_SCHEMA",
            user_id="system",
            ip_address="localhost",
            details={"error": str(e)},
            request_id=request_id
        )
        logger.error(f"数据库表创建失败: {str(e)}")
        raise