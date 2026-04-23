# datamind/db/core/uow.py

"""工作单元

统一事务管理器，确保一个请求中的所有数据库操作在同一个事务中完成。

核心功能：
  - UnitOfWork: 工作单元，管理事务生命周期
  - 提供所有 writer 的统一入口

使用示例：
  from datamind.db.core.uow import UnitOfWork
  from datamind.db.core.context import set_context

  set_context(user_id="admin", trace_id="trace-001")

  with UnitOfWork() as uow:
      req = uow.request().write(
          request_id="r1",
          model_id="m1",
          payload={"x": 1}
      )
      uow.audit().write(
          action="request",
          target_type="request",
          target_id=req.id
      )
"""

from dataclasses import dataclass

from datamind.db.core.session import get_session


@dataclass
class UnitOfWork:
    """统一事务管理器（工作单元）"""

    session = None

    def __post_init__(self):
        self.session = get_session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc:
                self.session.rollback()
            else:
                self.session.commit()
        finally:
            self.session.close()

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