"""运行时服务缓存结构.

核心功能：
  - ServiceCacheEntry: 保存 Worker 本地服务缓存项

使用示例：
  from datamind.runtime.server.cache import ServiceCacheEntry

  entry = ServiceCacheEntry(
      service=runtime_service,
      generation=1,
      identity=id(runtime_model),
  )
"""

from dataclasses import dataclass, field
from uuid import uuid4

from datamind.runtime.serving.base import BaseRuntimeService


@dataclass(slots=True)
class ServiceCacheEntry:
    """Worker 本地服务缓存项.

    属性：
        service: RuntimeService 实例
        generation: 创建服务时已应用的控制版本
        identity: 创建服务时的模型对象标识
        instance_id: 运行时服务实例的唯一标识
    """

    service: BaseRuntimeService
    generation: int | None
    identity: int
    instance_id: str = field(default_factory=lambda: uuid4().hex)
