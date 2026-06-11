# datamind/runtime/serving/base.py

"""模型服务基类

定义运行时服务统一接口。

核心功能：
  - predict: 模型推理
  - health: 健康检查

使用示例：
    class ScoringService(ModelService):

        async def predict(
            self,
            features: dict,
        ) -> dict:
            ...

"""

from abc import ABC, abstractmethod
from typing import Any


class ModelService(ABC):
    """模型服务基类"""

    def __init__(self, model: Any):
        """
        参数：
            model: 已加载模型对象
        """
        self.model = model

    @abstractmethod
    async def predict(
        self,
        features: dict,
    ) -> dict:
        """执行推理

        参数：
            features: 输入特征

        返回：
            推理结果
        """
        raise NotImplementedError

    async def health(self) -> dict[str, str]:
        """健康检查

        返回：
            健康状态
        """
        return {
            "status": "healthy"
        }