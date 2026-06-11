# datamind/runtime/registry.py

"""运行时服务注册表

维护当前进程内已启动的推理服务实例。

核心功能：
  - register: 注册服务实例
  - unregister: 注销服务实例
  - get: 获取服务实例
  - get_by_deployment: 根据部署 ID 获取服务实例
  - list: 获取全部服务实例

使用示例：
  from datamind.runtime.registry import RuntimeRegistry

  registry = RuntimeRegistry()

  registry.register(
      service_id="svc_xxx",
      deployment_id="dep_xxx",
      endpoint="http://127.0.0.1:3000"
  )

  service = registry.get("svc_xxx")
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class RuntimeService:
    """运行时服务"""

    service_id: str
    deployment_id: str

    endpoint: str

    pid: int | None = None
    port: int | None = None

    created_at: datetime | None = None


class RuntimeRegistry:
    """运行时注册表"""

    def __init__(self):
        """初始化注册表"""
        self._services: dict[str, RuntimeService] = {}

    def register(
        self,
        *,
        service_id: str,
        deployment_id: str,
        endpoint: str,
        pid: int | None = None,
        port: int | None = None,
    ) -> RuntimeService:
        """注册服务

        参数：
            service_id: 服务 ID
            deployment_id: 部署 ID
            endpoint: 服务地址
            pid: 进程 ID
            port: 服务端口

        返回：
            服务对象
        """
        service = RuntimeService(
            service_id=service_id,
            deployment_id=deployment_id,
            endpoint=endpoint,
            pid=pid,
            port=port,
            created_at=datetime.now(timezone.utc),
        )

        self._services[service_id] = service

        return service

    def unregister(
        self,
        service_id: str,
    ) -> None:
        """注销服务

        参数：
            service_id: 服务 ID
        """
        self._services.pop(service_id, None)

    def get(
        self,
        service_id: str,
    ) -> RuntimeService | None:
        """获取服务

        参数：
            service_id: 服务 ID

        返回：
            服务对象
        """
        return self._services.get(service_id)

    def get_by_deployment(
        self,
        deployment_id: str,
    ) -> RuntimeService | None:
        """根据部署 ID 获取服务

        参数：
            deployment_id: 部署 ID

        返回：
            服务对象
        """
        for service in self._services.values():
            if service.deployment_id == deployment_id:
                return service

        return None

    def list(
        self,
    ) -> list[RuntimeService]:
        """获取全部服务

        返回：
            服务列表
        """
        return list(self._services.values())

    def exists(
        self,
        service_id: str,
    ) -> bool:
        """服务是否存在

        参数：
            service_id: 服务 ID

        返回：
            是否存在
        """
        return service_id in self._services

    def clear(self) -> None:
        """清空注册表"""
        self._services.clear()