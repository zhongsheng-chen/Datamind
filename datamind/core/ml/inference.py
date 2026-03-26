# datamind/core/ml/inference.py

"""推理引擎

提供统一的模型推理服务，支持评分卡模型和反欺诈模型。

核心功能：
  - predict_scorecard: 评分卡模型预测
  - predict_fraud: 反欺诈模型预测
  - predict_scorecard_batch: 批量评分卡预测
  - predict_fraud_batch: 批量反欺诈预测
  - 输入特征验证：自动验证输入特征是否完整
  - 自动模型加载：如果模型未加载，自动触发加载
  - 结果缓存：缓存推理结果，避免重复计算
  - 解释器缓存：复用 ShapExplainer 实例
  - API调用日志：记录每次推理请求到数据库
  - 审计日志：记录所有推理操作
  - 链路追踪：完整的 span 追踪
"""

import hashlib
import json
import time
import traceback
from datetime import datetime
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

from datamind.core.ml.model_loader import get_model_loader
from datamind.core.ml.adapters.factory import get_adapter
from datamind.core.ml.cache import LRUCache, CacheKeyGenerator
from datamind.core.ml.scorecard import Scorecard
from datamind.core.ml.explain import ShapExplainer
from datamind.core.ml.exceptions import ModelInferenceException, ModelNotFoundException
from datamind.core.db.database import get_db
from datamind.core.db.models import ApiCallLog
from datamind.core.domain.enums import TaskType, AuditAction
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging.debug import debug_print


