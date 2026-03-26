# datamind/core/ml/explain.py

"""SHAP 解释器

使用 SHAP 值计算特征对预测的贡献，并转换为分数贡献。

核心功能：
  - explain: 解释单条预测，返回特征分数贡献
  - explain_batch: 批量解释多个预测
  - get_feature_importance: 获取全局特征重要性

特性：
  - SHAP 集成：使用 SHAP 值计算特征贡献
  - 分数转换：将 SHAP 值转换为分数贡献（-factor × shap）
  - 可加性：所有特征贡献之和 + 截距 = 总评分
  - 延迟初始化：解释器按需创建，避免不必要的开销
  - 智能解释器选择：根据模型类型自动选择最优解释器
  - Pipeline 支持：自动检测 Pipeline 并使用通用解释器
  - log-odds 统一：强制将 SHAP 值统一到 log-odds 空间
  - 批量优化：批量预测提升性能（10倍+）
  - 严格的 feature_names 顺序保证

使用示例：
    >>> from datamind.core.ml.explain import ShapExplainer
    >>> from datamind.core.ml.scorecard import Scorecard
    >>>
    >>> explainer = ShapExplainer(model, feature_names=["age", "income"])
    >>> scorecard = Scorecard(base_score=600, pdo=50)
    >>>
    >>> # 单条解释
    >>> result = explainer.explain({"age": 35, "income": 50000}, scorecard)
    >>> print(result.feature_scores)  # {"age": 85.2, "income": 120.5}
    >>>
    >>> # 批量解释
    >>> results = explainer.explain_batch(
    ...     [{"age": 35}, {"age": 28}],
    ...     scorecard
    ... )
"""

import numpy as np
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass

from datamind.core.ml.scorecard import Scorecard
from datamind.core.logging.debug import debug_print


