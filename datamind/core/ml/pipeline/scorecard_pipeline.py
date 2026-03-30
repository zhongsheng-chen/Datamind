# datamind/core/ml/pipeline/scorecard_pipeline.py
"""评分卡 Pipeline

银行评分卡的完整执行流程。

流程：
  1. WOE 转换 + 分箱信息提取
  2. 模型预测（LR）
  3. 分数转换
  4. 特征分解释（可选）
  5. 拒绝原因（可选）

特性：
  - 完整分箱信息：返回每个特征的分箱详情
  - 可审计：所有转换步骤可追溯
  - 支持 challenger 模式：陪跑模型不输出评分

使用示例：
  >>> from datamind.core.ml.pipeline.scorecard_pipeline import ScorecardPipeline
  >>>
  >>> pipeline = ScorecardPipeline(transformer, scorer, explainer, reason_engine)
  >>> result = pipeline.run(model, metadata, features, need_explain=True, need_reason=True)
"""

from typing import Dict, Any, Optional

from datamind.core.ml.features.transformer import WOETransformer
from datamind.core.ml.postprocess.scorer import ScoreScorer
from datamind.core.ml.explain.scorecard import ScorecardExplainer
from datamind.core.ml.explain.reason_code import ReasonCodeEngine
from datamind.core.ml.adapters.factory import get_adapter


class ScorecardPipeline:
    """银行评分卡 Pipeline"""

    def __init__(
        self,
        transformer: WOETransformer,
        scorer: ScoreScorer,
        explainer: ScorecardExplainer,
        reason_engine: Optional[ReasonCodeEngine] = None,
        threshold: float = 0.5
    ):
        """
        初始化评分卡 Pipeline

        参数:
            transformer: WOE 转换器
            scorer: 分数转换器
            explainer: 评分卡解释器
            reason_engine: 拒绝原因引擎（可选）
            threshold: 分类阈值，默认 0.5
        """
        self.transformer = transformer
        self.scorer = scorer
        self.explainer = explainer
        self.reason_engine = reason_engine
        self.threshold = threshold

    def run(
        self,
        model,
        metadata: Dict[str, Any],
        features: Dict[str, Any],
        is_challenger: bool = False,
        need_explain: bool = False,
        need_reason: bool = False
    ) -> Dict[str, Any]:
        """
        执行评分卡预测

        参数:
            model: LR 模型
            metadata: 模型元数据
            features: 原始特征字典
            is_challenger: 是否为陪跑模型（不输出评分）
            need_explain: 是否需要特征分解释
            need_reason: 是否需要拒绝原因

        返回:
            预测结果字典，包含：
                - prediction: 分类结果（0/1）
                - proba: 违约概率
                - score: 信用评分（challenger 模式不返回）
                - explain: 特征分解释（need_explain=True 时返回）
                - reason_codes: 拒绝原因（need_reason=True 时返回）
        """
        # 1️⃣ WOE 转换 + 分箱信息
        feature_meta = self.transformer.transform_with_meta(features)

        # 2️⃣ 提取 WOE 向量
        X_woe = self.transformer.to_woe_vector(feature_meta)

        # 3️⃣ 模型预测
        adapter = get_adapter(model, list(X_woe.keys()))
        proba = adapter.predict_proba(list(X_woe.values()))

        # 4️⃣ 分类结果
        prediction = 1 if proba >= self.threshold else 0

        result = {
            "prediction": prediction,
            "proba": round(float(proba), 6)
        }

        # ⭐ challenger 模式：不输出评分
        if is_challenger:
            return result

        # 5️⃣ 转分数
        score = self.scorer.score(proba)
        result["score"] = round(float(score), 2)

        # 6️⃣ 特征分解释
        if need_explain:
            explain = self.explainer.explain(adapter, feature_meta, self.scorer.factor)
            result["explain"] = explain

            # 7️⃣ 拒绝原因
            if need_reason and self.reason_engine:
                result["reason_codes"] = self.reason_engine.generate(explain)

        return result