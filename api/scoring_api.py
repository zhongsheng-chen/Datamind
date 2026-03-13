# api/scoring_api.py
import bentoml
from bentoml.io import JSON
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import time
import logging


class ScoringRequest(BaseModel):
    """评分请求"""
    request_id: str
    model_id: str
    model_version: Optional[str] = "latest"
    experiment_id: Optional[str] = None
    features: Dict[str, Any]


class ScoringResponse(BaseModel):
    """评分响应 - 只返回模型结果"""
    request_id: str
    model_id: str
    model_version: str
    task_type: str = "scoring"
    total_score: float
    feature_scores: Dict[str, float]
    processing_time_ms: float
    experiment_info: Optional[Dict] = None


@bentoml.service(
    name="datamind-scoring",
    traffic={"timeout": 10, "max_concurrency": 200},
    resources={"cpu": "2", "memory": "2Gi"}
)
class ScoringService:
    """评分服务 - 只返回模型评分"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.model_repo = ModelRepository()
        self.model_loader = ModelLoader()
        self.inference_engine = InferenceEngine()
        self.ab_test = ABTestManager(redis_client)  # redis_client需要注入

    @bentoml.api(
        route="/v1/scoring/predict",
        input=JSON(pydantic_model=ScoringRequest),
        output=JSON()
    )
    async def predict(self, request: ScoringRequest) -> Dict:
        """评分预测接口"""
        start_time = time.time()

        try:
            # 1. 确定模型版本（AB测试）
            model_version = request.model_version
            experiment_info = None

            if request.experiment_id:
                variant = self.ab_test.get_variant(
                    request.experiment_id,
                    request.request_id
                )
                if variant:
                    model_version = variant['version']
                    experiment_info = {
                        "experiment_id": request.experiment_id,
                        "variant": variant['variant']
                    }

            # 2. 获取模型信息
            model_info = self.model_repo.get_model_info(
                task_type="scoring",
                model_id=request.model_id,
                version=model_version
            )

            # 3. 加载模型
            model = self.model_loader.load_model(model_info)

            # 4. 执行推理
            result = self.inference_engine.predict(
                model=model,
                model_info=model_info,
                features=request.features
            )

            # 5. 构建响应
            processing_time = (time.time() - start_time) * 1000
            response = ScoringResponse(
                request_id=request.request_id,
                model_id=model_info['model_id'],
                model_version=model_info['version'],
                total_score=result['total_score'],
                feature_scores=result.get('feature_scores', {}),
                processing_time_ms=processing_time,
                experiment_info=experiment_info
            )

            # 6. 记录AB测试结果
            if experiment_info:
                self.ab_test.record_result(
                    experiment_id=experiment_info['experiment_id'],
                    variant=experiment_info['variant'],
                    request_id=request.request_id,
                    score=result['total_score']
                )

            return response.dict()

        except Exception as e:
            self.logger.error(f"评分失败: {e}")
            raise bentoml.exceptions.BentoMLException(f"评分失败: {str(e)}")