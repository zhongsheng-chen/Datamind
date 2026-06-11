# datamind/runtime/serving/scoring_service.py

"""评分卡推理服务

负责将评分卡模型包装为 BentoML 推理服务。

核心功能：
  - create_scoring_service: 创建评分卡推理服务

使用示例：
    from datamind.runtime.loader import ModelLoader
    from datamind.runtime.serving.scoring_service import (
        create_scoring_service
    )

    loader = ModelLoader()

    model = loader.load(
        framework="sklearn",
        tag="scorecard:latest",
    )

    service = create_scoring_service(
        deployment_id="dep_xxx",
        model=model,
        config={
            "pdo": 50,
            "base_score": 600,
        }
    )
"""

from __future__ import annotations

from typing import Any

import bentoml
from pydantic import BaseModel


class ScoringRequest(BaseModel):
    """评分请求"""

    features: dict[str, Any]


class ScoringResponse(BaseModel):
    """评分响应"""

    score: float
    probability: float | None = None


def create_scoring_service(
    *,
    deployment_id: str,
    model: Any,
    config: dict[str, Any] | None = None,
):
    """创建评分卡推理服务

    参数：
        deployment_id: 部署 ID
        model: 已加载模型
        config: 推理配置

    返回：
        BentoML Service
    """

    config = config or {}

    @bentoml.service(
        name=f"scoring-{deployment_id}",
    )
    class ScoringService:
        """评分卡推理服务"""

        @bentoml.api
        def predict(
            self,
            request: ScoringRequest,
        ) -> ScoringResponse:
            """评分预测"""

            features = request.features

            probability = None
            score = None

            # 优先使用评分卡模型接口
            if hasattr(model, "predict_score"):
                score = float(
                    model.predict_score(features)
                )

            else:
                # sklearn 风格模型
                data = [list(features.values())]

                if hasattr(model, "predict_proba"):
                    probability = float(
                        model.predict_proba(data)[0][1]
                    )

                if hasattr(model, "predict"):
                    prediction = model.predict(data)

                    if probability is None:
                        probability = float(prediction[0])

                # 暂时简单返回概率作为 score
                score = float(probability or 0)

            return ScoringResponse(
                score=score,
                probability=probability,
            )

        @bentoml.api
        def health(self) -> dict[str, str]:
            """健康检查"""

            return {
                "deployment_id": deployment_id,
                "status": "healthy",
            }

    return ScoringService