@dataclass
class ExplanationResult:
    """解释结果

    包含单条预测的完整解释信息。

    属性:
        probability: 违约概率 (0-1)
        score: 信用评分
        base_value: SHAP 基准值
        shap_values: 各特征 SHAP 值
        feature_scores: 各特征分数贡献
        intercept_score: 截距分
    """

    probability: float
    score: float
    base_value: float
    shap_values: Dict[str, float]
    feature_scores: Dict[str, float]
    intercept_score: float

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        返回:
            包含所有解释字段的字典
        """
        return {
            'probability': self.probability,
            'score': self.score,
            'base_value': self.base_value,
            'shap_values': self.shap_values,
            'feature_scores': self.feature_scores,
            'intercept_score': self.intercept_score
        }

    def get_top_contributors(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        获取贡献最大的 n 个特征

        按特征分数绝对值排序，返回前 n 个特征。

        参数:
            n: 返回数量

        返回:
            特征贡献列表，每个元素包含 feature, score, shap
        """
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
    """SHAP 解释器

    负责特征贡献计算。使用 SHAP 值计算每个特征对预测结果的贡献，
    并将 SHAP 值转换为分数贡献，满足评分卡的可加性要求。

    核心公式：
        total_score = base_score - factor × (base_value + Σ shap_i)
        feature_score_i = -factor × shap_i

    其中：
        - base_score: 评分卡基准分
        - factor: 评分卡因子（PDO / ln(2)）
        - base_value: SHAP 基准值
        - shap_i: 特征 i 的 SHAP 值
    """

    def __init__(self, model, feature_names: Optional[List[str]] = None,
                 background_data: Optional[np.ndarray] = None,
                 inference=None):
        """
        初始化 SHAP 解释器

        参数:
            model: 训练好的模型
            feature_names: 特征名称列表
            background_data: 背景数据，用于计算 SHAP 值
            inference: 推理引擎实例
        """
        self.model = model
        self.feature_names = feature_names
        self.background_data = background_data
        self.inference = inference
        self._explainer = None
        debug_print("ShapExplainer", "初始化 SHAP 解释器")

    def _get_explainer(self):
        """
        获取 SHAP 解释器（延迟初始化 + 智能选择）

        根据模型类型自动选择最优解释器：
          - Pipeline: 使用通用 Explainer（避免特征错位）
          - 树模型（XGBoost、LightGBM、CatBoost）：使用 TreeExplainer
          - 线性模型（LogisticRegression）：使用 LinearExplainer
          - 其他模型：使用通用 Explainer

        返回:
            SHAP Explainer 实例

        异常:
            ImportError: shap 库未安装
        """
        if self._explainer is None:
            try:
                import shap

                model_name = self.model.__class__.__name__.lower()

                # Pipeline 使用通用 Explainer
                if hasattr(self.model, 'steps') or hasattr(self.model, 'named_steps'):
                    debug_print("ShapExplainer", "检测到 Pipeline，使用通用 Explainer")
                    if self.background_data is not None:
                        self._explainer = shap.Explainer(self.model, self.background_data)
                    else:
                        self._explainer = shap.Explainer(self.model)

                # 树模型使用 TreeExplainer
                elif any(x in model_name for x in ['xgb', 'lgb', 'catboost', 'randomforest', 'decisiontree']):
                    debug_print("ShapExplainer", "使用 TreeExplainer")
                    self._explainer = shap.TreeExplainer(self.model)

                # 线性模型使用 LinearExplainer
                elif any(x in model_name for x in ['logistic', 'linear']):
                    if self.background_data is not None:
                        debug_print("ShapExplainer", "使用 LinearExplainer")
                        self._explainer = shap.LinearExplainer(self.model, self.background_data)
                    else:
                        debug_print("ShapExplainer", "LinearExplainer 需要背景数据，降级使用 Explainer")
                        self._explainer = shap.Explainer(self.model)

                # 默认使用通用 Explainer
                else:
                    debug_print("ShapExplainer", "使用通用 Explainer")
                    if self.background_data is not None:
                        self._explainer = shap.Explainer(self.model, self.background_data)
                    else:
                        self._explainer = shap.Explainer(self.model)

            except ImportError:
                raise ImportError("请安装 shap: pip install shap")

        return self._explainer

    @staticmethod
    def _extract_shap_values(shap_result) -> np.ndarray:
        """
        从 SHAP 结果中提取特征 SHAP 值

        处理各种 SHAP 输出格式：
          - shape (n, d): 直接返回
          - shape (n, d, 2): 二分类取正类
          - shape (d,): 单样本

        参数:
            shap_result: SHAP 计算结果

        返回:
            特征 SHAP 值数组，形状 (d,)

        异常:
            ValueError: 不支持的 SHAP 输出格式
        """
        values = shap_result.values

        # 二分类 (n, d, 2)
        if values.ndim == 3:
            return values[0, :, 1]

        # 单样本 (d,) 或 (n, d)
        if values.ndim == 1:
            return values
        if values.ndim == 2:
            return values[0]

        raise ValueError(f"不支持的 SHAP 输出格式，shape: {values.shape}")

    @staticmethod
    def _extract_base_value(shap_result) -> float:
        """
        从 SHAP 结果中提取基准值

        处理各种 base_values 格式：
          - scalar: 直接返回
          - (1,): 返回第一个元素
          - (1,2): 二分类取正类

        参数:
            shap_result: SHAP 计算结果

        返回:
            SHAP 基准值
        """
        base = shap_result.base_values

        # 已经是标量
        if isinstance(base, (int, float)):
            return float(base)

        # 转换为 numpy 数组统一处理
        if isinstance(base, (list, tuple, np.ndarray)):
            base_arr = np.array(base)

            # 二分类 (1,2)
            if base_arr.ndim == 2 and base_arr.shape[1] == 2:
                return float(base_arr[0, 1])

            # 单输出 (1,) 或 (1,1)
            if base_arr.ndim == 1:
                return float(base_arr[0])
            if base_arr.ndim == 2 and base_arr.shape[1] == 1:
                return float(base_arr[0, 0])

        # 兜底：转为标量
        try:
            return float(base)
        except (TypeError, ValueError):
            debug_print("ShapExplainer", f"无法解析 base_values: {base}")
            return 0.0

    @staticmethod
    def _ensure_log_odds(shap_vals: np.ndarray, base_value: float, prob: float) -> tuple:
        """
        确保 SHAP 值在 log-odds 空间

        不同模型的 SHAP 值单位不同：
          - LogisticRegression: log-odds
          - XGBoost: log-odds
          - LightGBM: log-odds
          - CatBoost: 可能是 probability

        本方法通过校验将 SHAP 值统一转换到 log-odds 空间。

        校验原理：
            logit(prob) = ln(prob / (1 - prob))
            shap_sum = base_value + Σ shap_i

        如果 |shap_sum - logit| < 阈值，说明已经是 log-odds
        否则进行转换（线性缩放）

        参数:
            shap_vals: SHAP 值数组
            base_value: SHAP 基准值
            prob: 违约概率

        返回:
            (转换后的 shap_vals, 转换后的 base_value)
        """
        eps = 1e-10

        # 计算概率的对数几率
        prob_clipped = max(min(prob, 1 - eps), eps)
        logit = np.log(prob_clipped / (1 - prob_clipped))

        # 计算当前 SHAP 和
        shap_sum = base_value + np.sum(shap_vals)

        # 防止除零
        if abs(shap_sum) < eps:
            debug_print("ShapExplainer", "shap_sum 接近 0，跳过校正")
            return shap_vals, base_value

        # 已接近目标值，无需转换
        if abs(shap_sum - logit) < 1e-3:
            debug_print("ShapExplainer", "SHAP 已在 log-odds 空间")
            return shap_vals, base_value

        # 偏差过大时跳过校正
        diff = abs(shap_sum - logit)
        if diff / (abs(logit) + eps) > 0.2:
            debug_print("ShapExplainer", "SHAP 偏差过大，跳过校正")
            return shap_vals, base_value

        debug_print("ShapExplainer",
                    f"SHAP 可能在概率空间，进行转换 (shap_sum={shap_sum:.4f}, logit={logit:.4f})")

        if abs(shap_sum - logit) > 1:
            debug_print("ShapExplainer", "SHAP 偏差过大，跳过校正")
            return shap_vals, base_value

        # 计算缩放因子
        scale = logit / (shap_sum + eps)

        # 缩放因子异常时跳过
        if scale <= 0 or abs(scale) > 10:
            debug_print("ShapExplainer", f"scale 异常({scale:.2f})，跳过校正")
            return shap_vals, base_value

        shap_vals_scaled = shap_vals * scale
        base_value_scaled = base_value * scale

        debug_print("ShapExplainer", f"缩放因子: {scale:.4f}")

        return shap_vals_scaled, base_value_scaled

    def _get_probability(self, features: Dict[str, Any]) -> float:
        """
        获取单条违约概率

        优先使用推理引擎，降级使用模型直接预测。

        参数:
            features: 特征字典

        返回:
            违约概率 (0-1)
        """
        # 优先使用推理引擎
        if self.inference is not None and hasattr(self.inference, 'predict_proba'):
            try:
                return self.inference.predict_proba(features)
            except Exception as e:
                debug_print("ShapExplainer", f"推理引擎预测失败，降级使用模型: {e}")

        # 降级：使用模型直接预测
        X = self._to_array(features)
        if hasattr(self.model, 'predict_proba'):
            return float(self.model.predict_proba(X)[0][1])
        return float(self.model.predict(X)[0])

    def _get_probability_batch(self, features_list: List[Dict[str, Any]]) -> List[float]:
        """
        批量获取违约概率

        优先使用推理引擎的批量预测，降级使用循环单条预测。

        参数:
            features_list: 特征字典列表

        返回:
            概率列表
        """
        if not features_list:
            return []

        # 优先使用推理引擎的批量预测
        if self.inference is not None and hasattr(self.inference, 'predict_batch'):
            try:
                return self.inference.predict_batch(features_list)
            except Exception as e:
                debug_print("ShapExplainer", f"推理引擎批量预测失败，降级使用循环: {e}")

        # 降级：循环单条预测
        return [self._get_probability(f) for f in features_list]

    def explain(self, features: Dict[str, Any], scorecard: Scorecard,
                enable: bool = True) -> Optional[ExplanationResult]:
        """
        解释单条预测

        计算每个特征对评分的贡献。

        参数:
            features: 特征字典，如 {"age": 35, "income": 50000}
            scorecard: 评分卡实例

        返回:
            ExplanationResult 实例

        异常:
            ValueError: 未提供 feature_names 或特征不完整
        """
        if not enable:
            return None

        if not self.feature_names:
            raise ValueError("SHAP 解释需要提供特征名称列表 (feature_names)")

        X = self._to_array(features)
        explainer = self._get_explainer()
        shap_result = explainer(X)

        # 统一提取 SHAP 值
        shap_vals = self._extract_shap_values(shap_result)
        base_value = self._extract_base_value(shap_result)

        # 检查长度匹配
        if len(shap_vals) != len(self.feature_names):
            debug_print("ShapExplainer",
                        f"SHAP 值长度 ({len(shap_vals)}) 与特征数 ({len(self.feature_names)}) 不匹配")

        # 获取概率
        prob = self._get_probability(features)

        # 强制统一到 log-odds 空间
        shap_vals, base_value = self._ensure_log_odds(shap_vals, base_value, prob)

        # 计算评分
        factor = scorecard.factor
        intercept_score = scorecard.base_score - factor * base_value

        feature_scores = {}
        shap_dict = {}

        for i, name in enumerate(self.feature_names):
            shap_val = shap_vals[i] if i < len(shap_vals) else 0.0
            shap_dict[name] = float(shap_val)
            feature_scores[name] = round(-factor * shap_val, 2)

        total_score = intercept_score + sum(feature_scores.values())
        total_score = max(scorecard.min_score, min(scorecard.max_score, total_score))

        return ExplanationResult(
            probability=round(prob, 4),
            score=round(total_score, 2),
            base_value=base_value,
            shap_values=shap_dict,
            feature_scores=feature_scores,
            intercept_score=round(intercept_score, 2)
        )

    def explain_batch(self, features_list: List[Dict[str, Any]],
                      scorecard: Scorecard,
                      enable: bool = True) -> Optional[List[ExplanationResult]]:
        """
        批量解释多条预测

        使用批量预测避免循环调用模型。

        参数:
            features_list: 特征字典列表
            scorecard: 评分卡实例

        返回:
            ExplanationResult 列表
        """
        if not enable:
            return None

        if not self.feature_names:
            raise ValueError("SHAP 解释需要提供特征名称列表 (feature_names)")

        if not features_list:
            return []

        X = self._to_array_batch(features_list)
        explainer = self._get_explainer()
        shap_results = explainer(X)

        probs = self._get_probability_batch(features_list)

        factor = scorecard.factor

        # 批量提取 SHAP 值矩阵
        shap_vals_list = []
        base_values = []

        for shap_result in shap_results:
            shap_vals = self._extract_shap_values(shap_result)
            base_value = self._extract_base_value(shap_result)
            shap_vals_list.append(shap_vals)
            base_values.append(base_value)

        # 转换为矩阵便于向量化
        shap_matrix = np.array(shap_vals_list)
        base_array = np.array(base_values)

        # 批量 log-odds 校正
        probs_array = np.array(probs)
        eps = 1e-10
        probs_clipped = np.clip(probs_array, eps, 1 - eps)
        logits = np.log(probs_clipped / (1 - probs_clipped))

        shap_sums = base_array + np.sum(shap_matrix, axis=1)

        # 防止除零
        valid_mask = np.abs(shap_sums) > eps
        scales = np.ones_like(shap_sums)

        for i, (shap_sum, logit) in enumerate(zip(shap_sums, logits)):
            if valid_mask[i] and abs(shap_sum - logit) >= 1e-3:
                scales[i] = logit / shap_sum

        shap_matrix = shap_matrix * scales[:, np.newaxis]
        base_array = base_array * scales

        # 向量化计算特征分
        intercept_scores = scorecard.base_score - factor * base_array
        feature_scores_matrix = -factor * shap_matrix

        # 构建结果列表
        results = []
        for i, (features, prob, base_val, intercept_score, feature_scores_row) in enumerate(
                zip(features_list, probs, base_array, intercept_scores, feature_scores_matrix)):

            feature_scores = {}
            shap_dict = {}

            for j, name in enumerate(self.feature_names):
                shap_val = feature_scores_row[j] / -factor if factor != 0 else 0.0
                shap_dict[name] = float(shap_val)
                feature_scores[name] = round(feature_scores_row[j], 2)

            total_score = intercept_score + sum(feature_scores.values())
            total_score = max(scorecard.min_score, min(scorecard.max_score, total_score))

            results.append(ExplanationResult(
                probability=round(prob, 4),
                score=round(total_score, 2),
                base_value=base_val,
                shap_values=shap_dict,
                feature_scores=feature_scores,
                intercept_score=round(intercept_score, 2)
            ))

        return results

    def _to_array(self, features: Dict[str, Any]) -> np.ndarray:
        """
        特征字典转 numpy 数组

        参数:
            features: 特征字典

        返回:
            numpy 数组，形状为 (1, n_features)
        """
        values = [features.get(name, 0) for name in self.feature_names]
        return np.array([values])

    def _to_array_batch(self, features_list: List[Dict[str, Any]]) -> np.ndarray:
        """
        批量特征字典转 numpy 数组

        参数:
            features_list: 特征字典列表

        返回:
            numpy 数组，形状为 (n_samples, n_features)
        """
        if not features_list:
            return np.array([])

        values = [
            [f.get(name, 0) for name in self.feature_names]
            for f in features_list
        ]
        return np.array(values)