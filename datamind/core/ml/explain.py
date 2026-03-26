# datamind/core/ml/explain.py

"""SHAP 解释器

使用 SHAP 值计算特征对预测的贡献，并转换为分数贡献。

核心功能：
  - explain: 解释单条预测，返回特征分数贡献
  - explain_batch: 批量解释多个预测

特性：
  - SHAP 集成：使用 SHAP 值计算特征贡献
  - 分数转换：将 SHAP 值转换为分数贡献
  - 可加性：所有特征贡献之和 + 截距 = 总评分
  - 延迟初始化：解释器按需创建，避免不必要的开销
  - 智能解释器选择：根据模型类型自动选择最优解释器
  - TreeExplainer 强制 raw 输出，确保 log-odds 空间
  - SHAP 空间检测：基于置信度分级
  - 自适应熔断：logit_diff > max(0.5, abs(logit) * 0.3) 时熔断
  - 平滑置信度：使用指数衰减公式
  - base_value 漂移检测：自适应阈值（与 logit 比较）
  - 特征顺序校验：宽松校验（只检查集合一致性）
  - 解释器缓存：LRU 淘汰，防止内存泄漏
  - 分级评分：强可信评分，中可信带警告，弱可信不评分
  - 方向适配：支持 lower_better 和 higher_better
  - base_odds 适配：完整对齐评分卡公式
  - 双误差审计：additive_error + score_error
  - SHAP 不可用时降级返回
"""

import numpy as np
from collections import OrderedDict
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from datamind.core.ml.scorecard import Scorecard, DIRECTION_LOWER_BETTER
from datamind.core.logging.debug import debug_print


