# datamind/serving/fraud_service.py
"""反欺诈 BentoML 服务

提供反欺诈模型的 BentoML 服务封装。
"""

import bentoml
import time
from typing import Dict, Any

from datamind.serving.base import BaseBentoService
from datamind.core.ml.model import get_inference_engine
from datamind.core.common.exceptions import ModelNotFoundException, ModelInferenceException
from datamind.core.logging import log_audit, context, log_performance
from datamind.core.logging.debug import debug_print
from datamind.core.domain.enums import AuditAction
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.config import get_settings

settings = get_settings()


@bentoml.service(
    name="fraud_service",
    version=settings.app.version,
    description="反欺诈模型服务 - 返回欺诈概率和风险评分",
    resources={
        "cpu": getattr(settings.inference, 'resources_cpu', "1"),
        "memory": getattr(settings.inference, 'resources_memory', "2Gi")
    },
    traffic={
        "timeout": settings.inference.timeout,
        "concurrency": 100
    }
)
class FraudService:
    """反欺诈服务"""

    def __init__(self):
        self.base = BaseBentoService('fraud_detection', 'fraud_service')
        self._inference_engine = get_inference_engine()
        debug_print("FraudService", "初始化反欺诈服务")

    @bentoml.api(route="/predict")
    async def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        反欺诈预测

        请求格式:
            {
                "application_id": "APP_001",
                "features": {"amount": 10000, "ip_risk": 0.8},
                "model_id": "MDL_002",
                "ab_test_id": "ABT_002"
            }

        响应格式:
            {
                "probability": 0.12,
                "risk_score": 12.0,
                "risk_factors": [
                    {"factor": "high_amount", "value": 10000, "weight": 0.6}
                ],
                "model_id": "MDL_002",
                "model_version": "1.0.0",
                "application_id": "APP_001",
                "processing_time_ms": 8.5,
                "from_cache": false
            }
        """
        start_time = time.time()
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        # 获取请求参数
        application_id = request.get("application_id")
        features = request.get("features", {})
        model_id = request.get("model_id")
        ab_test_id = request.get("ab_test_id")

        # 验证必需参数
        if not application_id:
            raise ValueError("application_id is required")
        if not features:
            raise ValueError("features is required")

        # A/B 测试分流
        actual_model_id = model_id
        ab_test_info = None

        if ab_test_id and settings.ab_test.enabled:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=ab_test_id,
                    user_id=application_id,
                    ip_address=None
                )
                if assignment.get('in_test') and assignment.get('model_id'):
                    actual_model_id = assignment['model_id']
                    ab_test_info = {
                        'test_id': assignment['test_id'],
                        'group_name': assignment['group_name']
                    }
            except Exception as e:
                debug_print("FraudService", f"A/B测试错误: {e}")

        # 如果没有指定模型，使用生产模型
        if not actual_model_id:
            mid, _, _ = self.base.get_model()
            if mid:
                actual_model_id = mid
            else:
                raise ValueError("未指定模型ID且没有生产模型")

        try:
            # 执行预测
            result = self._inference_engine.predict_fraud(
                model_id=actual_model_id,
                features=features,
                application_id=application_id,
                user_id=None,
                ip_address=None,
                use_cache=True
            )

            processing_time_ms = (time.time() - start_time) * 1000

            # 构建响应
            response = {
                "probability": result['fraud_probability'],
                "risk_score": result['risk_score'],
                "risk_factors": result['risk_factors'],
                "model_id": result['model_id'],
                "model_version": result['model_version'],
                "application_id": application_id,
                "processing_time_ms": round(processing_time_ms, 2),
                "timestamp": result.get('timestamp'),
                "from_cache": result.get('from_cache', False),
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id
            }

            # 添加特征重要性
            if 'feature_importance' in result:
                response["feature_importance"] = result['feature_importance']

            # 添加A/B测试信息
            if ab_test_info:
                response["ab_test_info"] = ab_test_info

            # 审计日志
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                ip_address=None,
                details={
                    "application_id": application_id,
                    "model_id": result['model_id'],
                    "model_version": result['model_version'],
                    "fraud_probability": result['fraud_probability'],
                    "risk_score": result['risk_score'],
                    "processing_time_ms": round(processing_time_ms, 2),
                    "from_cache": result.get('from_cache', False),
                    "ab_test_id": ab_test_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            # 性能日志
            log_performance(
                operation=AuditAction.MODEL_INFERENCE.value,
                duration_ms=processing_time_ms,
                extra={
                    "model_id": result['model_id'],
                    "application_id": application_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                }
            )

            return response

        except ModelNotFoundException as e:
            processing_time_ms = (time.time() - start_time) * 1000
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                details={
                    "application_id": application_id,
                    "error": str(e),
                    "processing_time_ms": round(processing_time_ms, 2),
                    "trace_id": trace_id,
                    "span_id": span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

        except ModelInferenceException as e:
            processing_time_ms = (time.time() - start_time) * 1000
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                details={
                    "application_id": application_id,
                    "error": str(e),
                    "processing_time_ms": round(processing_time_ms, 2),
                    "trace_id": trace_id,
                    "span_id": span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                details={
                    "application_id": application_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "processing_time_ms": round(processing_time_ms, 2),
                    "trace_id": trace_id,
                    "span_id": span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    @bentoml.api(route="/health")
    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        return self.base.health_check()

    @bentoml.api(route="/models")
    async def list_models(self) -> Dict[str, Any]:
        """列出已加载的模型"""
        return {
            "service": "fraud_service",
            "models": self.base.get_loaded_models(),
            "total": len(self.base.get_loaded_models())
        }

    @bentoml.api(route="/models/reload")
    async def reload_model(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """重新加载模型"""
        model_id = request.get("model_id")
        if not model_id:
            return {"success": False, "message": "model_id is required"}
        return self.base.reload_model(model_id)