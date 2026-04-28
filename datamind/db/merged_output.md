## Project Structure
```
    __init__.py
    __pycache__/
    core/
        __init__.py
        __pycache__/
        base.py
        engine.py
        mixins.py
        session.py
        uow.py
    init.py
    models/
        __init__.py
        __pycache__/
        assignments.py
        audit.py
        deployments.py
        experiments.py
        metadata.py
        requests.py
        routing.py
        versions.py
    writer/
        __init__.py
        __pycache__/
        assignment_writer.py
        audit_writer.py
        base_writer.py
        deployment_writer.py
        experiment_writer.py
        metadata_writer.py
        request_writer.py
        routing_writer.py
        version_writer.py
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\init.py
```python
# datamind/db/init.py

"""数据库初始化

负责：
- 初始化数据库连接
- 创建所有数据表

核心功能：
  - init_db: 初始化数据库（创建所有表）
  - check_db_connection: 检查数据库连接
  - create_tables: 创建表
  - drop_tables: 删除表（危险）
  - reset_database: 重建数据库（危险）
"""

from sqlalchemy import text

from datamind.db.core import Base, get_engine
from datamind.config.database import DatabaseConfig


def init_db(config: DatabaseConfig = None, recreate: bool = False):
    """初始化数据库

    参数：
        config: 数据库配置对象
        recreate: 是否重新创建表（危险，会删除所有数据）

    异常：
        初始化失败时抛出异常
    """
    engine = get_engine(config)

    if recreate:
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)


def check_db_connection(config: DatabaseConfig = None) -> bool:
    """检查数据库连接

    参数：
        config: 数据库配置对象

    返回：
        bool: 连接是否正常
    """
    try:
        engine = get_engine(config)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return False


def create_tables(config: DatabaseConfig = None):
    """创建表（不删除已有表）

    参数：
        config: 数据库配置对象
    """
    engine = get_engine(config)
    Base.metadata.create_all(bind=engine)


def drop_tables(config: DatabaseConfig = None):
    """删除所有表（危险操作）

    参数：
        config: 数据库配置对象
    """
    engine = get_engine(config)
    Base.metadata.drop_all(bind=engine)


def reset_database(config: DatabaseConfig = None):
    """重建数据库（危险操作，会删除所有数据）

    参数：
        config: 数据库配置对象
    """
    drop_tables(config)
    create_tables(config)
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\\_\_init\_\_.py
```python
# datamind/db/__init__.py

"""数据库模块

提供数据库连接管理、模型定义和异步写入能力。

核心功能：
  - init_db: 初始化数据库（创建所有表）
  - check_db_connection: 检查数据库连接
  - create_tables: 创建表
  - drop_tables: 删除表（危险）
  - reset_database: 重建数据库（危险）
  - get_engine: 获取数据库引擎
  - init_engine: 重置并重新初始化数据库引擎
  - get_session: 获取数据库会话
  - session_scope: 会话上下文管理器
  - AuditWriter: 审计日志写入器
  - RequestWriter: 请求写入器
  - AssignmentWriter: 分配记录写入器
  - RoutingWriter: 路由规则写入器
  - DeploymentWriter: 部署写入器
  - ExperimentWriter: 实验写入器
  - MetadataWriter: 模型元数据写入器
  - VersionWriter: 模型版本写入器

使用示例：
  from datamind.db import init_db, get_session, session_scope, AuditWriter
  from datamind.config import get_settings

  # 初始化数据库
  settings = get_settings()
  init_db(settings.database)

  # 获取会话
  session = get_session()

  # 使用上下文管理器
  with session_scope() as session:
      session.query(Model).all()

  # 写入审计日志
  writer = AuditWriter(session)
  writer.write(action="test", target_type="model", target_id="001")
"""

import datamind.db.models.requests
import datamind.db.models.audit
import datamind.db.models.metadata
import datamind.db.models.versions
import datamind.db.models.deployments
import datamind.db.models.experiments
import datamind.db.models.assignments
import datamind.db.models.routing

from datamind.db.core.engine import get_engine, init_engine
from datamind.db.core.session import (
    get_session,
    session_scope,
    get_session_manager,
    SessionManager,
)
from datamind.db.writer.audit_writer import AuditWriter
from datamind.db.writer.request_writer import RequestWriter
from datamind.db.writer.assignment_writer import AssignmentWriter
from datamind.db.writer.routing_writer import RoutingWriter
from datamind.db.writer.deployment_writer import DeploymentWriter
from datamind.db.writer.experiment_writer import ExperimentWriter
from datamind.db.writer.metadata_writer import MetadataWriter
from datamind.db.writer.version_writer import VersionWriter
from datamind.db.init import (
    init_db,
    check_db_connection,
    create_tables,
    drop_tables,
    reset_database,
)

__all__ = [
    "init_db",
    "check_db_connection",
    "create_tables",
    "drop_tables",
    "reset_database",
    "get_engine",
    "init_engine",
    "get_session",
    "session_scope",
    "get_session_manager",
    "SessionManager",
    "AuditWriter",
    "RequestWriter",
    "AssignmentWriter",
    "RoutingWriter",
    "DeploymentWriter",
    "ExperimentWriter",
    "MetadataWriter",
    "VersionWriter",
]
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\core\\base.py
```python
# datamind/db/core/base.py

