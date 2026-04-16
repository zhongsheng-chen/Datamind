# datamind/core/scoring/engine.py

"""评分卡引擎

支持：
  - RuleScorecardEngine: 规则评分卡（基于分箱）
  - LogisticRegressionScorecardEngine: 逻辑回归评分卡（基于系数）
  - PipelineScorecardEngine: 管道评分卡（基于WOE转换和逻辑回归）

核心功能：
  - predict: 预测最终分数
  - feature_score: 计算各特征分数
  - raw_score: 计算原始分数
  - final_score: 计算最终分数
  - explain: 计算完整解释信息

三层分数体系：
  - feature_score: 各特征独立贡献，用于解释
  - raw_score: 特征分数总和加上截距，用于模型层
  - final_score: 原始分数经过偏移和缩放，用于业务层

分箱区间定义：
  - 数值型分箱采用左闭右开区间
  - 左边界为 None 表示负无穷，右边界为 None 表示正无穷
  - 分箱配置不允许重叠，不允许有空洞

使用示例：
    from datamind.core.scoring.engine import RuleScorecardEngine

    bins = {
        "age": {
            "type": "numeric",
            "bins": [
                {"min": None, "max": 25, "score": 20},
                {"min": 25, "max": 35, "score": 40},
                {"min": 35, "max": 50, "score": 60},
                {"min": 50, "max": None, "score": 80},
            ]
        }
    }

    engine = RuleScorecardEngine(bins=bins)
    score = engine.predict({"age": 30})
"""

from typing import Dict, Any, Optional, List
import math

from datamind.core.scoring.capability import (
    ScorecardCapability,
    infer_scorecard_capabilities,
)


class BaseScorecardEngine:
    """评分卡引擎基类

    属性:
        capabilities: 引擎能力集
        offset: 分数偏移量
        factor: 分数缩放因子
    """

    def __init__(self, offset: float = 0.0, factor: float = 1.0):
        """
        初始化评分卡引擎

        参数:
            offset: 分数偏移量，默认 0.0
            factor: 分数缩放因子，默认 1.0
        """
        self.capabilities: ScorecardCapability = ScorecardCapability.NONE
        self.offset = offset
        self.factor = factor

    def predict(self, X: Dict[str, Any]) -> float:
        """
        预测最终分数

        参数:
            X: 特征字典

        返回:
            最终分数
        """
        return self.final_score(X)

    def feature_score(self, X: Dict[str, Any]) -> Dict[str, float]:
        """
        计算各特征分数（子类必须实现）

        参数:
            X: 特征字典

        返回:
            特征分数字典
        """
        raise NotImplementedError

    def raw_score(self, X: Dict[str, Any]) -> float:
        """
        计算原始分数（子类必须实现）

        语义依赖引擎类型：
            - RuleScorecardEngine: raw_score = Σ feature_score
            - LogisticRegressionScorecardEngine: raw_score = intercept + Σ(coef × value)
            - PipelineScorecardEngine: raw_score = intercept + Σ(coef × woe)

        参数:
            X: 特征字典

        返回:
            原始分数

        异常:
            RuntimeError: 原始分数为 None
        """
        raise NotImplementedError

    def final_score(self, X: Dict[str, Any]) -> float:
        """
        计算最终分数

        公式: final_score = offset + factor × raw_score

        参数:
            X: 特征字典

        返回:
            最终分数
        """
        raw = self.raw_score(X)
        if raw is None:
            raise RuntimeError("raw_score 返回了 None")
        return self.offset + self.factor * raw

    def explain(self, X: Dict[str, Any]) -> Dict[str, Any]:
        """
        计算完整解释信息

        返回:
            包含特征分数、原始分数、最终分数、特征分数类型的字典
        """
        fs = self.feature_score(X)
        raw = self.raw_score(X)
        if raw is None:
            raise RuntimeError("raw_score 返回了 None")
        final = self.offset + self.factor * raw

        return {
            "feature_score": fs,
            "feature_score_type": self._get_feature_score_type(),
            "raw_score": raw,
            "final_score": final,
        }

    def get_capabilities(self) -> ScorecardCapability:
        """获取引擎能力集"""
        return self.capabilities

    def _get_feature_score_type(self) -> str:
        """
        获取特征分数类型（子类可重写）

        返回:
            特征分数类型标识
        """
        return "unknown"

    @staticmethod
    def _validate_numeric_value(value: Any) -> Optional[float]:
        """
        验证并转换数值类型

        参数:
            value: 特征值

        返回:
            转换后的浮点数，无效时返回 None
        """
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        return None


