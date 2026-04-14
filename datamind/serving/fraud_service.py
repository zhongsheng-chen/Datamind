# datamind/serving/fraud_service.py

"""反欺诈 BentoML 服务

提供反欺诈模型的 BentoML 服务封装。

核心功能：
  - 单条预测：返回欺诈概率、风险评分和风险因子
  - 健康检查：检查服务状态和模型加载情况
  - 模型管理：列出已加载模型、重新加载模型
  - 异步写入：非阻塞数据库写入
  - 启动预热：服务启动时自动加载生产模型
  - 内存监控：监控已加载模型的内存占用

特性：
  - A/B测试支持：集成 A/B 测试分流（使用 customer_id 保证永久一致性）
  - 风险评分转换：将欺诈概率转换为 0-100 的风险评分
  - 风险因子提取：基于特征重要性提取主要风险因素
  - 完整审计：记录所有预测请求
  - 链路追踪：完整的 span 追踪
"""

import time
import uuid
import asyncio
import psutil
import bentoml
import traceback
from datetime import datetime
from typing import Dict, Any, List
from dataclasses import dataclass

from datamind.serving.base import BaseBentoService
from datamind.core.logging import log_performance, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction, PerformanceOperation, TaskType
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.core.db import get_async_writer, close_async_writer, get_sync_writer
from datamind.core.db.models import AuditLog
from datamind.core.db.models.monitoring import ApiCallLog, ModelPerformanceMetrics
from datamind.core.model import get_model_registry, get_model_loader
from datamind.config import get_settings

settings = get_settings()

_logger = get_logger(__name__)


