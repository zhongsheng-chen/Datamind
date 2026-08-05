# datamind/runtime/serving/scoring_service.py

"""评分模型运行服务

提供评分模型的在线推理、评分和特征贡献分解能力。

核心功能：
  - ScoringService: 评分模型运行服务
  - predict: 单条评分
  - predict_batch: 批量评分

使用示例：
  from datamind.runtime.serving import ScoringService

  service = ScoringService(
      runtime_model=runtime_model,
  )

  result = service.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })

  batch_result = service.predict_batch([
      {
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      },
      {
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      },
  ])
"""

from typing import Any

from datamind.config.scorecard import ScorecardConfig
from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.core.scoring import (
    LRContrib,
    Scorer,
    ScoreTransformer,
)
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService


class ScoringService(BaseRuntimeService):
    """评分模型运行服务

    基于模型概率和 Logit 输出生成评分结果。

    对 Logistic Regression 模型提供特征贡献分解能力。

    属性：
        SERVICE_TYPE: 服务类型
        transformer: 评分转换器
        scorer: 评分器
        contrib: 特征贡献分解器
    """

    SERVICE_TYPE = "scoring"

    def __init__(
            self,
            *,
            runtime_model: RuntimeModel,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            scorecard_config: ScorecardConfig | dict[str, Any] | None = None,
    ):
        """初始化评分模型服务

        参数：
            runtime_model: 已加载运行时模型
            feature_names: 特征名称列表
            data_types: 特征类型映射
            scorecard_config: 评分配置

        异常：
            NotImplementedError:
                模型不支持概率预测或 Logit 输出
        """
        super().__init__(
            runtime_model=runtime_model,
            feature_names=feature_names,
            data_types=data_types,
        )

        self.require_capability(
            ModelCapability.PREDICT_PROBA
        )

        self.require_capability(
            ModelCapability.PREDICT_LOG_ODDS
        )

        config = self._resolve_scorecard_config(
            scorecard_config
        )

        self.transformer = ScoreTransformer(
            config=config,
        )

        self.scorer = Scorer(
            inference=self.inference,
            transformer=self.transformer,
        )

        self.contrib: LRContrib | None = None

        model_type = str(
            self.metadata.get(
                "model_type",
                ""
            )
        ).strip().lower()

        if model_type == "logistic_regression":
            self.contrib = LRContrib(
                inference=self.inference,
                transformer=self.transformer,
            )

    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """单条评分

        参数：
            features: 特征字典

        返回：
            评分结果，包含：
              - probability
              - logit
              - score
              - score_detail
              - deployment_id
              - model_id
              - version_id
              - framework
              - service_type

        异常：
            ValueError: features 为空
            TypeError: 推理结果类型异常
        """
        if not features:
            raise ValueError(
                "features 不能为空"
            )

        probability = self.inference.predict(
            features
        )

        logit = self.inference.predict_logit(
            features
        )

        if isinstance(probability, list):
            raise TypeError(
                "单条评分返回了批量概率结果"
            )

        if isinstance(logit, list):
            raise TypeError(
                "单条评分返回了批量 Logit 结果"
            )

        probability_value = float(
            probability
        )

        logit_value = float(
            logit
        )

        score = self.scorer.logit_to_score(
            logit_value
        )

        score_detail = None

        if self.contrib is not None:
            explanation = self.contrib.explain(
                features
            )

            score_detail = self._build_score_detail(
                explanation
            )

        self.touch()

        return self.build_result({
            "probability": probability_value,
            "logit": logit_value,
            "score": float(score),
            "score_detail": score_detail,
        })

    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量评分

        参数：
            features_list: 特征字典列表

        返回：
            批量评分结果，包含：
              - count
              - predictions
              - deployment_id
              - model_id
              - version_id
              - framework
              - service_type

        异常：
            TypeError: 批量推理结果类型异常
            RuntimeError:
                概率、Logit 或贡献分解结果数量不一致
            NotImplementedError:
                模型不支持批量推理
        """
        self.require_capability(
            ModelCapability.BATCH_PREDICT
        )

        if not features_list:
            return self.build_result({
                "count": 0,
                "predictions": [],
            })

        probabilities = self.inference.predict(
            features_list
        )

        logits = self.inference.predict_logit(
            features_list
        )

        if not isinstance(
                probabilities,
                list,
        ):
            raise TypeError(
                "批量评分未返回概率列表"
            )

        if not isinstance(
                logits,
                list,
        ):
            raise TypeError(
                "批量评分未返回 Logit 列表"
            )

        if len(probabilities) != len(logits):
            raise RuntimeError(
                "概率预测结果数量与 Logit 结果数量不一致"
            )

        score_details: list[
            dict[str, Any] | None
            ]

        if self.contrib is not None:
            explanations = self.contrib.explain_batch(
                features_list
            )

            if len(explanations) != len(probabilities):
                raise RuntimeError(
                    "特征贡献分解结果数量与预测结果数量不一致"
                )

            score_details = [
                self._build_score_detail(
                    explanation
                )
                for explanation in explanations
            ]

        else:
            score_details = [
                None
                for _ in probabilities
            ]

        predictions = []

        for probability, logit, score_detail in zip(
                probabilities,
                logits,
                score_details,
        ):
            probability_value = float(
                probability
            )

            logit_value = float(
                logit
            )

            score = self.scorer.logit_to_score(
                logit_value
            )

            predictions.append({
                "probability": probability_value,
                "logit": logit_value,
                "score": float(score),
                "score_detail": score_detail,
            })

        self.touch()

        return self.build_result({
            "count": len(predictions),
            "predictions": predictions,
        })

    @staticmethod
    def _build_score_detail(
            explanation: dict[str, float],
    ) -> dict[str, Any]:
        """构造评分明细

        参数：
            explanation: LR 特征贡献分解结果

        返回：
            评分明细，包含：
              - intercept_score
              - feature_score
              - raw_score
              - feature_scores
        """
        summary_fields = {
            "intercept_score",
            "feature_score",
            "raw_score",
        }

        feature_scores = {
            name: float(value)
            for name, value in explanation.items()
            if name not in summary_fields
        }

        return {
            "intercept_score": float(
                explanation["intercept_score"]
            ),
            "feature_score": float(
                explanation["feature_score"]
            ),
            "raw_score": float(
                explanation["raw_score"]
            ),
            "feature_scores": feature_scores,
        }

    def _resolve_scorecard_config(
            self,
            config: ScorecardConfig | dict[str, Any] | None,
    ) -> ScorecardConfig:
        """解析评分配置

        优先级：
          - 显式传入 scorecard_config
          - RuntimeModel metadata 中的 config
          - ScorecardConfig 默认配置

        参数：
            config: 显式评分配置

        返回：
            ScorecardConfig 实例
        """
        if isinstance(
                config,
                ScorecardConfig,
        ):
            return config

        if isinstance(
                config,
                dict,
        ):
            return ScorecardConfig(
                **config
            )

        runtime_config = self.metadata.get(
            "config"
        )

        if isinstance(
                runtime_config,
                dict,
        ):
            return ScorecardConfig(
                **runtime_config
            )

        return ScorecardConfig()