"""数据库基类

定义 SQLAlchemy 的声明式基类。
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\core\\engine.py
```python
# datamind/db/core/engine.py

"""数据库引擎管理

提供数据库引擎的单例管理和连接池配置。

核心功能：
  - get_engine: 获取数据库引擎实例（单例）
  - init_engine: 初始化数据库引擎（重置单例）
"""

from sqlalchemy import create_engine
from datamind.config.database import DatabaseConfig

_engine = None


def get_engine(config: DatabaseConfig = None):
    """获取数据库引擎实例（单例）

    参数：
        config: 数据库配置对象

    返回：
        SQLAlchemy 引擎实例
    """
    global _engine
    if _engine is None:
        if config is None:
            from datamind.config import get_settings
            config = get_settings().database

        db_url = f"postgresql+psycopg2://{config.user}:{config.password}@{config.host}:{config.port}/{config.database}"

        _engine = create_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            future=True,
            echo=False,
            isolation_level="READ COMMITTED",
        )
    return _engine


def init_engine(config: DatabaseConfig = None):
    """初始化数据库引擎（重置单例）

    参数：
        config: 数据库配置对象
    """
    global _engine
    _engine = None
    return get_engine(config)
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\core\\mixins.py
```python
# datamind/db/core/mixins.py

"""模型混入类

提供通用的模型字段和功能。

核心功能：
  - IdMixin: 自增主键
  - TimestampMixin: 创建时间和更新时间
"""

from sqlalchemy import Column, DateTime, BigInteger, Identity
from sqlalchemy.sql import func


class IdMixin:
    """自增主键混入类"""

    id = Column(BigInteger, primary_key=True, autoincrement=True)


class TimestampMixin:
    """时间戳混入类

    属性：
        created_at: 创建时间
        updated_at: 更新时间
    """

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\core\\session.py
```python
# datamind/db/core/session.py

"""数据库会话管理

提供会话工厂和会话获取函数。

核心功能：
  - SessionManager: 会话管理器类
  - get_session_manager: 获取全局会话管理器单例
  - get_session: 获取数据库会话
  - session_scope: 会话上下文管理器

使用示例：
  from datamind.db.core.session import get_session, session_scope

  # 获取会话
  session = get_session()

  # 使用上下文管理器
  with session_scope() as session:
      session.query(Model).all()
"""

from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, Session
from datamind.db.core.engine import get_engine


class SessionManager:
    """会话管理器

    负责会话工厂的创建和会话的获取。
    """

    def __init__(self, config=None):
        """初始化会话管理器

        参数：
            config: 数据库配置对象
        """
        engine = get_engine(config)
        self._factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def get_session(self) -> Session:
        """获取数据库会话

        返回：
            数据库会话实例
        """
        return self._factory()

    @staticmethod
    def close_session(session: Session) -> None:
        """关闭数据库会话

        参数：
            session: 数据库会话实例
        """
        session.close()

    @contextmanager
    def session_scope(self):
        """会话上下文管理器

        自动处理提交和回滚。

        使用示例：
            with session_scope() as session:
                session.add(model)
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# 全局单例
_default_manager = None


def get_session_manager(config=None):
    """获取全局会话管理器单例

    参数：
        config: 数据库配置对象

    返回：
        SessionManager 实例
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = SessionManager(config)
    return _default_manager


def get_session(config=None):
    """获取数据库会话（便捷函数）

    参数：
        config: 数据库配置对象

    返回：
        数据库会话实例
    """
    return get_session_manager(config).get_session()


@contextmanager
def session_scope(config=None):
    """会话上下文管理器（便捷函数）

    参数：
        config: 数据库配置对象

    使用示例：
        with session_scope() as session:
            session.query(Model).all()
    """
    with get_session_manager(config).session_scope() as session:
        yield session
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\core\\uow.py
```python
# datamind/db/core/uow.py

"""工作单元

统一事务管理器，确保一个请求中的所有数据库操作在同一事务中完成。

核心功能：
  - UnitOfWork: 工作单元，管理事务生命周期
  - 提供所有 writer 的统一入口

使用示例：
  from datamind.db.core.uow import UnitOfWork

  with UnitOfWork() as uow:
      req = uow.request().write(
          request_id="r1",
          model_id="m1",
          payload={"x": 1}
      )
      uow.audit().write(
          action="request.create",
          target_type="request",
          target_id=req.id
      )
