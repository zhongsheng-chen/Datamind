# datamind/serving/scoring_service.py
"""评分卡 BentoML 服务

提供评分卡模型的 BentoML 服务封装。
"""

import bentoml
import time
from typing import Dict, Any

from datamind.serving.base import BaseBentoService
from datamind.core.ml.inference import inference_engine
from datamind.core.ml.exceptions import ModelNotFoundException, ModelInferenceException
from datamind.core.logging import log_audit, context, log_performance
from datamind.core.logging.debug import debug_print
from datamind.core.domain.enums import AuditAction
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.config import get_settings

settings = get_settings()


@bentoml.service(
    name="scoring_service",
    version=settings.app.version,
    description="评分卡模型服务 - 返回信用评分和特征贡献分",
    resources={
        "cpu": getattr(settings.inference, 'resources_cpu', "1"),
        "memory": getattr(settings.inference, 'resources_memory', "2Gi")
    },
    traffic={
        "timeout": settings.inference.timeout,
        "concurrency": 100
    }
)
class ScoringService:
    """评分卡服务"""

    def __init__(self):
        self.base = BaseBentoService('scoring', 'scoring_service')
        debug_print("ScoringService", "初始化评分卡服务")

    @bentoml.api
    async def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        评分卡预测

        请求格式:
            {
                "application_id": "APP_001",
                "features": {"age": 35, "income": 50000},
                "model_id": "MDL_001",
                "ab_test_id": "ABT_001",
                "return_details": false
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
        return_details = request.get("return_details", False)

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
                debug_print("ScoringService", f"A/B测试错误: {e}")

        # 如果没有指定模型，使用生产模型
        if not actual_model_id:
            mid, _, _ = self.base.get_model()
            if mid:
                actual_model_id = mid
            else:
                raise ValueError("未指定模型ID且没有生产模型")

        try:
            # 执行预测
            result = inference_engine.predict_scorecard(
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
                "score": result['total_score'],
                "probability": result['default_probability'],
                "feature_contributions": result['feature_scores'],
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

            # 添加详细特征信息
            if return_details:
                response["feature_details"] = [
                    {
                        "name": name,
                        "value": features.get(name),
                        "score": score
                    }
                    for name, score in result['feature_scores'].items()
                    if name in features
                ]

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
                    "total_score": result['total_score'],
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

    @bentoml.api
    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        return self.base.health_check()

    @bentoml.api
    async def models(self) -> Dict[str, Any]:
        """列出已加载的模型"""
        return {
            "service": "scoring_service",
            "models": self.base.get_loaded_models(),
            "total": len(self.base.get_loaded_models())
        }

    @bentoml.api
    async def reload_model(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """重新加载模型"""
        model_id = request.get("model_id")
        if not model_id:
            return {"success": False, "message": "model_id is required"}
        return self.base.reload_model(model_id)