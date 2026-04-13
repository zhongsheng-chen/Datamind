# datamind/serving/scoring_service.py

"""评分卡 BentoML 服务

提供评分卡模型的 BentoML 服务封装。

核心功能：
  - 单条评分预测：返回信用评分、违约概率和特征贡献
  - 健康检查：检查服务状态和模型加载情况
  - 模型管理：列出已加载模型、重新加载模型

特性：
  - A/B测试支持：集成 A/B 测试分流（主模型和陪跑模型）
  - 多解释体系：统一接口支持 scorecard、shap、unsupported 三种解释类型
  - 特征贡献转换：使用 ContributionConverter 确保评分贡献转换一致性
  - 完整审计：记录所有预测请求
  - 链路追踪：完整的 span 追踪
"""

import time
import uuid
import bentoml
import traceback
from datetime import datetime
from typing import Dict, Any

from datamind.serving.base import BaseBentoService
from datamind.core.scoring.engine import ScoringEngine
from datamind.core.scoring.contrib import ContributionConverter
from datamind.core.logging import log_performance, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction, PerformanceOperation, TaskType
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.core.db.database import get_db
from datamind.core.db.models.monitoring import ApiCallLog, ModelPerformanceMetrics
from datamind.core.db.models import AuditLog
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
        """初始化评分卡服务"""
        self.base = BaseBentoService('scoring', 'scoring_service')
        _logger.info("评分卡服务初始化完成")

    @staticmethod
    def _get_score_mapping(engine: ScoringEngine) -> Dict[str, Any]:
        """
        获取评分映射配置（用于审计）

        参数:
            engine: 评分引擎实例

        返回:
            评分映射配置字典
        """
        return {
            "type": "pdo",
            "pdo": engine.score_converter.pdo,
            "base_score": engine.score_converter.base_score,
            "base_odds": engine.score_converter.base_odds,
            "min_score": engine.score_converter.min_score,
            "max_score": engine.score_converter.max_score
        }

    @staticmethod
    def _make_explain(
        explain_result: Dict[str, Any],
        score: float,
        engine: ScoringEngine
    ) -> Dict[str, Any]:
        """
        构建特征贡献响应

        使用 ContributionConverter 将 logit 空间的贡献转换为评分空间，
        确保与 Score 模块的转换逻辑完全一致。

        参数:
            explain_result: engine.explain() 返回的结果
            score: 预测的信用评分（用于验证）
            engine: 评分引擎实例（用于获取评分参数）

        返回:
            统一格式的 explain 响应
        """
        explain_type = explain_result.get('explain_type', 'unknown')

        if explain_type == 'scorecard':
            converter = ContributionConverter(engine.score_converter)

            factor = converter.get_factor()
            offset = converter.get_offset()

            log_odds_contrib = explain_result.get("log_odds_contributions", {})
            intercept_log_odds = explain_result.get("intercept_log_odds", 0.0)
            total_log_odds = explain_result.get("total_log_odds", 0.0)

            score_contrib = converter.logit_to_score(log_odds_contrib)
            intercept_score = -factor * intercept_log_odds
            total_score = engine.score_converter.from_logit(total_log_odds)

            score_params = {
                "factor": factor,
                "offset": offset,
                "pdo": engine.score_converter.pdo,
                "base_score": engine.score_converter.base_score,
                "base_odds": engine.score_converter.base_odds
            }

            original_score_contrib = explain_result.get("score_contributions", {})
            has_original = bool(original_score_contrib)

            return {
                "type": "scorecard",
                "contribution_unit": "score",
                "score_params": score_params,
                "details": {
                    "log_odds": log_odds_contrib,
                    "score": score_contrib,
                    "intercept_log_odds": intercept_log_odds,
                    "intercept_score": intercept_score,
                    "total_log_odds": total_log_odds,
                    "total_score": total_score,
                    "validation": {
                        "score_from_explain": total_score,
                        "score_match": abs(total_score - score) < 0.01,
                        "converter_used": True,
                        "has_original_score_contrib": has_original
                    }
                }
            }

        elif explain_type == 'blackbox':
            shap_values = explain_result.get("shap_values", {})
            base_value = explain_result.get("base_value", 0)
            expected_value = explain_result.get("expected_value", 0)

            predicted_value = base_value + sum(shap_values.values())
            if 0 <= predicted_value <= 1:
                output_space = "probability"
            else:
                output_space = "log_odds"

            return {
                "type": "shap",
                "contribution_unit": output_space,
                "details": {
                    "shap_values": shap_values,
                    "base_value": base_value,
                    "expected_value": expected_value,
                    "prediction_output": predicted_value,
                    "output_space": output_space,
                    "validation": {
                        "shap_sum": sum(shap_values.values()),
                        "base_plus_sum": predicted_value,
                        "output_space": output_space
                    }
                }
            }

        else:
            return {
                "type": "unsupported",
                "reason": explain_result.get("reason", "model_not_supported"),
                "message": explain_result.get("message", "当前模型不支持特征贡献解释")
            }

    @staticmethod
    def _write_api_log(
        request_id: str,
        application_id: str,
        model_id: str,
        model_version: str,
        endpoint: str,
        processing_time_ms: int,
        status_code: int,
        score: float = None,
        probability: float = None,
        error_message: str = None
    ) -> None:
        """写入 API 调用日志到数据库"""
        try:
            with get_db() as session:
                api_log = ApiCallLog(
                    request_id=request_id,
                    application_id=application_id,
                    model_id=model_id,
                    model_version=model_version,
                    endpoint=endpoint,
                    processing_time_ms=processing_time_ms,
                    status_code=status_code,
                    task_type=TaskType.SCORING.value,
                    error_message=error_message,
                    business_metrics={
                        "score": score,
                        "probability": probability
                    } if score else None
                )
                session.add(api_log)
                session.commit()
                _logger.debug("API调用日志已写入: %s", request_id)
        except Exception as e:
            _logger.error("写入API调用日志失败: %s", e)

    @staticmethod
    def _write_audit_log(
        action: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        details: Dict[str, Any],
        success: bool,
        reason: str = None
    ) -> None:
        """写入审计日志到数据库"""
        try:
            with get_db() as session:
                audit = AuditLog(
                    audit_id=f"AUD_{uuid.uuid4().hex[:12]}",
                    event_type="api_call",
                    action=action,
                    operator=user_id,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=details,
                    result="success" if success else "failure",
                    reason=reason
                )
                session.add(audit)
                session.commit()
                _logger.debug("审计日志已写入: %s", action)
        except Exception as e:
            _logger.error("写入审计日志失败: %s", e)

    @staticmethod
    def _update_performance_metrics(
        model_id: str,
        model_version: str,
        success: bool,
        processing_time_ms: int,
        score: float = None,
        probability: float = None
    ) -> None:
        """更新模型性能指标（日聚合）

        参数:
            model_id: 模型ID
            model_version: 模型版本
            success: 是否成功
            processing_time_ms: 处理耗时（毫秒）
            score: 评分（可选）
            probability: 违约概率（可选）
        """
        try:
            # 获取当天零点时间
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            with get_db() as session:
                record = session.query(ModelPerformanceMetrics).filter(
                    ModelPerformanceMetrics.model_id == model_id,
                    ModelPerformanceMetrics.model_version == model_version,
                    ModelPerformanceMetrics.date == today
                ).first()

                if not record:
                    record = ModelPerformanceMetrics.create(
                        model_id=model_id,
                        model_version=model_version,
                        task_type=TaskType.SCORING.value,
                        date=today
                    )
                    session.add(record)
                    session.flush()

                record.total_requests += 1
                if success:
                    record.success_count += 1
                else:
                    record.error_count += 1

                current_total = record.total_requests
                if record.avg_response_time_ms is not None:
                    record.avg_response_time_ms = (
                        (record.avg_response_time_ms * (current_total - 1) + processing_time_ms) / current_total
                    )
                else:
                    record.avg_response_time_ms = processing_time_ms

                if record.min_response_time_ms is None or processing_time_ms < record.min_response_time_ms:
                    record.min_response_time_ms = processing_time_ms
                if record.max_response_time_ms is None or processing_time_ms > record.max_response_time_ms:
                    record.max_response_time_ms = processing_time_ms

                if record.p95_response_time_ms is None or processing_time_ms > record.p95_response_time_ms:
                    record.p95_response_time_ms = processing_time_ms

                if score is not None:
                    if record.avg_score is not None:
                        record.avg_score = (record.avg_score * (current_total - 1) + score) / current_total
                    else:
                        record.avg_score = score

                    if record.score_distribution:
                        bin_key = f"{int(score // 50) * 50}-{int(score // 50) * 50 + 50}"
                        if bin_key in record.score_distribution:
                            record.score_distribution[bin_key] += 1
                        else:
                            record.score_distribution[bin_key] = 1
                    else:
                        record.score_distribution = {f"{int(score // 50) * 50}-{int(score // 50) * 50 + 50}": 1}

                if probability is not None:
                    if record.fraud_rate is not None:
                        record.fraud_rate = (record.fraud_rate * (current_total - 1) + probability) / current_total
                    else:
                        record.fraud_rate = probability

                session.commit()
                _logger.debug("性能指标已更新: model=%s v%s, total=%d, avg=%.2fms",
                              model_id, model_version, record.total_requests, record.avg_response_time_ms)

        except Exception as e:
            _logger.error("更新性能指标失败: model=%s, error=%s", model_id, e)

    @bentoml.api
    async def predict(self, request: dict) -> dict:
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
                "message": "成功",
                "data": {
                    "score": 685.42,
                    "probability": 0.023,
                    "model": {
                        "id": "MDL_001",
                        "version": "1.0.0",
                        "type": "logistic_regression",
                        "framework": "sklearn",
                        "score_mapping": {...}
                    },
                    "experiment": {
                        "test_id": "ABT_001",
                        "group_name": "challenger",
                        "is_challenger": true,
                        "champion_model_id": "MDL_001",
                        "challenger_model_id": "MDL_002",
                        "in_test": true
                    },
                    "trace": {
                        "request_id": "req-xxx",
                        "trace_id": "trace-xxx",
                        "span_id": "span-xxx",
                        "parent_span_id": "",
                        "latency_ms": 12.5
                    },
                    "explain": {...}
                }
            }
        """
        start_time = time.time()

        request_id = context.generate_request_id()
        trace_id = context.generate_trace_id()
        span_id = context.generate_span_id()

        context.set_request_id(request_id)
        context.set_trace_id(trace_id)
        context.set_span_id(span_id)
        parent_span_id = context.get_parent_span_id()

        application_id = request.get("application_id")
        features = request.get("features", {})
        model_id = request.get("model_id")
        ab_test_id = request.get("ab_test_id")
        return_details = request.get("return_details", False)

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

        if not model_id:
            _logger.warning("请求缺少 model_id: 申请ID=%s", application_id)
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "model_id 不能为空"}
            }

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

                if assignment.get('in_test'):
                    challenger_model_id = assignment.get('model_id')
                    if challenger_model_id:
                        actual_model_id = challenger_model_id
                        ab_test_info = {
                            'test_id': assignment['test_id'],
                            'group_name': assignment['group_name'],
                            'is_challenger': True,
                            'champion_model_id': model_id,
                            'challenger_model_id': challenger_model_id
                        }
                        _logger.info("A/B测试分流: 申请ID=%s, 测试ID=%s, 分组=%s, 陪跑模型=%s, 主模型=%s",
                                     application_id, ab_test_id, assignment['group_name'],
                                     challenger_model_id, model_id)
                    else:
                        ab_test_info = {
                            'test_id': assignment['test_id'],
                            'group_name': assignment['group_name'],
                            'is_challenger': False,
                            'champion_model_id': model_id,
                            'reason': 'no_challenger_model'
                        }
                        _logger.warning("用户进入测试组但没有陪跑模型: 申请ID=%s, 测试ID=%s, 分组=%s",
                                        application_id, ab_test_id, assignment['group_name'])
                else:
                    ab_test_info = {
                        'test_id': assignment['test_id'],
                        'group_name': 'default',
                        'is_challenger': False,
                        'champion_model_id': model_id
                    }
                    _logger.debug("用户不在测试组，使用主模型: 申请ID=%s, 模型ID=%s",
                                  application_id, model_id)
            except Exception as e:
                _logger.warning("A/B测试分配失败: 测试ID=%s, 申请ID=%s, 错误=%s",
                                ab_test_id, application_id, e)

        try:
            _, engine, model_version = self.base.get_model(actual_model_id)
            if engine is None:
                _logger.warning("模型未加载: 申请ID=%s, 模型ID=%s", application_id, actual_model_id)

                latency_ms = int((time.time() - start_time) * 1000)

                self._write_api_log(
                    request_id=request_id,
                    application_id=application_id,
                    model_id=actual_model_id,
                    model_version="unknown",
                    endpoint="/predict",
                    processing_time_ms=latency_ms,
                    status_code=1003,
                    error_message=f"模型 {actual_model_id} 未加载"
                )

                self._update_performance_metrics(
                    model_id=actual_model_id,
                    model_version="unknown",
                    success=False,
                    processing_time_ms=latency_ms
                )

                return {
                    "code": 1003,
                    "message": "模型未加载",
                    "data": {"error": f"模型 {actual_model_id} 未加载"}
                }

            model_meta = self.base.get_model_metadata(actual_model_id) or {}
            model_type = model_meta.get('model_type', 'unknown')
            framework = model_meta.get('framework', 'unknown')

            result = engine.score(features, return_proba=True)

            latency_ms = (time.time() - start_time) * 1000
            score = result.get('score')
            probability = result.get('proba')

            _logger.info("评分预测完成: 申请ID=%s, 模型ID=%s, 版本=%s, 评分=%.2f, 概率=%.6f, 耗时=%.2fms",
                         application_id, actual_model_id, model_version, score, probability, latency_ms)

            response_data = {
                "score": score,
                "probability": probability,
                "model": {
                    "id": actual_model_id,
                    "version": model_version,
                    "type": model_type,
                    "framework": framework,
                    "score_mapping": self._get_score_mapping(engine)
                },
                "trace": {
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id or "",
                    "latency_ms": round(latency_ms, 2)
                }
            }

            if ab_test_info:
                response_data["experiment"] = {
                    "test_id": ab_test_info['test_id'],
                    "group_name": ab_test_info['group_name'],
                    "is_challenger": ab_test_info['is_challenger'],
                    "champion_model_id": ab_test_info.get('champion_model_id'),
                    "in_test": ab_test_info['is_challenger']
                }
                if ab_test_info.get('challenger_model_id'):
                    response_data["experiment"]["challenger_model_id"] = ab_test_info['challenger_model_id']
                if ab_test_info.get('reason'):
                    response_data["experiment"]["reason"] = ab_test_info['reason']

            if return_details:
                try:
                    explain_result = engine.explain(features, return_score_scale=True)
                    response_data["explain"] = self._make_explain(
                        explain_result,
                        score,
                        engine
                    )
                    _logger.debug("特征贡献解释完成: 申请ID=%s, 解释类型=%s",
                                  application_id, explain_result.get('explain_type', 'unknown'))
                except Exception as e:
                    _logger.warning("获取特征贡献失败: 申请ID=%s, 错误=%s", application_id, e)
                    response_data["explain"] = {
                        "type": "unsupported",
                        "reason": "explain_failed",
                        "message": f"特征贡献解释失败: {str(e)}"
                    }

            self._write_api_log(
                request_id=request_id,
                application_id=application_id,
                model_id=actual_model_id,
                model_version=model_version,
                endpoint="/predict",
                processing_time_ms=int(latency_ms),
                status_code=0,
                score=score,
                probability=probability
            )

            self._write_audit_log(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                resource_type="model",
                resource_id=actual_model_id,
                details={
                    "application_id": application_id,
                    "champion_model_id": model_id,
                    "model_version": model_version,
                    "score": score,
                    "probability": probability,
                    "latency_ms": round(latency_ms, 2),
                    "ab_test_id": ab_test_id,
                    "is_challenger": ab_test_info.get('is_challenger') if ab_test_info else False,
                    "return_details": return_details
                },
                success=True
            )

            self._update_performance_metrics(
                model_id=actual_model_id,
                model_version=model_version,
                success=True,
                processing_time_ms=int(latency_ms),
                score=score,
                probability=probability
            )

            log_performance(
                operation=PerformanceOperation.MODEL_INFERENCE,
                duration_ms=latency_ms,
                extra={
                    "model_id": actual_model_id,
                    "application_id": application_id,
                    "request_id": request_id
                }
            )

            return {
                "code": 0,
                "message": "成功",
                "data": response_data
            }

        except ModelNotFoundException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            _logger.warning("模型未找到: 申请ID=%s, 模型ID=%s, 错误=%s",
                            application_id, actual_model_id, e)

            self._write_api_log(
                request_id=request_id,
                application_id=application_id,
                model_id=actual_model_id,
                model_version="unknown",
                endpoint="/predict",
                processing_time_ms=latency_ms,
                status_code=1003,
                error_message=str(e)
            )

            self._update_performance_metrics(
                model_id=actual_model_id,
                model_version="unknown",
                success=False,
                processing_time_ms=latency_ms
            )

            return {
                "code": 1003,
                "message": "模型未找到",
                "data": {"error": str(e)}
            }

        except ModelInferenceException as e:
            latency_ms = int((time.time() - start_time) * 1000)
            _logger.error("模型预测失败: 申请ID=%s, 模型ID=%s, 错误=%s",
                          application_id, actual_model_id, e)

            self._write_api_log(
                request_id=request_id,
                application_id=application_id,
                model_id=actual_model_id,
                model_version="unknown",
                endpoint="/predict",
                processing_time_ms=latency_ms,
                status_code=1005,
                error_message=str(e)
            )

            self._update_performance_metrics(
                model_id=actual_model_id,
                model_version="unknown",
                success=False,
                processing_time_ms=latency_ms
            )

            return {
                "code": 1005,
                "message": "模型预测失败",
                "data": {"error": str(e)}
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            _logger.error("预测异常: 申请ID=%s, 模型ID=%s, 错误=%s",
                          application_id, actual_model_id, e, exc_info=True)

            self._write_api_log(
                request_id=request_id,
                application_id=application_id,
                model_id=actual_model_id,
                model_version="unknown",
                endpoint="/predict",
                processing_time_ms=latency_ms,
                status_code=1001,
                error_message=str(e)
            )

            self._write_audit_log(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                resource_type="model",
                resource_id=actual_model_id,
                details={
                    "application_id": application_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                },
                success=False,
                reason=str(e)
            )

            self._update_performance_metrics(
                model_id=actual_model_id,
                model_version="unknown",
                success=False,
                processing_time_ms=latency_ms
            )

            return {
                "code": 1001,
                "message": "系统错误",
                "data": {"error": f"预测失败: {str(e)}"}
            }

    @bentoml.api
    async def health(self) -> dict:
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
    async def models(self) -> dict:
        """列出已加载的模型"""
        models = self.base.get_loaded_models()
        _logger.info("列出已加载模型: 服务=%s, 模型数量=%d", "scoring_service", len(models))
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
    async def reload_model(self, request: dict) -> dict:
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