"""

from typing import Optional
from sqlalchemy.orm import Session

from datamind.db.core.session import SessionManager


class UnitOfWork:
    """统一事务管理器"""

    def __init__(self, session: Optional[Session] = None, session_manager: SessionManager = None):
        self._session = session
        self._session_manager = session_manager
        self._committed = False
        self._closed = False

    @property
    def session(self) -> Session:
        if self._session is None:
            if self._session_manager is None:
                from datamind.db.core.session import get_session_manager
                self._session_manager = get_session_manager()
            self._session = self._session_manager.get_session()
        return self._session

    def __enter__(self):
        _ = self.session
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()

    def commit(self):
        if self._closed:
            return
        if self._session and not self._committed:
            self._session.commit()
            self._committed = True

    def rollback(self):
        if self._session and not self._closed:
            self._session.rollback()

    def flush(self):
        if self._session:
            self._session.flush()

    def close(self):
        if self._session and not self._closed:
            self._session.close()
            self._closed = True
            self._session = None

    def audit(self):
        """获取审计日志写入器"""
        from datamind.db.writer.audit_writer import AuditWriter
        return AuditWriter(self.session)

    def request(self):
        """获取请求记录写入器"""
        from datamind.db.writer.request_writer import RequestWriter
        return RequestWriter(self.session)

    def assignment(self):
        """获取分配记录写入器"""
        from datamind.db.writer.assignment_writer import AssignmentWriter
        return AssignmentWriter(self.session)

    def routing(self):
        """获取路由规则写入器"""
        from datamind.db.writer.routing_writer import RoutingWriter
        return RoutingWriter(self.session)

    def deployment(self):
        """获取部署记录写入器"""
        from datamind.db.writer.deployment_writer import DeploymentWriter
        return DeploymentWriter(self.session)

    def experiment(self):
        """获取实验记录写入器"""
        from datamind.db.writer.experiment_writer import ExperimentWriter
        return ExperimentWriter(self.session)

    def metadata(self):
        """获取模型元数据写入器"""
        from datamind.db.writer.metadata_writer import MetadataWriter
        return MetadataWriter(self.session)

    def version(self):
        """获取模型版本写入器"""
        from datamind.db.writer.version_writer import VersionWriter
        return VersionWriter(self.session)
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\core\\\_\_init\_\_.py
```python
# datamind/db/core/__init__.py

"""数据库核心模块

提供数据库引擎、会话管理和基础模型类。

核心功能：
  - Base: SQLAlchemy 声明式基类
  - IdMixin: 自增主键混入类
  - TimestampMixin: 时间戳混入类
  - get_engine: 获取数据库引擎
  - init_engine: 初始化数据库引擎
  - SessionManager: 会话管理器
  - get_session_manager: 获取全局会话管理器
  - get_session: 获取数据库会话
  - session_scope: 会话上下文管理器

使用示例：
  from datamind.db.core import Base, IdMixin, TimestampMixin
  from datamind.db.core import get_engine, get_session, session_scope

  # 初始化引擎
  engine = get_engine(config)

  # 获取会话
  session = get_session()

  # 使用上下文管理器
  with session_scope() as session:
      session.query(Model).all()
"""

from datamind.db.core.base import Base
from datamind.db.core.mixins import IdMixin, TimestampMixin
from datamind.db.core.engine import get_engine, init_engine
from datamind.db.core.session import (
    SessionManager,
    get_session_manager,
    get_session,
    session_scope,
)

__all__ = [
    "Base",
    "IdMixin",
    "TimestampMixin",
    "get_engine",
    "init_engine",
    "SessionManager",
    "get_session_manager",
    "get_session",
    "session_scope",
]
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\assignments.py
```python
# datamind/db/models/assignments.py

"""请求分配表

