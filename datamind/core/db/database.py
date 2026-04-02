# datamind/core/db/database.py

"""PostgreSQL数据库管理器

提供数据库连接管理、会话管理、事务管理、复制监控等功能。

核心功能：
  - 数据库连接池管理（支持主库和只读副本）
  - 会话管理（自动提交/回滚）
  - 事务管理（支持手动和自动事务）
  - 健康检查（定期检查数据库连接状态）
  - 自动重连（连接失败时自动重试）
  - 重试机制（使用 tenacity 实现）
  - 复制状态监控（主备复制延迟监控）
  - 同步复制检查（同步复制配置检查）
  - 复制槽监控（物理复制槽状态监控）
  - 复制性能指标（延迟、吞吐量等）
  - 复制优化建议（根据当前状态提供改进建议）

特性：
  - 连接池：使用 QueuePool 管理连接
  - 连接参数：支持超时、keepalive 等参数配置
  - 事件监听：连接建立、连接取出等事件
  - 健康检查：执行 SELECT 1 验证连接可用性
  - 重试机制：连接失败时自动重试（最多3次，指数退避）
  - 只读副本：支持配置只读数据库，分担查询压力
  - 复制监控：实时监控主从复制状态和延迟
  - 告警机制：复制延迟超过阈值时自动告警
  - 复制槽监控：检测不活跃复制槽，防止 WAL 堆积
"""

import logging
import traceback
from contextlib import contextmanager
from typing import Generator, Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError, OperationalError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging import get_logger
from datamind.core.db.base import Base
from datamind.core.domain.enums import AuditAction
from datamind.config import get_settings

logger = get_logger(__name__)


