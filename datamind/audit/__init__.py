# datamind/audit/__init__.py

"""审计模块

对外提供审计装饰器与运行控制接口。

核心功能：
  - audit: 审计装饰器
  - start_audit_worker: 启动审计 Worker
  - stop_audit_worker: 停止审计 Worker

使用示例：

  from datamind.audit import audit, start_audit_worker, stop_audit_worker

  await start_audit_worker()

  @audit(
      action="model.register",
      target_type="model",
      target_id_from="model_id",
  )
  async def register(model_id: str):
      ...

  await stop_audit_worker()
"""

from datamind.audit.decorator import audit
from datamind.audit.worker import start_audit_worker, stop_audit_worker

__all__ = [
    "audit",
    "start_audit_worker",
    "stop_audit_worker",
]