class RuleScorecardEngine(BaseScorecardEngine):
    """
    规则评分卡引擎

    基于分箱的规则评分卡，支持数值型和分类型特征。

    分箱区间定义：
        - 数值型分箱采用左闭右开区间
        - 左边界为 None 表示负无穷，右边界为 None 表示正无穷
        - 分箱配置不允许重叠，不允许有空洞

    bins 格式:
        {
            "age": {
                "type": "numeric",
                "bins": [
                    {"min": None, "max": 25, "score": 20},
                    {"min": 25, "max": 35, "score": 40},
                    {"min": 35, "max": 50, "score": 60},
                    {"min": 50, "max": None, "score": 80},
                ]
            },
            "gender": {
                "type": "categorical",
                "bins": [
                    {"value": "male", "score": 10},
                    {"value": "female", "score": 20},
                ]
            }
        }

    属性:
        bins: 分箱配置字典
        default_score: 默认分数
    """

    def __init__(
        self,
        bins: Dict[str, Any],
        default_score: float = 0.0,
        offset: float = 0.0,
        factor: float = 1.0,
    ):
        """
        初始化规则评分卡引擎

        参数:
            bins: 分箱配置字典
            default_score: 默认分数，默认 0.0
            offset: 分数偏移量，默认 0.0
            factor: 分数缩放因子，默认 1.0
        """
        super().__init__(offset, factor)
        self.bins = bins
        self.default_score = default_score
        self._validate_bins()
        self.capabilities = infer_scorecard_capabilities(self)

    def _validate_bins(self) -> None:
        """校验分箱配置，检查重叠和空洞"""
        if not __debug__:
            return

        for feature, cfg in self.bins.items():
            if cfg["type"] != "numeric":
                continue

            bins = cfg["bins"]
            if not bins:
                raise ValueError(f"特征 {feature} 的分箱配置为空")

            prev_max = None
            for i, b in enumerate(bins):
                min_val = b.get("min")
                max_val = b.get("max")

                # 检查第一个分箱左边界
                if i == 0:
                    if min_val is not None:
                        raise ValueError(
                            f"分箱配置错误: 特征 {feature} 的第一个分箱左边界应为 None，"
                            f"当前为 {min_val}"
                        )
                else:
                    if min_val is None:
                        raise ValueError(
                            f"分箱配置错误: 特征 {feature} 的第 {i + 1} 个分箱左边界不能为 None"
                        )

                # 检查最后一个分箱右边界
                if i == len(bins) - 1:
                    if max_val is not None:
                        raise ValueError(
                            f"分箱配置错误: 特征 {feature} 的最后一个分箱右边界应为 None，"
                            f"当前为 {max_val}"
                        )
                else:
                    if max_val is None:
                        raise ValueError(
                            f"分箱配置错误: 特征 {feature} 的第 {i + 1} 个分箱右边界不能为 None"
                        )

                # 检查重叠
                if prev_max is not None and min_val is not None and prev_max > min_val:
                    raise ValueError(
                        f"分箱配置错误: 特征 {feature} 的分箱存在重叠，"
                        f"第 {i} 箱最大值 {prev_max} 大于第 {i + 1} 箱最小值 {min_val}"
                    )

                # 检查空洞
                if prev_max is not None and min_val is not None and prev_max < min_val:
                    raise ValueError(
                        f"分箱配置错误: 特征 {feature} 的分箱存在空洞，"
                        f"区间 ({prev_max}, {min_val}) 没有覆盖"
                    )

                prev_max = max_val

    def _get_feature_score_type(self) -> str:
        """返回规则评分卡的特征分数类型"""
        return "rule"

    def _match_numeric_bin(self, feature: str, value: float) -> float:
        """
        匹配数值型分箱

        参数:
            feature: 特征名称
            value: 特征值

        返回:
            分箱分数
        """
        cfg = self.bins[feature]

        for b in cfg["bins"]:
            min_val = b.get("min")
            max_val = b.get("max")

            if (min_val is None or value >= min_val) and \
               (max_val is None or value < max_val):
                return float(b["score"])

        return self.default_score

    def _match_categorical_bin(self, feature: str, value: str) -> float:
        """
        匹配分类型分箱

        参数:
            feature: 特征名称
            value: 特征值

        返回:
            分箱分数
        """
        cfg = self.bins[feature]

        for b in cfg["bins"]:
            if value == b["value"]:
                return float(b["score"])

        return self.default_score

    def feature_score(self, X: Dict[str, Any]) -> Dict[str, float]:
        """
        计算各特征分数

        参数:
            X: 特征字典

        返回:
            特征分数字典
        """
        result: Dict[str, float] = {}

        for feature, cfg in self.bins.items():
            value = X.get(feature)

            if value is None:
                result[feature] = self.default_score
                continue

            if cfg["type"] == "numeric":
                numeric_val = self._validate_numeric_value(value)
                if numeric_val is None:
                    result[feature] = self.default_score
                    continue
                result[feature] = self._match_numeric_bin(feature, numeric_val)

            elif cfg["type"] == "categorical":
                if not isinstance(value, str):
                    result[feature] = self.default_score
                    continue
                result[feature] = self._match_categorical_bin(feature, value)

            else:
                result[feature] = self.default_score

        return result

    def raw_score(self, X: Dict[str, Any]) -> float:
        """
        计算原始分数

        公式: raw_score = Σ feature_score

        参数:
            X: 特征字典

        返回:
            原始分数
        """
        return sum(self.feature_score(X).values())


