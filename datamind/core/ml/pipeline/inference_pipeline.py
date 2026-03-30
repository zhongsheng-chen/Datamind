# datamind/core/ml/pipeline/inference_pipeline.py
"""通用推理流程

陪跑模型（XGBoost、LightGBM、随机森林等）的预测流程。

流程：
  1. 特征验证
  2. 模型预测
  3. 分数转换（概率 → 0-1000 分）

使用示例：
  >>> from datamind.core.ml.pipeline.inference_pipeline import InferencePipeline
  >>>
  >>> pipeline = InferencePipeline()
  >>> result = pipeline.run(model, metadata, features)
"""

from typing import Dict, Any, List
import pandas as pd

from datamind.core.ml.adapters.factory import get_adapter


class InferencePipeline:
    """通用推理流程（陪跑模型）"""

    def run(
        self,
        model,
        metadata: Dict[str, Any],
        features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行通用预测

        参数:
            model: 训练好的模型
            metadata: 模型元数据
            features: 原始特征字典

        返回:
            预测结果字典，包含：
                - proba: 违约概率
                - score: 风险评分（概率 * 1000）
                - prediction: 分类结果（0/1）
        """
        feature_names = metadata.get('input_features', [])
        adapter = get_adapter(model, feature_names)

        # 构建特征数组
        ordered_values = [features.get(name, 0) for name in feature_names]
        X = pd.DataFrame([ordered_values], columns=feature_names)

        # 预测概率
        proba = adapter.predict_proba(X.values)

        # 转换为 0-1000 分
        score = proba * 1000

        # 分类结果
        prediction = 1 if proba >= 0.5 else 0

        return {
            "prediction": prediction,
            "proba": round(float(proba), 6),
            "score": round(float(score), 2),
            "feature_scores": None
        }