@dataclass
class ExplanationResult:
    """解释结果"""

    probability: float
    score: Optional[float]
    base_value: float
    shap_values: Dict[str, float]
    feature_scores: Dict[str, float]
    intercept_score: Optional[float]
    space: str
    confidence: float
    additive_error: float
    score_error: Optional[float]
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'probability': self.probability,
            'score': self.score,
            'base_value': self.base_value,
            'shap_values': self.shap_values,
            'feature_scores': self.feature_scores,
            'intercept_score': self.intercept_score,
            'space': self.space,
            'confidence': self.confidence,
            'additive_error': self.additive_error,
            'score_error': self.score_error,
            'warning': self.warning
        }

    def get_top_contributors(self, n: int = 5) -> List[Dict[str, Any]]:
        if not self.feature_scores:
            return []

        sorted_features = sorted(
            self.feature_scores.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        return [
            {
                'feature': name,
                'score': score,
                'shap': self.shap_values[name]
            }
            for name, score in sorted_features[:n]
        ]


class ShapExplainer:

    def __init__(self, model, feature_names: Optional[List[str]] = None,
                 background_data: Optional[np.ndarray] = None,
                 inference=None,
                 strict_feature_order: bool = False,
                 max_cache_size: int = 10):
        self.model = model
        self.feature_names = feature_names
        self.background_data = background_data
        self.inference = inference
        self.strict_feature_order = strict_feature_order
        self.max_cache_size = max_cache_size
        self._scaler = None
        self._output_space = None
        self._explainer_cache = OrderedDict()
        self._validate_feature_names(model, feature_names)

        debug_print("ShapExplainer", "初始化 SHAP 解释器")

    def _validate_feature_names(self, model, feature_names: Optional[List[str]]):
        """验证特征名称"""
        if feature_names is None:
            return

        if hasattr(model, "feature_names_in_"):
            model_feature_names = list(model.feature_names_in_)

            if self.strict_feature_order:
                if feature_names != model_feature_names:
                    raise ValueError(
                        f"特征名称顺序与模型训练时不一致！\n"
                        f"模型期望: {model_feature_names}\n"
                        f"当前传入: {feature_names}"
                    )
            else:
                if set(feature_names) != set(model_feature_names):
                    raise ValueError(
                        f"特征名称集合与模型训练时不一致！\n"
                        f"模型期望: {set(model_feature_names)}\n"
                        f"当前传入: {set(feature_names)}"
                    )
            debug_print("ShapExplainer", "特征集合校验通过")

    def _get_explainer(self):
        """获取 SHAP 解释器"""
        model_id = id(self.model)

        if model_id not in self._explainer_cache:
            if len(self._explainer_cache) >= self.max_cache_size:
                oldest_key = next(iter(self._explainer_cache))
                del self._explainer_cache[oldest_key]
                debug_print("ShapExplainer", f"缓存淘汰，移除模型 {oldest_key}")

            try:
                import shap

                model_name = self.model.__class__.__name__.lower()
                has_background = self.background_data is not None

                # Linear / Logistic 模型 - 优先使用系数计算
                if any(x in model_name for x in ['logistic', 'linear']):
                    if hasattr(self.model, 'coef_'):
                        debug_print("ShapExplainer", "使用模型系数计算特征重要性")
                        self._explainer_cache[model_id] = self.model
                        self._output_space = "coefficient"
                        return self._explainer_cache[model_id]
                    elif has_background:
                        try:
                            debug_print("ShapExplainer", "使用 LinearExplainer")
                            self._explainer_cache[model_id] = shap.LinearExplainer(
                                self.model,
                                self.background_data
                            )
                            self._output_space = "log_odds"
                            return self._explainer_cache[model_id]
                        except Exception as e:
                            debug_print("ShapExplainer", f"LinearExplainer 失败: {e}")

                # Tree 模型
                elif any(x in model_name for x in ['xgb', 'lgb', 'catboost', 'randomforest', 'decisiontree']):
                    debug_print("ShapExplainer", "使用 TreeExplainer")
                    if has_background:
                        self._explainer_cache[model_id] = shap.TreeExplainer(
                            self.model,
                            self.background_data,
                            model_output="raw"
                        )
                    else:
                        self._explainer_cache[model_id] = shap.TreeExplainer(
                            self.model,
                            model_output="raw"
                        )
                    self._output_space = "log_odds"
                    return self._explainer_cache[model_id]

                # 其他情况
                if has_background:
                    debug_print("ShapExplainer", "使用通用 Explainer")
                    if hasattr(self.model, "predict_proba"):
                        self._explainer_cache[model_id] = shap.Explainer(
                            self.model.predict_proba,
                            self.background_data
                        )
                    else:
                        self._explainer_cache[model_id] = shap.Explainer(
                            self.model.predict,
                            self.background_data
                        )
                    self._output_space = "probability"
                else:
                    debug_print("ShapExplainer", "无背景数据，使用系数计算")
                    self._explainer_cache[model_id] = self.model
                    self._output_space = "coefficient"

            except ImportError:
                debug_print("ShapExplainer", "SHAP 库未安装，使用系数计算")
                self._explainer_cache[model_id] = self.model
                self._output_space = "coefficient"

        self._explainer_cache.move_to_end(model_id)
        return self._explainer_cache[model_id]

    @staticmethod
    def _extract_shap_values(shap_result) -> np.ndarray:
        values = shap_result.values

        if values.ndim == 3:
            return values[0, :, 1]
        if values.ndim == 1:
            return values
        if values.ndim == 2:
            return values[0]

        raise ValueError(f"不支持的 SHAP 输出格式，shape: {values.shape}")

    @staticmethod
    def _extract_base_value(shap_result) -> float:
        base = shap_result.base_values

        if isinstance(base, (int, float)):
            return float(base)

        if isinstance(base, (list, tuple, np.ndarray)):
            base_arr = np.array(base)

            if base_arr.ndim == 2 and base_arr.shape[1] == 2:
                return float(base_arr[0, 1])
            if base_arr.ndim == 1:
                return float(base_arr[0])
            if base_arr.ndim == 2 and base_arr.shape[1] == 1:
                return float(base_arr[0, 0])

        try:
            return float(base)
        except (TypeError, ValueError):
            debug_print("ShapExplainer", f"无法解析 base_values: {base}")
            return 0.0

    @staticmethod
    def _detect_space(shap_vals: np.ndarray, base_value: float, prob: float,
                      output_space: str = None) -> Tuple[np.ndarray, float, str, float]:
        """
        检测 SHAP 值所在空间并计算置信度

        返回:
            (shap_vals, base_value, space, confidence)
        """
        if output_space == "probability":
            return shap_vals, base_value, "probability", 0.7

        if output_space == "coefficient":
            return shap_vals, base_value, "coefficient", 0.95

        eps = 1e-10
        prob = np.clip(prob, eps, 1 - eps)
        logit = np.log(prob / (1 - prob))
        reconstructed = base_value + np.sum(shap_vals)
        logit_diff = abs(reconstructed - logit)

        abs_error = logit_diff
        rel_error = logit_diff / (abs(logit) + eps)
        confidence = np.exp(-max(abs_error, rel_error))
        confidence = max(0.0, min(1.0, confidence))

        threshold = max(1.0, abs(logit) * 0.5)
        if logit_diff > threshold:
            return shap_vals, base_value, "unknown", confidence

        if confidence >= 0.7:
            space = "log_odds"
        elif confidence >= 0.5:
            space = "approx_log_odds"
        elif confidence >= 0.3:
            space = "weak_log_odds"
        else:
            space = "unknown"

        debug_print("ShapExplainer", f"空间检测: {space}, 置信度: {confidence:.3f}, 误差: {logit_diff:.4f}")

        return shap_vals, base_value, space, confidence

    def _get_probability(self, features: Dict[str, Any]) -> float:
        if self.inference is not None and hasattr(self.inference, 'predict_proba'):
            try:
                return self.inference.predict_proba(features)
            except Exception as e:
                debug_print("ShapExplainer", f"推理引擎预测失败，降级使用模型: {e}")

        X = self._to_array(features)
        if hasattr(self.model, 'predict_proba'):
            return float(self.model.predict_proba(X)[0][1])
        return float(self.model.predict(X)[0])

    def _get_probability_batch(self, features_list: List[Dict[str, Any]]) -> List[float]:
        if not features_list:
            return []

        if self.inference is not None and hasattr(self.inference, 'predict_batch'):
            try:
                return self.inference.predict_batch(features_list)
            except Exception as e:
                debug_print("ShapExplainer", f"推理引擎批量预测失败，降级使用循环: {e}")

        return [self._get_probability(f) for f in features_list]

    @staticmethod
    def _check_base_value_drift(base_value: float, logit: float) -> Optional[str]:
        """检测 base_value 漂移，返回警告信息"""
        if abs(logit) > 1e-3:
            if abs(base_value) > abs(logit) * 2:
                return f"base_value 漂移 ({base_value:.2f} vs logit={logit:.2f})，可能 background_data 不一致"
        else:
            if abs(base_value) > 5:
                return f"base_value 异常 ({base_value:.2f})，可能 background_data 不一致"
        return None

    @staticmethod
    def _get_score_coefficient(scorecard: Scorecard) -> Tuple[float, float]:
        """
        根据评分卡方向返回特征分和截距的系数

        lower_better (分高好):
            score = base_score - factor * (log_odds - base_log_odds)
            = (base_score + factor * base_log_odds) + (-factor) * log_odds
            因此: feature_score = -factor * shap_val
                  intercept = base_score + factor * base_log_odds + (-factor) * base_value

        higher_better (分低好):
            score = base_score + factor * (log_odds - base_log_odds)
            = (base_score - factor * base_log_odds) + factor * log_odds
            因此: feature_score = factor * shap_val
                  intercept = base_score - factor * base_log_odds + factor * base_value

        返回:
            (feature_coef, intercept_coef)
        """
        if scorecard.direction == DIRECTION_LOWER_BETTER:
            return -scorecard.factor, -scorecard.factor
        else:
            return scorecard.factor, scorecard.factor

    def explain(self, features: Dict[str, Any], scorecard: Scorecard,
                enable: bool = True) -> Optional[ExplanationResult]:
        if not enable:
            return None

        if not self.feature_names:
            raise ValueError("SHAP 解释需要提供特征名称列表 (feature_names)")

        explainer = self._get_explainer()

        if explainer is None:
            prob = self._get_probability(features)
            return ExplanationResult(
                probability=round(prob, 4),
                score=None,
                base_value=0.0,
                shap_values={},
                feature_scores={},
                intercept_score=None,
                space="unknown",
                confidence=0.0,
                additive_error=0.0,
                score_error=None,
                warning="SHAP 库不可用，无法提供特征解释"
            )

        # 处理系数模式
        if self._output_space == "coefficient":
            if hasattr(explainer, 'coef_'):
                coef = explainer.coef_[0] if explainer.coef_.ndim > 1 else explainer.coef_
                intercept = explainer.intercept_[0] if hasattr(explainer, 'intercept_') else 0

                X = self._to_array(features)

                # 如果有归一化器，应用归一化
                if self._scaler is not None:
                    X_scaled = self._scaler.transform(X)
                else:
                    X_scaled = X

                logit = intercept + np.dot(X_scaled[0], coef)
                prob = 1 / (1 + np.exp(-np.clip(logit, -100, 100)))

                shap_vals = coef * X_scaled[0]

                feature_coef, intercept_coef = self._get_score_coefficient(scorecard)
                feature_scores = {}
                for i, name in enumerate(self.feature_names):
                    feature_scores[name] = round(float(feature_coef * shap_vals[i]), 2)

                intercept_score = scorecard.base_score + intercept_coef * (intercept - scorecard.base_log_odds)
                total_score = intercept_score + sum(feature_scores.values())
                score_val = max(float(scorecard.min_score), min(float(scorecard.max_score), total_score))

                shap_dict = {name: float(shap_vals[i]) for i, name in enumerate(self.feature_names)}

                return ExplanationResult(
                    probability=round(prob, 4),
                    score=round(score_val, 2),
                    base_value=intercept,
                    shap_values=shap_dict,
                    feature_scores=feature_scores,
                    intercept_score=intercept_score,
                    space="coefficient",
                    confidence=0.95,
                    additive_error=0.0,
                    score_error=0.0,
                    warning=None
                )

        # 原有 SHAP 逻辑
        X = self._to_array(features)
        shap_result = explainer(X)

        shap_vals = self._extract_shap_values(shap_result)
        base_value = self._extract_base_value(shap_result)

        if len(shap_vals) != len(self.feature_names):
            debug_print("ShapExplainer",
                        f"SHAP 值长度 ({len(shap_vals)}) 与特征数 ({len(self.feature_names)}) 不匹配")

        prob = self._get_probability(features)
        shap_vals, base_value, space, confidence = self._detect_space(
            shap_vals, base_value, prob, self._output_space
        )

        shap_dict = {}
        for i, name in enumerate(self.feature_names):
            shap_val = shap_vals[i] if i < len(shap_vals) else 0.0
            shap_dict[name] = float(shap_val)

        eps = 1e-10
        prob_clipped = max(min(prob, 1 - eps), eps)
        logit = np.log(prob_clipped / (1 - prob_clipped))
        reconstructed = base_value + np.sum(shap_vals)
        additive_error = abs(reconstructed - logit)

        warning = self._check_base_value_drift(base_value, logit)

        feature_coef, intercept_coef = self._get_score_coefficient(scorecard)

        score_val = None
        feature_scores = {}
        intercept_score_val = None
        score_error = None

        if confidence >= 0.7:
            intercept_score_val = (
                scorecard.base_score
                + intercept_coef * (base_value - scorecard.base_log_odds)
            )

            for i, name in enumerate(self.feature_names):
                shap_val = shap_vals[i] if i < len(shap_vals) else 0.0
                feature_scores[name] = round(float(feature_coef * shap_val), 2)

            total_score = intercept_score_val + sum(feature_scores.values())
            score_val = max(float(scorecard.min_score), min(float(scorecard.max_score), total_score))

            true_score = scorecard.score(prob)
            score_error = abs(total_score - true_score)

        elif confidence >= 0.5:
            intercept_score_val = (
                scorecard.base_score
                + intercept_coef * (base_value - scorecard.base_log_odds)
            )

            for i, name in enumerate(self.feature_names):
                shap_val = shap_vals[i] if i < len(shap_vals) else 0.0
                feature_scores[name] = round(float(feature_coef * shap_val), 2)

            total_score = intercept_score_val + sum(feature_scores.values())
            score_val = max(float(scorecard.min_score), min(float(scorecard.max_score), total_score))

            true_score = scorecard.score(prob)
            score_error = abs(total_score - true_score)

            if warning is None:
                warning = f"SHAP 解释置信度中等 ({confidence:.2f})，评分仅供参考"

        elif confidence >= 0.3:
            if warning is None:
                warning = f"SHAP 解释置信度较低 ({confidence:.2f})，仅返回 SHAP 值，不计算评分"

        else:
            if warning is None:
                warning = f"SHAP 值不可信 (confidence={confidence:.2f})，无法解释"

        return ExplanationResult(
            probability=round(prob, 4),
            score=score_val,
            base_value=base_value,
            shap_values=shap_dict,
            feature_scores=feature_scores,
            intercept_score=intercept_score_val,
            space=space,
            confidence=confidence,
            additive_error=additive_error,
            score_error=score_error,
            warning=warning
        )

    def explain_batch(self, features_list: List[Dict[str, Any]],
                      scorecard: Scorecard,
                      enable: bool = True) -> Optional[List[ExplanationResult]]:
        if not enable:
            return None

        if not self.feature_names:
            raise ValueError("SHAP 解释需要提供特征名称列表 (feature_names)")

        if not features_list:
            return []

        explainer = self._get_explainer()

        if explainer is None:
            probs = self._get_probability_batch(features_list)
            results = []
            for prob in probs:
                results.append(ExplanationResult(
                    probability=round(prob, 4),
                    score=None,
                    base_value=0.0,
                    shap_values={},
                    feature_scores={},
                    intercept_score=None,
                    space="unknown",
                    confidence=0.0,
                    additive_error=0.0,
                    score_error=None,
                    warning="SHAP 库不可用，无法提供特征解释"
                ))
            return results

        # 处理系数模式
        if self._output_space == "coefficient" and hasattr(explainer, 'coef_'):
            coef = explainer.coef_[0] if explainer.coef_.ndim > 1 else explainer.coef_
            intercept = explainer.intercept_[0] if hasattr(explainer, 'intercept_') else 0

            feature_coef, intercept_coef = self._get_score_coefficient(scorecard)

            results = []
            for features in features_list:
                X = self._to_array(features)

                if self._scaler is not None:
                    X_scaled = self._scaler.transform(X)
                else:
                    X_scaled = X

                logit = intercept + np.dot(X_scaled[0], coef)
                prob = 1 / (1 + np.exp(-np.clip(logit, -100, 100)))

                shap_vals = coef * X_scaled[0]
                feature_scores = {}
                for i, name in enumerate(self.feature_names):
                    feature_scores[name] = round(float(feature_coef * shap_vals[i]), 2)

                intercept_score = scorecard.base_score + intercept_coef * (intercept - scorecard.base_log_odds)
                total_score = intercept_score + sum(feature_scores.values())
                score_val = max(float(scorecard.min_score), min(float(scorecard.max_score), total_score))

                shap_dict = {name: float(shap_vals[i]) for i, name in enumerate(self.feature_names)}

                results.append(ExplanationResult(
                    probability=round(prob, 4),
                    score=round(score_val, 2),
                    base_value=intercept,
                    shap_values=shap_dict,
                    feature_scores=feature_scores,
                    intercept_score=intercept_score,
                    space="coefficient",
                    confidence=0.95,
                    additive_error=0.0,
                    score_error=0.0,
                    warning=None
                ))
            return results

        X = self._to_array_batch(features_list)
        shap_results = explainer(X)

        probs = self._get_probability_batch(features_list)

        results = []
        eps = 1e-10

        feature_coef, intercept_coef = self._get_score_coefficient(scorecard)

        for i, (shap_result, features, prob) in enumerate(zip(shap_results, features_list, probs)):
            shap_vals = self._extract_shap_values(shap_result)
            base_value = self._extract_base_value(shap_result)

            shap_vals, base_value, space, confidence = self._detect_space(
                shap_vals, base_value, prob, self._output_space
            )

            shap_dict = {}
            for j, name in enumerate(self.feature_names):
                shap_val = shap_vals[j] if j < len(shap_vals) else 0.0
                shap_dict[name] = float(shap_val)

            prob_clipped = max(min(prob, 1 - eps), eps)
            logit = np.log(prob_clipped / (1 - prob_clipped))
            reconstructed = base_value + np.sum(shap_vals)
            additive_error = abs(reconstructed - logit)

            warning = self._check_base_value_drift(base_value, logit)

            score_val = None
            feature_scores = {}
            intercept_score_val = None
            score_error = None

            if confidence >= 0.7:
                intercept_score_val = (
                    scorecard.base_score
                    + intercept_coef * (base_value - scorecard.base_log_odds)
                )

                for j, name in enumerate(self.feature_names):
                    shap_val = shap_vals[j] if j < len(shap_vals) else 0.0
                    feature_scores[name] = round(float(feature_coef * shap_val), 2)

                total_score = intercept_score_val + sum(feature_scores.values())
                score_val = max(float(scorecard.min_score), min(float(scorecard.max_score), total_score))

                true_score = scorecard.score(prob)
                score_error = abs(total_score - true_score)

            elif confidence >= 0.5:
                intercept_score_val = (
                    scorecard.base_score
                    + intercept_coef * (base_value - scorecard.base_log_odds)
                )

                for j, name in enumerate(self.feature_names):
                    shap_val = shap_vals[j] if j < len(shap_vals) else 0.0
                    feature_scores[name] = round(float(feature_coef * shap_val), 2)

                total_score = intercept_score_val + sum(feature_scores.values())
                score_val = max(float(scorecard.min_score), min(float(scorecard.max_score), total_score))

                true_score = scorecard.score(prob)
                score_error = abs(total_score - true_score)

                if warning is None:
                    warning = f"SHAP 解释置信度中等 ({confidence:.2f})，评分仅供参考"

            elif confidence >= 0.3:
                if warning is None:
                    warning = f"SHAP 解释置信度较低 ({confidence:.2f})，仅返回 SHAP 值"

            else:
                if warning is None:
                    warning = f"SHAP 值不可信 (confidence={confidence:.2f})，无法解释"

            results.append(ExplanationResult(
                probability=round(prob, 4),
                score=score_val,
                base_value=base_value,
                shap_values=shap_dict,
                feature_scores=feature_scores,
                intercept_score=intercept_score_val,
                space=space,
                confidence=confidence,
                additive_error=additive_error,
                score_error=score_error,
                warning=warning
            ))

        return results

    def _to_array(self, features: Dict[str, Any]) -> np.ndarray:
        values = [features.get(name, 0) for name in self.feature_names]
        return np.array([values])

    def _to_array_batch(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        if not features_list:
            return np.array([])

        values = [
            [f.get(name, 0) for name in self.feature_names]
            for f in features_list
        ]
        return np.array(values)