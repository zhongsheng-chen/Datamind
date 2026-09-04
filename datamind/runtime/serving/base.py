# datamind/runtime/serving/base.py

"""运行时服务基类

定义运行时模型服务的统一接口和公共能力。

核心功能：
  - BaseRuntimeService: 运行时服务基类
  - predict: 单条预测接口
  - predict_batch: 批量预测接口
  - get_capabilities: 获取模型能力集
  - has_capability: 检查模型能力
  - require_capability: 校验模型能力
  - build_result: 构造统一预测结果

使用示例：
  from datamind.runtime.serving.base import BaseRuntimeService
"""

from abc import ABC, abstractmethod
from typing import Any

from datamind.constants import DataType
from datamind.core.capability import (
    ModelCapability,
    get_model_capability_list,
)
from datamind.core.inference import Inference
from datamind.models.schema import SchemaExtractor
from datamind.runtime.registry import RuntimeModel


class BaseRuntimeService(ABC):
    """运行时服务基类

    所有具体运行时服务必须继承此类。

    属性：
        SERVICE_TYPE: 服务类型
        runtime_model: 运行时模型
        feature_names: 特征名称列表
        data_types: 特征类型映射
        inference: 统一推理组件
    """

    SERVICE_TYPE = "base"

    def __init__(
            self,
            *,
            runtime_model: RuntimeModel,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
    ):
        """初始化运行时服务

        参数：
            runtime_model: 已加载的运行时模型
            feature_names: 特征名称列表
            data_types: 特征类型映射

        异常：
            ValueError: runtime_model 为空
        """
        if runtime_model is None:
            raise ValueError(
                "runtime_model 不能为空"
            )

        self.runtime_model = runtime_model

        model_schema = SchemaExtractor.extract(
            model=runtime_model.model,
            framework=runtime_model.framework,
        ) or {}

        self.feature_names = (
            feature_names
            or self._get_schema_feature_names(
                model_schema
            )
        )

        self.data_types = (
            data_types
            or self._get_schema_data_types(
                model_schema
            )
            or {}
        )

        self.inference = Inference(
            model=runtime_model.model,
            feature_names=self.feature_names,
            data_types=self.data_types,
        )

    @property
    def deployment_id(
            self,
    ) -> str:
        """获取部署 ID"""
        return self.runtime_model.deployment_id

    @property
    def model_id(
            self,
    ) -> str:
        """获取模型 ID"""
        return self.runtime_model.model_id

    @property
    def version_id(
            self,
    ) -> str:
        """获取版本 ID"""
        return self.runtime_model.version_id

    @property
    def framework(
            self,
    ) -> str:
        """获取模型框架"""
        return self.runtime_model.framework

    @property
    def metadata(
            self,
    ) -> dict[str, Any]:
        """获取运行时元数据"""
        return self.runtime_model.metadata or {}

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取当前模型能力集

        返回：
            模型能力位掩码
        """
        return (
            self.inference.adapter
            .get_capabilities()
        )

    def get_capability_names(
            self,
    ) -> list[str]:
        """获取当前模型能力名称列表

        返回：
            能力名称列表
        """
        return get_model_capability_list(
            self.get_capabilities()
        )

    def has_capability(
            self,
            capability: ModelCapability,
    ) -> bool:
        """检查模型是否支持指定能力

        参数：
            capability: 模型能力

        返回：
            支持返回 True，否则返回 False
        """
        return (
            self.inference.adapter
            .has_capability(
                capability
            )
        )

    def require_capability(
            self,
            capability: ModelCapability,
    ) -> None:
        """校验模型能力

        参数：
            capability: 所需模型能力

        异常：
            NotImplementedError:
                当前模型不支持指定能力
        """
        self.inference.adapter.require_capability(
            capability
        )

    @abstractmethod
    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """单条预测

        参数：
            features: 特征字典

        返回：
            预测结果
        """
        raise NotImplementedError

    @abstractmethod
    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量预测

        参数：
            features_list: 特征字典列表

        返回：
            批量预测结果
        """
        raise NotImplementedError

    def build_result(
            self,
            result: dict[str, Any],
    ) -> dict[str, Any]:
        """构造统一预测结果

        在具体业务结果中增加模型运行信息。

        参数：
            result: 具体业务预测结果

        返回：
            完整预测结果
        """
        return {
            "deployment_id": self.deployment_id,
            "model_id": self.model_id,
            "version_id": self.version_id,
            "framework": self.framework,
            "service_type": self.SERVICE_TYPE,
            **result,
        }

    def touch(
            self,
    ) -> None:
        """更新运行时模型访问状态

        更新：
          - last_used_at
          - access_count
        """
        self.runtime_model.touch()

    @staticmethod
    def _get_schema_feature_names(
            schema: dict[str, Any],
    ) -> list[str] | None:
        """从模型 Schema 获取特征名称

        参数：
            schema: 从模型提取的 Schema

        返回：
            特征名称列表；
            不存在或类型不正确时返回 None
        """
        feature_names = schema.get(
            "feature_names"
        )
        return feature_names or None

    @staticmethod
    def _get_schema_data_types(
            schema: dict[str, Any],
    ) -> dict[str, DataType] | None:
        """从模型 Schema 获取特征类型

        参数：
            schema: 从模型提取的 Schema

        返回：
            特征类型映射；
            不存在或类型不正确时返回 None
        """
        data_types = schema.get(
            "data_types"
        )

        if not isinstance(
                data_types,
                dict,
        ):
            return None

        result: dict[str, DataType] = {}

        for name, data_type in data_types.items():
            if not isinstance(
                    name,
                    str,
            ):
                continue

            if isinstance(
                    data_type,
                    DataType,
            ):
                result[name] = data_type
                continue

            try:
                result[name] = DataType(
                    data_type
                )
            except (
                    TypeError,
                    ValueError,
            ):
                continue

        return result or None
