# datamind/serving/fraud_service.py

"""反欺诈 BentoML 服务

提供反欺诈模型的 BentoML 服务封装。

核心功能：
  - 单条预测：返回欺诈概率、风险评分和风险因子
  - 健康检查：检查服务状态和模型加载情况
  - 模型管理：列出已加载模型、重新加载模型

特性：
  - A/B测试支持：集成 A/B 测试分流
  - 生产模型自动选择：未指定模型时使用生产模型
  - 风险评分转换：将欺诈概率转换为 0-100 的风险评分
  - 风险因子提取：基于特征重要性提取主要风险因素
  - 完整审计：记录所有预测请求
  - 链路追踪：完整的 trace_id, span_id, parent_span_id
"""

import time
import json
import bentoml
import traceback
from typing import Dict, Any, List

from datamind.serving.base import BaseBentoService
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.config import get_settings

settings = get_settings()

logger = get_logger(__name__)


class ModelNotFoundException(Exception):
    """模型未找到异常"""
    pass


class ModelInferenceException(Exception):
    """模型推理异常"""
    pass


@bentoml.service(
    name="fraud_service",
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
class FraudService:
    """反欺诈服务"""

    def __init__(self):
        """初始化反欺诈服务"""
        debug = getattr(settings, 'debug', False)
        self.base = BaseBentoService('fraud_detection', 'fraud_service', debug=debug)
        self._debug_enabled = debug

        logger.info("反欺诈服务初始化完成")

    @staticmethod
    def _calculate_risk_score(probability: float) -> float:
        """
        将欺诈概率转换为风险评分（0-100）

        参数:
            probability: 欺诈概率 (0-1)

        返回:
            风险评分 (0-100)，分数越高风险越大
        """
        return min(100.0, max(0.0, probability * 100))

    @staticmethod
    def _get_risk_factors(
        features: Dict[str, Any],
        feature_importance: Dict[str, float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        获取主要风险因子

        参数:
            features: 原始特征字典
            feature_importance: 特征重要性字典
            top_k: 返回前 K 个风险因子

        返回:
            风险因子列表
        """
        if not feature_importance:
            return []

        # 按重要性排序
        sorted_features = sorted(
            feature_importance.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:top_k]

        risk_factors = []
        for feature_name, importance in sorted_features:
            risk_factors.append({
                "factor": feature_name,
                "value": features.get(feature_name),
                "weight": float(importance)
            })

        return risk_factors

    @bentoml.api
    async def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        反欺诈预测

        请求格式:
            {
                "application_id": "APP_001",
                "features": {"amount": 10000, "ip_risk": 0.8, ...},
                "model_id": "MDL_002",
                "ab_test_id": "ABT_002",
                "return_details": false
            }

        响应格式:
            {
                "code": 0,
                "message": "成功",
                "data": {
                    "probability": 0.12,
                    "risk_score": 12.0,
                    "risk_factors": [
                        {"factor": "amount", "value": 10000, "weight": 0.6}
                    ],
                    "model": {
                        "id": "MDL_002",
                        "version": "1.0.0",
                        "type": "xgboost",
                        "framework": "xgboost"
                    },
                    "trace": {
                        "request_id": "req-xxx",
                        "trace_id": "trace-xxx",
                        "span_id": "span-xxx",
                        "parent_span_id": "",
                        "latency_ms": 8.5
                    },
                    "feature_importance": {...}
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
            if self._debug_enabled:
                logger.debug("application_id 为空")
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "application_id 不能为空"}
            }
        if not features:
            if self._debug_enabled:
                logger.debug("features 为空")
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
                    if self._debug_enabled:
                        logger.debug("A/B测试分配: test=%s, group=%s, model=%s",
                                     ab_test_id, assignment['group_name'], actual_model_id)
            except Exception as e:
                logger.debug("A/B测试错误: %s", e)

        # 如果没有指定模型，使用生产模型
        if not actual_model_id:
            prod_model_id, _, _ = self.base.get_production_model()
            if prod_model_id:
                actual_model_id = prod_model_id
                if self._debug_enabled:
                    logger.debug("使用生产模型: %s", actual_model_id)
            else:
                logger.warning("未指定 model_id 且没有生产模型")
                return {
                    "code": 1003,
                    "message": "模型未加载",
                    "data": {"error": "未指定 model_id 且没有生产模型"}
                }

        try:
            # 获取模型引擎
            _, engine, model_version = self.base.get_model(actual_model_id)
            if engine is None:
                logger.warning("模型未加载: %s", actual_model_id)
                return {
                    "code": 1003,
                    "message": "模型未加载",
                    "data": {"error": f"模型 {actual_model_id} 未加载"}
                }

            # 获取模型元数据
            model_meta = self.base.get_model_metadata(actual_model_id) or {}
            model_type = model_meta.get('model_type', 'unknown')
            framework = model_meta.get('framework', 'unknown')

            # 执行预测（返回概率）
            result = engine.score(features, return_proba=True)
            fraud_probability = result.get('proba', 0.0)
            risk_score = self._calculate_risk_score(fraud_probability)

            latency_ms = (time.time() - start_time) * 1000

            if self._debug_enabled:
                logger.debug("预测完成: model=%s, proba=%.6f, risk_score=%.2f, latency=%.2fms",
                             actual_model_id, fraud_probability, risk_score, latency_ms)

            # 获取特征重要性（如果需要详细信息）
            feature_importance = {}
            if return_details:
                try:
                    feature_importance = engine.get_feature_importance()
                except Exception as e:
                    logger.debug("获取特征重要性失败: %s", e)

            # 获取风险因子
            risk_factors = self._get_risk_factors(features, feature_importance)

            # 构建响应数据
            response_data = {
                "probability": fraud_probability,
                "risk_score": risk_score,
                "risk_factors": risk_factors,
                "model": {
                    "id": actual_model_id,
                    "version": model_version,
                    "type": model_type,
                    "framework": framework
                },
                "trace": {
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id or "",
                    "latency_ms": round(latency_ms, 2)
                }
            }

            # 添加特征重要性（如果需要详细信息）
            if return_details and feature_importance:
                response_data["feature_importance"] = feature_importance

            # 添加 A/B 测试信息
            if ab_test_info:
                response_data["experiment"] = {
                    "test_id": ab_test_info['test_id'],
                    "group_name": ab_test_info['group_name'],
                    "in_test": True
                }

            # 构建最终响应
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
                    "model_id": actual_model_id,
                    "model_version": model_version,
                    "fraud_probability": fraud_probability,
                    "risk_score": risk_score,
                    "latency_ms": round(latency_ms, 2),
                    "ab_test_id": ab_test_id,
                    "return_details": return_details,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            # 性能日志
            log_performance(
                operation=AuditAction.MODEL_INFERENCE.value,
                duration_ms=latency_ms,
                extra={
                    "model_id": actual_model_id,
                    "application_id": application_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                }
            )

            return response

        except ModelNotFoundException as e:
            logger.warning("模型未找到: %s, %s", actual_model_id, e)
            return {
                "code": 1003,
                "message": "模型未找到",
                "data": {"error": str(e)}
            }

        except ModelInferenceException as e:
            logger.error("模型预测失败: %s, %s", actual_model_id, e)
            return {
                "code": 1005,
                "message": "模型预测失败",
                "data": {"error": str(e)}
            }

        except Exception as e:
            logger.error("预测失败: %s, error=%s", actual_model_id, e, exc_info=True)
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
        logger.debug("健康检查: status=%s", result.get("status"))
        return {
            "code": 0,
            "message": "成功" if result.get("status") == "healthy" else "服务降级",
            "data": result
        }

    @bentoml.api
    async def models(self) -> Dict[str, Any]:
        """列出已加载的模型"""
        models = self.base.get_loaded_models()
        logger.debug("列出模型: total=%d", len(models))
        return {
            "code": 0,
            "message": "成功",
            "data": {
                "service": "fraud_service",
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
        logger.info("手动重新加载模型: %s", model_id)
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
        """测试反欺诈服务"""
        service = FraudService()

        logger.info("等待模型加载...")
        await asyncio.sleep(3)

        loaded_models = service.base.get_loaded_models()
        logger.info("已加载模型: %s", loaded_models)

        if not loaded_models:
            logger.warning("没有已加载的模型，跳过测试")
            return

        def random_features():
            return {
                "amount": random.randint(1000, 500000),
                "ip_risk": round(random.uniform(0, 1), 2),
                "device_risk": round(random.uniform(0, 1), 2),
                "location_risk": round(random.uniform(0, 1), 2),
                "transaction_frequency": random.randint(1, 100),
                "time_since_last": random.randint(0, 3600)
            }

        test_cases = [
            {
                "application_id": f"TEST_{context.generate_request_id()}",
                "features": random_features(),
                "return_details": True
            }
        ]

        print("\n" + "=" * 60)
        print("开始测试反欺诈服务")
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

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)


    try:
        asyncio.run(run_test())
    finally:
        flush_bootstrap_logs()