记录每个请求被路由到的模型版本及分配原因，用于 A/B 测试和灰度发布的审计追踪。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Assignment(Base, IdMixin, TimestampMixin):
    """请求分配记录表

    属性：
        request_id: 请求唯一标识
        model_id: 被分配到的模型ID
        version: 被分配到的模型版本
        user: 用户
        source: 分配来源（routing/experiment/deployment）
        strategy: 分配策略（random/hash/weighted）
        context: 分配上下文（实验ID、分组、权重等）
        routed_at: 路由分配时间
    """

    __tablename__ = "assignments"

    __table_args__ = (
        Index("idx_assignments_model_id", "model_id"),
        Index("idx_assignments_request_id", "request_id"),
        Index("idx_assignments_model_version", "model_id", "version"),
        Index("idx_assignments_created_at", "created_at"),
        Index("idx_assignments_source", "source"),
        Index("idx_assignments_user", "user"),
    )

    request_id = Column(String(64), nullable=False)
    model_id = Column(String(64), nullable=False)

    version = Column(String(50), nullable=False)

    user = Column(String(64), nullable=True)
    source = Column(String(20), nullable=False)

    strategy = Column(String(20), nullable=True)

    context = Column(JSON, nullable=True)

    routed_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Assignment(request_id='{self.request_id}', model_id='{self.model_id}', version='{self.version}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\audit.py
```python
# datamind/db/models/audit.py

"""审计日志表

记录系统控制平面的所有变更行为，满足金融级审计要求。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Audit(Base, IdMixin, TimestampMixin):
    """审计日志表

    属性：
        user: 操作者
        ip: 操作者IP地址
        action: 操作类型（create/update/delete/deploy/pause/resume/rollback）
        target_type: 目标类型（experiment/deployment/routing/model/version）
        target_id: 目标ID
        before: 变更前数据
        after: 变更后数据
        context: 操作上下文（原因、审批信息等）
        occurred_at: 实际操作发生时间
    """

    __tablename__ = "audit"

    __table_args__ = (
        Index("idx_audit_action", "action"),
        Index("idx_audit_user", "user"),
        Index("idx_audit_target", "target_type", "target_id"),
        Index("idx_audit_occurred_at", "occurred_at"),
        Index("idx_audit_target_occurred_at", "target_type", "occurred_at"),
        Index("idx_audit_created_at", "created_at"),
    )

    user = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)

    action = Column(String(50), nullable=False)

    target_type = Column(String(50), nullable=False)
    target_id = Column(String(64), nullable=False)

    before = Column(JSON, nullable=True)
    after = Column(JSON, nullable=True)

    context = Column(JSON, nullable=True)

    occurred_at = Column(DateTime, nullable=False)

    def __repr__(self):
        return f"<Audit(action='{self.action}', target='{self.target_type}', user='{self.user}, ip='{self.ip}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\deployments.py
```python
# datamind/db/models/deployments.py

"""模型部署表

记录模型版本在生产环境中的生效区间与流量分配。
"""

from sqlalchemy import CheckConstraint
from sqlalchemy import Column, String, Float, Index, DateTime

from datamind.db.core import Base, IdMixin, TimestampMixin


class Deployment(Base, IdMixin, TimestampMixin):
    """模型部署表

    用于管理某个模型版本在生产环境中的生效状态和流量分配。

    属性：
        model_id: 所属模型ID
        version: 部署的版本号
        framework: 框架
        status: 部署状态（active/inactive）
        traffic_ratio: 流量占比（0.0 ~ 1.0）
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        deployed_by: 部署操作人
        description: 部署说明
    """

    __tablename__ = "deployments"

    __table_args__ = (
        Index("idx_deployments_model_id", "model_id"),
        Index("idx_deployments_version", "model_id", "version"),
        Index("idx_deployments_framework", "framework"),
        Index("idx_deployments_status", "status"),
        Index("idx_deployments_effective_time", "model_id", "effective_from", "effective_to"),
        Index("uk_deployments_model_id_version", "model_id", "version", unique=True),
        CheckConstraint("traffic_ratio >= 0 AND traffic_ratio <= 1"),
    )

    model_id = Column(String(64), nullable=False)

    version = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)

    status = Column(String(20), nullable=False, default="active")

    traffic_ratio = Column(Float, nullable=False, default=1.0)

    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)

    deployed_by = Column(String(50))
    description = Column(String(255))

    def __repr__(self):
        return f"<Deployment(model_id='{self.model_id}', version='{self.version}', status='{self.status}'>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\experiments.py
```python
# datamind/db/models/experiments.py

"""实验表

定义模型版本之间的 AB 实验或灰度策略配置。
"""

from sqlalchemy import Column, String, DateTime, Index, JSON

from datamind.db.core import Base, IdMixin, TimestampMixin


class Experiment(Base, IdMixin, TimestampMixin):
    """实验表

    属性：
        experiment_id: 实验唯一标识
        model_id: 所属模型ID
        name: 实验名称
        description: 实验描述
        status: 实验状态（running/paused/completed）
        config: 实验配置（策略、变体、权重等）
        effective_from: 生效开始时间
        effective_to: 生效结束时间
        created_by: 创建人
    """

    __tablename__ = "experiments"

    __table_args__ = (
        Index("idx_experiments_model_id", "model_id"),
        Index("idx_experiments_status", "status"),
        Index("idx_experiments_created_at", "created_at"),
        Index("idx_experiments_effective_time", "effective_from", "effective_to"),
        Index("idx_experiments_model_id_status", "model_id", "status"),
    )

    experiment_id = Column(String(64), nullable=False, unique=True)
    model_id = Column(String(64), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)

    status = Column(String(20), nullable=False, default="running")

    config = Column(JSON, nullable=True)

    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)

    created_by = Column(String(50), nullable=True)

    def __repr__(self):
        return f"<Experiment(experiment_id='{self.experiment_id}', name='{self.name}', status='{self.status}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\metadata.py
```python
# datamind/db/models/metadata.py