@dataclass
class ModelMemoryInfo:
    """模型内存信息"""
    model_id: str
    model_name: str
    model_version: str
    memory_mb: float
    loaded_at: str


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
        self._async_writer = None
        self._sync_writer = get_sync_writer()
        self._warmed_up = False
        self._model_memory_stats: Dict[str, ModelMemoryInfo] = {}
        _logger.info("反欺诈服务初始化完成")

    @bentoml.on_startup
    async def _init_async_writer(self):
        """启动时初始化异步写入器"""
        self._async_writer = await get_async_writer()
        _logger.debug("异步写入器已初始化")

    @bentoml.on_shutdown
    async def _close_async_writer(self):
        """关闭时清理异步写入器"""
        await close_async_writer()
        _logger.debug("异步写入器已关闭")

    @bentoml.on_startup
    async def warm_up(self):
        """启动时加载并预热生产模型"""
        start_time = time.time()

        try:
            registry = get_model_registry()
            loader = get_model_loader()

            production_models: List[Dict[str, Any]] = registry.get_production_models(include_details=True)

            if not production_models:
                _logger.warning("未找到生产模型")
                return

            _logger.debug("发现 %d 个生产模型", len(production_models))

            process = psutil.Process()
            initial_memory = process.memory_info().rss / 1024 / 1024

            loaded_count = 0
            failed_count = 0

            for model_info in production_models:
                model_id = model_info.get('model_id')
                model_name = model_info.get('model_name')
                model_version = model_info.get('model_version')

                _logger.debug("加载模型: %s v%s", model_name, model_version)

                load_start = time.time()

                success = self.base.load_model(model_id)

                load_time = (time.time() - load_start) * 1000

                if success:
                    warm_up_success = loader.warm_up_model(model_id)

                    current_memory = process.memory_info().rss / 1024 / 1024
                    model_memory = current_memory - initial_memory

                    self._model_memory_stats[model_id] = ModelMemoryInfo(
                        model_id=model_id,
                        model_name=model_name,
                        model_version=model_version,
                        memory_mb=round(model_memory, 2),
                        loaded_at=datetime.now().isoformat()
                    )

                    _logger.info(
                        "模型加载成功: %s v%s (%s), 加载耗时=%.2fms, 预热=%s, 内存增量=%.2fMB",
                        model_name, model_version, model_id, load_time,
                        "成功" if warm_up_success else "失败",
                        model_memory
                    )
                    loaded_count += 1
                else:
                    _logger.error("模型加载失败: %s v%s", model_name, model_version)
                    failed_count += 1

                initial_memory = process.memory_info().rss / 1024 / 1024

            final_memory = process.memory_info().rss / 1024 / 1024

            _logger.info(
                "模型预热完成: 成功=%d, 失败=%d, 总耗时=%.2fms, 总内存=%.2fMB",
                loaded_count, failed_count, (time.time() - start_time) * 1000, final_memory
            )

            self._warmed_up = True

        except Exception as e:
            _logger.error("模型预热失败: %s", e, exc_info=True)

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取模型内存统计信息"""
        process = psutil.Process()
        total_memory = process.memory_info().rss / 1024 / 1024

        models_memory = [
            {
                "model_id": info.model_id,
                "model_name": info.model_name,
                "model_version": info.model_version,
                "memory_mb": info.memory_mb,
                "loaded_at": info.loaded_at
            }
            for info in self._model_memory_stats.values()
        ]

        return {
            "total_memory_mb": round(total_memory, 2),
            "models_count": len(self._model_memory_stats),
            "models": models_memory
        }

    @staticmethod
    def _calculate_risk_score(probability: float) -> float:
        """将欺诈概率转换为风险评分（0-100）"""
        return min(100.0, max(0.0, probability * 100))

    @staticmethod
    def _get_risk_factors(
        features: Dict[str, Any],
        feature_importance: Dict[str, float],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """获取主要风险因子"""
        if not feature_importance:
            return []

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

    async def _write_api_log_async(
            self,
            request_id: str,
            application_id: str,
            model_id: str,
            model_version: str,
            endpoint: str,
            processing_time_ms: int,
            status_code: int,
            probability: float = None,
            risk_score: float = None,
            error_message: str = None
    ) -> None:
        """异步写入 API 调用日志"""
        if self._async_writer:
            await self._async_writer.write(
                ApiCallLog,
                request_id=request_id,
                application_id=application_id,
                model_id=model_id,
                model_version=model_version,
                endpoint=endpoint,
                processing_time_ms=processing_time_ms,
                status_code=status_code,
                task_type="fraud_detection",
                error_message=error_message,
                business_metrics={
                    "probability": probability,
                    "risk_score": risk_score
                } if probability else None
            )
        else:
            self._sync_writer.write(
                ApiCallLog,
                request_id=request_id,
                application_id=application_id,
                model_id=model_id,
                model_version=model_version,
                endpoint=endpoint,
                processing_time_ms=processing_time_ms,
                status_code=status_code,
                task_type="fraud_detection",
                error_message=error_message,
                business_metrics={
                    "probability": probability,
                    "risk_score": risk_score
                } if probability else None
            )

    async def _write_audit_log_async(
            self,
            action: str,
            user_id: str,
            resource_type: str,
            resource_id: str,
            details: Dict[str, Any],
            success: bool,
            reason: str = None
    ) -> None:
        """异步写入审计日志"""
        if self._async_writer:
            await self._async_writer.write(
                AuditLog,
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
        else:
            self._sync_writer.write(
                AuditLog,
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

    @staticmethod
    async def _update_performance_metrics_async(
            model_id: str,
            model_version: str,
            success: bool,
            processing_time_ms: int,
            probability: float = None
    ) -> None:
        """异步更新性能指标"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        from datamind.core.db.database import get_db
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
                    task_type=TaskType.FRAUD_DETECTION,
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

            if probability is not None:
                if record.fraud_rate is not None:
                    record.fraud_rate = (record.fraud_rate * (current_total - 1) + probability) / current_total
                else:
                    record.fraud_rate = probability

                if probability > 0.5:
                    record.fraud_count = (record.fraud_count or 0) + 1

            session.commit()

    @staticmethod
    def _error_response(
            code: int,
            message: str,
            request_id: str,
            trace_id: str,
            span_id: str,
            parent_span_id: str,
            latency_ms: float = 0
    ) -> dict:
        """构建错误响应"""
        return {
            "code": code,
            "message": message,
            "data": None,
            "trace": {
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id or "-",
                "latency_ms": round(latency_ms, 2)
            }
        }

    async def _do_predict(
            self,
            application_id: str,
            customer_id: str,
            features: Dict[str, Any],
            champion_model_id: str,
            ab_test_id: str,
            return_details: bool
    ) -> Dict[str, Any]:
        """执行预测的核心逻辑"""
        actual_model_id = champion_model_id
        ab_test_info = None
        ab_user_id = customer_id or application_id

        if ab_test_id and settings.ab_test.enabled:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=ab_test_id,
                    customer_id=ab_user_id,
                    ip_address=None,
                    return_details=return_details
                )
                _logger.debug("A/B测试分配结果: %s", assignment)

                if assignment.get('in_test') and assignment.get('model_id'):
                    actual_model_id = assignment['model_id']
                    ab_test_info = {
                        'test_id': assignment['test_id'],
                        'group_name': assignment['group_name'],
                        'is_challenger': True,
                        'champion_model_id': champion_model_id,
                        'challenger_model_id': assignment['model_id'],
                        'in_test': True
                    }
                    _logger.info("A/B测试分流: 申请ID=%s, 客户ID=%s, 测试ID=%s, 分组=%s, 陪跑模型=%s, 主模型=%s",
                                 application_id, ab_user_id, ab_test_id, assignment['group_name'],
                                 assignment['model_id'], champion_model_id)
                else:
                    ab_test_info = {
                        'test_id': ab_test_id,
                        'group_name': 'default',
                        'is_challenger': False,
                        'champion_model_id': champion_model_id,
                        'in_test': False
                    }
                    _logger.debug("用户不在测试组，使用主模型: 申请ID=%s, 客户ID=%s, 模型ID=%s",
                                  application_id, ab_user_id, champion_model_id)
            except Exception as e:
                _logger.warning("A/B测试分配失败: 测试ID=%s, 申请ID=%s, 错误=%s",
                                ab_test_id, application_id, e)

        _, engine, model_version = self.base.get_model(actual_model_id)
        if engine is None:
            raise ModelNotFoundException(f"模型 {actual_model_id} 未加载")

        model_meta = self.base.get_model_metadata(actual_model_id) or {}
        model_type = model_meta.get('model_type', 'unknown')
        framework = model_meta.get('framework', 'unknown')

        result = engine.score(features, return_proba=True)
        fraud_probability = result.get('proba', 0.0)
        risk_score = self._calculate_risk_score(fraud_probability)

        feature_importance = {}
        if return_details:
            try:
                feature_importance = engine.get_feature_importance()
            except Exception as e:
                _logger.debug("获取特征重要性失败: %s", e)

        risk_factors = self._get_risk_factors(features, feature_importance)

        return {
            "actual_model_id": actual_model_id,
            "model_version": model_version,
            "model_type": model_type,
            "framework": framework,
            "fraud_probability": fraud_probability,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "feature_importance": feature_importance,
            "ab_test_info": ab_test_info
        }

    @bentoml.api
    async def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        反欺诈预测

        请求格式:
            {
                "application_id": "APP_001",
                "customer_id": "CUST_001",
                "features": {"amount": 10000, "ip_risk": 0.8, ...},
                "model_id": "MDL_002",
                "ab_test_id": "ABT_002",
                "return_details": false
            }

        响应格式 (return_details=false):
            {
                "code": 0,
                "message": "success",
                "data": {
                    "probability": 0.12,
                    "risk_score": 12.0,
                    "model_id": "MDL_002",
                    "model_version": "1.0.0",
                    "model_type": "xgboost",
                    "framework": "xgboost",
                    "ab_test_id": "ABT_002",
                    "ab_test_group": "challenger"
                },
                "trace": {
                    "request_id": "req-xxx",
                    "trace_id": "trace-xxx",
                    "span_id": "span-xxx",
                    "parent_span_id": "-",
                    "latency_ms": 8.5
                }
            }
        """
        start_time = time.time()

        request_id = context.generate_request_id()
        trace_id = context.generate_trace_id()
        span_id = context.generate_span_id()
        parent_span_id = context.get_parent_span_id() or "-"

        context.set_request_id(request_id)
        context.set_trace_id(trace_id)
        context.set_span_id(span_id)

        application_id = request.get("application_id")
        customer_id = request.get("customer_id")
        features = request.get("features", {})
        champion_model_id = request.get("model_id")
        ab_test_id = request.get("ab_test_id")
        return_details = request.get("return_details", False)

        if not application_id:
            _logger.debug("请求参数缺失: application_id 为空")
            return self._error_response(1006, "application_id is required",
                                        request_id, trace_id, span_id, parent_span_id)

        if not features:
            _logger.debug("请求参数缺失: features 为空")
            return self._error_response(1006, "features is required",
                                        request_id, trace_id, span_id, parent_span_id)

        if not champion_model_id:
            _logger.warning("请求缺少 model_id: 申请ID=%s", application_id)
            return self._error_response(1006, "model_id is required",
                                        request_id, trace_id, span_id, parent_span_id)

        try:
            result = await asyncio.wait_for(
                self._do_predict(
                    application_id=application_id,
                    customer_id=customer_id,
                    features=features,
                    champion_model_id=champion_model_id,
                    ab_test_id=ab_test_id,
                    return_details=return_details
                ),
                timeout=settings.inference.timeout
            )

            latency_ms = (time.time() - start_time) * 1000
            fraud_probability = result.get('fraud_probability')
            risk_score = result.get('risk_score')

            _logger.info("反欺诈预测完成: 申请ID=%s, 模型ID=%s, 版本=%s, 欺诈概率=%.6f, 风险评分=%.2f, 耗时=%.2fms",
                         application_id, result["actual_model_id"], result["model_version"],
                         fraud_probability, risk_score, latency_ms)

            response_data = {
                "probability": fraud_probability,
                "risk_score": risk_score,
                "model_id": result["actual_model_id"],
                "model_version": result["model_version"],
                "model_type": result["model_type"],
                "framework": result["framework"]
            }

            ab_test_info = result.get("ab_test_info")
            if ab_test_info and ab_test_info.get('in_test'):
                response_data["ab_test_id"] = ab_test_info['test_id']
                response_data["ab_test_group"] = ab_test_info['group_name']

            trace_data: Dict[str, Any] = {
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id,
                "latency_ms": round(latency_ms, 2)
            }

            if return_details:
                response_data["risk_factors"] = result.get("risk_factors", [])
                if result.get("feature_importance"):
                    response_data["feature_importance"] = result.get("feature_importance")

                if ab_test_info and ab_test_info.get('in_test') and ab_test_info.get('is_challenger'):
                    trace_data["ab_test"] = {
                        "id": ab_test_info['test_id'],
                        "group": ab_test_info['group_name'],
                        "key": "customer_id",
                        "champion_model_id": ab_test_info.get('champion_model_id'),
                        "challenger_model_id": ab_test_info.get('challenger_model_id')
                    }

            await self._write_api_log_async(
                request_id=request_id,
                application_id=application_id,
                model_id=result["actual_model_id"],
                model_version=result["model_version"],
                endpoint="/predict",
                processing_time_ms=int(latency_ms),
                status_code=0,
                probability=fraud_probability,
                risk_score=risk_score
            )

            await self._write_audit_log_async(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                resource_type="model",
                resource_id=result["actual_model_id"],
                details={
                    "application_id": application_id,
                    "customer_id": customer_id or application_id,
                    "champion_model_id": champion_model_id,
                    "model_version": result["model_version"],
                    "fraud_probability": fraud_probability,
                    "risk_score": risk_score,
                    "latency_ms": round(latency_ms, 2),
                    "ab_test_id": ab_test_id,
                    "is_challenger": ab_test_info.get('is_challenger') if ab_test_info else False,
                    "return_details": return_details
                },
                success=True
            )

            await self._update_performance_metrics_async(
                model_id=result["actual_model_id"],
                model_version=result["model_version"],
                success=True,
                processing_time_ms=int(latency_ms),
                probability=fraud_probability
            )

            log_performance(
                operation=PerformanceOperation.MODEL_INFERENCE,
                duration_ms=latency_ms,
                extra={
                    "model_id": result["actual_model_id"],
                    "application_id": application_id,
                    "request_id": request_id
                }
            )

            return {
                "code": 0,
                "message": "success",
                "data": response_data,
                "trace": trace_data
            }

        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            _logger.error("预测超时: 申请ID=%s, 模型ID=%s, 耗时=%.2fms",
                          application_id, champion_model_id, latency_ms)
            return self._error_response(1008, "Prediction timeout",
                                        request_id, trace_id, span_id, parent_span_id, latency_ms)

        except ModelNotFoundException as e:
            latency_ms = (time.time() - start_time) * 1000
            _logger.warning("模型未找到: 申请ID=%s, 模型ID=%s, 错误=%s",
                            application_id, champion_model_id, e)
            return self._error_response(1003, str(e),
                                        request_id, trace_id, span_id, parent_span_id, latency_ms)

        except ModelInferenceException as e:
            latency_ms = (time.time() - start_time) * 1000
            _logger.error("模型预测失败: 申请ID=%s, 模型ID=%s, 错误=%s",
                          application_id, champion_model_id, e)
            return self._error_response(1005, str(e),
                                        request_id, trace_id, span_id, parent_span_id, latency_ms)

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            _logger.error("预测异常: 申请ID=%s, 模型ID=%s, 错误=%s",
                          application_id, champion_model_id, e, exc_info=True)

            await self._write_audit_log_async(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                resource_type="model",
                resource_id=champion_model_id,
                details={
                    "application_id": application_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                },
                success=False,
                reason=str(e)
            )

            await self._update_performance_metrics_async(
                model_id=champion_model_id,
                model_version="unknown",
                success=False,
                processing_time_ms=int(latency_ms)
            )

            return self._error_response(1001, f"Prediction failed: {str(e)}",
                                        request_id, trace_id, span_id, parent_span_id, latency_ms)

    @bentoml.api
    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        result = self.base.health_check()
        status = result.get("status")

        memory_stats = self.get_memory_stats()

        result["warmed_up"] = self._warmed_up
        result["memory_stats"] = memory_stats
        result["async_writer_running"] = self._async_writer is not None

        if status == "healthy":
            _logger.debug("健康检查: 状态=健康, 预热=%s, 模型数=%d, 内存=%.2fMB",
                         self._warmed_up, result.get("loaded_models", 0),
                         memory_stats.get("total_memory_mb", 0))
        else:
            _logger.warning("健康检查: 状态=%s", status)

        return {
            "code": 0,
            "message": "success" if status == "healthy" else "service degraded",
            "data": result
        }

    @bentoml.api
    async def models(self) -> Dict[str, Any]:
        """列出已加载的模型"""
        models = self.base.get_loaded_models()
        memory_stats = self.get_memory_stats()

        return {
            "code": 0,
            "message": "success",
            "data": {
                "service": "fraud_service",
                "models": models,
                "total": len(models),
                "warmed_up": self._warmed_up,
                "memory_stats": memory_stats
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
                "message": "parameter error",
                "data": {"error": "model_id is required"}
            }
        _logger.info("手动重新加载模型: 模型ID=%s", model_id)
        result = self.base.reload_model(model_id)
        if result.get("success"):
            _logger.info("模型重新加载成功: 模型ID=%s, 版本=%s", model_id, result.get("version"))
        else:
            _logger.error("模型重新加载失败: 模型ID=%s, 错误=%s", model_id, result.get("message"))
        return {
            "code": 0 if result.get("success") else 1001,
            "message": "success" if result.get("success") else "failed",
            "data": result
        }

    @bentoml.api
    async def memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        memory_stats = self.get_memory_stats()
        return {
            "code": 0,
            "message": "success",
            "data": memory_stats
        }