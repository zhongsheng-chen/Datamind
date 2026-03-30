# datamind/core/ml/model/inference.py
"""推理引擎

统一入口，根据模型类型分发到评分卡或陪跑预测器。

核心功能：
  - predict: 预测评分，自动路由到正确的预测器

特性：
  - 自动路由：LR 模型使用评分卡预测器，其他模型使用陪跑预测器
  - 统一接口：所有模型使用相同的调用方式
  - 审计日志：记录所有推理操作
  - 链路追踪：完整的 span 追踪

使用示例：
  >>> from datamind.core.ml.model.inference import InferenceEngine
  >>>
  >>> engine = InferenceEngine()
  >>> result = engine.predict("MDL_001", {"age": 35, "income": 50000})
  >>> print(result['score'])
  685.42
"""

from typing import Dict, Any

from datamind.core.ml.common.exceptions import ModelNotFoundException
from datamind.core.ml.model.loader import get_model_loader
from datamind.core.ml.scorecard.predictor import ScorecardPredictor
from datamind.core.ml.companion.predictor import CompanionPredictor
from datamind.core.domain.enums import ModelType


class InferenceEngine:
    """推理引擎

    根据模型类型将请求路由到对应的预测器。
    """

    def __init__(self):
        self._loader = get_model_loader()

    def predict(self, model_id: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        预测评分

        参数:
            model_id: 模型ID
            features: 特征字典，格式：{"feature_name": value, ...}

        返回:
            预测结果字典，包含：
                - score: 总评分
                - probability: 违约概率
                - feature_scores: 特征分（仅 LR 模型有值）
                - model_id: 模型ID
                - model_type: 模型类型
                - supports_feature_scores: 是否支持特征分

        异常:
            ModelNotFoundException: 模型不存在
        """
        model, metadata = self._get_model_with_metadata(model_id)
        model_type = metadata.get('model_type')

        if model_type == ModelType.LOGISTIC_REGRESSION.value:
            predictor = ScorecardPredictor(model, metadata)
        else:
            predictor = CompanionPredictor(model, metadata)

        return predictor.predict(features)

    def _get_model_with_metadata(self, model_id: str):
        """获取模型和元数据"""
        model = self._loader.get_model(model_id)

        if model is None:
            if not self._loader.load_model(model_id):
                raise ModelNotFoundException(model_id)
            model = self._loader.get_model(model_id)

        metadata = self._loader.get_model_metadata(model_id)

        if metadata is None:
            raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

        return model, metadata


def get_inference_engine() -> InferenceEngine:
    """获取推理引擎实例"""
    return InferenceEngine()