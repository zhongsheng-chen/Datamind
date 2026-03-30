# datamind/core/ml/explain/reason_code.py
"""拒绝原因生成器

银行核心模块：将技术特征分转换为业务可读的拒绝原因。

核心功能：
  - generate: 从特征分生成 TopN 拒绝原因

特性：
  - 规则驱动：支持配置化的拒绝原因映射
  - 分箱感知：可根据分箱标签匹配原因
  - 多维度：支持严重程度、分类
  - 可扩展：支持多语言

使用示例：
  >>> from datamind.core.ml.explain.reason_code import ReasonCodeEngine
  >>>
  >>> config = {
  ...     "income": [
  ...         {
  ...             "code": "RC_INCOME_LOW",
  ...             "rule": lambda x: x["bin"]["upper"] <= 5000,
  ...             "message": "收入较低，还款能力不足",
  ...             "severity": "HIGH",
  ...             "category": "AFFORDABILITY"
  ...         }
  ...     ]
  ... }
  >>> engine = ReasonCodeEngine(config, top_k=3)
  >>> reasons = engine.generate(explain_result)
"""

from typing import Dict, Any, List, Optional, Callable
import logging


class ReasonCodeEngine:
    """拒绝原因引擎"""

    def __init__(
        self,
        reason_config: Dict[str, List[Dict[str, Any]]],
        top_k: int = 3,
        threshold: float = 0.0
    ):
        """
        初始化拒绝原因引擎

        参数:
            reason_config: 拒绝原因配置
                格式：
                {
                    "age": [
                        {
                            "code": "RC_AGE_LOW",
                            "rule": lambda x: x["bin"]["lower"] < 25,
                            "message": "年龄较低，信用历史较短",
                            "severity": "MEDIUM",
                            "category": "DEMOGRAPHIC"
                        }
                    ]
                }
            top_k: 返回的拒绝原因数量
            threshold: 只考虑贡献分低于此阈值的特征（默认0，只取负向）
        """
        self.reason_config = reason_config
        self.top_k = top_k
        self.threshold = threshold
        self._logger = logging.getLogger(__name__)

    def generate(self, explain_result: List[Dict]) -> List[Dict[str, Any]]:
        """
        从解释结果生成拒绝原因

        参数:
            explain_result: ScorecardExplainer 的输出

        返回:
            拒绝原因列表，按影响从大到小排序
        """
        # 1️⃣ 筛选负向贡献（降低评分）
        negative_features = [
            x for x in explain_result
            if x["score"] < self.threshold
        ]

        # 2️⃣ 按影响排序（越负越靠前）
        negative_features.sort(key=lambda x: x["score"])

        # 3️⃣ 取 TopK
        top_features = negative_features[:self.top_k]

        results = []
        for feat in top_features:
            rc = self._match_reason(feat)
            if rc:
                results.append(rc)

        return results

    def _match_reason(self, feat: Dict) -> Optional[Dict]:
        """
        匹配拒绝原因

        参数:
            feat: 单个特征的解释结果

        返回:
            拒绝原因字典，包含 code、message、severity、category
        """
        feature = feat["feature"]
        rules = self.reason_config.get(feature, [])

        for rule in rules:
            try:
                if rule["rule"](feat):
                    return {
                        "code": rule["code"],
                        "feature": feature,
                        "message": rule["message"],
                        "impact": round(feat["score"], 2),
                        "severity": rule.get("severity", "MEDIUM"),
                        "category": rule.get("category", "GENERAL"),
                        "bin": feat["bin"]["label"]
                    }
            except Exception as e:
                self._logger.warning(
                    f"Reason code rule failed for {feature}: {e}"
                )
                continue

        # 默认拒绝原因（兜底）
        return {
            "code": "RC_GENERAL",
            "feature": feature,
            "message": f"{feature} 风险因素",
            "impact": round(feat["score"], 2),
            "severity": "LOW",
            "category": "GENERAL",
            "bin": feat["bin"]["label"]
        }