class DatabaseManager:
    """PostgreSQL数据库管理器"""

    def __init__(self):
        self._engines = {}
        self._session_factories = {}
        self._scoped_sessions = {}
        self._initialized = False
        self._settings = None

        # 复制告警阈值配置
        self.replication_alert_thresholds = {
            'warning_lag_seconds': 10,
            'critical_lag_seconds': 60,
            'warning_lag_bytes': 100 * 1024 * 1024,
            'critical_lag_bytes': 1024 * 1024 * 1024,
        }

    def _get_settings(self):
        """获取配置（带缓存）"""
        if self._settings is None:
            self._settings = get_settings()
        return self._settings

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
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        settings = self._get_settings()

        try:
            self.database_url = database_url or settings.database.url
            self.pool_size = pool_size or settings.database.pool_size
            self.max_overflow = max_overflow or settings.database.max_overflow
            self.pool_timeout = pool_timeout or settings.database.pool_timeout
            self.pool_recycle = pool_recycle or settings.database.pool_recycle
            self.echo = echo or settings.database.echo

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

            if settings.database.readonly_url:
                self._create_engine(
                    'readonly',
                    settings.database.readonly_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_timeout=self.pool_timeout,
                    pool_recycle=self.pool_recycle,
                    echo=self.echo
                )

            self._initialized = True

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_audit(
                action=AuditAction.DB_INITIALIZE.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "database_url": self.database_url.split('@')[-1],
                    "pool_size": pool_size,
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            self.logger.info(f"数据库初始化完成: {self.database_url.split('@')[-1]}")

        except Exception as e:
            log_audit(
                action=AuditAction.DB_INITIALIZE.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            self.logger.error(f"数据库初始化失败: {str(e)}")
            raise

    def _create_engine(self, name: str, url: str, **kwargs):
        """创建数据库引擎"""
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

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

            self.logger.info(f"数据库引擎创建成功: {name}")

        except Exception as e:
            log_audit(
                action=AuditAction.DB_CREATE_ENGINE.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "engine_name": name,
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
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
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            if engine_name not in self._scoped_sessions:
                engine_name = 'default'

            session = self._scoped_sessions[engine_name]()
            self._health_check(session)

            self.logger.debug(f"获取数据库会话: {engine_name}")
            return session

        except OperationalError as e:
            log_audit(
                action=AuditAction.DB_GET_SESSION.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "engine_name": engine_name,
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason="数据库连接失败",
                request_id=request_id
            )
            self.logger.error(f"获取数据库会话失败 (将重试): {engine_name}, {str(e)}")
            self.reconnect(engine_name)
            raise
        except Exception as e:
            log_audit(
                action=AuditAction.DB_GET_SESSION.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "engine_name": engine_name,
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            self.logger.error(f"获取数据库会话失败: {engine_name}, {str(e)}")
            raise

    def _health_check(self, session: Session):
        """数据库健康检查"""
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            session.execute(text("SELECT 1"))
        except Exception as e:
            log_audit(
                action=AuditAction.DB_HEALTH_CHECK.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            self.logger.error(f"数据库健康检查失败: {str(e)}")
            raise

    @contextmanager
    def session_scope(self, engine_name: str = 'default', commit: bool = True) -> Generator[Session, None, None]:
        """会话上下文管理器（自动提交/回滚）"""
        session = self.get_session(engine_name)
        start_time = datetime.now()

        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            self.logger.debug(f"开始事务: {engine_name}")
            yield session

            if commit:
                session.commit()
                duration = (datetime.now() - start_time).total_seconds() * 1000

                log_audit(
                    action=AuditAction.DB_TRANSACTION.value,
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "engine_name": engine_name,
                        "duration_ms": round(duration, 2),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id,
                        "trace_id": trace_id
                    },
                    request_id=request_id
                )

                if duration > 100:
                    log_performance(
                        operation=AuditAction.DB_TRANSACTION.value,
                        duration_ms=duration,
                        extra={
                            "engine_name": engine_name,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id,
                            "trace_id": trace_id
                        }
                    )

                self.logger.debug(f"事务提交成功，耗时: {duration:.2f}ms")

        except SQLAlchemyError as e:
            session.rollback()
            duration = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = str(e)
            error_trace = traceback.format_exc()

            log_audit(
                action=AuditAction.DB_TRANSACTION.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "engine_name": engine_name,
                    "error": error_msg,
                    "traceback": error_trace,
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id,
                    "trace_id": trace_id
                },
                reason=error_msg,
                request_id=request_id
            )

            self.logger.error(f"事务回滚: {error_msg}, 耗时: {duration:.2f}ms")
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
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        settings = self._get_settings()

        try:
            if engine_name in self._engines:
                self._engines[engine_name].dispose()
                self.logger.info(f"数据库引擎已释放: {engine_name}")

            if engine_name == 'default':
                self._create_engine(engine_name, self.database_url)
            elif engine_name == 'readonly' and settings.database.readonly_url:
                self._create_engine(engine_name, settings.database.readonly_url)

            log_audit(
                action=AuditAction.DB_RECONNECT.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "engine_name": engine_name,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            self.logger.info(f"数据库重新连接成功: {engine_name}")

        except Exception as e:
            log_audit(
                action=AuditAction.DB_RECONNECT.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "engine_name": engine_name,
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            self.logger.error(f"数据库重新连接失败: {engine_name}, {str(e)}")
            raise

    def check_health(self) -> dict:
        """健康检查"""
        health_status = {'status': 'healthy', 'engines': {}}
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        for name, engine in self._engines.items():
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    health_status['engines'][name] = {'status': 'healthy'}

                self.logger.debug(f"数据库健康检查通过: {name}")

            except Exception as e:
                health_status['status'] = 'unhealthy'
                health_status['engines'][name] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }

                log_audit(
                    action=AuditAction.DB_HEALTH_CHECK.value,
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "engine_name": name,
                        "error": str(e),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )
                self.logger.error(f"数据库健康检查失败: {name}, {str(e)}")

        return health_status

    def check_replication_status(self) -> Dict[str, Any]:
        """检查主备复制状态"""
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with self.get_session('default') as session:
                is_replica = session.execute(
                    text("SELECT pg_is_in_recovery();")
                ).scalar()

                if is_replica:
                    return {
                        'status': 'replica',
                        'is_replica': True,
                        'message': '当前数据库是备库，无法查询复制状态',
                        'timestamp': datetime.now().isoformat()
                    }

                has_permission = session.execute(
                    text("""
                        SELECT has_database_privilege(current_user, current_database(), 'CONNECT')
                        AND has_table_privilege('pg_stat_replication', 'SELECT');
                    """)
                ).scalar()

                if not has_permission:
                    return {
                        'status': 'insufficient_permission',
                        'error': '需要 SUPERUSER 或 MONITOR 权限查询复制状态',
                        'timestamp': datetime.now().isoformat()
                    }

                result = session.execute(text("""
                                              SELECT application_name,
                                                     client_addr,
                                                     state,
                                                     sync_state,
                                                     replay_lag,
                                                     EXTRACT(EPOCH FROM replay_lag)                    as replay_lag_seconds,
                                                     write_lag,
                                                     flush_lag,
                                                     pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) as byte_lag
                                              FROM pg_stat_replication;
                                              """)).fetchall()

                replicas = []
                max_lag = 0
                max_byte_lag = 0

                for row in result:
                    lag_seconds = row.replay_lag_seconds or 0
                    byte_lag = row.byte_lag or 0
                    max_lag = max(max_lag, lag_seconds)
                    max_byte_lag = max(max_byte_lag, byte_lag)

                    replicas.append({
                        'name': row.application_name or 'unknown',
                        'address': str(row.client_addr) if row.client_addr else None,
                        'state': row.state,
                        'sync_state': row.sync_state,
                        'replay_lag_seconds': float(lag_seconds),
                        'byte_lag': byte_lag,
                        'byte_lag_mb': round(byte_lag / 1024 / 1024, 2),
                        'write_lag': str(row.write_lag) if row.write_lag else None,
                        'flush_lag': str(row.flush_lag) if row.flush_lag else None,
                    })

                if max_lag > self.replication_alert_thresholds['critical_lag_seconds']:
                    status = 'critical'
                elif max_lag > self.replication_alert_thresholds['warning_lag_seconds']:
                    status = 'warning'
                else:
                    status = 'healthy'

                log_audit(
                    action=AuditAction.REPLICATION_STATUS.value,
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "replicas_count": len(replicas),
                        "max_lag_seconds": max_lag,
                        "max_byte_lag_mb": round(max_byte_lag / 1024 / 1024, 2),
                        "status": status,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                if status in ['warning', 'critical']:
                    self._send_replication_alert(status, max_lag, max_byte_lag, replicas)

                return {
                    'status': status,
                    'replicas': replicas,
                    'max_lag_seconds': max_lag,
                    'max_byte_lag_mb': round(max_byte_lag / 1024 / 1024, 2),
                    'timestamp': datetime.now().isoformat(),
                    'has_replicas': len(replicas) > 0
                }

        except Exception as e:
            self.logger.error(f"检查复制状态失败: {e}")
            log_audit(
                action=AuditAction.REPLICATION_STATUS.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason="复制状态检查失败",
                request_id=request_id
            )
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def check_sync_status(self) -> Dict[str, Any]:
        """检查同步复制状态"""
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with self.get_session('default') as session:
                result = session.execute(text("""
                    SELECT 
                        synchronous_standby_names,
                        synchronous_commit,
                        in_recovery,
                        pg_is_in_recovery() as is_replica
                """)).fetchone()

                log_audit(
                    action=AuditAction.SYNC_STATUS.value,
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "synchronous_commit": result.synchronous_commit,
                        "is_primary": not result.in_recovery,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                return {
                    'synchronous_standby_names': result.synchronous_standby_names,
                    'synchronous_commit': result.synchronous_commit,
                    'is_primary': not result.in_recovery,
                    'is_replica': result.is_replica,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            self.logger.error(f"检查同步状态失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}

    def check_replication_slots(self) -> Dict[str, Any]:
        """检查复制槽状态"""
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with self.get_session('default') as session:
                is_replica = session.execute(
                    text("SELECT pg_is_in_recovery();")
                ).scalar()

                if is_replica:
                    return {
                        'status': 'replica',
                        'is_replica': True,
                        'message': '当前数据库是备库，无法查询复制槽状态',
                        'timestamp': datetime.now().isoformat()
                    }

                result = session.execute(text("""
                                              SELECT slot_name,
                                                     slot_type,
                                                     database,
                                                     active,
                                                     restart_lsn,
                                                     pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) as wal_retained_bytes,
                                                     CASE
                                                         WHEN active = false THEN 'inactive'
                                                         WHEN pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) > 1024 * 1024 * 1024
                                                             THEN 'high_lag'
                                                         ELSE 'healthy'
                                                         END                                            as status
                                              FROM pg_replication_slots
                                              WHERE slot_type = 'physical';
                                              """)).fetchall()

                slots = []
                for row in result:
                    slots.append({
                        'name': row.slot_name,
                        'type': row.slot_type,
                        'database': row.database,
                        'active': row.active,
                        'restart_lsn': row.restart_lsn,
                        'wal_retained_bytes': row.wal_retained_bytes or 0,
                        'wal_retained_mb': round((row.wal_retained_bytes or 0) / 1024 / 1024, 2),
                        'status': row.status
                    })

                inactive_slots = [s for s in slots if not s['active']]
                if inactive_slots:
                    self.logger.warning(f"发现不活跃的复制槽: {[s['name'] for s in inactive_slots]}")

                log_audit(
                    action=AuditAction.REPLICATION_SLOTS.value,
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "total_slots": len(slots),
                        "active_slots": len([s for s in slots if s['active']]),
                        "inactive_slots": len(inactive_slots),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                return {
                    'slots': slots,
                    'total_slots': len(slots),
                    'active_slots': len([s for s in slots if s['active']]),
                    'inactive_slots': len(inactive_slots),
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            self.logger.error(f"检查复制槽失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}

    def get_replication_metrics(self) -> Dict[str, Any]:
        """获取复制性能指标"""
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with self.get_session('default') as session:
                is_replica = session.execute(
                    text("SELECT pg_is_in_recovery();")
                ).scalar()

                if is_replica:
                    return {
                        'status': 'replica',
                        'is_replica': True,
                        'message': '当前数据库是备库，无法获取复制指标',
                        'timestamp': datetime.now().isoformat()
                    }

                result = session.execute(text("""
                                              SELECT COUNT(*)                                               as total_replicas,
                                                     COUNT(CASE WHEN state = 'streaming' THEN 1 END)        as streaming_replicas,
                                                     AVG(EXTRACT(EPOCH FROM replay_lag))                    as avg_replay_lag,
                                                     MAX(EXTRACT(EPOCH FROM replay_lag))                    as max_replay_lag,
                                                     SUM(pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn)) as total_byte_lag,
                                                     COUNT(CASE WHEN sync_state = 'sync' THEN 1 END)        as sync_replicas,
                                                     COUNT(CASE WHEN sync_state = 'quorum' THEN 1 END)      as quorum_replicas,
                                                     COUNT(CASE WHEN sync_state = 'async' THEN 1 END)       as async_replicas
                                              FROM pg_stat_replication;
                                              """)).fetchone()

                log_audit(
                    action=AuditAction.REPLICATION_METRICS.value,
                    user_id="system",
                    ip_address="localhost",
                    details={
                        "total_replicas": result.total_replicas or 0,
                        "streaming_replicas": result.streaming_replicas or 0,
                        "avg_replay_lag_seconds": float(result.avg_replay_lag or 0),
                        "max_replay_lag_seconds": float(result.max_replay_lag or 0),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                return {
                    'total_replicas': result.total_replicas or 0,
                    'streaming_replicas': result.streaming_replicas or 0,
                    'avg_replay_lag_seconds': float(result.avg_replay_lag or 0),
                    'max_replay_lag_seconds': float(result.max_replay_lag or 0),
                    'total_byte_lag_mb': round((result.total_byte_lag or 0) / 1024 / 1024, 2),
                    'sync_replicas': result.sync_replicas or 0,
                    'quorum_replicas': result.quorum_replicas or 0,
                    'async_replicas': result.async_replicas or 0,
                    'timestamp': datetime.now().isoformat()
                }

        except Exception as e:
            self.logger.error(f"获取复制指标失败: {e}")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}

    def get_replication_recommendations(self) -> Dict[str, Any]:
        """获取复制优化建议"""
        status = self.check_replication_status()
        recommendations = []

        if status.get('status') == 'error':
            recommendations.append({
                'severity': 'high',
                'issue': '无法获取复制状态',
                'suggestion': '检查数据库连接和权限配置',
                'action': f"错误详情: {status.get('error', 'Unknown error')}"
            })
        elif status.get('status') == 'replica':
            recommendations.append({
                'severity': 'info',
                'issue': '当前是备库节点',
                'suggestion': '复制状态需要从主库查询',
                'action': '请连接到主库进行复制状态检查'
            })
        else:
            if not status.get('has_replicas', False):
                recommendations.append({
                    'severity': 'high',
                    'issue': '未配置任何只读副本',
                    'suggestion': '建议配置至少一个只读副本以提高可用性和查询性能',
                    'action': '使用 pg_basebackup 创建流复制备库'
                })

            max_lag = status.get('max_lag_seconds', 0)
            if max_lag > 60:
                recommendations.append({
                    'severity': 'critical',
                    'issue': f'复制延迟过高 ({max_lag:.2f}秒)',
                    'suggestion': '检查网络带宽、备库磁盘I/O和主库负载',
                    'action': '优化WAL传输参数，考虑使用同步复制或增加网络带宽'
                })
            elif max_lag > 10:
                recommendations.append({
                    'severity': 'medium',
                    'issue': f'复制延迟较高 ({max_lag:.2f}秒)',
                    'suggestion': '监控网络和磁盘性能，检查是否有长时间运行的事务',
                    'action': '考虑调整 max_wal_senders 和 wal_keep_size 参数'
                })

            sync_status = self.check_sync_status()
            if sync_status.get('synchronous_commit') == 'on' and not sync_status.get('synchronous_standby_names'):
                recommendations.append({
                    'severity': 'medium',
                    'issue': '同步复制已启用但未配置同步备库',
                    'suggestion': '配置 synchronous_standby_names 或关闭同步复制',
                    'action': '设置 synchronous_standby_names 为备库名称或改为 async 模式'
                })

        return {
            'recommendations': recommendations,
            'timestamp': datetime.now().isoformat()
        }

    def _send_replication_alert(self, status: str, lag_seconds: float, byte_lag: int, replicas: List[Dict]):
        """发送复制告警"""
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        request_id = context.get_request_id()

        alert_msg = (
            f"数据库复制{status.upper()}告警！\n"
            f"副本数量: {len(replicas)}\n"
            f"最大延迟: {lag_seconds:.2f}秒\n"
            f"最大字节延迟: {byte_lag / 1024 / 1024:.2f}MB\n"
            f"副本详情:\n"
        )

        for replica in replicas:
            alert_msg += (
                f"  - {replica['name']}: "
                f"状态={replica['state']}, "
                f"延迟={replica['replay_lag_seconds']:.2f}秒\n"
            )

        self.logger.warning(alert_msg)

        log_audit(
            action=AuditAction.REPLICATION_ALERT.value,
            user_id="system",
            ip_address="localhost",
            details={
                "status": status,
                "max_lag_seconds": lag_seconds,
                "max_byte_lag_mb": round(byte_lag / 1024 / 1024, 2),
                "replicas_count": len(replicas),
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            reason=f"复制{status}告警",
            request_id=request_id
        )

    @property
    def logger(self):
        """获取日志记录器"""
        return logging.getLogger(f"{self._get_settings().app.app_name}.database")


# 全局数据库管理器实例
db_manager = DatabaseManager()


def get_engine(engine_name: str = 'default') -> Engine:
    """获取数据库引擎

    参数:
        engine_name: 引擎名称 ('default' 或 'readonly')

    返回:
        SQLAlchemy Engine 对象
    """
    if not db_manager._initialized:
        db_manager.initialize()

    if engine_name not in db_manager._engines:
        raise ValueError(f"引擎 '{engine_name}' 不存在，可用的引擎: {list(db_manager._engines.keys())}")

    return db_manager._engines[engine_name]


def get_engines() -> Dict[str, Engine]:
    """获取所有数据库引擎"""
    if not db_manager._initialized:
        db_manager.initialize()
    return db_manager._engines


@contextmanager
def get_db(engine_name: str = 'default') -> Generator[Session, None, None]:
    """获取数据库会话的上下文管理器"""
    with db_manager.session_scope(engine_name) as session:
        yield session


def init_db(database_url: str = None):
    """初始化数据库（创建表）"""
    start_time = datetime.now()
    request_id = context.get_request_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    settings = get_settings()
    logger_db = logging.getLogger(f"{settings.app.app_name}.database.init")

    try:
        if not database_url:
            database_url = settings.database.url

        engine = create_engine(database_url)
        logger_db.info(f"开始初始化数据库表: {database_url.split('@')[-1]}")

        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"))
            conn.commit()

        Base.metadata.create_all(engine)

        duration = (datetime.now() - start_time).total_seconds() * 1000

        log_audit(
            action=AuditAction.DB_INIT_SCHEMA.value,
            user_id="system",
            ip_address="localhost",
            details={
                "database_url": database_url.split('@')[-1],
                "duration_ms": round(duration, 2),
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        logger_db.info(f"数据库表创建完成，耗时: {round(duration, 2)}ms")

    except Exception as e:
        log_audit(
            action=AuditAction.DB_INIT_SCHEMA.value,
            user_id="system",
            ip_address="localhost",
            details={
                "error": str(e),
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )
        logger_db.error(f"数据库表创建失败: {str(e)}")
        raise