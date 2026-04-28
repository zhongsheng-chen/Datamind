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