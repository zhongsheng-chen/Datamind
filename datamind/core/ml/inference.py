# datamind/core/ml/inference.py

"""推理引擎

提供统一的模型推理服务，支持评分卡模型和反欺诈模型。

核心功能：
  - predict_scorecard: 评分卡模型预测，返回违约概率和信用评分
  - predict_fraud: 反欺诈模型预测，返回欺诈概率和风险评分
  - predict_batch: 批量预测，提高吞吐量
  - explain_prediction: 特征重要性解释（SHAP/特征贡献度）
  - 输入特征验证：自动验证输入特征是否完整
  - 自动模型加载：如果模型未加载，自动触发加载
  - 性能监控：记录推理耗时和统计信息
  - API调用日志：记录每次推理请求到数据库
  - 审计日志：记录所有推理操作
  - 结果缓存：缓存推理结果，避免重复计算
  - 链路追踪：完整的 span 追踪

支持的框架：
  - sklearn / xgboost / lightgbm / catboost
  - torch / tensorflow / onnx
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
from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print


class LRUCache:
    """LRU 缓存实现"""

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化 LRU 缓存

        参数:
            max_size: 最大缓存数量
            ttl: 缓存过期时间（秒）
        """
        self.cache = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if key not in self.cache:
            return None

        value, timestamp = self.cache[key]
        if (datetime.now() - timestamp).total_seconds() > self.ttl:
            del self.cache[key]
            return None

        # 移动到末尾（最近使用）
        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any):
        """设置缓存值"""
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            # 移除最久未使用的
            self.cache.popitem(last=False)

        self.cache[key] = (value, datetime.now())

    def clear(self):
        """清空缓存"""
        self.cache.clear()

    def size(self) -> int:
        """获取缓存大小"""
        return len(self.cache)


