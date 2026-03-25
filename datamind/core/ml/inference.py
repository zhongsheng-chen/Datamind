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
  - 特征分计算：基于特征重要性计算每个特征对评分的贡献
"""

import time
import traceback
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, List, Optional

import numpy as np
import pandas as pd

from datamind.core.ml.model_loader import get_model_loader
from datamind.core.ml.cache import LRUCache, CacheKeyGenerator
from datamind.core.ml.exceptions import ModelInferenceException, ModelNotFoundException
from datamind.core.db.database import get_db
from datamind.core.db.models import ApiCallLog
from datamind.core.domain.enums import TaskType, AuditAction
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging.debug import debug_print


# ==================== 策略模式：框架推理策略 ====================

class InferenceStrategy(ABC):
    """推理策略基类"""

    @abstractmethod
    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        """获取预测概率"""
        pass

    @abstractmethod
    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        """提取特征重要性"""
        pass


class SklearnInferenceStrategy(InferenceStrategy):
    """Sklearn 推理策略"""

    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        if hasattr(model, 'predict_proba'):
            proba = model.predict_proba(input_data)[0, 1]
        else:
            proba = model.predict(input_data)[0]
        return float(proba)

    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        importance = {}
        if hasattr(model, 'feature_importances_'):
            values = model.feature_importances_
        elif hasattr(model, 'coef_'):
            values = abs(model.coef_[0]) if model.coef_.ndim > 1 else abs(model.coef_)
        else:
            return {}

        for i, feat in enumerate(input_features):
            if i < len(values):
                importance[feat] = float(values[i])
        return importance


class XGBoostInferenceStrategy(InferenceStrategy):
    """XGBoost 推理策略"""

    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        import xgboost as xgb
        dmatrix = xgb.DMatrix(input_data)
        proba = model.predict(dmatrix)[0]
        return float(proba)

    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        if hasattr(model, 'get_score'):
            scores = model.get_score(importance_type='weight')
            return {feat: float(scores.get(feat, 0)) for feat in input_features}
        return {}


class LightGBMInferenceStrategy(InferenceStrategy):
    """LightGBM 推理策略"""

    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        proba = model.predict(input_data)[0]
        return float(proba)

    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        if hasattr(model, 'feature_importance'):
            values = model.feature_importance()
            return {feat: float(values[i]) for i, feat in enumerate(input_features) if i < len(values)}
        return {}


class CatBoostInferenceStrategy(InferenceStrategy):
    """CatBoost 推理策略"""

    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        proba = model.predict_proba(input_data)[0, 1] if hasattr(model, 'predict_proba') else model.predict(input_data)[0]
        return float(proba)

    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        if hasattr(model, 'get_feature_importance'):
            values = model.get_feature_importance()
            return {feat: float(values[i]) for i, feat in enumerate(input_features) if i < len(values)}
        return {}


class TorchInferenceStrategy(InferenceStrategy):
    """PyTorch 推理策略"""

    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        import torch
        with torch.no_grad():
            output = model(torch.tensor(input_data.values))
            if output.shape[-1] == 2:
                proba = torch.softmax(output, dim=1)[0, 1].item()
            else:
                proba = output.item() if output.numel() == 1 else output[0].item()
        return float(proba)

    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        return {}


class TensorFlowInferenceStrategy(InferenceStrategy):
    """TensorFlow 推理策略"""

    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        output = model.predict(input_data)
        if output.shape[-1] == 2:
            proba = output[0][1]
        else:
            proba = output[0] if output.ndim == 1 else output[0][0]
        return float(proba)

    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        return {}


class ONNXInferenceStrategy(InferenceStrategy):
    """ONNX 推理策略"""

    def predict_proba(self, model, input_data: pd.DataFrame) -> float:
        output = model.run(None, {model.get_inputs()[0].name: input_data.values.astype('float32')})
        if len(output[0].shape) > 1 and output[0].shape[1] == 2:
            proba = output[0][0][1]
        else:
            proba = output[0][0] if output[0].ndim > 0 else output[0]
        return float(proba)

    def extract_feature_importance(self, model, input_features: List[str]) -> Dict[str, float]:
        return {}


INFERENCE_STRATEGIES = {
    'sklearn': SklearnInferenceStrategy(),
    'xgboost': XGBoostInferenceStrategy(),
    'lightgbm': LightGBMInferenceStrategy(),
    'catboost': CatBoostInferenceStrategy(),
    'torch': TorchInferenceStrategy(),
    'pytorch': TorchInferenceStrategy(),
    'tensorflow': TensorFlowInferenceStrategy(),
    'onnx': ONNXInferenceStrategy(),
}


def get_inference_strategy(framework: str) -> InferenceStrategy:
    """获取推理策略"""
    strategy = INFERENCE_STRATEGIES.get(framework.lower())
    if not strategy:
        raise ModelInferenceException(f"不支持的框架: {framework}")
    return strategy


# ==================== 特征分计算器 ====================

@dataclass
class FeatureScoreCalculator:
    """特征分计算器"""

    def calculate(
            self,
            features: Dict[str, Any],
            input_features: List[str],
            feature_importance: Dict[str, float],
            total_score: float,
            default_prob: float
    ) -> Dict[str, float]:
        """计算特征分"""
        if not input_features:
            return {}

        normalized_importance = self._normalize_importance(feature_importance, input_features)

        if normalized_importance:
            return self._calculate_weighted_scores(
                features, input_features, normalized_importance, total_score, default_prob
            )
        else:
            return self._calculate_equal_scores(features, input_features, total_score)

    def _normalize_importance(self, importance: Dict[str, float], input_features: List[str]) -> Dict[str, float]:
        """归一化特征重要性"""
        if not importance:
            return {}

        filtered = {k: v for k, v in importance.items() if k in input_features}
        total = sum(filtered.values())
        if total <= 0:
            return {}

        return {k: v / total for k, v in filtered.items()}

    def _calculate_weighted_scores(
            self,
            features: Dict[str, Any],
            input_features: List[str],
            importance: Dict[str, float],
            total_score: float,
            default_prob: float
    ) -> Dict[str, float]:
        """基于权重的特征分计算"""
        scores = {}

        for feat in input_features:
            weight = importance.get(feat, 0)
            impact = self._calculate_feature_impact(features.get(feat, 0), default_prob)
            score = total_score * weight * (1 + impact * 0.3)
            scores[feat] = round(score, 2)

        return scores

    def _calculate_equal_scores(self, features: Dict[str, Any], input_features: List[str], total_score: float) -> Dict[str, float]:
        """平均分配的特征分计算"""
        base_score = total_score / len(input_features)
        scores = {}

        for feat in input_features:
            value = features.get(feat, 0)
            if isinstance(value, (int, float)):
                adjustment = 1 + (value / 100) * 0.2
                adjustment = max(0.5, min(1.5, adjustment))
                scores[feat] = round(base_score * adjustment, 2)
            else:
                scores[feat] = round(base_score, 2)

        return scores

    @staticmethod
    def _calculate_feature_impact(value: Any, default_prob: float) -> float:
        """计算特征影响系数"""
        if not isinstance(value, (int, float)):
            return 0

        normalized = value / 100 if abs(value) < 1000 else 0
        normalized = max(-1, min(1, normalized))
        return normalized * (1 + default_prob)


# ==================== 评分卡转换器 ====================

@dataclass
class ScorecardConverter:
    """评分卡转换器"""

    base_score: int = 600
    pdo: int = 50
    min_score: Optional[int] = 300
    max_score: Optional[int] = 900
    direction: str = "higher_better"

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> 'ScorecardConverter':
        return cls(
            base_score=params.get('base_score', 600),
            pdo=params.get('pdo', 50),
            min_score=params.get('min_score'),
            max_score=params.get('max_score'),
            direction=params.get('direction', 'higher_better')
        )

    def convert(self, default_prob: float) -> float:
        """将违约概率转换为评分"""
        EPS = 1e-10
        p = max(min(default_prob, 1.0 - EPS), EPS)
        odds = p / (1.0 - p)
        log_odds = math.log(odds)

        if self.direction == "higher_better":
            score = self.base_score - (self.pdo / math.log(2)) * log_odds
        else:
            score = self.base_score + (self.pdo / math.log(2)) * log_odds

        if self.min_score is not None:
            score = max(score, self.min_score)
        if self.max_score is not None:
            score = min(score, self.max_score)

        return score


# ==================== 风险分析器 ====================

@dataclass
class RiskAnalyzer:
    """风险分析器"""

    def analyze(
            self,
            fraud_prob: float,
            feature_importance: Dict[str, float],
            features: Dict[str, Any],
            risk_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """分析风险"""
        risk_score = fraud_prob * 100
        risk_level = self._determine_risk_level(fraud_prob, risk_config.get('levels', {}))
        risk_factors = self._extract_risk_factors(fraud_prob, feature_importance, features)

        return {
            'risk_score': round(risk_score, 2),
            'risk_level': risk_level,
            'risk_factors': risk_factors
        }

    @staticmethod
    def _determine_risk_level(prob: float, levels: Dict[str, Dict]) -> str:
        """确定风险等级"""
        for level_name, config in levels.items():
            min_val = config.get('min', 0)
            max_val = config.get('max', 1)
            if min_val <= prob <= max_val:
                return level_name
        return "unknown"

    def _extract_risk_factors(
            self,
            fraud_prob: float,
            feature_importance: Dict[str, float],
            features: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """提取风险因素"""
        factors = []

        if fraud_prob > 0.7:
            factors.append({
                'factor': 'high_fraud_probability',
                'value': fraud_prob,
                'weight': 0.8,
                'description': f'欺诈概率过高 ({fraud_prob:.2%})'
            })

        if feature_importance:
            total = sum(feature_importance.values())
            if total > 0:
                for feat_name, importance in feature_importance.items():
                    feat_value = features.get(feat_name, 0)
                    if importance / total > 0.2 and feat_value > 0.7:
                        factors.append({
                            'factor': feat_name,
                            'value': feat_value,
                            'weight': importance / total,
                            'description': f'特征 {feat_name} 值过高'
                        })

        return factors[:5]


# ==================== 推理引擎 ====================

class InferenceEngine:
    """统一推理引擎"""

    def __init__(
            self,
            cache_size: int = 1000,
            cache_ttl: int = 3600,
            model_loader=None
    ):
        self._stats = {
            'total_inferences': 0,
            'success_inferences': 0,
            'failed_inferences': 0,
            'total_duration_ms': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self._cache = LRUCache(max_size=cache_size, ttl=cache_ttl)
        self._model_loader = model_loader or get_model_loader()
        self._key_generator = CacheKeyGenerator()
        self._feature_score_calculator = FeatureScoreCalculator()
        debug_print("InferenceEngine", f"初始化推理引擎, 缓存大小: {cache_size} 条, TTL: {cache_ttl} 秒")

    def _get_model_with_metadata(self, model_id: str, user_id: str, ip_address: str):
        """获取模型和元数据（使用公开 API）"""
        model = self._model_loader.get_model(model_id)
        if not model:
            if not self._model_loader.load_model(model_id, user_id or "system", ip_address):
                raise ModelNotFoundException(f"模型未加载或不存在: {model_id}")
            model = self._model_loader.get_model(model_id)

        metadata = self._model_loader.get_model_metadata(model_id)

        if not metadata:
            raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

        return model, metadata

    def _log_api_call(
            self,
            request_id: str,
            application_id: str,
            model_id: str,
            model_version: str,
            task_type: str,
            features: Dict,
            response: Dict,
            processing_time_ms: int,
            inference_time_ms: int,
            ip_address: str,
            api_key: str,
            user_id: str,
            status_code: int = 200,
            error: str = None
    ):
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
                    model_inference_time_ms=inference_time_ms,
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

    def _update_stats(self, success: bool, duration_ms: float):
        """更新统计信息"""
        self._stats['total_inferences'] += 1
        if success:
            self._stats['success_inferences'] += 1
        else:
            self._stats['failed_inferences'] += 1
        self._stats['total_duration_ms'] += duration_ms

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
        """评分卡模型预测"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        cache_key = self._key_generator.for_prediction(model_id, features)

        if use_cache:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self._stats['cache_hits'] += 1
                debug_print("InferenceEngine", f"缓存命中: {model_id}")

                result = {
                    **cached_result,
                    'from_cache': True,
                    'request_id': request_id,
                    'trace_id': trace_id,
                    'span_id': span_id
                }
                return result

        self._stats['cache_misses'] += 1

        with context.SpanContext("scorecard_inference"):
            try:
                model, metadata = self._get_model_with_metadata(model_id, user_id, ip_address)

                if metadata.get('task_type') != TaskType.SCORING.value:
                    raise ModelInferenceException(
                        f"模型类型不匹配: 期望 scoring, 实际 {metadata.get('task_type')}"
                    )

                input_features = metadata.get('input_features', [])
                missing = [f for f in input_features if f not in features]
                if missing:
                    raise ModelInferenceException(f"缺少必要特征: {missing}")

                ordered_features = {f: features[f] for f in input_features if f in features}
                input_data = pd.DataFrame([ordered_features])

                framework = metadata.get('framework')
                strategy = get_inference_strategy(framework)

                inference_start = time.time()
                default_prob = strategy.predict_proba(model, input_data)
                inference_time = (time.time() - inference_start) * 1000

                scorecard_params = metadata.get('model_params', {}).get('scorecard', {})
                converter = ScorecardConverter.from_params(scorecard_params)
                total_score = converter.convert(default_prob)

                feature_importance = metadata.get('feature_importance', {})
                if not feature_importance:
                    feature_importance = strategy.extract_feature_importance(model, input_features)

                feature_scores = self._feature_score_calculator.calculate(
                    features=features,
                    input_features=input_features,
                    feature_importance=feature_importance,
                    total_score=total_score,
                    default_prob=default_prob
                )

                result_data = {
                    'default_probability': round(default_prob, 4),
                    'total_score': round(total_score, 2),
                    'feature_scores': feature_scores,
                    'feature_importance': feature_importance
                }

                total_time = (time.time() - start_time) * 1000
                model_version = metadata.get('model_version', 'unknown')

                self._log_api_call(
                    request_id=request_id,
                    application_id=application_id,
                    model_id=model_id,
                    model_version=model_version,
                    task_type="scoring",
                    features=features,
                    response=result_data,
                    processing_time_ms=int(total_time),
                    inference_time_ms=int(inference_time),
                    ip_address=ip_address,
                    api_key=api_key,
                    user_id=user_id,
                    status_code=200
                )

                self._update_stats(True, total_time)

                log_audit(
                    action=AuditAction.MODEL_INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "model_version": model_version,
                        "application_id": application_id,
                        "task_type": "scoring",
                        "default_probability": result_data['default_probability'],
                        "total_score": result_data['total_score'],
                        "processing_time_ms": round(total_time, 2),
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

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
                    **result_data,
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
                    cache_value = {
                        'default_probability': result_data['default_probability'],
                        'total_score': result_data['total_score'],
                        'feature_scores': result_data['feature_scores'],
                        'feature_importance': result_data.get('feature_importance', {}),
                        'model_id': model_id,
                        'model_version': model_version,
                        'application_id': application_id,
                        'processing_time_ms': result['processing_time_ms'],
                        'timestamp': result['timestamp']
                    }
                    self._cache.set(cache_key, cache_value)

                debug_print("InferenceEngine", f"评分卡推理成功: {model_id}, 耗时: {total_time:.2f}ms")
                return result

            except Exception as e:
                total_time = (time.time() - start_time) * 1000
                self._update_stats(False, total_time)

                error_trace = traceback.format_exc()
                model_version = metadata.get('model_version', 'unknown') if 'metadata' in locals() else 'unknown'

                self._log_api_call(
                    request_id=request_id,
                    application_id=application_id,
                    model_id=model_id,
                    model_version=model_version,
                    task_type="scoring",
                    features=features,
                    response=None,
                    processing_time_ms=int(total_time),
                    inference_time_ms=0,
                    ip_address=ip_address,
                    api_key=api_key,
                    user_id=user_id,
                    status_code=500,
                    error=str(e)
                )

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
        """反欺诈模型预测"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        cache_key = self._key_generator.for_prediction(model_id, features)

        if use_cache:
            cached_result = self._cache.get(cache_key)
            if cached_result is not None:
                self._stats['cache_hits'] += 1
                debug_print("InferenceEngine", f"缓存命中: {model_id}")

                result = {
                    **cached_result,
                    'from_cache': True,
                    'request_id': request_id,
                    'trace_id': trace_id,
                    'span_id': span_id
                }
                return result

        self._stats['cache_misses'] += 1

        with context.SpanContext("fraud_inference"):
            try:
                model, metadata = self._get_model_with_metadata(model_id, user_id, ip_address)

                if metadata.get('task_type') != TaskType.FRAUD_DETECTION.value:
                    raise ModelInferenceException(
                        f"模型类型不匹配: 期望 fraud_detection, 实际 {metadata.get('task_type')}"
                    )

                input_features = metadata.get('input_features', [])
                missing = [f for f in input_features if f not in features]
                if missing:
                    raise ModelInferenceException(f"缺少必要特征: {missing}")

                ordered_features = {f: features[f] for f in input_features if f in features}
                input_data = pd.DataFrame([ordered_features])

                framework = metadata.get('framework')
                strategy = get_inference_strategy(framework)

                inference_start = time.time()
                fraud_prob = strategy.predict_proba(model, input_data)
                inference_time = (time.time() - inference_start) * 1000

                feature_importance = metadata.get('feature_importance', {})
                if not feature_importance:
                    feature_importance = strategy.extract_feature_importance(model, input_features)

                risk_config = metadata.get('model_params', {}).get('risk_config', {})
                risk_analyzer = RiskAnalyzer()
                risk_result = risk_analyzer.analyze(
                    fraud_prob=fraud_prob,
                    feature_importance=feature_importance,
                    features=features,
                    risk_config=risk_config
                )

                result_data = {
                    'fraud_probability': round(fraud_prob, 4),
                    **risk_result
                }

                total_time = (time.time() - start_time) * 1000
                model_version = metadata.get('model_version', 'unknown')

                self._log_api_call(
                    request_id=request_id,
                    application_id=application_id,
                    model_id=model_id,
                    model_version=model_version,
                    task_type="fraud_detection",
                    features=features,
                    response=result_data,
                    processing_time_ms=int(total_time),
                    inference_time_ms=int(inference_time),
                    ip_address=ip_address,
                    api_key=api_key,
                    user_id=user_id,
                    status_code=200
                )

                self._update_stats(True, total_time)

                log_audit(
                    action=AuditAction.MODEL_INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "model_version": model_version,
                        "application_id": application_id,
                        "task_type": "fraud_detection",
                        "fraud_probability": result_data['fraud_probability'],
                        "risk_score": result_data['risk_score'],
                        "risk_level": result_data['risk_level'],
                        "processing_time_ms": round(total_time, 2),
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

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
                    **result_data,
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
                    cache_value = {
                        'fraud_probability': result_data['fraud_probability'],
                        'risk_score': result_data['risk_score'],
                        'risk_level': result_data['risk_level'],
                        'risk_factors': result_data['risk_factors'],
                        'model_id': model_id,
                        'model_version': model_version,
                        'application_id': application_id,
                        'processing_time_ms': result['processing_time_ms'],
                        'timestamp': result['timestamp']
                    }
                    self._cache.set(cache_key, cache_value)

                debug_print("InferenceEngine", f"反欺诈推理成功: {model_id}, 耗时: {total_time:.2f}ms")
                return result

            except Exception as e:
                total_time = (time.time() - start_time) * 1000
                self._update_stats(False, total_time)

                error_trace = traceback.format_exc()
                model_version = metadata.get('model_version', 'unknown') if 'metadata' in locals() else 'unknown'

                self._log_api_call(
                    request_id=request_id,
                    application_id=application_id,
                    model_id=model_id,
                    model_version=model_version,
                    task_type="fraud_detection",
                    features=features,
                    response=None,
                    processing_time_ms=int(total_time),
                    inference_time_ms=0,
                    ip_address=ip_address,
                    api_key=api_key,
                    user_id=user_id,
                    status_code=500,
                    error=str(e)
                )

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
        """批量预测"""
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        batch_start_time = time.time()

        if len(features_list) != len(application_ids):
            raise ValueError("features_list 和 application_ids 长度必须一致")

        results = []
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

        log_audit(
            action=AuditAction.MODEL_BATCH_INFERENCE.value,
            user_id=user_id or "system",
            ip_address=ip_address,
            details={
                "model_id": model_id,
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

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats['total_inferences'] > 0:
            stats['avg_duration_ms'] = stats['total_duration_ms'] / stats['total_inferences']
            stats['success_rate'] = stats['success_inferences'] / stats['total_inferences']
        return stats

    def clear_cache(self, model_id: Optional[str] = None):
        """清除缓存"""
        if model_id:
            prefix = self._key_generator.for_model(model_id)
            removed = self._cache.delete_by_prefix(prefix)
            debug_print("InferenceEngine", f"清除模型缓存: {model_id}, 移除 {removed} 条")
        else:
            self._cache.clear()
            debug_print("InferenceEngine", "清除所有缓存")

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        total_requests = self._stats['cache_hits'] + self._stats['cache_misses']
        cache_stats = self._cache.get_stats()

        return {
            'cache_size': cache_stats['size'],
            'cache_max_size': cache_stats['max_size'],
            'cache_ttl': cache_stats['ttl'],
            'cache_hits': self._stats['cache_hits'],
            'cache_misses': self._stats['cache_misses'],
            'cache_hit_rate': self._stats['cache_hits'] / total_requests if total_requests > 0 else 0,
        }


# ==================== 工厂函数 ====================

def get_inference_engine():
    """获取推理引擎实例"""
    return InferenceEngine()