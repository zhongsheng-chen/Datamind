# datamind/serving/fraud_service.py
import bentoml
from bentoml.io import JSON
from typing import Dict, Any, List
from datetime import datetime

from datamind.core import log_manager, get_request_id, debug_print
from datamind.serving.base import FraudModelService

# 创建BentoML服务实例
fraud_service = FraudModelService()


@bentoml.service(
    name="fraud-service",
    traffic={
        "timeout": 30,
        "concurrency": 10,
        "max_batch_size": 50
    },
    resources={
        "cpu": "1000m",
        "memory": "2Gi"
    }
)
class FraudBentoService:
    """
    反欺诈模型服务

    提供反欺诈模型的在线预测服务
    """

    def __init__(self):
        self.service = fraud_service.bento_service()
        debug_print("FraudBentoService", "反欺诈Bento服务初始化完成")

    @bentoml.api(input=JSON(), output=JSON())
    async def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        反欺诈预测

        Args:
            input_data: {
                "model_id": "模型ID",
                "application_id": "申请ID",
                "features": {
                    "ip_address": "192.168.1.1",
                    "device_id": "device123",
                    "amount": 10000,
                    ...
                },
                "ab_test_id": "可选AB测试ID"
            }
        """
        request_id = get_request_id()
        debug_print("FraudBentoService", f"收到反欺诈预测请求: {request_id}")

        result = await self.service.predict(input_data)

        # 记录服务层日志
        if result.get('success'):
            log_manager.log_audit(
                action="FRAUD_SERVICE_PREDICT",
                user_id="system",
                ip_address="internal",
                resource_type="fraud",
                details={
                    "model_id": input_data.get('model_id'),
                    "application_id": input_data.get('application_id'),
                    "fraud_probability": result.get('data', {}).get('fraud_probability'),
                    "risk_level": result.get('data', {}).get('risk_level')
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
        debug_print("FraudBentoService", f"收到批量预测请求: {len(inputs)} 条")

        results = []
        for i, input_data in enumerate(inputs):
            debug_print("FraudBentoService", f"处理第 {i + 1} 条请求")
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

        debug_print("FraudBentoService",
                    f"批量预测完成: 成功 {sum(1 for r in results if r.get('success'))}/{len(results)}")
        return results

    @bentoml.api(input=JSON(), output=JSON())
    async def explain(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        预测解释（特征重要性）

        返回每个特征对预测结果的贡献
        """
        request_id = get_request_id()
        debug_print("FraudBentoService", f"收到解释请求: {request_id}")

        try:
            # 获取模型
            model_id = input_data.get('model_id')
            if not model_id:
                raise ValueError("缺少 model_id")

            # 执行预测
            result = await self.predict(input_data)

            if not result.get('success'):
                return result

            # 获取特征重要性（如果有）
            model_info = fraud_service.model_metadata.get(model_id, {})
            feature_importance = model_info.get('feature_importance', {})

            # 计算特征贡献
            features = input_data.get('features', {})
            contributions = []

            for feature, value in features.items():
                importance = feature_importance.get(feature, 0)
                contribution = {
                    'feature': feature,
                    'value': value,
                    'importance': importance,
                    'impact': importance * (float(value) if isinstance(value, (int, float)) else 0)
                }
                contributions.append(contribution)

            # 按影响排序
            contributions.sort(key=lambda x: abs(x['impact']), reverse=True)

            result['explanation'] = {
                'contributions': contributions[:10],  # 返回前10个
                'feature_importance': feature_importance
            }

            log_manager.log_audit(
                action="FRAUD_SERVICE_EXPLAIN",
                user_id="system",
                ip_address="internal",
                resource_type="fraud",
                resource_id=model_id,
                details={
                    "application_id": input_data.get('application_id'),
                    "feature_count": len(contributions)
                },
                request_id=request_id
            )

            debug_print("FraudBentoService", f"解释完成: 分析了 {len(contributions)} 个特征")

            return result

        except Exception as e:
            debug_print("FraudBentoService", f"解释失败: {str(e)}")

            log_manager.log_audit(
                action="FRAUD_SERVICE_EXPLAIN_ERROR",
                user_id="system",
                ip_address="internal",
                details={
                    "error": str(e)
                },
                reason=str(e),
                request_id=request_id
            )

            return {
                "success": False,
                "error": str(e),
                "request_id": request_id
            }

    @bentoml.api(input=JSON(), output=JSON())
    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "status": "healthy",
            "service": "fraud-service",
            "timestamp": datetime.now().isoformat(),
            "request_id": get_request_id()
        }


# 导出服务实例
service = FraudBentoService()