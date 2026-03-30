# datamind/core/ml/explain/scorecard.py
"""评分卡解释器

基于 WOE 体系计算特征分。

核心功能：
  - explain: 计算每个特征的特征分

公式：
    feature_score = -factor * coefficient * WOE

特性：
  - 完整分箱信息：返回 bin_id、bin_label、边界等
  - 风险信息：可选返回坏账率、样本占比
  - 按贡献排序：特征分按绝对值降序排列

使用示例：
  >>> from datamind.core.ml.explain.scorecard import ScorecardExplainer
  >>>
  >>> explainer = ScorecardExplainer()
  >>> result = explainer.explain(adapter, feature_meta, factor=20.0)
  >>> for item in result:
  >>>     print(f"{item['feature']}: {item['score']:+.2f}")
"""

from typing import Dict, Any, List


class ScorecardExplainer:
    """评分卡解释器

    基于 WOE 体系计算特征分，返回完整的特征贡献分解。
    """

    def explain(
        self,
        adapter,
        feature_meta: Dict[str, Dict],
        factor: float
    ) -> List[Dict[str, Any]]:
        """
        解释评分结果

        参数:
            adapter: 模型适配器（需实现 get_coef 方法）
            feature_meta: WOE 转换后的特征元信息
            factor: 评分因子（pdo / ln(2)）

        返回:
            特征分列表，按贡献绝对值降序排列

        示例:
            >>> explainer = ScorecardExplainer()
            >>> result = explainer.explain(adapter, feature_meta, 20.0)
            >>> result[0]
            {
                "feature": "age",
                "value": 45,
                "bin": {
                    "id": 3,
                    "label": "[40, 50)",
                    "lower": 40,
                    "upper": 50,
                    "is_missing": False,
                    "description": "中年稳定客群"
                },
                "woe": 0.12,
                "coefficient": -0.8,
                "score": 8.6,
                "risk": {"bad_rate": 0.08, "sample_ratio": 0.25}
            }
        """
        results = []

        for feature, meta in feature_meta.items():
            coef = adapter.get_coef(feature)

            # 特征分 = -factor * coefficient * WOE
            score = -factor * coef * meta["woe"]

            result_item = {
                "feature": feature,
                "value": meta["value"],
                "bin": {
                    "id": meta["bin_id"],
                    "label": meta["bin_label"],
                    "lower": meta["lower"],
                    "upper": meta["upper"],
                    "is_missing": meta["is_missing"],
                    "description": meta.get("description"),
                },
                "woe": round(meta["woe"], 4),
                "coefficient": round(coef, 4),
                "score": round(score, 2),
            }

            # 可选：风险信息
            if meta.get("bad_rate") is not None:
                result_item["risk"] = {
                    "bad_rate": round(meta["bad_rate"], 4),
                    "sample_ratio": round(meta["sample_ratio"], 4) if meta.get("sample_ratio") else None
                }

            results.append(result_item)

        # 按贡献绝对值降序排列
        results.sort(key=lambda x: abs(x["score"]), reverse=True)

        return results