class InferenceEngine:
    """统一推理引擎"""

    def __init__(self, cache_size: int = 1000, cache_ttl: int = 3600):
        self._cache = LRUCache(max_size=cache_size, ttl=cache_ttl)
        self._key_generator = CacheKeyGenerator()
        self._model_loader = get_model_loader()
        self._explainer_cache: Dict[str, ShapExplainer] = {}
        self._stats = {
            'total_inferences': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0
        }

    @staticmethod
    def _generate_cache_key(model_id: str, features: Dict[str, Any],
                            explain: bool = False) -> str:
        """生成缓存键"""
        sorted_items = []
        for k, v in sorted(features.items()):
            if isinstance(v, float):
                sorted_items.append((k, round(v, 6)))
            else:
                sorted_items.append((k, v))

        features_str = json.dumps(sorted_items, sort_keys=True)
        feature_hash = hashlib.md5(features_str.encode()).hexdigest()

        if explain:
            return f"pred:{model_id}:{feature_hash}:explain"
        return f"pred:{model_id}:{feature_hash}"

    def _get_explainer(self, model, model_id: str, feature_names: List[str]) -> ShapExplainer:
        """获取或创建 ShapExplainer 实例"""
        cache_key = f"{model_id}:{tuple(feature_names)}"

        if cache_key not in self._explainer_cache:
            debug_print("InferenceEngine", f"创建新的 ShapExplainer 实例: {cache_key}")
            self._explainer_cache[cache_key] = ShapExplainer(
                model=model,
                feature_names=feature_names,
                background_data=None,
                inference=self
            )

        return self._explainer_cache[cache_key]

    def _get_model_with_metadata(self, model_id: str, user_id: str, ip_address: str):
        """获取模型和元数据"""
        model = self._model_loader.get_model(model_id)

        if model is None:
            if not self._model_loader.load_model(model_id, user_id or "system", ip_address):
                raise ModelNotFoundException(f"模型未加载或不存在: {model_id}")
            model = self._model_loader.get_model(model_id)

        metadata = self._model_loader.get_model_metadata(model_id)

        if metadata is None:
            raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

        return model, metadata

    @staticmethod
    def _log_api_call(request_id: str, application_id: str, model_id: str,
                      model_version: str, task_type: str, features: Dict,
                      response: Optional[Dict], processing_time_ms: int,
                      ip_address: str, api_key: str, user_id: str,
                      status_code: int = 200, error: str = None):
        """记录 API 调用日志"""
        try:
            with get_db() as session:
                log = ApiCallLog(
                    request_id=request_id,
                    application_id=application_id,
                    model_id=model_id,
                    model_version=model_version,
                    task_type=task_type,
                    endpoint=f"/api/v1/{task_type}/predict",
                    request_data=features,
                    response_data=response,
                    processing_time_ms=processing_time_ms,
                    status_code=status_code,
                    error_message=error,
                    ip_address=ip_address,
                    api_key=api_key,
                    user_id=user_id
                )
                session.add(log)
                session.commit()
        except Exception as e:
            debug_print("InferenceEngine", f"记录API调用日志失败: {e}")

    @staticmethod
    def _validate_features(features: Dict[str, Any], input_features: List[str]) -> None:
        """验证输入特征"""
        missing = [f for f in input_features if f not in features]
        if missing:
            raise ModelInferenceException(f"缺少必要特征: {missing}")

    @staticmethod
    def _get_scorecard_from_params(model_params: Dict[str, Any]) -> Scorecard:
        """从模型参数中获取评分卡实例"""
        scorecard_params = model_params.get('scorecard', {})
        return Scorecard(
            base_score=scorecard_params.get('base_score', 600),
            pdo=scorecard_params.get('pdo', 50),
            min_score=scorecard_params.get('min_score', 300),
            max_score=scorecard_params.get('max_score', 950),
            direction=scorecard_params.get('direction', 'lower_better'),
            base_odds=scorecard_params.get('base_odds', 1.0)
        )

    @staticmethod
    def _extract_classifier_from_pipeline(model):
        """从 Pipeline 中提取分类器"""
        if hasattr(model, 'named_steps'):
            for step_name, step in model.named_steps.items():
                if hasattr(step, 'predict_proba') or hasattr(step, 'predict'):
                    return step
        return model

    @staticmethod
    def _extract_scaler_from_pipeline(model):
        """从 Pipeline 中提取标准化器"""
        if hasattr(model, 'named_steps'):
            for step_name, step in model.named_steps.items():
                if hasattr(step, 'transform') and hasattr(step, 'mean_'):
                    return step
        return None

    def _is_pipeline(self, model) -> bool:
        """检查是否为 Pipeline"""
        return hasattr(model, 'named_steps')

    def predict_scorecard(self, model_id: str, features: Dict[str, Any],
                          application_id: str, user_id: Optional[str] = None,
                          ip_address: Optional[str] = None,
                          api_key: Optional[str] = None,
                          use_cache: bool = True,
                          explain: bool = False) -> Dict[str, Any]:
        """
        评分卡模型预测

        参数:
            model_id: 模型ID
            features: 特征字典
            application_id: 申请ID
            user_id: 用户ID
            ip_address: IP地址
            api_key: API密钥（用于日志）
            use_cache: 是否使用缓存
            explain: 是否返回特征解释

        返回:
            预测结果字典
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        cache_key = self._generate_cache_key(model_id, features, explain)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                self._stats['cache_hits'] += 1
                self._stats['total_inferences'] += 1
                cached['from_cache'] = True
                cached['request_id'] = request_id
                cached['trace_id'] = trace_id
                cached['span_id'] = span_id
                cached['parent_span_id'] = parent_span_id
                return cached

        self._stats['cache_misses'] += 1
        self._stats['total_inferences'] += 1

        metadata = None

        try:
            model, metadata = self._get_model_with_metadata(model_id, user_id, ip_address)

            if metadata.get('task_type') != TaskType.SCORING.value:
                raise ModelInferenceException(
                    f"模型类型不匹配: 期望 scoring, 实际 {metadata.get('task_type')}"
                )

            input_features = metadata.get('input_features', [])
            self._validate_features(features, input_features)

            ordered_values = [features.get(f, 0) for f in input_features]
            X = pd.DataFrame([ordered_values], columns=input_features)

            model_params = metadata.get('model_params', {})
            scorecard = self._get_scorecard_from_params(model_params)
            is_pipeline = self._is_pipeline(model)

            if is_pipeline:
                classifier = self._extract_classifier_from_pipeline(model)
                scaler = self._extract_scaler_from_pipeline(model)

                if scaler:
                    X_scaled = scaler.transform(X.values)
                    debug_print("InferenceEngine", f"Pipeline: 应用归一化 (type={type(scaler).__name__})")
                else:
                    X_scaled = X.values

                if hasattr(classifier, 'predict_proba'):
                    prob = classifier.predict_proba(X_scaled)[0][1]
                else:
                    prob = classifier.predict(X_scaled)[0]

                total_score = scorecard.score(prob)

                result = {
                    'default_probability': round(prob, 4),
                    'total_score': round(total_score, 2),
                    'model_id': model_id,
                    'model_version': metadata.get('model_version', 'unknown'),
                    'application_id': application_id,
                    'processing_time_ms': round((time.time() - start_time) * 1000, 2),
                    'timestamp': datetime.now().isoformat(),
                    'from_cache': False,
                    'request_id': request_id,
                    'trace_id': trace_id,
                    'span_id': span_id,
                    'parent_span_id': parent_span_id
                }

                if explain and classifier:
                    try:
                        explainer = ShapExplainer(
                            classifier,
                            feature_names=input_features,
                            background_data=X_scaled,
                            inference=self
                        )
                        if scaler:
                            explainer._scaler = scaler
                        explanation = explainer.explain(features, scorecard, enable=True)

                        if explanation:
                            result['feature_scores'] = explanation.feature_scores
                            result['shap_values'] = explanation.shap_values
                            result['explain_confidence'] = explanation.confidence
                            result['explain_space'] = explanation.space
                            result['additive_error'] = explanation.additive_error
                            result['score_error'] = explanation.score_error

                            if explanation.score_error and explanation.score_error > 5:
                                result['warning'] = f"评分偏差较大 ({explanation.score_error:.2f})，解释可能不可靠"
                            elif explanation.warning:
                                result['warning'] = explanation.warning
                        else:
                            result['feature_scores'] = {}
                            result['explain_warning'] = "解释不可用"
                    except Exception as e:
                        debug_print("InferenceEngine", f"SHAP 解释失败: {e}")
                        result['feature_scores'] = {}
                        result['explain_warning'] = f"解释失败: {str(e)[:100]}"
                else:
                    result['feature_scores'] = {}

            else:
                adapter = get_adapter(model, feature_names=input_features)
                prob = adapter.predict_proba(X.values)
                total_score = scorecard.score(prob)

                result = {
                    'default_probability': round(prob, 4),
                    'total_score': round(total_score, 2),
                    'model_id': model_id,
                    'model_version': metadata.get('model_version', 'unknown'),
                    'application_id': application_id,
                    'processing_time_ms': round((time.time() - start_time) * 1000, 2),
                    'timestamp': datetime.now().isoformat(),
                    'from_cache': False,
                    'request_id': request_id,
                    'trace_id': trace_id,
                    'span_id': span_id,
                    'parent_span_id': parent_span_id
                }

                if explain:
                    try:
                        explainer = self._get_explainer(model, model_id, input_features)
                        explanation = explainer.explain(features, scorecard, enable=True)

                        if explanation:
                            result['feature_scores'] = explanation.feature_scores
                            result['shap_values'] = explanation.shap_values
                            result['explain_confidence'] = explanation.confidence
                            result['explain_space'] = explanation.space
                            result['additive_error'] = explanation.additive_error
                            result['score_error'] = explanation.score_error

                            if explanation.score_error and explanation.score_error > 5:
                                result['warning'] = f"评分偏差较大 ({explanation.score_error:.2f})，解释可能不可靠"
                            elif explanation.warning:
                                result['warning'] = explanation.warning
                        else:
                            result['feature_scores'] = {}
                            result['explain_warning'] = "解释不可用"
                    except Exception as e:
                        debug_print("InferenceEngine", f"SHAP 解释失败: {e}")
                        result['feature_scores'] = {}
                        result['explain_warning'] = f"解释失败: {str(e)[:100]}"
                else:
                    result['feature_scores'] = {}

            cache_value = {
                'default_probability': result['default_probability'],
                'total_score': result['total_score'],
                'model_id': model_id,
                'model_version': result['model_version'],
                'application_id': application_id,
                'processing_time_ms': result['processing_time_ms'],
                'timestamp': result['timestamp']
            }
            if explain and result.get('feature_scores'):
                cache_value['feature_scores'] = result['feature_scores']
                if result.get('warning'):
                    cache_value['warning'] = result['warning']

            self._cache.set(cache_key, cache_value)

            self._log_api_call(
                request_id=request_id,
                application_id=application_id,
                model_id=model_id,
                model_version=result['model_version'],
                task_type="scoring",
                features=features,
                response=result,
                processing_time_ms=int(result['processing_time_ms']),
                ip_address=ip_address,
                api_key=api_key,
                user_id=user_id
            )

            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=user_id or "system",
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "model_version": result['model_version'],
                    "application_id": application_id,
                    "task_type": "scoring",
                    "default_probability": result['default_probability'],
                    "total_score": result['total_score'],
                    "processing_time_ms": result['processing_time_ms'],
                    "explain": explain,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            log_performance(
                operation=AuditAction.MODEL_INFERENCE.value,
                duration_ms=result['processing_time_ms'],
                extra={
                    "model_id": model_id,
                    "model_version": result['model_version'],
                    "application_id": application_id,
                    "task_type": "scoring",
                    "explain": explain,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            debug_print("InferenceEngine", f"评分卡推理成功: {model_id}, 耗时: {result['processing_time_ms']:.2f}毫秒")
            return result

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            self._stats['errors'] += 1

            error_msg = str(e)
            error_trace = traceback.format_exc()
            actual_model_version = metadata.get('model_version', 'unknown') if metadata else 'unknown'

            self._log_api_call(
                request_id=request_id,
                application_id=application_id,
                model_id=model_id,
                model_version=actual_model_version,
                task_type="scoring",
                features=features,
                response=None,
                processing_time_ms=int(processing_time_ms),
                ip_address=ip_address,
                api_key=api_key,
                user_id=user_id,
                status_code=500,
                error=error_msg
            )

            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=user_id or "system",
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "application_id": application_id,
                    "task_type": "scoring",
                    "error": error_msg,
                    "traceback": error_trace[:2000],
                    "processing_time_ms": round(processing_time_ms, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=error_msg,
                request_id=request_id
            )

            debug_print("InferenceEngine", f"评分卡推理失败: {model_id}, 错误: {error_msg}")
            raise ModelInferenceException(f"预测失败: {error_msg}")

    def predict_scorecard_batch(self, model_id: str, features_list: List[Dict[str, Any]],
                                application_ids: List[str], user_id: Optional[str] = None,
                                ip_address: Optional[str] = None,
                                api_key: Optional[str] = None,
                                use_cache: bool = True,
                                explain: bool = False) -> List[Dict[str, Any]]:
        """
        批量评分卡预测

        参数:
            model_id: 模型ID
            features_list: 特征字典列表
            application_ids: 申请ID列表
            user_id: 用户ID
            ip_address: IP地址
            api_key: API密钥（用于日志）
            use_cache: 是否使用缓存（由单次预测处理）
            explain: 是否返回特征解释

        返回:
            预测结果列表
        """
        if len(features_list) != len(application_ids):
            raise ValueError("features_list 和 application_ids 长度必须一致")

        if not features_list:
            return []

        results = []
        for features, app_id in zip(features_list, application_ids):
            result = self.predict_scorecard(
                model_id=model_id,
                features=features,
                application_id=app_id,
                user_id=user_id,
                ip_address=ip_address,
                api_key=api_key,
                use_cache=use_cache,
                explain=explain
            )
            results.append(result)

        return results

    def predict_fraud(self, model_id: str, features: Dict[str, Any],
                      application_id: str, user_id: Optional[str] = None,
                      ip_address: Optional[str] = None,
                      api_key: Optional[str] = None,
                      use_cache: bool = True) -> Dict[str, Any]:
        """
        反欺诈模型预测
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        cache_key = self._generate_cache_key(model_id, features, explain=False)

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                self._stats['cache_hits'] += 1
                self._stats['total_inferences'] += 1
                cached['from_cache'] = True
                cached['request_id'] = request_id
                cached['trace_id'] = trace_id
                cached['span_id'] = span_id
                cached['parent_span_id'] = parent_span_id
                return cached

        self._stats['cache_misses'] += 1
        self._stats['total_inferences'] += 1

        metadata = None

        try:
            model, metadata = self._get_model_with_metadata(model_id, user_id, ip_address)

            if metadata.get('task_type') != TaskType.FRAUD_DETECTION.value:
                raise ModelInferenceException(
                    f"模型类型不匹配: 期望 fraud_detection, 实际 {metadata.get('task_type')}"
                )

            input_features = metadata.get('input_features', [])
            self._validate_features(features, input_features)

            ordered_values = [features.get(f, 0) for f in input_features]
            X = pd.DataFrame([ordered_values], columns=input_features)

            is_pipeline = self._is_pipeline(model)

            if is_pipeline:
                classifier = self._extract_classifier_from_pipeline(model)
                scaler = self._extract_scaler_from_pipeline(model)

                if scaler:
                    X_scaled = scaler.transform(X.values)
                else:
                    X_scaled = X.values

                prob = classifier.predict_proba(X_scaled)[0][1] if hasattr(classifier, 'predict_proba') else classifier.predict(X_scaled)[0]
            else:
                adapter = get_adapter(model, feature_names=input_features)
                prob = adapter.predict_proba(X.values)

            risk_score = prob * 100

            model_params = metadata.get('model_params', {})
            risk_config = model_params.get('risk_config', {})
            levels = risk_config.get('levels', {
                'low': {'min': 0, 'max': 0.3},
                'medium': {'min': 0.3, 'max': 0.7},
                'high': {'min': 0.7, 'max': 1.0}
            })

            risk_level = 'low'
            for level_name, level_config in levels.items():
                if level_config.get('min', 0) <= prob <= level_config.get('max', 1):
                    risk_level = level_name
                    break

            feature_importance = metadata.get('feature_importance', {})
            if not feature_importance:
                if is_pipeline:
                    classifier = self._extract_classifier_from_pipeline(model)
                    if hasattr(classifier, 'coef_'):
                        importance = np.abs(classifier.coef_[0])
                        feature_importance = {f: float(imp) for f, imp in zip(input_features, importance)}
                    elif hasattr(classifier, 'feature_importances_'):
                        importance = classifier.feature_importances_
                        feature_importance = {f: float(imp) for f, imp in zip(input_features, importance)}
                else:
                    adapter = get_adapter(model, feature_names=input_features)
                    feature_importance = adapter.get_feature_importance()

            total_importance = sum(feature_importance.values())
            risk_factors = []
            if total_importance > 0:
                for feat, importance in sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:5]:
                    if prob > 0.5:
                        risk_factors.append({
                            'factor': feat,
                            'value': features.get(feat, 0),
                            'weight': importance / total_importance,
                            'description': f'特征 {feat} 值异常'
                        })

            processing_time_ms = (time.time() - start_time) * 1000
            model_version = metadata.get('model_version', 'unknown')

            result = {
                'fraud_probability': round(prob, 4),
                'risk_score': round(risk_score, 2),
                'risk_level': risk_level,
                'risk_factors': risk_factors[:5],
                'model_id': model_id,
                'model_version': model_version,
                'application_id': application_id,
                'processing_time_ms': round(processing_time_ms, 2),
                'timestamp': datetime.now().isoformat(),
                'from_cache': False,
                'request_id': request_id,
                'trace_id': trace_id,
                'span_id': span_id,
                'parent_span_id': parent_span_id
            }

            cache_value = {
                'fraud_probability': result['fraud_probability'],
                'risk_score': result['risk_score'],
                'risk_level': result['risk_level'],
                'risk_factors': result['risk_factors'],
                'model_id': model_id,
                'model_version': model_version,
                'application_id': application_id,
                'processing_time_ms': result['processing_time_ms'],
                'timestamp': result['timestamp']
            }
            self._cache.set(cache_key, cache_value)

            self._log_api_call(
                request_id=request_id,
                application_id=application_id,
                model_id=model_id,
                model_version=model_version,
                task_type="fraud_detection",
                features=features,
                response=result,
                processing_time_ms=int(processing_time_ms),
                ip_address=ip_address,
                api_key=api_key,
                user_id=user_id
            )

            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=user_id or "system",
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "model_version": model_version,
                    "application_id": application_id,
                    "task_type": "fraud_detection",
                    "fraud_probability": result['fraud_probability'],
                    "risk_score": result['risk_score'],
                    "risk_level": result['risk_level'],
                    "processing_time_ms": round(processing_time_ms, 2),
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
                    "model_id": model_id,
                    "model_version": model_version,
                    "application_id": application_id,
                    "task_type": "fraud_detection",
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            debug_print("InferenceEngine", f"反欺诈推理成功: {model_id}, 耗时: {processing_time_ms:.2f}毫秒")
            return result

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            self._stats['errors'] += 1

            error_msg = str(e)
            error_trace = traceback.format_exc()
            actual_model_version = metadata.get('model_version', 'unknown') if metadata else 'unknown'

            self._log_api_call(
                request_id=request_id,
                application_id=application_id,
                model_id=model_id,
                model_version=actual_model_version,
                task_type="fraud_detection",
                features=features,
                response=None,
                processing_time_ms=int(processing_time_ms),
                ip_address=ip_address,
                api_key=api_key,
                user_id=user_id,
                status_code=500,
                error=error_msg
            )

            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=user_id or "system",
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "application_id": application_id,
                    "task_type": "fraud_detection",
                    "error": error_msg,
                    "traceback": error_trace[:2000],
                    "processing_time_ms": round(processing_time_ms, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=error_msg,
                request_id=request_id
            )

            debug_print("InferenceEngine", f"反欺诈推理失败: {model_id}, 错误: {error_msg}")
            raise ModelInferenceException(f"预测失败: {error_msg}")

    def predict_fraud_batch(self, model_id: str, features_list: List[Dict[str, Any]],
                            application_ids: List[str], user_id: Optional[str] = None,
                            ip_address: Optional[str] = None,
                            api_key: Optional[str] = None,
                            use_cache: bool = True) -> List[Dict[str, Any]]:
        """批量反欺诈预测"""
        if len(features_list) != len(application_ids):
            raise ValueError("features_list 和 application_ids 长度必须一致")

        results = []
        for features, app_id in zip(features_list, application_ids):
            result = self.predict_fraud(
                model_id=model_id,
                features=features,
                application_id=app_id,
                user_id=user_id,
                ip_address=ip_address,
                api_key=api_key,
                use_cache=use_cache
            )
            results.append(result)

        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self._stats['total_inferences']
        cache_hits = self._stats['cache_hits']
        cache_misses = self._stats['cache_misses']
        return {
            'total_inferences': total,
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
            'cache_hit_rate': cache_hits / total if total > 0 else 0,
            'errors': self._stats['errors'],
            'explainer_cache_size': len(self._explainer_cache)
        }

    def clear_cache(self, model_id: Optional[str] = None):
        """清除缓存"""
        if model_id:
            prefix = f"pred:{model_id}"
            self._cache.delete_by_prefix(prefix)
        else:
            self._cache.clear()
            self._explainer_cache.clear()


def get_inference_engine() -> InferenceEngine:
    """获取推理引擎实例"""
    return InferenceEngine()