"""模型元数据模型

存储模型的元数据信息，包括模型标识、类型、Schema和状态等。
"""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Metadata(Base, IdMixin, TimestampMixin):
    """模型元数据表

    属性：
        model_id: 模型唯一标识
        name: 模型名称
        description: 模型描述
        model_type: 模型类型（logistic_regression/decision_tree/random_forest/xgboost/lightgbm/catboost）
        task_type: 任务类型（classification/scoring）
        framework: 框架（sklearn/xgboost/lightgbm/torch/tensorflow/onnx/catboost）
        input_schema: 输入Schema
        output_schema: 输出Schema
        status: 状态（active/inactive/deprecated/archived）
        created_by: 创建人
        updated_by: 更新人
    """

    __tablename__ = "metadata"

    __table_args__ = (
        Index("idx_metadata_name", "name"),
        Index("idx_metadata_status", "status"),
        Index("idx_metadata_framework", "framework"),
        Index("idx_metadata_model_type", "model_type"),
        Index("idx_metadata_task_type", "task_type"),
        Index("idx_metadata_created_at", "created_at"),
    )

    model_id = Column(String(64), nullable=False, unique=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)

    model_type = Column(String(50), nullable=False)
    task_type = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)

    input_schema = Column(JSONB)
    output_schema = Column(JSONB)

    status = Column(String(20), nullable=False, default="active")

    created_by = Column(String(50))
    updated_by = Column(String(50))

    def __repr__(self):
        return f"<Metadata(name='{self.name}', model_id='{self.model_id}', model_type='{self.model_type}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\requests.py
```python
# datamind/db/models/requests.py

"""请求表

记录进入系统的原始请求信息，用于请求追踪和性能分析。
"""

from sqlalchemy import Column, String, Index, JSON, Float

from datamind.db.core import Base, IdMixin, TimestampMixin


class Request(Base, IdMixin, TimestampMixin):
    """请求表

    属性：
        request_id: 请求唯一标识
        model_id: 目标模型ID
        payload: 请求输入
        source: 请求来源
        latency_ms: 处理耗时（毫秒）
        user: 用户
        ip: 客户端IP
    """

    __tablename__ = "requests"

    __table_args__ = (
        Index("idx_requests_request_id", "request_id"),
        Index("idx_requests_model_id", "model_id"),
        Index("idx_requests_created_at", "created_at"),
        Index("idx_requests_source", "source"),
        Index("idx_requests_user", "user"),
    )

    request_id = Column(String(64), nullable=False, unique=True)

    model_id = Column(String(64), nullable=False)

    payload = Column(JSON, nullable=True)

    source = Column(String(50), nullable=True)

    latency_ms = Column(Float, nullable=True)

    user = Column(String(64), nullable=True)
    ip = Column(String(64), nullable=True)

    def __repr__(self):
        return f"<Request(request_id='{self.request_id}', source='{self.source}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\routing.py
```python
# datamind/db/models/routing.py

"""模型路由表

定义模型版本的流量分配规则，支持多种路由策略。
"""

from sqlalchemy import Column, String, Boolean, JSON, Index

from datamind.db.core import Base, IdMixin, TimestampMixin


class Routing(Base, IdMixin, TimestampMixin):
    """模型路由表

    属性：
        model_id: 所属模型ID
        strategy: 路由策略（RANDOM/CONSISTENT/BUCKET/ROUND_ROBIN/WEIGHTED）
        config: 策略配置（权重、桶范围等）
        enabled: 是否启用（true/false）
    """

    __tablename__ = "routing"

    __table_args__ = (
        Index("idx_routing_model_id", "model_id"),
        Index("idx_routing_strategy", "strategy"),
        Index("idx_routing_enabled", "enabled"),
    )

    model_id = Column(String(64), nullable=False)

    strategy = Column(String(20), nullable=False)

    config = Column(JSON, nullable=True)

    enabled = Column(Boolean, nullable=False, default=True)

    def __repr__(self):
        return f"<Routing(model_id='{self.model_id}', strategy='{self.strategy}', enabled='{self.enabled}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\versions.py
