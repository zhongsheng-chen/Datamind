# Datamind/datamind/serving/base.py
import bentoml
from bentoml.io import JSON
import numpy as np
import pandas as pd
from typing import Dict, Any, List
from datetime import datetime
import traceback
import math
from datamind.core import log_manager, get_request_id, debug_print
from datamind.core.ml.model_loader import model_loader
from datamind.core.ml.model_registry import model_registry
from datamind.core.db.database import get_db
from datamind.core import ApiCallLog
from datamind.core import TaskType

class ScoreTransformer:
    """
    通用打分引擎：根据模型输出概率和请求配置计算信用评分。

    默认逻辑：
      - 高概率代表高风险（分数越低）
      - 评分方向：lower_better（可通过 request["scoring"]["direction"] 改为 higher_better）

    支持配置项：
      - base_score: 基准分（默认 600）
      - pdo: 每翻倍赔率对应的分数变化（默认 50）
      - min_score: 最低分（默认 None，不限制）
      - max_score: 最高分（默认 None，不限制）
      - direction: "lower_better"（默认）或 "higher_better" . lower_better 表示高概率，高风险，分数低
    """

    DEFAULT_BASE_SCORE = 600
    DEFAULT_MIN_SCORE = 320
    DEFAULT_MAX_SCORE = 960
    DEFAULT_DIRECTION = "lower_better"
    DEFAULT_PDO = 50
    _EPS = 1e-6

    @classmethod
    def _extract_params(cls, request: dict):
        """统一从 request 中提取参数"""
        scoring = {}
        if isinstance(request, dict):
            scoring = request.get("scoring", {}) if isinstance(request.get("scoring", {}), dict) else {}
            base_score = scoring.get("base_score", request.get("base_score", cls.DEFAULT_BASE_SCORE))
            pdo = scoring.get("pdo", request.get("pdo", cls.DEFAULT_PDO))
            min_score = scoring.get("min_score", request.get("min_score", cls.DEFAULT_MIN_SCORE))
            max_score = scoring.get("max_score", request.get("max_score", cls.DEFAULT_MAX_SCORE))
            direction = scoring.get("direction", request.get("direction", cls.DEFAULT_DIRECTION))
        else:
            base_score, pdo = cls.DEFAULT_BASE_SCORE, cls.DEFAULT_PDO
            min_score = max_score = None
            direction = "lower_better"

        # 类型安全检查
        try:
            base_score = int(base_score)
        except Exception:
            base_score = cls.DEFAULT_BASE_SCORE

        try:
            pdo = float(pdo)
        except Exception:
            pdo = float(cls.DEFAULT_PDO)
        if pdo <= 0:
            pdo = float(cls.DEFAULT_PDO)

        try:
            min_score = int(min_score) if min_score is not None else None
        except Exception:
            min_score = None

        try:
            max_score = int(max_score) if max_score is not None else None
        except Exception:
            max_score = None

        direction = str(direction).lower().strip()
        if direction not in ("higher_better", "lower_better"):
            direction = "lower_better"

        return base_score, pdo, min_score, max_score, direction

    @classmethod
    def probability_to_score(cls, probability: float, request: dict = None) -> int:
        """根据请求配置计算概率对应的信用分"""
        base_score, pdo, min_score, max_score, direction = cls._extract_params(request or {})

        # 限制概率范围，避免 log(0)
        p = min(max(float(probability), cls._EPS), 1.0 - cls._EPS)
        odds = p / (1.0 - p)

        # 计算分数
        if direction == "lower_better":
            # 高概率 -> 高风险 -> 分数低
            score = base_score - (pdo / math.log(2)) * math.log(odds)
        else:
            # higher_better: 高概率 -> 分数高
            score = base_score + (pdo / math.log(2)) * math.log(odds)

        # 限定上下界
        if min_score is not None:
            score = max(score, min_score)
        if max_score is not None:
            score = min(score, max_score)

        return int(round(score))

    @staticmethod
    def get_feature_score(model, X):
        """
        获取模型的特征重要性或特征评分

        参数:
            model: sklearn-like 模型或 Pipeline
            X: pd.DataFrame, 输入特征（未经过 Pipeline 预处理）

        返回:
            dict: {feature_name: score}
        """
        import numpy as np

        # 如果是 Pipeline，取最后一步模型
        if hasattr(model, 'steps'):
            final_model = model.steps[-1][1]
            # 尝试获取经过预处理后的特征名
            try:
                X_transformed = model[:-1].transform(X)
                if hasattr(model[:-1], 'get_feature_names_out'):
                    feature_names = model[:-1].get_feature_names_out(X.columns)
                else:
                    feature_names = X.columns
            except Exception:
                # 如果 transform 出错，直接用原始特征
                X_transformed = X.values
                feature_names = X.columns
        else:
            final_model = model
            X_transformed = X.values
            feature_names = X.columns

        # 逻辑回归
        if hasattr(final_model, 'coef_'):
            coefs = final_model.coef_
            if coefs.ndim == 2 and coefs.shape[0] == 1:
                coefs = coefs[0]
            scores = {f: float(coef) for f, coef in zip(feature_names, coefs)}

        # 树模型
        elif hasattr(final_model, 'feature_importances_'):
            importances = final_model.feature_importances_
            scores = {f: float(imp) for f, imp in zip(feature_names, importances)}

        # 回退到 SHAP
        else:
            try:
                import shap
                explainer = shap.Explainer(final_model, X_transformed)
                shap_values = explainer(X_transformed)
                mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
                scores = {f: float(v) for f, v in zip(feature_names, mean_abs_shap)}
            except Exception:
                # 如果 SHAP 也失败
                scores = {f: None for f in feature_names}

        return scores

