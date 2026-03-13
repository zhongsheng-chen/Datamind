# api/fraud_detection_api.py
import bentoml
from bentoml.io import JSON
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import time
import logging


class FraudRequest(BaseModel):
    """反欺诈请求"""
    request_id: str
    model_id: str
    model_version: Optional[str] = "latest"
    experiment_id: Optional[str] = None
    features: Dict[str, Any]


class FraudResponse(BaseModel):
    """反欺诈响应 - 只返回模型结果"""
    request_id: str
    model_id: str
    model_version: str
    task_type: str = "fraud_detection"
    fraud_score: float
    model_scores: Dict[str, float]  # 各子模型分数（如果是集成模型）
    processing_time_ms: float
    experiment_info: Optional[Dict] = None


@bentoml.service(
    name="datamind-fraud",
    traffic={"timeout": 10, "max_concurrency": 200},
    resources={"cpu": "2", "memory": "2Gi"}
)
class FraudService:
    """反欺诈服务 - 只返回欺诈分数"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.model_repo = ModelRepository()
        self.model_loader = ModelLoader()
        self.inference_engine = InferenceEngine()
        self.ab_test = ABTestManager(redis_client)

    @bentoml.api(
        route="/v1/fraud/predict",
        input=JSON(pydantic_model=FraudRequest),
        output=JSON()
    )
    async def predict(self, request: FraudRequest) -> Dict:
        """反欺诈预测接口"""
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
                task_type="fraud_detection",
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
            response = FraudResponse(
                request_id=request.request_id,
                model_id=model_info['model_id'],
                model_version=model_info['version'],
                fraud_score=result['fraud_score'],
                model_scores=result.get('model_scores', {}),
                processing_time_ms=processing_time,
                experiment_info=experiment_info
            )

            # 6. 记录AB测试结果
            if experiment_info:
                self.ab_test.record_result(
                    experiment_id=experiment_info['experiment_id'],
                    variant=experiment_info['variant'],
                    request_id=request.request_id,
                    score=result['fraud_score']
                )

            return response.dict()

        except Exception as e:
            self.logger.error(f"反欺诈预测失败: {e}")
            raise bentoml.exceptions.BentoMLException(f"反欺诈预测失败: {str(e)}")