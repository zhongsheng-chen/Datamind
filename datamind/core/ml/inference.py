# Datamind/datamind/core/ml/inference.py
import time
import traceback
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from datamind.core.logging import log_manager, get_request_id, debug_print
from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.exceptions import ModelInferenceException, ModelNotFoundException
from datamind.core.db.database import get_db
from datamind.core.db.models import ApiCallLog
from datamind.core.domain.enums import TaskType, AuditAction


class InferenceEngine:
    """统一推理引擎 - 支持评分卡和反欺诈模型"""

    def __init__(self):
        self._stats = {
            'total_inferences': 0,
            'success_inferences': 0,
            'failed_inferences': 0,
            'total_duration_ms': 0
        }
        debug_print("InferenceEngine", "初始化推理引擎")

    def predict_scorecard(
            self,
            model_id: str,
            features: Dict[str, Any],
            application_id: str,
            user_id: Optional[str] = None,
            ip_address: Optional[str] = None,
            api_key: Optional[str] = None
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

        返回:
            Dict: {
                'total_score': float,  # 总评分
                'feature_scores': Dict[str, float],  # 特征分详情
                'model_id': str,
                'model_version': str,
                'application_id': str,
                'processing_time_ms': float,
                'timestamp': str
            }
        """
        request_id = get_request_id()
        start_time = time.time()

        try:
            # 获取模型
            model = model_loader.get_model(model_id)
            if not model:
                # 尝试加载模型
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
            result = self._do_inference(model, input_data, metadata.framework)
            inference_time = (time.time() - inference_start) * 1000

            # 解析评分卡结果
            score_result = self._parse_scorecard_result(
                result, metadata.output_schema, features
            )

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
            log_manager.log_audit(
                action=AuditAction.INFERENCE.value,
                user_id=user_id or "system",
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "model_version": metadata.model_version,
                    "application_id": application_id,
                    "task_type": "scoring",
                    "total_score": score_result['total_score'],
                    "processing_time_ms": round(total_time, 2)
                },
                request_id=request_id
            )

            debug_print("InferenceEngine", f"评分卡推理成功: {model_id}, 耗时: {total_time:.2f}ms")

            return {
                **score_result,
                'model_id': model_id,
                'model_version': metadata.model_version,
                'application_id': application_id,
                'processing_time_ms': round(total_time, 2),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            self._update_stats(False, total_time)

            error_trace = traceback.format_exc()

            # 记录错误日志
            log_manager.log_audit(
                action=AuditAction.INFERENCE.value,
                user_id=user_id or "system",
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "application_id": application_id,
                    "task_type": "scoring",
                    "error": str(e),
                    "traceback": error_trace,
                    "processing_time_ms": round(total_time, 2)
                },
                reason=str(e),
                request_id=request_id
            )

            # 记录API调用失败日志
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
            api_key: Optional[str] = None
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

        返回:
            Dict: {
                'fraud_probability': float,  # 欺诈概率
                'risk_score': float,  # 风险评分
                'risk_factors': List[Dict],  # 风险因素
                'model_id': str,
                'model_version': str,
                'application_id': str,
                'processing_time_ms': float,
                'timestamp': str
            }
        """
        request_id = get_request_id()
        start_time = time.time()

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
            result = self._do_inference(model, input_data, metadata.framework)
            inference_time = (time.time() - inference_start) * 1000

            # 解析反欺诈结果
            fraud_result = self._parse_fraud_result(
                result, metadata.output_schema, features
            )

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
            log_manager.log_audit(
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
                    "processing_time_ms": round(total_time, 2)
                },
                request_id=request_id
            )

            debug_print("InferenceEngine", f"反欺诈推理成功: {model_id}, 耗时: {total_time:.2f}ms")

            return {
                **fraud_result,
                'model_id': model_id,
                'model_version': metadata.model_version,
                'application_id': application_id,
                'processing_time_ms': round(total_time, 2),
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            total_time = (time.time() - start_time) * 1000
            self._update_stats(False, total_time)

            error_trace = traceback.format_exc()

            log_manager.log_audit(
                action=AuditAction.INFERENCE.value,
                user_id=user_id or "system",
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "application_id": application_id,
                    "task_type": "fraud_detection",
                    "error": str(e),
                    "traceback": error_trace,
                    "processing_time_ms": round(total_time, 2)
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

    def _parse_scorecard_result(self, raw_result, output_schema: Dict, features: Dict) -> Dict:
        """解析评分卡结果"""
        try:
            # 评分卡模型通常返回总分
            if isinstance(raw_result, (np.ndarray, list)):
                total_score = float(raw_result[0] if len(raw_result) > 0 else 0)
            else:
                total_score = float(raw_result)

            # 计算特征分（这里简化处理，实际需要根据模型类型计算）
            feature_scores = {}
            for feature_name, feature_value in features.items():
                # 这里需要根据具体模型计算特征贡献
                # 简化处理：按特征值比例分配
                feature_scores[feature_name] = float(feature_value) if isinstance(feature_value, (int, float)) else 0

            return {
                'total_score': total_score,
                'feature_scores': feature_scores
            }
        except Exception as e:
            raise ModelInferenceException(f"解析评分卡结果失败: {str(e)}")

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


# 全局推理引擎实例
inference_engine = InferenceEngine()