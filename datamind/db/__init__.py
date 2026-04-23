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