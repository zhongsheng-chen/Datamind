# datamind/runtime/registry.py

"""运行时模型注册表

管理已经加载到内存中的模型对象。

核心功能：
  - RuntimeModel: 已加载模型运行对象
  - RuntimeRegistry: 运行时模型注册表

使用示例：
  from datamind.runtime.registry import RuntimeRegistry

  registry = RuntimeRegistry()

  registry.register(
      deployment_id="dep_a1b2c3d4",
      model_id="mdl_a1b2c3d4",
      version_id="ver_a1b2c3d4",
      framework="sklearn",
      model=model,
      metadata={
          "bento_tag": "scorecard:abc123def",
      },
  )

  runtime_model = registry.get("dep_a1b2c3d4")

  if runtime_model is not None:
      model = runtime_model.model

  runtime_models = registry.all()
  runtime_infos = registry.to_dicts()
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
            metadata: 运行时元数据，可记录 bento_tag、model_path 等信息

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

    def get_model(
        self,
        deployment_id: str,
        *,
        touch: bool = True,
    ) -> Any | None:
        """获取已加载模型对象

        参数：
            deployment_id: 部署 ID
            touch: 是否记录访问时间和访问次数，默认 True

        返回：
            已加载模型对象；不存在时返回 None
        """
        runtime_model = self.get(
            deployment_id,
            touch=touch,
        )

        if runtime_model is None:
            return None

        return runtime_model.model

    def exists(
        self,
        deployment_id: str,
    ) -> bool:
        """判断部署是否已加载

        参数：
            deployment_id: 部署 ID

        返回：
            是否已加载
        """
        if not deployment_id:
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

    def all(
        self,
    ) -> list[RuntimeModel]:
        """获取所有已加载模型

        返回：
            运行时模型对象列表
        """
        with self._lock:
            return list(self._models.values())

    def to_dicts(
        self,
    ) -> list[dict]:
        """转换为字典列表

        返回：
            运行时模型字典列表
        """
        with self._lock:
            return [
                runtime_model.to_dict()
                for runtime_model in self._models.values()
            ]

    def count(self) -> int:
        """获取已加载模型数量

        返回：
            已加载模型数量
        """
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