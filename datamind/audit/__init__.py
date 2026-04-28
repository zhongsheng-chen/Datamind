# datamind/audit/__init__.py

"""审计模块

提供统一审计能力，支持装饰器审计与手动审计记录。

核心功能：
  - audit: 审计装饰器
  - AuditRecorder: 审计记录器

使用示例：

  from datamind.audit import audit


  @audit(
      action="model.register",
      target_type="model",
      target_id_from="model_id",
  )
  def register(model_id: str, name: str):
      return {"model_id": model_id}


  register("mdl_001", "scorecard")
"""

from datamind.audit.decorator import audit
from datamind.audit.recorder import AuditRecorder

__all__ = [
    "audit",
    "AuditRecorder",
]