class InferenceEngine:
    """统一推理引擎 - 支持评分卡和反欺诈模型"""

    def __init__(self, cache_size: int = 1000, cache_ttl: int = 3600):
        """
        初始化推理引擎

        参数:
            cache_size: 结果缓存大小
            cache_ttl: 缓存过期时间（秒）
        """
        self._stats = {
            'total_inferences': 0,
            'success_inferences': 0,
            'failed_inferences': 0,
            'total_duration_ms': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self._cache = LRUCache(max_size=cache_size, ttl=cache_ttl)
        debug_print("InferenceEngine", f"初始化推理引擎, 缓存大小: {cache_size}, TTL: {cache_ttl}s")

    def _get_cache_key(self, model_id: str, features: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 对特征进行排序和序列化
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
            Dict: {
                'default_probability': float,  # 违约概率 (0-1)
                'total_score': float,          # 信用评分 (通常 300-900)
                'feature_scores': Dict[str, float],  # 特征分详情
                'feature_importance': Dict[str, float],  # 特征重要性
                'model_id': str,
                'model_version': str,
                'application_id': str,
                'processing_time_ms': float,
                'timestamp': str,
                'from_cache': bool
            }
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        # 检查缓存
        cache_key = self._get_cache_key(model_id, features)
        if use_cache:
            cached_result = self._cache.get(cache_key)
            if cached_result:
                self._stats['cache_hits'] += 1
                debug_print("InferenceEngine", f"缓存命中: {model_id}")
                cached_result['from_cache'] = True
                return cached_result

        self._stats['cache_misses'] += 1

        # 创建推理 span
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
                metadata = model_info.get('metadata')

                if not metadata:
                    raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

                # 验证任务类型
                if metadata.task_type != TaskType.SCORING.value:
                    raise ModelInferenceException(
                        f"模型类型不匹配: 期望 scoring, 实际 {metadata.task_type}"
                    )

                # 验证输入特征
                self._validate_features(features, metadata.input_features)

                # 准备输入数据
                input_data = self._prepare_input(features, metadata.input_features)

                # 执行推理
                inference_start = time.time()
                raw_result = self._do_inference(model, input_data, metadata.framework)
                inference_time = (time.time() - inference_start) * 1000

                # 计算特征重要性
                feature_importance = self._calculate_feature_importance(
                    model, input_data, metadata.framework, features
                )

                # 解析评分卡结果
                score_result = self._parse_scorecard_result(
                    raw_result, metadata.output_schema, features, metadata.model_params
                )
                score_result['feature_importance'] = feature_importance

                total_time = (time.time() - start_time) * 1000

                # 记录API调用日志
                self._log_api_call(
                    application_id=application_id,
                    model_id=model_id,
                    model_version=metadata.model_version,
                    task_type=TaskType.SCORING.value,
                    endpoint="/api/v1/scoring/predict",
                    request_data=features,
                    response_data=score_result,
                    processing_time_ms=total_time,
                    model_inference_time_ms=inference_time,
                    status_code=200,
                    ip_address=ip_address,
                    user_id=user_id,
                    api_key=api_key,
                    request_id=request_id
                )

                # 更新统计
                self._update_stats(True, total_time)

                # 记录审计日志
                log_audit(
                    action=AuditAction.INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "model_version": metadata.model_version,
                        "application_id": application_id,
                        "task_type": "scoring",
                        "default_probability": score_result['default_probability'],
                        "total_score": score_result['total_score'],
                        "processing_time_ms": round(total_time, 2),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                result = {
                    **score_result,
                    'model_id': model_id,
                    'model_version': metadata.model_version,
                    'application_id': application_id,
                    'processing_time_ms': round(total_time, 2),
                    'timestamp': datetime.now().isoformat(),
                    'from_cache': False
                }

                # 缓存结果
                if use_cache:
                    self._cache.set(cache_key, result)

                debug_print("InferenceEngine", f"评分卡推理成功: {model_id}, 耗时: {total_time:.2f}ms")

                return result

            except Exception as e:
                total_time = (time.time() - start_time) * 1000
                self._update_stats(False, total_time)

                error_trace = traceback.format_exc()

                log_audit(
                    action=AuditAction.INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "application_id": application_id,
                        "task_type": "scoring",
                        "error": str(e),
                        "traceback": error_trace,
                        "processing_time_ms": round(total_time, 2),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    reason=str(e),
                    request_id=request_id
                )

                self._log_api_call(
                    application_id=application_id,
                    model_id=model_id,
                    model_version=metadata.model_version if 'metadata' in locals() else 'unknown',
                    task_type=TaskType.SCORING.value,
                    endpoint="/api/v1/scoring/predict",
                    request_data=features,
                    response_data=None,
                    processing_time_ms=total_time,
                    status_code=500,
                    error_message=str(e),
                    error_traceback=error_trace,
                    ip_address=ip_address,
                    user_id=user_id,
                    api_key=api_key,
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
            Dict: {
                'fraud_probability': float,  # 欺诈概率
                'risk_score': float,  # 风险评分
                'risk_factors': List[Dict],  # 风险因素
                'feature_importance': Dict[str, float],  # 特征重要性
                'model_id': str,
                'model_version': str,
                'application_id': str,
                'processing_time_ms': float,
                'timestamp': str,
                'from_cache': bool
            }
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        # 检查缓存
        cache_key = self._get_cache_key(model_id, features)
        if use_cache:
            cached_result = self._cache.get(cache_key)
            if cached_result:
                self._stats['cache_hits'] += 1
                debug_print("InferenceEngine", f"缓存命中: {model_id}")
                cached_result['from_cache'] = True
                return cached_result

        self._stats['cache_misses'] += 1

        # 创建推理 span
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
                metadata = model_info.get('metadata')

                if not metadata:
                    raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

                # 验证任务类型
                if metadata.task_type != TaskType.FRAUD_DETECTION.value:
                    raise ModelInferenceException(
                        f"模型类型不匹配: 期望 fraud_detection, 实际 {metadata.task_type}"
                    )

                # 验证输入特征
                self._validate_features(features, metadata.input_features)

                # 准备输入数据
                input_data = self._prepare_input(features, metadata.input_features)

                # 执行推理
                inference_start = time.time()
                raw_result = self._do_inference(model, input_data, metadata.framework)
                inference_time = (time.time() - inference_start) * 1000

                # 计算特征重要性
                feature_importance = self._calculate_feature_importance(
                    model, input_data, metadata.framework, features
                )

                # 解析反欺诈结果
                fraud_result = self._parse_fraud_result(
                    raw_result, metadata.output_schema, features
                )
                fraud_result['feature_importance'] = feature_importance

                total_time = (time.time() - start_time) * 1000

                # 记录API调用日志
                self._log_api_call(
                    application_id=application_id,
                    model_id=model_id,
                    model_version=metadata.model_version,
                    task_type=TaskType.FRAUD_DETECTION.value,
                    endpoint="/api/v1/fraud/predict",
                    request_data=features,
                    response_data=fraud_result,
                    processing_time_ms=total_time,
                    model_inference_time_ms=inference_time,
                    status_code=200,
                    ip_address=ip_address,
                    user_id=user_id,
                    api_key=api_key,
                    request_id=request_id
                )

                # 更新统计
                self._update_stats(True, total_time)

                # 记录审计日志
                log_audit(
                    action=AuditAction.INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "model_version": metadata.model_version,
                        "application_id": application_id,
                        "task_type": "fraud_detection",
                        "fraud_probability": fraud_result['fraud_probability'],
                        "risk_score": fraud_result['risk_score'],
                        "processing_time_ms": round(total_time, 2),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                result = {
                    **fraud_result,
                    'model_id': model_id,
                    'model_version': metadata.model_version,
                    'application_id': application_id,
                    'processing_time_ms': round(total_time, 2),
                    'timestamp': datetime.now().isoformat(),
                    'from_cache': False
                }

                # 缓存结果
                if use_cache:
                    self._cache.set(cache_key, result)

                debug_print("InferenceEngine", f"反欺诈推理成功: {model_id}, 耗时: {total_time:.2f}ms")

                return result

            except Exception as e:
                total_time = (time.time() - start_time) * 1000
                self._update_stats(False, total_time)

                error_trace = traceback.format_exc()

                log_audit(
                    action=AuditAction.INFERENCE.value,
                    user_id=user_id or "system",
                    ip_address=ip_address,
                    details={
                        "model_id": model_id,
                        "application_id": application_id,
                        "task_type": "fraud_detection",
                        "error": str(e),
                        "traceback": error_trace,
                        "processing_time_ms": round(total_time, 2),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    reason=str(e),
                    request_id=request_id
                )

                self._log_api_call(
                    application_id=application_id,
                    model_id=model_id,
                    model_version=metadata.model_version if 'metadata' in locals() else 'unknown',
                    task_type=TaskType.FRAUD_DETECTION.value,
                    endpoint="/api/v1/fraud/predict",
                    request_data=features,
                    response_data=None,
                    processing_time_ms=total_time,
                    status_code=500,
                    error_message=str(e),
                    error_traceback=error_trace,
                    ip_address=ip_address,
                    user_id=user_id,
                    api_key=api_key,
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
        if len(features_list) != len(application_ids):
            raise ValueError("features_list 和 application_ids 长度必须一致")

        results = []
        start_time = time.time()

        # 批量获取模型（只加载一次）
        model = model_loader.get_model(model_id)
        if not model:
            if not model_loader.load_model(model_id, user_id or "system", ip_address):
                raise ModelNotFoundException(f"模型未加载或不存在: {model_id}")
            model = model_loader.get_model(model_id)

        model_info = model_loader._loaded_models.get(model_id, {})
        metadata = model_info.get('metadata')

        if not metadata:
            raise ModelNotFoundException(f"模型元数据不存在: {model_id}")

        # 批量预测
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

            except Exception as e:
                # 单个失败不影响整体
                results.append({
                    'error': str(e),
                    'application_id': app_id,
                    'success': False
                })

        total_time = (time.time() - start_time) * 1000
        debug_print("InferenceEngine", f"批量预测完成: {len(results)} 条, 耗时: {total_time:.2f}ms")

        return results

    def _calculate_feature_importance(
            self,
            model,
            input_data: pd.DataFrame,
            framework: str,
            features: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        计算特征重要性

        支持的方法:
            - XGBoost/LightGBM: 内置 feature_importances_
            - Sklearn: 内置 feature_importances_ 或 coef_
            - 其他框架: 使用 SHAP (如果可用)
        """
        try:
            # 方法1: 使用模型内置的特征重要性
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
                feature_names = list(input_data.columns)
                if len(importances) == len(feature_names):
                    return dict(zip(feature_names, importances))

            # 方法2: 使用线性模型的系数
            if hasattr(model, 'coef_'):
                coef = model.coef_
                if len(coef.shape) == 1:
                    feature_names = list(input_data.columns)
                    # 取绝对值并归一化
                    abs_coef = np.abs(coef)
                    normalized = abs_coef / abs_coef.sum()
                    return dict(zip(feature_names, normalized))

            # 方法3: 使用 SHAP (如果可用)
            try:
                import shap
                explainer = shap.TreeExplainer(model)
                shap_values = explainer.shap_values(input_data)
                # 取绝对值并平均
                mean_shap = np.abs(shap_values).mean(axis=0)
                feature_names = list(input_data.columns)
                return dict(zip(feature_names, mean_shap / mean_shap.sum()))
            except ImportError:
                pass

            # 方法4: 使用排列重要性（降级方案）
            return self._calculate_permutation_importance(model, input_data)

        except Exception as e:
            debug_print("InferenceEngine", f"特征重要性计算失败: {e}")
            # 返回均匀分布
            feature_names = list(input_data.columns)
            uniform_weight = 1.0 / len(feature_names) if feature_names else 0
            return {name: uniform_weight for name in feature_names}

    def _calculate_permutation_importance(
            self,
            model,
            input_data: pd.DataFrame,
            n_repeats: int = 5
    ) -> Dict[str, float]:
        """
        计算排列重要性（降级方案）

        通过随机打乱特征列，观察预测结果的变化
        """
        try:
            # 原始预测
            base_pred = model.predict(input_data)

            importances = {}
            for col in input_data.columns:
                scores = []
                for _ in range(n_repeats):
                    # 复制数据并打乱指定列
                    permuted_data = input_data.copy()
                    permuted_data[col] = np.random.permutation(permuted_data[col].values)

                    # 打乱后的预测
                    perm_pred = model.predict(permuted_data)

                    # 计算性能下降（MSE）
                    mse = np.mean((base_pred - perm_pred) ** 2)
                    scores.append(mse)

                importances[col] = np.mean(scores)

            # 归一化
            total = sum(importances.values())
            if total > 0:
                importances = {k: v / total for k, v in importances.items()}

            return importances

        except Exception as e:
            debug_print("InferenceEngine", f"排列重要性计算失败: {e}")
            return {}

    def _validate_features(self, features: Dict, required_features: List[str]):
        """验证输入特征"""
        missing = [f for f in required_features if f not in features]
        if missing:
            raise ModelInferenceException(f"缺少必要特征: {missing}")

    def _prepare_input(self, features: Dict, input_features: List[str]) -> Union[pd.DataFrame, np.ndarray, Dict]:
        """准备输入数据"""
        # 按顺序提取特征
        ordered_features = {f: features[f] for f in input_features if f in features}
        # 转换为DataFrame
        return pd.DataFrame([ordered_features])

    def _do_inference(self, model, input_data, framework: str) -> Any:
        """执行具体推理"""
        try:
            if framework in ['sklearn', 'xgboost', 'lightgbm', 'catboost']:
                return model.predict(input_data)
            elif framework == 'torch':
                import torch
                with torch.no_grad():
                    return model(torch.tensor(input_data.values)).numpy()
            elif framework == 'tensorflow':
                return model.predict(input_data)
            elif framework == 'onnx':
                return model.run(None, {model.get_inputs()[0].name: input_data.values.astype('float32')})
            else:
                raise ModelInferenceException(f"不支持的框架: {framework}")
        except Exception as e:
            raise ModelInferenceException(f"推理执行失败: {str(e)}")

    def _parse_scorecard_result(
            self,
            raw_result,
            output_schema: Dict,
            features: Dict,
            model_params: Dict = None
    ) -> Dict:
        """
        解析评分卡结果，返回违约概率和信用评分

        参数:
            raw_result: 模型原始输出
            output_schema: 输出格式定义
            features: 输入特征
            model_params: 模型参数（包含评分卡转换参数）

        返回:
            Dict: {
                'default_probability': float,  # 违约概率
                'total_score': float,          # 信用评分
                'feature_scores': Dict[str, float]
            }
        """
        try:
            # 获取模型原始输出（通常是违约概率）
            if isinstance(raw_result, (np.ndarray, list)):
                default_prob = float(raw_result[0] if len(raw_result) > 0 else 0)
            else:
                default_prob = float(raw_result)

            # 从模型参数获取评分卡转换参数
            scorecard_params = model_params.get('scorecard', {}) if model_params else {}

            # 计算信用评分
            total_score = self._convert_probability_to_score(
                default_prob,
                scorecard_params
            )

            # 计算特征分（这里简化处理，实际需要根据模型类型计算）
            feature_scores = {}
            for feature_name, feature_value in features.items():
                feature_scores[feature_name] = float(feature_value) if isinstance(feature_value, (int, float)) else 0

            return {
                'default_probability': round(default_prob, 4),
                'total_score': round(total_score, 2),
                'feature_scores': feature_scores
            }
        except Exception as e:
            raise ModelInferenceException(f"解析评分卡结果失败: {str(e)}")

    def _convert_probability_to_score(
            self,
            probability: float,
            params: Dict = None
    ) -> float:
        """
        将违约概率转换为信用评分

        评分卡公式:
            - higher_better: Score = Base Score - PDO * (log odds) / ln(2)
            - lower_better: Score = Base Score + PDO * (log odds) / ln(2)

        其中 log odds = ln(p / (1-p))

        参数:
            probability: 违约概率 (0-1)
            params: 评分卡参数
                - base_score: 基准分 (默认 600)
                - pdo: Points to Double the Odds (默认 50)
                - min_score: 最低分 (默认 300)
                - max_score: 最高分 (默认 900)
                - direction: 'higher_better' 或 'lower_better'
                    - higher_better: 分数越高代表信用越好，概率越高分数越低
                    - lower_better: 分数越低代表信用越好，概率越高分数越高

        返回:
            信用评分
        """
        if params is None:
            params = {}

        # 默认参数
        base_score = params.get('base_score', 600)
        pdo = params.get('pdo', 50)
        min_score = params.get('min_score', 300)
        max_score = params.get('max_score', 900)
        direction = params.get('direction', 'higher_better')

        # EPS 用于避免 log(0) 或 log(inf)
        EPS = 1e-10

        # 限制概率范围，避免边界值
        p = max(min(float(probability), 1.0 - EPS), EPS)

        # 计算 odds (违约几率)
        odds = p / (1.0 - p)

        # 计算 log odds (对数几率)
        import math
        log_odds = math.log(odds)

        # 根据方向计算分数
        if direction == "higher_better":
            # 分数越高越好：高概率 -> 高风险 -> 分数低
            # 公式: Score = Base Score - PDO * (log odds) / ln(2)
            # 当 p=0.5, log_odds=0, score=base_score
            # 当 p<0.5, log_odds<0, score > base_score (好客户分数高)
            # 当 p>0.5, log_odds>0, score < base_score (坏客户分数低)
            score = base_score - (pdo / math.log(2)) * log_odds
        else:  # lower_better
            # 分数越低越好：高概率 -> 高风险 -> 分数高
            # 公式: Score = Base Score + PDO * (log odds) / ln(2)
            # 当 p=0.5, log_odds=0, score=base_score
            # 当 p<0.5, log_odds<0, score < base_score (好客户分数低)
            # 当 p>0.5, log_odds>0, score > base_score (坏客户分数高)
            score = base_score + (pdo / math.log(2)) * log_odds

        # 限定上下界
        if min_score is not None:
            score = max(score, min_score)
        if max_score is not None:
            score = min(score, max_score)

        return score

    def _parse_fraud_result(self, raw_result, output_schema: Dict, features: Dict) -> Dict:
        """解析反欺诈结果"""
        try:
            # 反欺诈模型通常返回概率
            if isinstance(raw_result, (np.ndarray, list)):
                fraud_prob = float(raw_result[0] if len(raw_result) > 0 else 0)
            else:
                fraud_prob = float(raw_result)

            # 计算风险评分（0-100）
            risk_score = fraud_prob * 100

            # 识别风险因素（简化处理）
            risk_factors = []
            if fraud_prob > 0.7:
                risk_factors.append({
                    'factor': 'high_fraud_probability',
                    'value': fraud_prob,
                    'weight': 0.8
                })

            return {
                'fraud_probability': round(fraud_prob, 4),
                'risk_score': round(risk_score, 2),
                'risk_factors': risk_factors
            }
        except Exception as e:
            raise ModelInferenceException(f"解析反欺诈结果失败: {str(e)}")

    def _log_api_call(self, **kwargs):
        """记录API调用日志到数据库"""
        try:
            with get_db() as session:
                log = ApiCallLog(
                    request_id=kwargs.get('request_id', ''),
                    application_id=kwargs.get('application_id', ''),
                    model_id=kwargs.get('model_id', ''),
                    model_version=kwargs.get('model_version', ''),
                    task_type=kwargs.get('task_type', ''),
                    endpoint=kwargs.get('endpoint', ''),
                    request_data=kwargs.get('request_data'),
                    response_data=kwargs.get('response_data'),
                    processing_time_ms=int(kwargs.get('processing_time_ms', 0)),
                    model_inference_time_ms=int(kwargs.get('model_inference_time_ms', 0)),
                    status_code=kwargs.get('status_code', 200),
                    error_message=kwargs.get('error_message'),
                    error_traceback=kwargs.get('error_traceback'),
                    ip_address=kwargs.get('ip_address'),
                    user_agent=kwargs.get('user_agent'),
                    api_key=kwargs.get('api_key'),
                    user_id=kwargs.get('user_id')
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

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = self._stats.copy()
        if stats['total_inferences'] > 0:
            stats['avg_duration_ms'] = stats['total_duration_ms'] / stats['total_inferences']
            stats['success_rate'] = stats['success_inferences'] / stats['total_inferences']
        return stats

    def clear_cache(self, model_id: Optional[str] = None):
        """
        清除缓存

        参数:
            model_id: 如果指定，只清除该模型的缓存
        """
        if model_id:
            # 清除指定模型的缓存
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
        """获取缓存统计信息"""
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