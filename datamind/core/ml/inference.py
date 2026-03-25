# datamind/core/ml/inference.py

"""推理引擎

提供统一的模型推理服务，支持评分卡模型和反欺诈模型。

核心功能：
  - predict_scorecard: 评分卡模型预测，返回违约概率和信用评分
  - predict_fraud: 反欺诈模型预测，返回欺诈概率和风险评分
  - predict_batch: 批量预测，提高吞吐量
  - 输入特征验证：自动验证输入特征是否完整
  - 自动模型加载：如果模型未加载，自动触发加载
  - 性能监控：记录推理耗时和统计信息
  - API调用日志：记录每次推理请求到数据库
  - 审计日志：记录所有推理操作
  - 结果缓存：缓存推理结果，避免重复计算
  - 链路追踪：完整的 span 追踪
"""

import time
import traceback
import hashlib
import json
import math
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from collections import OrderedDict

from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.exceptions import ModelInferenceException, ModelNotFoundException
from datamind.core.db.database import get_db
from datamind.core.db.models import ApiCallLog
from datamind.core.domain.enums import TaskType, AuditAction
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging.debug import debug_print


class LRUCache:
    """LRU 缓存实现"""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None

        value, timestamp = self.cache[key]
        if (datetime.now() - timestamp).total_seconds() > self.ttl:
            del self.cache[key]
            return None

        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any):
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[key] = (value, datetime.now())

    def clear(self):
        self.cache.clear()

    def size(self) -> int:
        return len(self.cache)