class BaseModelService:
    """
    基础模型服务类

    提供所有模型服务的通用功能，使用Datamind日志系统
    """

    def __init__(self, service_name: str, task_type: str):
        self.service_name = service_name
        self.task_type = task_type
        self.bento_service = None
        debug_print("BaseModelService", f"初始化服务: {service_name}, 任务类型: {task_type}")
        self._init_service()

    def _init_service(self):
        """初始化BentoML服务"""

        @bentoml.service(
            name=self.service_name,
            traffic={
                "timeout": 30,
                "concurrency": 10,
                "max_batch_size": 100
            },
            resources={
                "cpu": "1000m",
                "memory": "2Gi"
            }
        )
        class Service:
            def __init__(self):
                self.loaded_models = {}
                self.model_metadata = {}
                debug_print("BentoService", f"服务实例初始化: {self.__class__.__name__}")

            @bentoml.api(input=JSON(), output=JSON())
            async def predict(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
                """
                统一预测接口
                """
                request_id = get_request_id()
                start_time = datetime.now()

                debug_print("BentoService", f"收到预测请求: {request_id}")

                try:
                    # 验证输入
                    self._validate_input(input_data)

                    model_id = input_data['model_id']
                    application_id = input_data['application_id']
                    features = input_data['features']

                    debug_print("BentoService", f"请求详情: model={model_id}, app={application_id}")

                    # 获取模型
                    model = await self._get_model(model_id)

                    # 执行推理
                    result = await self._predict(model, features)

                    # 处理结果
                    processed_result = self._process_output(result, model_id)

                    # 记录审计日志
                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    log_manager.log_audit(
                        action="SERVING_PREDICT",
                        user_id="system",
                        ip_address="internal",
                        resource_type="model",
                        resource_id=model_id,
                        details={
                            "service": self.service_name,
                            "application_id": application_id,
                            "duration_ms": round(duration, 2)
                        },
                        request_id=request_id
                    )

                    # 记录调用日志
                    await self._log_call(
                        application_id=application_id,
                        model_id=model_id,
                        request_data=input_data,
                        response_data=processed_result,
                        start_time=start_time,
                        status_code=200
                    )

                    debug_print("BentoService", f"预测成功: {request_id}, 耗时: {duration:.2f}ms")

                    return {
                        "success": True,
                        "data": processed_result,
                        "request_id": request_id,
                        "model_id": model_id
                    }

                except Exception as e:
                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    error_trace = traceback.format_exc()

                    # 记录错误审计日志
                    log_manager.log_audit(
                        action="SERVING_PREDICT_ERROR",
                        user_id="system",
                        ip_address="internal",
                        resource_type="model",
                        resource_id=input_data.get('model_id', 'unknown'),
                        details={
                            "service": self.service_name,
                            "error": str(e),
                            "traceback": error_trace,
                            "duration_ms": round(duration, 2)
                        },
                        reason=str(e),
                        request_id=request_id
                    )

                    # 记录调用日志
                    await self._log_call(
                        application_id=input_data.get('application_id', 'unknown'),
                        model_id=input_data.get('model_id', 'unknown'),
                        request_data=input_data,
                        response_data=None,
                        start_time=start_time,
                        status_code=500,
                        error=str(e)
                    )

                    debug_print("BentoService", f"预测失败: {request_id}, 错误: {str(e)}")

                    return {
                        "success": False,
                        "error": str(e),
                        "request_id": request_id
                    }

            def _validate_input(self, input_data: Dict):
                """验证输入数据"""
                required_fields = ['model_id', 'application_id', 'features']
                for field in required_fields:
                    if field not in input_data:
                        raise ValueError(f"缺少必要字段: {field}")

            async def _get_model(self, model_id: str):
                """获取模型"""
                if model_id not in self.loaded_models:
                    debug_print("BentoService", f"加载模型: {model_id}")

                    # 从数据库获取模型信息
                    model_info = model_registry.get_model_info(model_id)
                    if not model_info:
                        error_msg = f"模型不存在: {model_id}"
                        log_manager.log_audit(
                            action="MODEL_NOT_FOUND",
                            user_id="system",
                            ip_address="internal",
                            resource_type="model",
                            resource_id=model_id,
                            details={"service": self.service_name},
                            reason=error_msg,
                            request_id=get_request_id()
                        )
                        raise ValueError(error_msg)

                    if model_info['task_type'] != self.task_type:
                        error_msg = f"模型类型不匹配: 期望 {self.task_type}, 实际 {model_info['task_type']}"
                        log_manager.log_audit(
                            action="MODEL_TYPE_MISMATCH",
                            user_id="system",
                            ip_address="internal",
                            resource_type="model",
                            resource_id=model_id,
                            details={
                                "expected": self.task_type,
                                "actual": model_info['task_type']
                            },
                            reason=error_msg,
                            request_id=get_request_id()
                        )
                        raise ValueError(error_msg)

                    # 加载模型
                    success = model_loader.load_model(model_id, "serving")
                    if not success:
                        error_msg = f"模型加载失败: {model_id}"
                        log_manager.log_audit(
                            action="MODEL_LOAD_FAILED",
                            user_id="system",
                            ip_address="internal",
                            resource_type="model",
                            resource_id=model_id,
                            details={"service": self.service_name},
                            reason=error_msg,
                            request_id=get_request_id()
                        )
                        raise ValueError(error_msg)

                    self.loaded_models[model_id] = model_loader.get_model(model_id)
                    self.model_metadata[model_id] = model_info

                    log_manager.log_audit(
                        action="MODEL_LOADED",
                        user_id="system",
                        ip_address="internal",
                        resource_type="model",
                        resource_id=model_id,
                        details={
                            "service": self.service_name,
                            "model_name": model_info.get('model_name'),
                            "model_version": model_info.get('model_version')
                        },
                        request_id=get_request_id()
                    )

                    debug_print("BentoService", f"模型加载成功: {model_id}")

                return self.loaded_models[model_id]

            async def _predict(self, model, features: Dict) -> Any:
                """执行预测（由子类实现）"""
                raise NotImplementedError

            def _process_output(self, raw_output: Any, model_id: str) -> Dict:
                """处理输出（由子类实现）"""
                raise NotImplementedError

            async def _log_call(self, **kwargs):
                """记录调用日志到数据库"""
                try:
                    duration = (datetime.now() - kwargs['start_time']).total_seconds() * 1000

                    with get_db() as session:
                        log = ApiCallLog(
                            request_id=get_request_id(),
                            application_id=kwargs['application_id'],
                            model_id=kwargs['model_id'],
                            model_version='unknown',  # TODO: 从metadata获取
                            task_type=self.task_type,
                            endpoint=f"/{self.service_name}/predict",
                            request_data=kwargs['request_data'],
                            response_data=kwargs['response_data'],
                            processing_time_ms=int(duration),
                            status_code=kwargs['status_code'],
                            error_message=kwargs.get('error')
                        )
                        session.add(log)
                        session.commit()

                    debug_print("BentoService", f"调用日志已记录: {kwargs['application_id']}")

                except Exception as e:
                    log_manager.log_audit(
                        action="LOG_CALL_FAILED",
                        user_id="system",
                        ip_address="internal",
                        details={"error": str(e)},
                        request_id=get_request_id()
                    )

        self.bento_service = Service


class ScoringModelService(BaseModelService):
    """
    评分卡模型服务 - 只返回评分和特征分，不输出决策

    使用 ScoreTransformer 进行评分转换
    """

    def __init__(self):
        super().__init__("scoring-service", TaskType.SCORING.value)
        self.score_transformer = ScoreTransformer()
        debug_print("ScoringModelService", "评分卡服务初始化完成")

    async def _predict(self, model, features: Dict) -> Any:
        """评分卡模型预测 - 获取原始概率"""
        debug_print("ScoringModelService", "执行评分卡预测")

        # 转换为DataFrame
        df = pd.DataFrame([features])

        # 执行预测 - 获取概率值
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(df)
            # 对于评分卡，通常取正类（坏样本）的概率
            if len(probabilities[0]) > 1:
                # 二分类，取正类概率（通常是类别1）
                raw_probability = probabilities[0][1]
            else:
                raw_probability = probabilities[0][0]
        elif hasattr(model, 'decision_function'):
            # 有些模型有decision_function，需要转换为概率
            raw_score = model.decision_function(df)[0]
            # 使用sigmoid转换为概率
            raw_probability = 1 / (1 + np.exp(-raw_score))
        else:
            # 直接预测，可能是概率值
            raw_probability = model.predict(df)[0]

        # 确保概率在[0,1]范围内
        raw_probability = np.clip(float(raw_probability), 0, 1)

        debug_print("ScoringModelService", f"原始概率: {raw_probability}")

        # 获取特征重要性
        try:
            feature_importance = self.score_transformer.get_feature_score(model, df)
        except Exception as e:
            debug_print("ScoringModelService", f"获取特征重要性失败: {e}")
            feature_importance = {}

        return {
            'probability': raw_probability,
            'probabilities': probabilities.tolist() if 'probabilities' in locals() else None,
            'feature_importance': feature_importance
        }

    def _process_output(self, raw_output: Any, model_id: str, input_data: Dict = None) -> Dict:
        """
        处理评分卡输出 - 使用 ScoreTransformer 计算分数

        返回格式:
        {
            "total_score": 725,               # 模型总评分（整数）
            "feature_scores": {                # 各个特征贡献的分数
                "age": 145.2,
                "income": 280.5,
                "credit_history": 195.3
            },
            "model_version": "1.0.0",          # 模型版本
            "scoring_params": {                 # 使用的评分卡参数
                "base_score": 600,
                "pdo": 50,
                "min_score": 320,
                "max_score": 960,
                "direction": "lower_better"
            }
        }
        """
        # 获取模型信息
        model_info = self.model_metadata.get(model_id, {})

        # 从raw_output获取概率
        probability = raw_output['probability']

        # 构建请求参数（从模型参数中获取评分卡配置，并允许从input_data覆盖）
        request_params = {}

        # 首先从模型参数中获取默认评分卡配置
        model_params = model_info.get('model_params', {})
        scorecard_params = model_params.get('scorecard', {})
        if scorecard_params:
            request_params['scoring'] = scorecard_params

        # 如果input_data中有scoring参数，则覆盖模型默认配置
        if input_data and 'scoring' in input_data:
            if isinstance(input_data['scoring'], dict):
                # 合并配置，请求参数优先
                if 'scoring' not in request_params:
                    request_params['scoring'] = {}
                request_params['scoring'].update(input_data['scoring'])

        # 使用 ScoreTransformer 计算总分
        total_score = self.score_transformer.probability_to_score(
            probability=probability,
            request=request_params
        )

        # 获取输入特征
        features = input_data.get('features', {}) if input_data else {}

        # 计算特征分
        feature_scores = self._calculate_feature_scores(
            total_score=total_score,
            probability=probability,
            features=features,
            feature_importance=raw_output.get('feature_importance', {}),
            request_params=request_params
        )

        # 提取使用的评分卡参数
        base_score, pdo, min_score, max_score, direction = self.score_transformer._extract_params(request_params)

        # 只返回评分和特征分，没有任何决策标签
        result = {
            'total_score': total_score,  # 已经是整数
            'feature_scores': {k: round(v, 2) for k, v in feature_scores.items() if v is not None},
            'model_version': model_info.get('model_version', 'unknown'),
            'scoring_params': {  # 返回评分卡参数供下游参考
                'base_score': base_score,
                'pdo': pdo,
                'min_score': min_score,
                'max_score': max_score,
                'direction': direction
            }
        }

        debug_print(
            "ScoringModelService",
            f"评分计算结果: 总分={result['total_score']}, "
            f"特征分数量={len(result['feature_scores'])}, "
            f"方向={direction}"
        )

        return result

    def _calculate_feature_scores(
            self,
            total_score: int,
            probability: float,
            features: Dict,
            feature_importance: Dict,
            request_params: Dict
    ) -> Dict:
        """
        计算特征分 - 基于特征重要性分解

        使用特征重要性来分配每个特征对总分的贡献
        """
        feature_scores = {}

        if not feature_importance:
            return feature_scores

        # 提取评分卡参数
        base_score, pdo, min_score, max_score, direction = self.score_transformer._extract_params(request_params)

        # 计算每个特征的分数贡献
        total_importance = sum(abs(v) for v in feature_importance.values() if v is not None)

        if total_importance > 0:
            # 计算基础赔率
            p = min(max(float(probability), self.score_transformer._EPS), 1.0 - self.score_transformer._EPS)
            odds = p / (1.0 - p)

            # 总对数赔率
            total_log_odds = math.log(odds)

            for feature, importance in feature_importance.items():
                if importance is None or feature not in features:
                    continue

                feature_value = features.get(feature)

                # 计算该特征的对数赔率贡献
                # 假设每个特征对总对数赔率的贡献与其重要性成正比
                feature_log_odds = total_log_odds * (abs(importance) / total_importance)

                # 根据特征值调整（如果有数值型特征）
                if isinstance(feature_value, (int, float)):
                    # 使用 sigmoid 归一化特征值
                    normalized_value = self._normalize_feature_value(feature_value)
                    # 如果特征重要性为正，特征值越大贡献越大；为负则相反
                    if importance > 0:
                        feature_log_odds *= normalized_value
                    else:
                        feature_log_odds *= (1 - normalized_value)

                # 计算特征分数贡献
                if direction == "lower_better":
                    feature_score = (pdo / math.log(2)) * feature_log_odds
                else:
                    feature_score = (pdo / math.log(2)) * feature_log_odds
                    # 对于 higher_better 方向，特征分保持正相关

                feature_scores[feature] = feature_score

        return feature_scores

    def _normalize_feature_value(self, value: float) -> float:
        """归一化特征值到0-1范围 - 使用sigmoid函数"""
        # 防止溢出
        if value > 10:
            return 1.0
        elif value < -10:
            return 0.0
        return 1 / (1 + math.exp(-value))


class FraudModelService(BaseModelService):
    """
    反欺诈模型服务 - 只输出概率和风险因素，不做决策

    支持可配置的风险等级阈值：
    - risk_levels: {
        "low": {"max": 0.3},
        "medium": {"min": 0.3, "max": 0.6},
        "high": {"min": 0.6, "max": 0.8},
        "very_high": {"min": 0.8}
    }
    """

    def __init__(self):
        super().__init__("fraud-service", TaskType.FRAUD_DETECTION.value)
        # 默认风险等级配置
        self.default_risk_levels = {
            "low": {"max": 0.3},
            "medium": {"min": 0.3, "max": 0.6},
            "high": {"min": 0.6, "max": 0.8},
            "very_high": {"min": 0.8}
        }
        debug_print("FraudModelService", "反欺诈服务初始化完成")

    async def _predict(self, model, features: Dict) -> Any:
        """反欺诈模型预测"""
        debug_print("FraudModelService", "执行反欺诈预测")

        # 转换为DataFrame
        df = pd.DataFrame([features])

        # 执行预测
        if hasattr(model, 'predict_proba'):
            probabilities = model.predict_proba(df)
            fraud_prob = probabilities[0][1] if len(probabilities[0]) > 1 else probabilities[0][0]
        else:
            fraud_prob = model.predict(df)[0]

        debug_print("FraudModelService", f"欺诈概率: {fraud_prob}")

        return {
            'fraud_probability': float(fraud_prob),
            'probabilities': probabilities.tolist() if 'probabilities' in locals() else None
        }

    def _process_output(self, raw_output: Any, model_id: str, input_data: Dict = None) -> Dict:
        """
        处理反欺诈输出 - 只输出概率和风险因素，不做决策

        返回格式:
        {
            "fraud_probability": 0.1234,        # 欺诈概率
            "risk_factors": [                    # 风险因素
                {
                    "factor": "device_fingerprint",
                    "value": 0.3,
                    "description": "设备指纹异常"
                }
            ],
            "risk_level": "low",                  # 风险等级（可配置阈值）
            "model_version": "1.0.0",              # 模型版本
            "risk_config": {                       # 使用的风险配置
                "levels": {
                    "low": {"max": 0.3},
                    "medium": {"min": 0.3, "max": 0.6},
                    "high": {"min": 0.6, "max": 0.8},
                    "very_high": {"min": 0.8}
                }
            }
        }
        """
        fraud_prob = raw_output['fraud_probability']

        # 获取模型信息
        model_info = self.model_metadata.get(model_id, {})

        # 从模型参数中获取风险等级配置
        model_params = model_info.get('model_params', {})
        risk_config = model_params.get('risk_config', {})
        risk_levels = risk_config.get('levels', self.default_risk_levels)

        # 如果请求中有风险配置，则覆盖
        if input_data and 'risk_config' in input_data:
            if isinstance(input_data['risk_config'], dict):
                request_risk_levels = input_data['risk_config'].get('levels')
                if request_risk_levels:
                    # 合并配置，请求参数优先
                    risk_levels.update(request_risk_levels)

        # 计算风险等级（使用可配置阈值）
        risk_level = self._get_risk_level(fraud_prob, risk_levels)

        # 识别风险因素 - 只输出特征层面的信息，不做决策
        risk_factors = self._identify_risk_factors(
            fraud_prob=fraud_prob,
            features=input_data.get('features', {}) if input_data else {},
            model_info=model_info,
            risk_levels=risk_levels
        )

        result = {
            'fraud_probability': round(fraud_prob, 4),
            'risk_factors': risk_factors,
            'risk_level': risk_level,
            'model_version': model_info.get('model_version', 'unknown'),
            'risk_config': {  # 返回使用的风险配置供下游参考
                'levels': risk_levels
            }
        }

        debug_print("FraudModelService", f"反欺诈结果: 概率={result['fraud_probability']}, 风险等级={risk_level}")
        return result

    def _get_risk_level(self, probability: float, risk_levels: Dict) -> str:
        """
        根据可配置的阈值获取风险等级

        Args:
            probability: 欺诈概率
            risk_levels: 风险等级配置，例如：
                {
                    "low": {"max": 0.3},
                    "medium": {"min": 0.3, "max": 0.6},
                    "high": {"min": 0.6, "max": 0.8},
                    "very_high": {"min": 0.8}
                }

        Returns:
            风险等级名称
        """
        for level_name, thresholds in risk_levels.items():
            min_thresh = thresholds.get('min', 0)
            max_thresh = thresholds.get('max', 1)

            # 检查概率是否在当前等级范围内
            if 'min' in thresholds and 'max' in thresholds:
                if min_thresh <= probability < max_thresh:
                    return level_name
            elif 'min' in thresholds:
                if probability >= min_thresh:
                    return level_name
            elif 'max' in thresholds:
                if probability < max_thresh:
                    return level_name

        # 如果没有匹配的等级，返回默认值
        return 'unknown'

    def _identify_risk_factors(
            self,
            fraud_prob: float,
            features: Dict,
            model_info: Dict,
            risk_levels: Dict
    ) -> List[Dict]:
        """
        识别风险因素 - 基于特征和模型信息

        返回格式:
        [
            {
                "factor": "device_fingerprint",  # 风险因素名称
                "value": 0.3,                     # 风险值
                "weight": 0.5,                     # 权重
                "description": "设备指纹异常"       # 描述
            }
        ]
        """
        risk_factors = []

        # 获取特征重要性
        feature_importance = model_info.get('feature_importance', {})

        # 根据概率高低添加基础风险因素
        if fraud_prob > 0.7:
            risk_factors.append({
                'factor': 'high_fraud_probability',
                'value': round(fraud_prob, 4),
                'weight': 0.8,
                'description': '欺诈概率偏高'
            })
        elif fraud_prob > 0.5:
            risk_factors.append({
                'factor': 'medium_fraud_probability',
                'value': round(fraud_prob, 4),
                'weight': 0.5,
                'description': '欺诈概率中等'
            })
        elif fraud_prob > 0.3:
            risk_factors.append({
                'factor': 'low_fraud_probability',
                'value': round(fraud_prob, 4),
                'weight': 0.2,
                'description': '欺诈概率较低'
            })

        # 根据特征重要性添加特征级别的风险因素
        for feature, importance in feature_importance.items():
            if feature in features and abs(importance) > 0.1:
                feature_value = features[feature]
                risk_factors.append({
                    'factor': feature,
                    'value': feature_value if isinstance(feature_value, (int, float)) else 0.5,
                    'weight': abs(importance),
                    'description': f'{feature} 特征异常' if importance > 0 else f'{feature} 特征正常'
                })

        # 按权重排序，返回前5个最重要的风险因素
        risk_factors.sort(key=lambda x: x.get('weight', 0), reverse=True)
        return risk_factors[:5]

    def _normalize_feature_value(self, value: float) -> float:
        """归一化特征值到0-1范围 - 使用sigmoid函数"""
        # 防止溢出
        if value > 10:
            return 1.0
        elif value < -10:
            return 0.0
        return 1 / (1 + math.exp(-value))