```python
# datamind/db/models/versions.py

"""模型版本模型

存储模型版本信息，每次模型注册生成一条记录。
"""

from sqlalchemy import Column, String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB

from datamind.db.core import Base, IdMixin, TimestampMixin


class Version(Base, IdMixin, TimestampMixin):
    """模型版本表

    属性：
        model_id: 所属模型ID
        version: 版本号
        framework: 框架
        bento_tag: BentoML 标签（格式：模型名:版本）
        model_path: 模型文件存储路径
        params: 模型参数
        metrics: 模型评估指标
        description: 版本说明
        created_by: 创建人
    """

    __tablename__ = "versions"

    __table_args__ = (
        Index("idx_versions_model_id", "model_id"),
        Index("idx_versions_framework", "framework"),
        Index("idx_versions_bento_tag", "bento_tag"),
        Index("idx_versions_created_at", "created_at"),
        Index("uk_versions_model_id_version", "model_id", "version", unique=True),
    )

    model_id = Column(String(64), nullable=False)
    version = Column(String(50), nullable=False)
    framework = Column(String(50), nullable=False)

    bento_tag = Column(String(100), nullable=False)

    model_path = Column(String(255), nullable=False)

    params = Column(JSONB)
    metrics = Column(JSONB)

    description = Column(Text)
    created_by = Column(String(50))

    def __repr__(self):
        return f"<Version(model_id='{self.model_id}', version='{self.version}')>"
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\models\\\_\_init\_\_.py
```python
# datamind/db/models/__init__.py

"""数据库模型模块

定义所有数据表模型，统一导入点。

模型列表：
  - Audit: 审计日志表
  - Request: 请求记录表
  - Assignment: 分配记录表
  - Routing: 路由规则表
  - Deployment: 模型部署表
  - Experiment: AB实验表
  - Metadata: 模型元数据表
  - Version: 模型版本表

使用示例：
  from datamind.db.models import Metadata, Version, Experiment
"""

from datamind.db.models.audit import Audit
from datamind.db.models.requests import Request
from datamind.db.models.assignments import Assignment
from datamind.db.models.routing import Routing
from datamind.db.models.deployments import Deployment
from datamind.db.models.experiments import Experiment
from datamind.db.models.metadata import Metadata
from datamind.db.models.versions import Version

__all__ = [
    "Audit",
    "Request",
    "Assignment",
    "Routing",
    "Deployment",
    "Experiment",
    "Metadata",
    "Version",
]
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\assignment\_writer.py
```python
# datamind/db/writer/assignment_writer.py

"""分配记录写入器

记录每个请求被路由到的模型版本及分配原因，用于 A/B 测试和灰度发布的审计追踪。

使用示例：
    writer = AssignmentWriter(session)
    writer.write(
        request_id="req-001",
        model_id="scorecard_v2",
        version="2.0.0",
        source="experiment",
        context={"experiment_id": "exp_001", "group": "B"},
    )
"""

from datetime import datetime

from datamind.db.models.assignments import Assignment
from datamind.db.writer.base_writer import BaseWriter


class AssignmentWriter(BaseWriter):
    """分配记录写入器"""

    def write(
        self,
        *,
        request_id: str,
        model_id: str,
        version: str,
        user: str = None,
        source: str,
        strategy: str = None,
        context: dict = None,
    ) -> Assignment:
        """写入分配记录

        参数：
            request_id: 请求ID
            model_id: 被分配的模型ID
            version: 被分配的版本
            user: 用户
            source: 分配来源
            strategy: 分配策略
            context: 分配上下文

        返回：
            分配记录对象
        """
        obj = Assignment(
            request_id=request_id,
            model_id=model_id,
            version=version,
            user=user,
            source=source,
            strategy=strategy,
            context=context,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\audit\_writer.py
```python
# datamind/db/writer/audit_writer.py

"""审计日志写入器

记录系统所有变更行为，满足金融级审计要求。

使用示例：
    writer = AuditWriter(session)
    writer.write(
        user="system",
        action="deployment.deploy",
        target_type="deployment",
        target_id="dep_001",
        after={"status": "active"}
    )
"""

from datetime import datetime

from datamind.db.models.audit import Audit
from datamind.db.writer.base_writer import BaseWriter