class LogisticRegressionScorecardEngine(BaseScorecardEngine):
    """
    逻辑回归评分卡引擎

    基于系数的逻辑回归评分卡，支持特征分数计算、分数缩放和概率输出。

    公式:
        raw_score = intercept + Σ(coef × value)
        final_score = offset + factor × raw_score
        probability = 1 / (1 + exp(-raw_score))

    属性:
        coef: 特征系数字典
        _intercept: 截距
    """

    def __init__(
        self,
        coef: Dict[str, float],
        intercept: float = 0.0,
        offset: float = 0.0,
        factor: float = 1.0,
    ):
        """
        初始化逻辑回归评分卡引擎

        参数:
            coef: 特征系数字典
            intercept: 截距，默认 0.0
            offset: 分数偏移量，默认 0.0
            factor: 分数缩放因子，默认 1.0
        """
        super().__init__(offset, factor)
        self.coef = coef
        self._intercept = intercept
        self.capabilities = infer_scorecard_capabilities(self)

    def _get_feature_score_type(self) -> str:
        """返回逻辑回归评分卡的特征分数类型"""
        return "linear"

    def feature_score(self, X: Dict[str, Any]) -> Dict[str, float]:
        """
        计算各特征分数

        公式: 特征分数 = coef × value

        参数:
            X: 特征字典

        返回:
            特征分数字典
        """
        result: Dict[str, float] = {}

        for feature, weight in self.coef.items():
            value = X.get(feature)

            numeric_val = self._validate_numeric_value(value)
            if numeric_val is None:
                result[feature] = 0.0
                continue

            result[feature] = weight * numeric_val

        return result

    def raw_score(self, X: Dict[str, Any]) -> float:
        """
        计算原始分数

        公式: raw_score = intercept + Σ(coef × value)

        参数:
            X: 特征字典

        返回:
            原始分数
        """
        fs = self.feature_score(X)
        return sum(fs.values()) + self._intercept

    def predict_proba(self, X: Dict[str, Any]) -> float:
        """
        预测违约概率

        参数:
            X: 特征字典

        返回:
            违约概率
        """
        raw = self.raw_score(X)
        return 1.0 / (1.0 + math.exp(-raw))


