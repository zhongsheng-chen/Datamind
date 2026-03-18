# Datamind/datamind/serving/scoring_service.py
import bentoml
from bentoml.io import JSON
from typing import Dict, Any, List
from datetime import datetime

from datamind.core import log_manager, get_request_id, debug_print
from datamind.serving.base import ScoringModelService

# 创建BentoML服务实例
scoring_service = ScoringModelService()


@bentoml.service(
    name="scoring-service",
    traffic={
        "timeout": 30,
        "concurrency": 10,
        "max_batch_size": 100
    },
    resources={
        "cpu": "1000m",
        "memory": "2Gi"
    }
)
class ScoringBentoService:
    """
    评分卡模型服务

    提供评分卡模型的在线预测服务
    """

    def __init__(self):
        self.service = scoring_service.bento_service()
        debug_print("ScoringBentoService", "评分卡Bento服务初始化完成")

    @bentoml.api(input=JSON(), output=JSON())
    async def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        评分卡预测

        Args:
            input_data: {
                "model_id": "模型ID",
                "application_id": "申请ID",
                "features": {
                    "age": 35,
                    "income": 50000,
                    ...
                },
                "ab_test_id": "可选AB测试ID"
            }
        """
        request_id = get_request_id()
        debug_print("ScoringBentoService", f"收到评分卡预测请求: {request_id}")

        result = await self.service.predict(input_data)

        # 记录服务层日志
        if result.get('success'):
            log_manager.log_audit(
                action="SCORING_SERVICE_PREDICT",
                user_id="system",
                ip_address="internal",
                resource_type="scoring",
                details={
                    "model_id": input_data.get('model_id'),
                    "application_id": input_data.get('application_id'),
                    "score": result.get('data', {}).get('total_score')
                },
                request_id=request_id
            )

        return result

    @bentoml.api(input=JSON(), output=JSON())
    async def batch_predict(self, inputs: List[Dict]) -> List[Dict]:
        """
        批量预测
        """
        request_id = get_request_id()
        debug_print("ScoringBentoService", f"收到批量预测请求: {len(inputs)} 条")

        results = []
        for i, input_data in enumerate(inputs):
            debug_print("ScoringBentoService", f"处理第 {i + 1} 条请求")
            try:
                result = await self.predict(input_data)
                results.append(result)
            except Exception as e:
                error_result = {
                    "success": False,
                    "error": str(e),
                    "request_id": request_id,
                    "index": i
                }
                results.append(error_result)

                log_manager.log_audit(
                    action="BATCH_PREDICT_ERROR",
                    user_id="system",
                    ip_address="internal",
                    details={
                        "index": i,
                        "error": str(e)
                    },
                    request_id=request_id
                )

        debug_print("ScoringBentoService",
                    f"批量预测完成: 成功 {sum(1 for r in results if r.get('success'))}/{len(results)}")
        return results

    @bentoml.api(input=JSON(), output=JSON())
    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy",
            "service": "scoring-service",
            "timestamp": datetime.now().isoformat(),
            "request_id": get_request_id()
        }


# 导出服务实例
service = ScoringBentoService()