class AuditWriter(BaseWriter):
    """审计日志写入器"""

    def write(
        self,
        *,
        user: str = None,
        ip: str = None,
        action: str,
        target_type: str,
        target_id: str,
        before: dict = None,
        after: dict = None,
        context: dict = None,
    ) -> Audit:
        """写入审计日志

        参数：
            user: 操作者
            ip: 操作者IP
            action: 操作类型（resource.verb 格式）
            target_type: 目标类型
            target_id: 目标ID
            before: 变更前数据
            after: 变更后数据
            context: 操作上下文

        返回：
            审计日志对象
        """
        obj = Audit(
            user=user,
            ip=ip,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            context=context,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\base\_writer.py
```python
# datamind/db/writer/base_writer.py

"""写入器基类

提供统一的数据库写入接口，事务由 UnitOfWork 统一管理。

注意：
  - Writer 只负责 add()，不负责 flush/commit
  - 事务控制由 UnitOfWork 统一管理
"""

from dataclasses import dataclass
from sqlalchemy.orm import Session


@dataclass
class BaseWriter:
    """写入器基类

    属性：
        session: 数据库会话
    """

    session: Session

    def add(self, obj):
        """添加单个对象"""
        self.session.add(obj)

    def add_all(self, objs):
        """添加多个对象"""
        self.session.add_all(objs)
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\deployment\_writer.py
```python
# datamind/db/writer/deployment_writer.py

"""部署写入器

记录模型版本在生产环境中的部署状态和流量分配。

使用示例：
    writer = DeploymentWriter(session)
    writer.write(
        model_id="scorecard_v1",
        version="1.0.0",
        status="active",
        traffic_ratio=1.0,
        deployed_by="system"
    )
"""

from datetime import datetime

from datamind.db.models.deployments import Deployment
from datamind.db.writer.base_writer import BaseWriter


class DeploymentWriter(BaseWriter):
    """部署写入器
    """

    def write(
        self,
        *,
        model_id: str,
        version: str,
        framework: str,
        status: str = "active",
        traffic_ratio: float = 1.0,
        effective_from: datetime = None,
        effective_to: datetime = None,
        deployed_by: str = None,
        description: str = None,
    ) -> Deployment:
        """写入部署记录

        参数：
            model_id: 模型ID
            version: 模型版本
            framework: 框架
            status: 部署状态
            traffic_ratio: 流量占比
            effective_from: 生效开始时间
            effective_to: 生效结束时间
            deployed_by: 部署人
            description: 部署说明

        返回：
            部署对象
        """
        obj = Deployment(
            model_id=model_id,
            version=version,
            framework=framework,
            status=status,
            traffic_ratio=traffic_ratio,
            effective_from=effective_from,
            effective_to=effective_to,
            deployed_by=deployed_by,
            description=description,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\experiment\_writer.py
```python
# datamind/db/writer/experiment_writer.py

"""实验写入器

记录 AB 实验或灰度策略的配置信息。

使用示例：
    writer = ExperimentWriter(session)
    writer.write(
        experiment_id="exp_001",
        model_id="scorecard_v1",
        name="模型对比实验",
        config={"strategy": "WEIGHTED", "variants": [...]},
        created_by="system"
    )
"""

from datetime import datetime

from datamind.db.models.experiments import Experiment
from datamind.db.writer.base_writer import BaseWriter


class ExperimentWriter(BaseWriter):
    """实验写入器"""

    def write(
        self,
        *,
        experiment_id: str,
        model_id: str,
        name: str,
        description: str = None,
        status: str = "running",
        config: dict = None,
        effective_from: datetime = None,
        effective_to: datetime = None,
        created_by: str = None,
    ) -> Experiment:
        """写入实验记录

        参数：
            experiment_id: 实验唯一标识
            model_id: 模型ID
            name: 实验名称
            description: 实验描述
            status: 实验状态
            config: 实验配置
            effective_from: 生效开始时间
            effective_to: 生效结束时间
            created_by: 创建人

        返回：
            实验对象
        """
        obj = Experiment(
            experiment_id=experiment_id,
            model_id=model_id,
            name=name,
            description=description,
            status=status,
            config=config,
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=created_by,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\metadata\_writer.py
```python
# datamind/db/writer/metadata_writer.py

"""模型元数据写入器

记录模型的基本定义信息，每个模型仅创建一次。

使用示例：
    writer = MetadataWriter(session)
    writer.create(
        model_id="scorecard_v1",
        name="信用评分卡",
        model_type="logistic_regression",
        task_type="scoring",
        framework="sklearn",
        description="基于逻辑回归的信用评分模型"
    )
"""

from datamind.db.models.metadata import Metadata
from datamind.db.writer.base_writer import BaseWriter


class MetadataWriter(BaseWriter):
    """模型元数据写入器"""

    def create(
        self,
        *,
        model_id: str,
        name: str,
        model_type: str,
        task_type: str,
        framework: str,
        description: str = None,
        input_schema: dict = None,
        output_schema: dict = None,
        created_by: str = None,
    ) -> Metadata:
        """创建模型元数据

        参数：
            model_id: 模型唯一标识
            name: 模型名称
            model_type: 模型类型
            task_type: 任务类型
            framework: 框架
            description: 模型描述
            input_schema: 输入Schema
            output_schema: 输出Schema
            created_by: 创建人

        返回：
            模型元数据对象
        """
        obj = Metadata(
            model_id=model_id,
            name=name,
            model_type=model_type,
            task_type=task_type,
            framework=framework,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            created_by=created_by,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\request\_writer.py
```python
# datamind/db/writer/request_writer.py

"""请求写入器

记录进入系统的原始请求信息，用于请求追踪和性能分析。

使用示例：
    writer = RequestWriter(session)
    writer.write(
        request_id="req-001",
        model_id="scorecard_v1",
        payload={"features": {"age": 35}},
        latency_ms=125.5
    )
"""

from datamind.db.models.requests import Request
from datamind.db.writer.base_writer import BaseWriter


class RequestWriter(BaseWriter):
    """请求写入器"""

    def write(
        self,
        *,
        request_id: str,
        model_id: str,
        payload: dict = None,
        source: str = None,
        latency_ms: float = None,
        user: str = None,
        ip: str = None,
    ) -> Request:
        """写入请求记录

        参数：
            request_id: 请求唯一标识
            model_id: 目标模型ID
            payload: 请求输入
            source: 请求来源
            latency_ms: 处理耗时（毫秒）
            user: 用户
            ip: 客户端IP

        返回：
            请求对象
        """
        obj = Request(
            request_id=request_id,
            model_id=model_id,
            payload=payload,
            source=source,
            latency_ms=latency_ms,
            user=user,
            ip=ip,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\routing\_writer.py
```python
# datamind/db/writer/routing_writer.py

"""路由规则写入器

定义模型版本的流量分配规则，支持多种路由策略。

使用示例：
    writer = RoutingWriter(session)
    writer.write(
        model_id="scorecard_v1",
        strategy="WEIGHTED",
        config={"versions": {"1.0.0": 80, "2.0.0": 20}}
    )
"""

from datamind.db.models.routing import Routing
from datamind.db.writer.base_writer import BaseWriter


class RoutingWriter(BaseWriter):
    """路由规则写入器"""

    def write(
        self,
        *,
        model_id: str,
        strategy: str,
        config: dict,
        enabled: bool = True,
    ) -> Routing:
        """写入路由规则

        参数：
            model_id: 模型ID
            strategy: 路由策略
            config: 策略配置
            enabled: 是否启用

        返回：
            路由规则对象
        """
        obj = Routing(
            model_id=model_id,
            strategy=strategy,
            config=config,
            enabled=enabled,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\version\_writer.py
```python
# datamind/db/writer/version_writer.py

"""模型版本写入器

记录模型的具体版本信息，每个模型可拥有多个版本。

使用示例：
    writer = VersionWriter(session)
    writer.create(
        model_id="mdl_xxxx",
        version="1.0.0",
        bento_tag="scorecard:abc123",
        model_path="s3://models/mdl_xxxx/1.0.0/model.pkl",
        params={"C": 1.0, "max_iter": 100},
        metrics={"accuracy": 0.85, "auc": 0.92}
    )
"""

from datamind.db.models.versions import Version
from datamind.db.writer.base_writer import BaseWriter


class VersionWriter(BaseWriter):
    """模型版本写入器"""

    def create(
        self,
        *,
        model_id: str,
        version: str,
        framework: str,
        bento_tag: str,
        model_path: str,
        params: dict = None,
        metrics: dict = None,
        description: str = None,
        created_by: str = None,
    ) -> Version:
        """创建模型版本

        参数：
            model_id: 所属模型ID
            version: 版本号
            framework: 框架
            bento_tag: BentoML 标签
            model_path: 模型文件存储路径
            params: 模型参数
            metrics: 模型评估指标
            description: 版本说明
            created_by: 创建人

        返回：
            模型版本对象
        """
        obj = Version(
            model_id=model_id,
            version=version,
            framework=framework,
            bento_tag=bento_tag,
            model_path=model_path,
            params=params,
            metrics=metrics,
            description=description,
            created_by=created_by,
        )
        self.add(obj)
        return obj
```

## C:\\Users\\zhongsheng\\PycharmProjects\\Datamind\\datamind\\db\\writer\\\_\_init\_\_.py
```python
# datamind/db/writer/__init__.py

"""数据库写入器模块

提供各数据表的统一写入接口。

写入器列表：
  - AuditWriter: 审计日志写入器
  - RequestWriter: 请求记录写入器
  - AssignmentWriter: 分配记录写入器
  - RoutingWriter: 路由规则写入器
  - DeploymentWriter: 模型部署写入器
  - ExperimentWriter: AB实验写入器
  - MetadataWriter: 模型元数据写入器
  - VersionWriter: 模型版本写入器

使用示例：
  from datamind.db.writer import MetadataWriter, VersionWriter

  writer = MetadataWriter(session)
  metadata = writer.create(
      model_id="scorecard_v1",
      name="信用评分卡",
      model_type="logistic_regression",
      task_type="scoring",
      framework="sklearn",
  )
"""

from datamind.db.writer.base_writer import BaseWriter
from datamind.db.writer.audit_writer import AuditWriter
from datamind.db.writer.request_writer import RequestWriter
from datamind.db.writer.assignment_writer import AssignmentWriter
from datamind.db.writer.routing_writer import RoutingWriter
from datamind.db.writer.deployment_writer import DeploymentWriter
from datamind.db.writer.experiment_writer import ExperimentWriter
from datamind.db.writer.metadata_writer import MetadataWriter
from datamind.db.writer.version_writer import VersionWriter

__all__ = [
    "BaseWriter",
    "AuditWriter",
    "RequestWriter",
    "AssignmentWriter",
    "RoutingWriter",
    "DeploymentWriter",
    "ExperimentWriter",
    "MetadataWriter",
    "VersionWriter",
]
```