class PipelineScorecardEngine(BaseScorecardEngine):
    """
    管道评分卡引擎

    支持 WOE 转换配合逻辑回归的管道评分卡。

    pipeline 格式:
        {
            "woe_transformer": WOETransformer实例,
            "model": 逻辑回归模型,
            "features": 特征名称列表
        }

    属性:
        woe_transformer: WOE 转换器
        features: 特征名称列表
        _coef: 模型系数数组
        _intercept: 模型截距
    """

    def __init__(
        self,
        woe_transformer: Any,
        model: Any,
        features: List[str],
        offset: float = 0.0,
        factor: float = 1.0,
    ):
        """
        初始化管道评分卡引擎

        参数:
            woe_transformer: WOE 转换器实例
            model: 逻辑回归模型
            features: 特征名称列表
            offset: 分数偏移量，默认 0.0
            factor: 分数缩放因子，默认 1.0

        异常:
            ValueError: 模型没有 coef_ 属性
        """
        super().__init__(offset, factor)
        self.woe_transformer = woe_transformer
        self.features = features
        self.capabilities = infer_scorecard_capabilities(self)

        # 提取模型系数
        if hasattr(model, "coef_"):
            self._coef = model.coef_.flatten()
        else:
            raise ValueError("管道评分卡引擎的模型没有 coef_ 属性")

        # 提取截距
        if hasattr(model, "intercept_"):
            self._intercept = float(model.intercept_[0])
        else:
            self._intercept = 0.0

    def _get_feature_score_type(self) -> str:
        """返回管道评分卡的特征分数类型"""
        return "woe_linear"

    def _apply_woe(self, X: Dict[str, Any]) -> Dict[str, float]:
        """
        应用 WOE 转换

        参数:
            X: 特征字典

        返回:
            WOE 转换后的特征字典
        """
        return self.woe_transformer.transform(X)

    def feature_score(self, X: Dict[str, Any]) -> Dict[str, float]:
        """
        计算各特征分数

        公式: 特征分数 = coef × woe

        参数:
            X: 特征字典

        返回:
            特征分数字典
        """
        X_woe = self._apply_woe(X)

        result: Dict[str, float] = {}

        for i, feature in enumerate(self.features):
            value = X_woe.get(feature, 0.0)

            numeric_val = self._validate_numeric_value(value)
            if numeric_val is None:
                result[feature] = 0.0
                continue

            result[feature] = self._coef[i] * numeric_val

        return result

    def raw_score(self, X: Dict[str, Any]) -> float:
        """
        计算原始分数

        公式: raw_score = intercept + Σ(coef × woe)

        参数:
            X: 特征字典

        返回:
            原始分数
        """
        fs = self.feature_score(X)
        return sum(fs.values()) + self._intercept

    def predict_proba(self, X: Dict[str, Any]) -> float:
        """
        预测违约概率

        参数:
            X: 特征字典

        返回:
            违约概率
        """
        raw = self.raw_score(X)
        return 1.0 / (1.0 + math.exp(-raw))


def create_scorecard_engine(mode: str, **kwargs) -> BaseScorecardEngine:
    """
    创建评分卡引擎

    参数:
        mode: 引擎类型，可选 'rule', 'logistic_regression', 'pipeline'
        **kwargs: 引擎特定参数
            - rule 模式: bins, default_score, offset, factor
            - logistic_regression 模式: coef, intercept, offset, factor
            - pipeline 模式: woe_transformer, model, features, offset, factor

    返回:
        BaseScorecardEngine 实例

    异常:
        ValueError: 不支持的引擎类型
    """
    if mode == "rule":
        return RuleScorecardEngine(
            bins=kwargs["bins"],
            default_score=kwargs.get("default_score", 0.0),
            offset=kwargs.get("offset", 0.0),
            factor=kwargs.get("factor", 1.0),
        )

    if mode == "logistic_regression":
        return LogisticRegressionScorecardEngine(
            coef=kwargs["coef"],
            intercept=kwargs.get("intercept", 0.0),
            offset=kwargs.get("offset", 0.0),
            factor=kwargs.get("factor", 1.0),
        )

    if mode == "pipeline":
        return PipelineScorecardEngine(
            woe_transformer=kwargs["woe_transformer"],
            model=kwargs["model"],
            features=kwargs["features"],
            offset=kwargs.get("offset", 0.0),
            factor=kwargs.get("factor", 1.0),
        )

    raise ValueError(f"不支持的评分卡引擎类型: {mode}")


__all__ = [
    'BaseScorecardEngine',
    'RuleScorecardEngine',
    'LogisticRegressionScorecardEngine',
    'PipelineScorecardEngine',
    'create_scorecard_engine',
]