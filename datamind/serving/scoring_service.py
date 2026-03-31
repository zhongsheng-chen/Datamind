# datamind/serving/scoring_service.py

"""评分卡 BentoML 服务

提供评分卡模型的 BentoML 服务封装。
"""

import time
import json
import bentoml
import traceback
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
    name="scoring_service",
    traffic={
        "timeout": settings.inference.timeout,
        "concurrency": 100
    },
    resources={
        "cpu": getattr(settings.inference, 'resources_cpu', "1"),
        "memory": getattr(settings.inference, 'resources_memory', "2Gi")
    },
    workers=1,
    threads=4,
)
class ScoringService:
    """评分卡服务"""

    def __init__(self):
        self.base = BaseBentoService('scoring', 'scoring_service')
        self._inference_engine = get_inference_engine()
        debug_print("ScoringService", "初始化评分卡服务")

    @bentoml.api
    async def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        评分卡预测

        请求格式:
            {
                "application_id": "APP_001",
                "features": {"age": 35, "income": 50000, ...},
                "model_id": "MDL_001",
                "ab_test_id": "ABT_001",
                "return_details": false
            }

        响应格式:
            {
                "code": 0,
                "message": "SUCCESS",
                "data": {
                    "score": 685.42,
                    "probability": 0.023,
                    "feature_contributions": {"age": 85.2, "income": 120.5},
                    "model_id": "MDL_001",
                    "model_version": "1.0.0",
                    "application_id": "APP_001",
                    "processing_time_ms": 12.5,
                    "request_id": "req-xxx",
                    "trace_id": "trace-xxx",
                    "span_id": "span-xxx"
                }
            }
        """
        start_time = time.time()

        # 生成追踪 ID
        request_id = context.generate_request_id()
        trace_id = context.generate_trace_id()
        span_id = context.generate_span_id()

        context.set_request_id(request_id)
        context.set_trace_id(trace_id)
        context.set_span_id(span_id)
        parent_span_id = context.get_parent_span_id()

        # 获取请求参数
        application_id = request.get("application_id")
        features = request.get("features", {})
        model_id = request.get("model_id")
        ab_test_id = request.get("ab_test_id")
        return_details = request.get("return_details", False)

        # 验证必需参数
        if not application_id:
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "application_id 不能为空"}
            }
        if not features:
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "features 不能为空"}
            }

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
            prod_model_id, prod_model, prod_version = self.base.get_production_model()
            if prod_model_id:
                actual_model_id = prod_model_id
            else:
                return {
                    "code": 1003,
                    "message": "模型未加载",
                    "data": {"error": "未指定 model_id 且没有生产模型"}
                }

        try:
            # 执行预测
            result = self._inference_engine.predict_scorecard(
                model_id=actual_model_id,
                features=features,
                application_id=application_id,
                user_id=None,
                ip_address=None,
                use_cache=True,
                explain=return_details
            )

            processing_time_ms = (time.time() - start_time) * 1000

            # 构建响应数据
            response_data = {
                "score": result['total_score'],
                "probability": result['default_probability'],
                "feature_contributions": result.get('feature_scores', {}),
                "model_id": result['model_id'],
                "model_version": result['model_version'],
                "application_id": application_id,
                "processing_time_ms": round(processing_time_ms, 2),
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id
            }

            if ab_test_info:
                response_data["ab_test_info"] = ab_test_info
            if result.get('warning'):
                response_data["warning"] = result['warning']

            response = {
                "code": 0,
                "message": "成功",
                "data": response_data
            }

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
                    "return_details": return_details,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            log_performance(
                operation=AuditAction.MODEL_INFERENCE.value,
                duration_ms=processing_time_ms,
                extra={
                    "model_id": result['model_id'],
                    "application_id": application_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                }
            )

            return response

        except ModelNotFoundException as e:
            return {
                "code": 1003,
                "message": "模型未找到",
                "data": {"error": str(e)}
            }

        except ModelInferenceException as e:
            return {
                "code": 1005,
                "message": "模型预测失败",
                "data": {"error": str(e)}
            }

        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                details={
                    "application_id": application_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                },
                reason=str(e),
                request_id=request_id
            )
            return {
                "code": 1001,
                "message": "系统错误",
                "data": {"error": f"预测失败: {str(e)}"}
            }

    @bentoml.api
    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        result = self.base.health_check()
        return {
            "code": 0,
            "message": "成功" if result.get("status") == "healthy" else "服务降级",
            "data": result
        }

    @bentoml.api
    async def models(self) -> Dict[str, Any]:
        """列出已加载的模型"""
        models = self.base.get_loaded_models()
        return {
            "code": 0,
            "message": "成功",
            "data": {
                "service": "scoring_service",
                "models": models,
                "total": len(models)
            }
        }

    @bentoml.api
    async def reload_model(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """重新加载模型"""
        model_id = request.get("model_id")
        if not model_id:
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "model_id 不能为空"}
            }
        result = self.base.reload_model(model_id)
        return {
            "code": 0 if result.get("success") else 1001,
            "message": "成功" if result.get("success") else "失败",
            "data": result
        }


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import asyncio
    import random

    from datamind.core.logging.bootstrap import install_bootstrap_logger, flush_bootstrap_logs

    install_bootstrap_logger()


    async def run_test():
        """测试评分卡服务"""
        service = ScoringService()

        # 等待模型加载
        debug_print("Test", "等待模型加载...")
        await asyncio.sleep(3)

        # 检查是否有模型
        loaded_models = service.base.get_loaded_models()
        debug_print("Test", f"已加载模型: {loaded_models}")

        if not loaded_models:
            debug_print("Test", "没有已加载的模型，跳过测试")
            return

        # 随机生成测试数据
        def random_features():
            return {
                "age": random.randint(18, 65),
                "income": random.randint(30000, 150000),
                "debt_ratio": round(random.uniform(0, 0.8), 2),
                "credit_history": random.randint(300, 850),
                "employment_years": random.randint(0, 40),
                "loan_amount": random.randint(10000, 500000)
            }

        # 测试数据
        test_cases = [
            {
                "application_id": f"TEST_{context.generate_request_id()}",
                "features": random_features(),
                "return_details": True
            },
            {
                "application_id": f"TEST_{context.generate_request_id()}",
                "features": random_features(),
                "return_details": True
            }
        ]

        print("\n" + "=" * 60)
        print("开始测试评分卡服务")
        print("=" * 60)

        for i, test_case in enumerate(test_cases):
            print(f"\n测试用例 {i + 1}:")
            print(f"  application_id: {test_case['application_id']}")
            print(f"  features: {json.dumps(test_case['features'], indent=4)}")
            print(f"  return_details: {test_case['return_details']}")

            try:
                response = await service.predict(test_case)
                print(f"\n响应:")
                print(json.dumps(response, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"\n错误: {e}")
                traceback.print_exc()

        # 健康检查
        print("\n" + "-" * 60)
        print("健康检查:")
        health = await service.health()
        print(json.dumps(health, ensure_ascii=False, indent=2))

        # 列出模型
        print("\n" + "-" * 60)
        print("列出已加载模型:")
        models_list = await service.models()
        print(json.dumps(models_list, ensure_ascii=False, indent=2))

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)


    try:
        asyncio.run(run_test())
    finally:
        flush_bootstrap_logs()