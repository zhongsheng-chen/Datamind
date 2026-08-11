# datamind/runtime/registry.py

"""运行时模型注册表

负责维护当前进程中已加载的运行时模型。

核心功能：
  - register: 注册运行时模型
  - get: 获取运行时模型
  - unregister: 注销运行时模型
  - restore: 恢复先前的运行时模型
  - all: 获取全部运行时模型
  - snapshot: 获取注册表状态快照
  - clear: 清空注册表

使用示例：
  from datamind.runtime.registry import RuntimeRegistry

  registry = RuntimeRegistry()

  registry.register(
      deployment_id="dep_0123456789abcdef",
      model_id="mdl_0123456789abcdef",
      version_id="ver_0123456789abcdef",
      framework="sklearn",
      model=model,
      metadata={
          "bento_tag": "scorecard:abc123def",
          "model_key": (
              "models/mdl_0123456789abcdef/1.0.0/"
              "artifacts/art_0123456789abcdef/model.pkl"
          ),
      },
  )

  runtime_model = registry.get("dep_0123456789abcdef")

  if runtime_model is not None:
      model = runtime_model.model

  runtime_models = registry.all()
  runtime_snapshot = registry.snapshot()
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass(slots=True)
class RuntimeModel:
    """运行时模型对象

    属性：
        deployment_id: 部署 ID
        model_id: 模型 ID
        version_id: 版本 ID
        framework: 模型框架
        model: 已加载的模型对象
        metadata: 运行时元数据
        loaded_at: 加载时间
        last_used_at: 最近使用时间
        access_count: 访问次数
    """

    deployment_id: str
    model_id: str
    version_id: str
    framework: str
    model: Any = field(repr=False)
    metadata: dict[str, Any] = field(default_factory=dict)
    loaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime | None = None
    access_count: int = 0

    def touch(self) -> None:
        """记录一次访问"""
        self.last_used_at = datetime.now(timezone.utc)
        self.access_count += 1

    def to_dict(self) -> dict:
        """转换为字典

        说明：
          - 不返回 model 对象本身
          - 仅返回可序列化的运行时元数据
        """
        return {
            "deployment_id": self.deployment_id,
            "model_id": self.model_id,
            "version_id": self.version_id,
            "framework": self.framework,
            "metadata": self.metadata,
            "loaded_at": self.loaded_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "access_count": self.access_count,
        }


class RuntimeRegistry:
    """运行时模型注册表

    在进程内保存 deployment_id 到 RuntimeModel 的映射关系。
    """

    def __init__(self):
        """初始化运行时模型注册表"""
        self._models: dict[str, RuntimeModel] = {}
        self._lock = RLock()

    def register(
            self,
            *,
            deployment_id: str,
            model_id: str,
            version_id: str,
            framework: str,
            model: Any,
            metadata: dict[str, Any] | None = None,
    ) -> RuntimeModel:
        """注册已加载模型

        参数：
            deployment_id: 部署 ID
            model_id: 模型 ID
            version_id: 版本 ID
            framework: 模型框架
            model: 已加载的模型对象
            metadata: 运行时元数据，可记录 bento_tag、model_key 等信息

        返回：
            运行时模型对象

        异常：
            ValueError: 参数为空
        """
        self._validate_required("deployment_id", deployment_id)
        self._validate_required("model_id", model_id)
        self._validate_required("version_id", version_id)
        self._validate_required("framework", framework)

        if model is None:
            raise ValueError("model 不能为空")

        runtime_model = RuntimeModel(
            deployment_id=deployment_id,
            model_id=model_id,
            version_id=version_id,
            framework=framework,
            model=model,
            metadata=dict(metadata or {}),
        )

        with self._lock:
            self._models[deployment_id] = runtime_model

        return runtime_model

    def get(
            self,
            deployment_id: str,
            *,
            touch: bool = True,
    ) -> RuntimeModel | None:
        """获取运行时模型

        参数：
            deployment_id: 部署 ID
            touch: 是否记录访问时间和访问次数，默认 True

        返回：
            运行时模型对象；不存在时返回 None
        """
        if not deployment_id:
            return None

        with self._lock:
            runtime_model = self._models.get(deployment_id)

            if runtime_model is not None and touch:
                runtime_model.touch()

            return runtime_model

    def __contains__(
            self,
            deployment_id: object,
    ) -> bool:
        """判断部署是否已加载

        参数：
            deployment_id: 部署 ID

        返回：
            是否已加载
        """
        if (
                not isinstance(deployment_id, str)
                or not deployment_id
        ):
            return False

        with self._lock:
            return deployment_id in self._models

    def unregister(
            self,
            deployment_id: str,
    ) -> RuntimeModel | None:
        """卸载运行时模型

        参数：
            deployment_id: 部署 ID

        返回：
            被移除的运行时模型对象；不存在时返回 None
        """
        if not deployment_id:
            return None

        with self._lock:
            return self._models.pop(deployment_id, None)

    def restore(self, runtime_model: RuntimeModel) -> None:
        """恢复先前可用的运行时模型对象"""
        with self._lock:
            self._models[runtime_model.deployment_id] = runtime_model

    def all(
            self,
    ) -> list[RuntimeModel]:
        """获取全部运行时模型

        返回：
            运行时模型对象列表
        """
        with self._lock:
            return list(self._models.values())

    def snapshot(
            self,
    ) -> list[dict]:
        """获取注册表状态快照

        返回：
            运行时模型字典列表
        """
        with self._lock:
            return [
                runtime_model.to_dict()
                for runtime_model in self._models.values()
            ]

    def __len__(self) -> int:
        """获取运行时模型数量"""
        with self._lock:
            return len(self._models)

    def clear(self) -> None:
        """清空注册表"""
        with self._lock:
            self._models.clear()

    @staticmethod
    def _validate_required(
            name: str,
            value: str,
    ) -> None:
        """校验必填字符串参数

        参数：
            name: 参数名称
            value: 参数值

        异常：
            ValueError: 参数为空
        """
        if not value:
            raise ValueError(f"{name} 不能为空")