class InferenceEngine:
    """统一推理引擎"""

    def __init__(self, cache_size: int = 1000, cache_ttl: int = 3600):
        self._stats = {
            'total_inferences': 0,
            'success_inferences': 0,
            'failed_inferences': 0,
            'total_duration_ms': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self._cache = LRUCache(max_size=cache_size, ttl=cache_ttl)
        debug_print("InferenceEngine", f"初始化推理引擎, 缓存大小: {cache_size} 条, TTL: {cache_ttl} 秒")

    def _get_cache_key(self, model_id: str, features: Dict[str, Any]) -> str:
        """生成缓存键"""
        sorted_features = json.dumps(features, sort_keys=True)
        key_str = f"{model_id}:{sorted_features}"
        return hashlib.md5(key_str.encode()).hexdigest()

    def predict_scorecard(
            self,
            model_id: str,
            features: Dict[str, Any],
            application_id: str,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            api_key: Optional[str] = None,
            use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        评分卡模型预测

        参数:
            model_id: 模型ID
            features: 特征字典
            application_id: 申请ID
            user_id: 用户ID
            ip_address: IP地址
            api_key: API密钥
            use_cache: 是否使用缓存

        返回:
            预测结果字典
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        cache_key = self._get_cache_key(model_id, features)
        if use_cache:
            cached_result = self._cache.get(cache_key)
            if cached_result:
                self._stats['cache_hits'] += 1
                debug_print("InferenceEngine", f"缓存命中: {model_id}")
                cached_result['from_cache'] = True
                cached_result['request_id'] = request_id
                cached_result['trace_id'] = trace_id
                cached_result['span_id'] = span_id
                return cached_result

        self._stats['cache_misses'] += 1

        with context.SpanContext("scorecard_inference"):
            try:
                # 获取模型
                model = model_loader.get_model(model_id)
                if not model:
                    if not model_loader.load_model(model_id, user_id or "system", ip_address):
                        raise ModelNotFoundException(f"模型未加载或不存在: {model_id}")
                    model = model_loader.get_model(model_id)

                # 获取模型元数据
                model_info = model_loader._loaded_models.get(model_id, {})
                metadata = model_info.get('metadata', {})

                if not metadata:
                    raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

                # 验证任务类型
                if metadata.get('task_type') != TaskType.SCORING.value:
                    raise ModelInferenceException(
                        f"模型类型不匹配: 期望 scoring, 实际 {metadata.get('task_type')}"
                    )

                # 验证输入特征
                input_features = metadata.get('input_features', [])
                missing = [f for f in input_features if f not in features]
                if missing:
                    raise ModelInferenceException(f"缺少必要特征: {missing}")

                # 准备输入数据
                ordered_features = {f: features[f] for f in input_features if f in features}
                input_data = pd.DataFrame([ordered_features])

                # 执行推理
                inference_start = time.time()
                framework = metadata.get('framework')
                if framework in ['sklearn', 'xgboost', 'lightgbm', 'catboost']:
                    raw_result = model.predict(input_data)
                elif framework == 'torch':
                    import torch
                    with torch.no_grad():
                        raw_result = model(torch.tensor(input_data.values)).numpy()
                elif framework == 'tensorflow':
                    raw_result = model.predict(input_data)
                elif framework == 'onnx':
                    raw_result = model.run(None, {model.get_inputs()[0].name: input_data.values.astype('float32')})
                else:
                    raise ModelInferenceException(f"不支持的框架: {framework}")

                inference_time = (time.time() - inference_start) * 1000

                # 提取违约概率
                if isinstance(raw_result, (np.ndarray, list)):
                    default_prob = float(raw_result[0] if len(raw_result) > 0 else 0)
                else:
                    default_prob = float(raw_result)

                # 评分卡转换
                scorecard_params = metadata.get('model_params', {}).get('scorecard', {})
                base_score = scorecard_params.get('base_score', 600)
                pdo = scorecard_params.get('pdo', 50)
                min_score = scorecard_params.get('min_score', 300)
                max_score = scorecard_params.get('max_score', 900)
                direction = scorecard_params.get('direction', 'higher_better')

                EPS = 1e-10
                p = max(min(default_prob, 1.0 - EPS), EPS)
                odds = p / (1.0 - p)
                log_odds = math.log(odds)

                if direction == "higher_better":
                    total_score = base_score - (pdo / math.log(2)) * log_odds
                else:
                    total_score = base_score + (pdo / math.log(2)) * log_odds

                if min_score is not None:
                    total_score = max(total_score, min_score)
                if max_score is not None:
                    total_score = min(total_score, max_score)

                # 特征分（简化版本）
                feature_scores = {}
                for feature_name, feature_value in features.items():
                    feature_scores[feature_name] = float(feature_value) if isinstance(feature_value, (int, float)) else 0

                score_result = {
                    'default_probability': round(default_prob, 4),
                    'total_score': round(total_score, 2),
                    'feature_scores': feature_scores
                }

                total_time = (time.time() - start_time) * 1000
                model_version = metadata.get('model_version', 'unknown')

                # 记录 API 调用日志
                try:
                    with get_db() as session:
                        log = ApiCallLog(
                            request_id=request_id,
                            application_id=application_id,
                            model_id=model_id,
                            model_version=model_version,
                            task_type=TaskType.SCORING.value,
                            endpoint="/api/v1/scoring/predict",
                            request_data=features,
                            response_data=score_result,
                            processing_time_ms=int(total_time),
                            model_inference_time_ms=int(inference_time),
                            status_code=200,
                            ip_address=ip_address,
                            api_key=api_key,
                            user_id=user_id
                        )
                        session.add(log)
                        session.commit()
                except Exception as e:
                    debug_print("InferenceEngine", f"记录API调用日志失败: {e}")

                self._update_stats(True, total_time)

                # 审计日志
                log_audit(
                    action=AuditAction.MODEL_INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "model_version": model_version,
                        "application_id": application_id,
                        "task_type": "scoring",
                        "default_probability": score_result['default_probability'],
                        "total_score": score_result['total_score'],
                        "processing_time_ms": round(total_time, 2),
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
                    duration_ms=total_time,
                    extra={
                        "model_id": model_id,
                        "model_version": model_version,
                        "application_id": application_id,
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    }
                )

                result = {
                    **score_result,
                    'model_id': model_id,
                    'model_version': model_version,
                    'application_id': application_id,
                    'processing_time_ms': round(total_time, 2),
                    'timestamp': datetime.now().isoformat(),
                    'from_cache': False,
                    'request_id': request_id,
                    'trace_id': trace_id,
                    'span_id': span_id
                }

                if use_cache:
                    self._cache.set(cache_key, result)

                debug_print("InferenceEngine", f"评分卡推理成功: {model_id}, 耗时: {total_time:.2f}ms")
                return result

            except Exception as e:
                total_time = (time.time() - start_time) * 1000
                self._update_stats(False, total_time)

                error_trace = traceback.format_exc()

                log_audit(
                    action=AuditAction.MODEL_INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "application_id": application_id,
                        "task_type": "scoring",
                        "error": str(e),
                        "traceback": error_trace[:2000],
                        "processing_time_ms": round(total_time, 2),
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    reason=str(e),
                    request_id=request_id
                )

                try:
                    model_version = metadata.get('model_version', 'unknown') if 'metadata' in locals() else 'unknown'
                except:
                    model_version = 'unknown'

                try:
                    with get_db() as session:
                        log = ApiCallLog(
                            request_id=request_id,
                            application_id=application_id,
                            model_id=model_id,
                            model_version=model_version,
                            task_type=TaskType.SCORING.value,
                            endpoint="/api/v1/scoring/predict",
                            request_data=features,
                            response_data=None,
                            processing_time_ms=int(total_time),
                            status_code=500,
                            error_message=str(e),
                            error_traceback=error_trace,
                            ip_address=ip_address,
                            api_key=api_key,
                            user_id=user_id
                        )
                        session.add(log)
                        session.commit()
                except Exception as log_error:
                    debug_print("InferenceEngine", f"记录API调用日志失败: {log_error}")

                debug_print("InferenceEngine", f"评分卡推理失败: {model_id}, 错误: {str(e)}")
                raise

    def predict_fraud(
            self,
            model_id: str,
            features: Dict[str, Any],
            application_id: str,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            api_key: Optional[str] = None,
            use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        反欺诈模型预测

        参数:
            model_id: 模型ID
            features: 特征字典
            application_id: 申请ID
            user_id: 用户ID
            ip_address: IP地址
            api_key: API密钥
            use_cache: 是否使用缓存

        返回:
            预测结果字典
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        cache_key = self._get_cache_key(model_id, features)
        if use_cache:
            cached_result = self._cache.get(cache_key)
            if cached_result:
                self._stats['cache_hits'] += 1
                debug_print("InferenceEngine", f"缓存命中: {model_id}")
                cached_result['from_cache'] = True
                cached_result['request_id'] = request_id
                cached_result['trace_id'] = trace_id
                cached_result['span_id'] = span_id
                return cached_result

        self._stats['cache_misses'] += 1

        with context.SpanContext("fraud_inference"):
            try:
                # 获取模型
                model = model_loader.get_model(model_id)
                if not model:
                    if not model_loader.load_model(model_id, user_id or "system", ip_address):
                        raise ModelNotFoundException(f"模型未加载或不存在: {model_id}")
                    model = model_loader.get_model(model_id)

                # 获取模型元数据
                model_info = model_loader._loaded_models.get(model_id, {})
                metadata = model_info.get('metadata', {})

                if not metadata:
                    raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

                # 验证任务类型
                if metadata.get('task_type') != TaskType.FRAUD_DETECTION.value:
                    raise ModelInferenceException(
                        f"模型类型不匹配: 期望 fraud_detection, 实际 {metadata.get('task_type')}"
                    )

                # 验证输入特征
                input_features = metadata.get('input_features', [])
                missing = [f for f in input_features if f not in features]
                if missing:
                    raise ModelInferenceException(f"缺少必要特征: {missing}")

                # 准备输入数据
                ordered_features = {f: features[f] for f in input_features if f in features}
                input_data = pd.DataFrame([ordered_features])

                # 执行推理
                inference_start = time.time()
                framework = metadata.get('framework')
                if framework in ['sklearn', 'xgboost', 'lightgbm', 'catboost']:
                    raw_result = model.predict(input_data)
                elif framework == 'torch':
                    import torch
                    with torch.no_grad():
                        raw_result = model(torch.tensor(input_data.values)).numpy()
                elif framework == 'tensorflow':
                    raw_result = model.predict(input_data)
                elif framework == 'onnx':
                    raw_result = model.run(None, {model.get_inputs()[0].name: input_data.values.astype('float32')})
                else:
                    raise ModelInferenceException(f"不支持的框架: {framework}")

                inference_time = (time.time() - inference_start) * 1000

                # 提取欺诈概率
                if isinstance(raw_result, (np.ndarray, list)):
                    fraud_prob = float(raw_result[0] if len(raw_result) > 0 else 0)
                else:
                    fraud_prob = float(raw_result)

                # 计算风险评分
                risk_score = fraud_prob * 100

                # 风险因素分析
                risk_factors = []
                if fraud_prob > 0.7:
                    risk_factors.append({
                        'factor': 'high_fraud_probability',
                        'value': fraud_prob,
                        'weight': 0.8
                    })

                fraud_result = {
                    'fraud_probability': round(fraud_prob, 4),
                    'risk_score': round(risk_score, 2),
                    'risk_factors': risk_factors
                }

                total_time = (time.time() - start_time) * 1000
                model_version = metadata.get('model_version', 'unknown')

                # 记录 API 调用日志
                try:
                    with get_db() as session:
                        log = ApiCallLog(
                            request_id=request_id,
                            application_id=application_id,
                            model_id=model_id,
                            model_version=model_version,
                            task_type=TaskType.FRAUD_DETECTION.value,
                            endpoint="/api/v1/fraud/predict",
                            request_data=features,
                            response_data=fraud_result,
                            processing_time_ms=int(total_time),
                            model_inference_time_ms=int(inference_time),
                            status_code=200,
                            ip_address=ip_address,
                            api_key=api_key,
                            user_id=user_id
                        )
                        session.add(log)
                        session.commit()
                except Exception as e:
                    debug_print("InferenceEngine", f"记录API调用日志失败: {e}")

                self._update_stats(True, total_time)

                # 审计日志
                log_audit(
                    action=AuditAction.MODEL_INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "model_version": model_version,
                        "application_id": application_id,
                        "task_type": "fraud_detection",
                        "fraud_probability": fraud_result['fraud_probability'],
                        "risk_score": fraud_result['risk_score'],
                        "processing_time_ms": round(total_time, 2),
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
                    duration_ms=total_time,
                    extra={
                        "model_id": model_id,
                        "model_version": model_version,
                        "application_id": application_id,
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    }
                )

                result = {
                    **fraud_result,
                    'model_id': model_id,
                    'model_version': model_version,
                    'application_id': application_id,
                    'processing_time_ms': round(total_time, 2),
                    'timestamp': datetime.now().isoformat(),
                    'from_cache': False,
                    'request_id': request_id,
                    'trace_id': trace_id,
                    'span_id': span_id
                }

                if use_cache:
                    self._cache.set(cache_key, result)

                debug_print("InferenceEngine", f"反欺诈推理成功: {model_id}, 耗时: {total_time:.2f}ms")
                return result

            except Exception as e:
                total_time = (time.time() - start_time) * 1000
                self._update_stats(False, total_time)

                error_trace = traceback.format_exc()

                log_audit(
                    action=AuditAction.MODEL_INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "application_id": application_id,
                        "task_type": "fraud_detection",
                        "error": str(e),
                        "traceback": error_trace[:2000],
                        "processing_time_ms": round(total_time, 2),
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    reason=str(e),
                    request_id=request_id
                )

                try:
                    model_version = metadata.get('model_version', 'unknown') if 'metadata' in locals() else 'unknown'
                except:
                    model_version = 'unknown'

                try:
                    with get_db() as session:
                        log = ApiCallLog(
                            request_id=request_id,
                            application_id=application_id,
                            model_id=model_id,
                            model_version=model_version,
                            task_type=TaskType.FRAUD_DETECTION.value,
                            endpoint="/api/v1/fraud/predict",
                            request_data=features,
                            response_data=None,
                            processing_time_ms=int(total_time),
                            status_code=500,
                            error_message=str(e),
                            error_traceback=error_trace,
                            ip_address=ip_address,
                            api_key=api_key,
                            user_id=user_id
                        )
                        session.add(log)
                        session.commit()
                except Exception as log_error:
                    debug_print("InferenceEngine", f"记录API调用日志失败: {log_error}")

                debug_print("InferenceEngine", f"反欺诈推理失败: {model_id}, 错误: {str(e)}")
                raise

    def predict_batch(
            self,
            model_id: str,
            features_list: List[Dict[str, Any]],
            application_ids: List[str],
            task_type: str,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            api_key: Optional[str] = None,
            use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        批量预测

        参数:
            model_id: 模型ID
            features_list: 特征列表
            application_ids: 申请ID列表
            task_type: 任务类型 (scoring/fraud_detection)
            user_id: 用户ID
            ip_address: IP地址
            api_key: API密钥
            use_cache: 是否使用缓存

        返回:
            预测结果列表
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        batch_start_time = time.time()

        if len(features_list) != len(application_ids):
            raise ValueError("features_list 和 application_ids 长度必须一致")

        results = []
        model = model_loader.get_model(model_id)
        if not model:
            if not model_loader.load_model(model_id, user_id or "system", ip_address):
                raise ModelNotFoundException(f"模型未加载或不存在: {model_id}")
            model = model_loader.get_model(model_id)

        model_info = model_loader._loaded_models.get(model_id, {})
        metadata = model_info.get('metadata', {})

        if not metadata:
            raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

        success_count = 0
        failed_count = 0

        for i, (features, app_id) in enumerate(zip(features_list, application_ids)):
            try:
                if task_type == TaskType.SCORING.value:
                    result = self.predict_scorecard(
                        model_id=model_id,
                        features=features,
                        application_id=app_id,
                        user_id=user_id,
                        ip_address=ip_address,
                        api_key=api_key,
                        use_cache=use_cache
                    )
                elif task_type == TaskType.FRAUD_DETECTION.value:
                    result = self.predict_fraud(
                        model_id=model_id,
                        features=features,
                        application_id=app_id,
                        user_id=user_id,
                        ip_address=ip_address,
                        api_key=api_key,
                        use_cache=use_cache
                    )
                else:
                    raise ModelInferenceException(f"不支持的任务类型: {task_type}")

                results.append(result)
                success_count += 1
            except Exception as e:
                results.append({
                    'error': str(e),
                    'application_id': app_id,
                    'success': False,
                    'index': i
                })
                failed_count += 1

        total_time = (time.time() - batch_start_time) * 1000

        # 审计日志
        log_audit(
            action=AuditAction.MODEL_BATCH_INFERENCE.value,
            user_id=user_id or "system",
            ip_address=ip_address,
            details={
                "model_id": model_id,
                "model_version": metadata.get('model_version', 'unknown'),
                "task_type": task_type,
                "total_requests": len(features_list),
                "success_count": success_count,
                "failed_count": failed_count,
                "processing_time_ms": round(total_time, 2),
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        # 性能日志
        log_performance(
            operation="batch_inference",
            duration_ms=total_time,
            extra={
                "model_id": model_id,
                "task_type": task_type,
                "batch_size": len(features_list),
                "success_count": success_count,
                "failed_count": failed_count,
                "request_id": request_id,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            }
        )

        debug_print("InferenceEngine", f"批量预测完成: {len(results)} 条, 耗时: {total_time:.2f}ms")
        return results

    def _update_stats(self, success: bool, duration_ms: float):
        """更新统计信息"""
        self._stats['total_inferences'] += 1
        if success:
            self._stats['success_inferences'] += 1
        else:
            self._stats['failed_inferences'] += 1
        self._stats['total_duration_ms'] += duration_ms

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        返回:
            统计信息字典
        """
        stats = self._stats.copy()
        if stats['total_inferences'] > 0:
            stats['avg_duration_ms'] = stats['total_duration_ms'] / stats['total_inferences']
            stats['success_rate'] = stats['success_inferences'] / stats['total_inferences']
        return stats

    def clear_cache(self, model_id: Optional[str] = None):
        """
        清除缓存

        参数:
            model_id: 模型ID，如果为None则清除所有缓存
        """
        if model_id:
            keys_to_remove = []
            for key in self._cache.cache.keys():
                if key.startswith(model_id):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._cache.cache[key]
            debug_print("InferenceEngine", f"清除模型缓存: {model_id}, 移除 {len(keys_to_remove)} 条")
        else:
            self._cache.clear()
            debug_print("InferenceEngine", "清除所有缓存")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        返回:
            缓存统计信息字典
        """
        total_requests = self._stats['cache_hits'] + self._stats['cache_misses']
        return {
            'cache_size': self._cache.size(),
            'cache_max_size': self._cache.max_size,
            'cache_ttl': self._cache.ttl,
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'cache_hit_rate': self._stats['cache_hits'] / total_requests if total_requests > 0 else 0
        }


# 全局推理引擎实例
inference_engine = InferenceEngine()