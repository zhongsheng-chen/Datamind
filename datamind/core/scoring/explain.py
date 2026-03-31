# datamind/core/scoring/explain.py

"""特征贡献解释器

提供统一的接口，用于获取单条或批量预测的特征贡献信息。

核心功能：
  - explain: 单条样本解释
  - explain_batch: 批量样本解释
  - get_feature_importance: 全局特征重要性
  - get_shap_summary: 获取 SHAP 摘要信息

特性：
  - 支持评分卡模型（WOE 分数贡献）
  - 支持非评分卡模型（SHAP 贡献）
  - 累计贡献由基线值和各特征贡献组成
  - 异常安全处理：模型未提供解释时返回空或默认值
  - 缓存优化：重复使用 SHAP Explainer 实例
"""

from typing import Dict, List, Optional, Any, Tuple
import numpy as np

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability, has_capability
from datamind.core.logging.manager import LogManager

try:
    import shap
except ImportError:
    shap = None


class Explainer:
    """特征贡献解释器

    根据模型类型提供特征贡献解释，支持评分卡和非评分卡模型。
    """

    def __init__(self, model_adapter: BaseModelAdapter, debug: bool = False):
        """
        初始化解释器

        参数:
            model_adapter: 模型适配器实例
            debug: 是否启用调试日志
        """
        self.model_adapter = model_adapter
        self._debug_enabled = debug

        # 获取日志器
        self._log_manager = LogManager()
        self.logger = self._log_manager.app_logger

        # 判断是否为评分卡模型（有 transformer 属性）
        self.is_scorecard = hasattr(model_adapter, "transformer")

        # 获取模型能力
        self.capabilities = model_adapter.get_capabilities()

        # SHAP 解释器缓存（按模型 ID）
        self._explainer_cache: Dict[int, Any] = {}

        # 背景样本缓存（用于 SHAP）
        self._background_data: Optional[np.ndarray] = None

        self._debug(
            "解释器初始化，评分卡模型: %s, SHAP 可用: %s",
            self.is_scorecard,
            shap is not None
        )

    def _debug(self, msg: str, *args) -> None:
        """调试输出"""
        if self._debug_enabled and self.logger:
            self.logger.debug(msg, *args)

    def _error(self, msg: str, *args) -> None:
        """错误输出"""
        if self.logger:
            self.logger.error(msg, *args)

    def _get_shap_explainer(self, background_data: Optional[np.ndarray] = None) -> Any:
        """
        获取或创建 SHAP 解释器

        参数:
            background_data: 背景样本数据（用于 KernelExplainer）

        返回:
            SHAP 解释器实例
        """
        model_id = id(self.model_adapter.model)

        if model_id in self._explainer_cache:
            return self._explainer_cache[model_id]

        self._debug("创建 SHAP 解释器，模型 ID: %d", model_id)

        # 尝试使用 TreeExplainer（适用于树模型）
        try:
            explainer = shap.TreeExplainer(self.model_adapter.model)
            self._debug("使用 TreeExplainer")
        except Exception:
            # 降级使用 KernelExplainer
            if background_data is None:
                self._error("KernelExplainer 需要背景样本数据")
                raise ValueError("KernelExplainer 需要提供 background_data")

            explainer = shap.KernelExplainer(
                self.model_adapter.model.predict_proba,
                background_data
            )
            self._debug("使用 KernelExplainer")

        self._explainer_cache[model_id] = explainer
        return explainer

    def set_background_data(self, X_batch: List[Dict[str, float]]) -> None:
        """
        设置背景样本数据（用于 KernelExplainer）

        参数:
            X_batch: 特征字典列表
        """
        if not X_batch:
            self._debug("背景样本数据为空")
            return

        # 转换为数组
        X_array = self.model_adapter.to_array_batch(X_batch)
        self._background_data = X_array
        self._debug("设置背景样本数据，样本数: %d", len(X_batch))

    def explain(self, X: Dict[str, float]) -> Dict[str, float]:
        """
        获取单条样本的特征贡献

        参数:
            X: 特征字典，格式 {"feature_name": value, ...}

        返回:
            特征贡献字典，格式 {"feature_name": 贡献值, ...}
            对于评分卡模型，贡献值已与基线分数组合可直接累加得到总分
        """
        try:
            # 评分卡模型：使用特征分数
            if self.is_scorecard:
                self._debug("使用评分卡模型解释")
                return self._explain_scorecard(X)

            # SHAP 解释（非评分卡模型）
            if shap and has_capability(self.capabilities, ScorecardCapability.SHAP):
                self._debug("使用 SHAP 解释")
                return self._explain_shap(X)

            # 模型不支持解释
            self._debug("模型不支持特征贡献解释")
            return {}

        except Exception as e:
            self._error("解释失败: %s", e)
            return {}

    def _explain_scorecard(self, X: Dict[str, float]) -> Dict[str, float]:
        """评分卡模型解释（特征分数）"""
        if not hasattr(self.model_adapter, 'transformer') or not self.model_adapter.transformer:
            return {}

        woe_features = self.model_adapter.transformer.transform(X)
        scores = {}

        for feat_name, woe in woe_features.items():
            try:
                scores[feat_name] = self.model_adapter.get_feature_score(feat_name, woe)
            except (RuntimeError, ValueError) as e:
                self._debug("获取特征 %s 分数失败: %s", feat_name, e)

        self._debug("评分卡解释完成，特征数: %d", len(scores))
        return scores

    def _explain_shap(self, X: Dict[str, float]) -> Dict[str, float]:
        """SHAP 模型解释"""
        try:
            # 获取解释器
            explainer = self._get_shap_explainer(self._background_data)

            # 将特征字典转换为数组
            X_array = self.model_adapter.to_array(X)

            # 计算 SHAP 值
            shap_values = explainer.shap_values(X_array)

            # 处理输出格式
            if isinstance(shap_values, list):
                # 二分类模型，取正类的 SHAP 值
                shap_vals = shap_values[1] if len(shap_values) > 1 else shap_values[0]
            else:
                shap_vals = shap_values

            # 构建结果字典
            if self.model_adapter.feature_names:
                result = {
                    feature: float(shap_vals[0][i])
                    for i, feature in enumerate(self.model_adapter.feature_names)
                }
            else:
                result = {
                    f"feature_{i}": float(val)
                    for i, val in enumerate(shap_vals[0])
                }

            self._debug("SHAP 解释完成，特征数: %d", len(result))
            return result

        except Exception as e:
            self._error("SHAP 解释失败: %s", e)
            return {}

    def explain_batch(
        self,
        X_batch: List[Dict[str, float]],
        use_vectorized: bool = True
    ) -> List[Dict[str, float]]:
        """
        批量获取特征贡献

        参数:
            X_batch: 特征字典列表，格式 [{"feature_name": value, ...}, ...]
            use_vectorized: 是否使用向量化计算（仅 SHAP）

        返回:
            特征贡献字典列表
        """
        if not X_batch:
            return []

        # 评分卡模型：循环计算
        if self.is_scorecard:
            return [self.explain(x) for x in X_batch]

        # SHAP 模型：尝试向量化计算
        if use_vectorized and shap and has_capability(self.capabilities, ScorecardCapability.SHAP):
            try:
                return self._explain_shap_batch(X_batch)
            except Exception as e:
                self._error("向量化批量解释失败，降级为循环: %s", e)

        # 降级：循环计算
        return [self.explain(x) for x in X_batch]

    def _explain_shap_batch(self, X_batch: List[Dict[str, float]]) -> List[Dict[str, float]]:
        """向量化批量 SHAP 解释"""
        self._debug("使用向量化批量 SHAP 解释，样本数: %d", len(X_batch))

        # 获取解释器
        explainer = self._get_shap_explainer(self._background_data)

        # 批量转换为数组
        X_array = self.model_adapter.to_array_batch(X_batch)

        # 批量计算 SHAP 值
        shap_values = explainer.shap_values(X_array)

        # 处理输出格式
        if isinstance(shap_values, list):
            # 二分类模型，取正类的 SHAP 值
            shap_vals = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        else:
            shap_vals = shap_values

        # 构建结果列表
        results = []
        feature_names = self.model_adapter.feature_names

        for i in range(len(X_batch)):
            if feature_names:
                result = {
                    feature: float(shap_vals[i][j])
                    for j, feature in enumerate(feature_names)
                }
            else:
                result = {
                    f"feature_{j}": float(val)
                    for j, val in enumerate(shap_vals[i])
                }
            results.append(result)

        self._debug("向量化批量 SHAP 解释完成")
        return results

    def get_feature_importance(
        self,
        X_batch: Optional[List[Dict[str, float]]] = None
    ) -> Dict[str, float]:
        """
        计算全局特征重要性

        参数:
            X_batch: 可选样本列表，用于非评分卡模型的 SHAP 重要性计算

        返回:
            特征重要性字典，值为绝对贡献平均值或评分卡权重
        """
        # 评分卡模型：从 transformer 获取 WOE 最大绝对值
        if self.is_scorecard and hasattr(self.model_adapter, 'transformer'):
            transformer = self.model_adapter.transformer
            if hasattr(transformer, 'binning'):
                importance = {}
                for feature, bins in transformer.binning.items():
                    importance[feature] = max(abs(b.woe) for b in bins)
                self._debug("从 transformer 获取特征重要性，特征数: %d", len(importance))
                return importance

        # SHAP 重要性（非评分卡模型）
        if X_batch and shap and has_capability(self.capabilities, ScorecardCapability.SHAP):
            self._debug("使用 SHAP 计算全局特征重要性，样本数: %d", len(X_batch))

            agg = {}
            for x in X_batch:
                vals = self.explain(x)
                for k, v in vals.items():
                    agg[k] = agg.get(k, 0) + abs(v)

            n = len(X_batch)
            result = {k: v / n for k, v in agg.items()}
            self._debug("SHAP 重要性计算完成，特征数: %d", len(result))
            return result

        # 从适配器获取特征重要性
        importance = self.model_adapter.get_feature_importance()
        if importance:
            self._debug("从适配器获取特征重要性，特征数: %d", len(importance))
            return importance

        self._debug("无法计算全局特征重要性")
        return {}

    def get_shap_summary(
        self,
        X_batch: List[Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        获取 SHAP 摘要信息（平均值、标准差、最大最小值）

        参数:
            X_batch: 特征字典列表

        返回:
            摘要信息字典
        """
        if not X_batch:
            return {}

        # 计算所有样本的 SHAP 值
        shap_results = self.explain_batch(X_batch, use_vectorized=True)

        if not shap_results:
            return {}

        # 按特征聚合统计
        summary = {}
        feature_names = set()
        for result in shap_results:
            feature_names.update(result.keys())

        for feature in feature_names:
            values = [r.get(feature, 0) for r in shap_results]
            summary[feature] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "abs_mean": float(np.mean(np.abs(values))),
            }

        return summary