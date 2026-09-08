"""运行时服务缓存结构

核心功能：
  - ServiceCacheEntry: 保存 Worker 本地服务缓存项

使用示例：
  from datamind.runtime.server.cache import ServiceCacheEntry

  entry = ServiceCacheEntry(
      service=runtime_service,
      generation=1,
      runtime_identity=id(runtime_model),
  )
"""

from dataclasses import dataclass

from datamind.runtime.serving.base import BaseRuntimeService


@dataclass(slots=True)
class ServiceCacheEntry:
    """Worker 本地服务缓存项

    属性：
        service: RuntimeService 实例
        generation: 创建服务时已应用的控制版本
        runtime_identity: RuntimeModel 对象身份标识
    """

    service: BaseRuntimeService
    generation: int | None
    runtime_identity: int
