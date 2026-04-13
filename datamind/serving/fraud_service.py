# datamind/serving/fraud_service.py

"""反欺诈 BentoML 服务

提供反欺诈模型的 BentoML 服务封装。

核心功能：
  - 单条预测：返回欺诈概率、风险评分和风险因子
  - 健康检查：检查服务状态和模型加载情况
  - 模型管理：列出已加载模型、重新加载模型

特性：
  - A/B测试支持：集成 A/B 测试分流
  - 风险评分转换：将欺诈概率转换为 0-100 的风险评分
  - 风险因子提取：基于特征重要性提取主要风险因素
  - 完整审计：记录所有预测请求
  - 链路追踪：完整的 span 追踪
"""

import time
import bentoml
import traceback
from typing import Dict, Any, List

from datamind.serving.base import BaseBentoService
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction, PerformanceOperation
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.config import get_settings

settings = get_settings()

_logger = get_logger(__name__)


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
        self.base = BaseBentoService('fraud_detection', 'fraud_service')
        _logger.info("反欺诈服务初始化完成")

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
            _logger.debug("请求参数缺失: application_id 为空")
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "application_id 不能为空"}
            }

        if not features:
            _logger.debug("请求参数缺失: features 为空")
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "features 不能为空"}
            }

        # 验证 model_id 必须存在
        if not model_id:
            _logger.warning("请求缺少 model_id: 申请ID=%s", application_id)
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "model_id 不能为空"}
            }

        # A/B 测试分流（内评系统传入 ab_test_id 时，可能覆盖 model_id）
        actual_model_id = model_id
        ab_test_info = None

        if ab_test_id and settings.ab_test.enabled:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=ab_test_id,
                    user_id=application_id,
                    ip_address=None
                )
                _logger.debug("A/B测试分配结果: %s", assignment)

                if assignment.get('in_test') and assignment.get('model_id'):
                    actual_model_id = assignment['model_id']
                    ab_test_info = {
                        'test_id': assignment['test_id'],
                        'group_name': assignment['group_name']
                    }
                    _logger.info("A/B测试分流: 申请ID=%s, 测试ID=%s, 分组=%s, 模型ID=%s",
                                 application_id, ab_test_id, assignment['group_name'], actual_model_id)
                else:
                    _logger.debug("用户不在测试中或没有模型ID: %s", assignment)
            except Exception as e:
                _logger.warning("A/B测试分配失败: 测试ID=%s, 申请ID=%s, 错误=%s",
                                ab_test_id, application_id, e)

        try:
            # 获取模型引擎
            _, engine, model_version = self.base.get_model(actual_model_id)
            if engine is None:
                _logger.warning("模型未加载: 申请ID=%s, 模型ID=%s", application_id, actual_model_id)
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

            _logger.info("反欺诈预测完成: 申请ID=%s, 模型ID=%s, 版本=%s, 欺诈概率=%.6f, 风险评分=%.2f, 耗时=%.2fms",
                         application_id, actual_model_id, model_version,
                         fraud_probability, risk_score, latency_ms)

            # 获取特征重要性（如果需要详细信息）
            feature_importance = {}
            if return_details:
                try:
                    feature_importance = engine.get_feature_importance()
                    _logger.debug("获取特征重要性成功: 申请ID=%s, 特征数量=%d",
                                  application_id, len(feature_importance))
                except Exception as e:
                    _logger.debug("获取特征重要性失败: 申请ID=%s, 错误=%s", application_id, e)

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
                operation=PerformanceOperation.MODEL_INFERENCE,
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
            _logger.warning("模型未找到: 申请ID=%s, 模型ID=%s, 错误=%s",
                            application_id, actual_model_id, e)
            return {
                "code": 1003,
                "message": "模型未找到",
                "data": {"error": str(e)}
            }

        except ModelInferenceException as e:
            _logger.error("模型预测失败: 申请ID=%s, 模型ID=%s, 错误=%s",
                          application_id, actual_model_id, e)
            return {
                "code": 1005,
                "message": "模型预测失败",
                "data": {"error": str(e)}
            }

        except Exception as e:
            _logger.error("预测异常: 申请ID=%s, 模型ID=%s, 错误=%s",
                          application_id, actual_model_id, e, exc_info=True)
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
        status = result.get("status")
        if status == "healthy":
            _logger.debug("健康检查: 状态=健康")
        else:
            _logger.warning("健康检查: 状态=%s, 问题=%s", status, result.get("issues", []))
        return {
            "code": 0,
            "message": "成功" if status == "healthy" else "服务降级",
            "data": result
        }

    @bentoml.api
    async def models(self) -> Dict[str, Any]:
        """列出已加载的模型"""
        models = self.base.get_loaded_models()
        _logger.info("列出已加载模型: 服务=%s, 模型数量=%d", "fraud_service", len(models))
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
            _logger.debug("重新加载模型请求缺少model_id参数")
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "model_id 不能为空"}
            }
        _logger.info("手动重新加载模型: 模型ID=%s", model_id)
        result = self.base.reload_model(model_id)
        if result.get("success"):
            _logger.info("模型重新加载成功: 模型ID=%s, 版本=%s", model_id, result.get("version"))
        else:
            _logger.error("模型重新加载失败: 模型ID=%s, 错误=%s", model_id, result.get("message"))
        return {
            "code": 0 if result.get("success") else 1001,
            "message": "成功" if result.get("success") else "失败",
            "data": result
        }