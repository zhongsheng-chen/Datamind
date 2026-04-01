# datamind/core/scoring/explain.py

"""特征贡献解释器

提供统一的特征贡献解释接口，所有输出统一为 logit 空间（bad/good）。

核心原则：
    - logit 是唯一核心解释空间（与 Score 模块完全一致）
    - Explainer 只负责“贡献计算”，不负责“评分转换”
    - score 转换应由 Score 模块完成

核心功能：
    - explain_logit: 单条样本特征贡献（logit 空间）
    - explain_logit_batch: 批量特征贡献（logit 空间）
    - get_feature_importance: 全局特征重要性（基于 logit |abs mean|）
    - get_shap_summary: SHAP 统计摘要（logit 空间）
    - set_background_data: 设置背景数据（用于 KernelExplainer）

特性：
    - SHAP 统一计算：单条/批量共用 _compute_shap，消除重复代码
    - 自动降级：批量解释失败时自动降级到单条循环
    - 能力集中：_supports_shap 统一管理能力判断，易于扩展
    - 生产容错：单条失败不阻塞批量，返回空字典
    - 缓存优化：SHAP explainer 按模型 ID 缓存，避免重复创建
"""

from typing import Dict, List, Optional, Any
import numpy as np

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability, has_capability
from datamind.core.logging.manager import LogManager

try:
    import shap
except ImportError:
    shap = None

_log_manager = LogManager()
logger = _log_manager.app_logger


class Explainer:
    """特征贡献解释器（统一 logit 空间）"""

    def __init__(self, model_adapter: BaseModelAdapter):
        """
        初始化解释器

        参数:
            model_adapter: 模型适配器实例
        """
        self.model_adapter = model_adapter

        # 模型类型判断
        self.is_scorecard = hasattr(model_adapter, "transformer")
        self.capabilities = model_adapter.get_capabilities()

        # SHAP explainer 缓存
        self._explainer_cache: Dict[str, Any] = {}

        # 背景数据（KernelExplainer）
        self._background_data: Optional[np.ndarray] = None

    # ==================== 能力判断 ====================

    def _supports_shap(self) -> bool:
        """检查是否支持 SHAP 解释"""
        return shap is not None and has_capability(
            self.capabilities, ScorecardCapability.SHAP
        )

    # ==================== SHAP 统一计算 ====================

    def _get_model_id(self) -> str:
        """获取模型唯一标识（用于缓存）"""
        if hasattr(self.model_adapter, "get_model_id"):
            return self.model_adapter.get_model_id()
        return str(id(self.model_adapter.model))

    def _get_shap_explainer(self):
        """
        获取 SHAP explainer

        TreeExplainer 优先（树模型），KernelExplainer 需显式设置背景数据。
        """
        if shap is None:
            raise RuntimeError("SHAP 未安装")

        model_id = self._get_model_id()

        if model_id in self._explainer_cache:
            return self._explainer_cache[model_id]

        # TreeExplainer 优先
        try:
            explainer = shap.TreeExplainer(self.model_adapter.model)
        except Exception:
            if self._background_data is None:
                raise RuntimeError(
                    "当前模型不支持 TreeExplainer，请先调用 set_background_data"
                )

            explainer = shap.KernelExplainer(
                self.model_adapter.model.predict_proba,
                self._background_data
            )

        self._explainer_cache[model_id] = explainer
        return explainer

    def _compute_shap(self, X_array: np.ndarray) -> np.ndarray:
        """
        统一 SHAP 计算（单条/批量通用）

        参数:
            X_array: 输入特征数组

        返回:
            SHAP 值数组（正类）
        """
        explainer = self._get_shap_explainer()
        shap_values = explainer.shap_values(X_array)

        # 二分类处理：统一取正类
        if isinstance(shap_values, list):
            return shap_values[1] if len(shap_values) > 1 else shap_values[0]

        return shap_values

    def _format_shap_output(self, row: np.ndarray) -> Dict[str, float]:
        """格式化 SHAP 输出为特征名-值字典"""
        # 将 NumPy 数组转换为 Python 列表
        values = row.tolist()
        feature_names = self.model_adapter.feature_names

        if feature_names:
            return dict(zip(feature_names, values))

        return {f"feature_{i}": v for i, v in enumerate(values)}

    # ==================== 评分卡解释 ====================

    def _explain_scorecard(self, X: Dict[str, float]) -> Dict[str, float]:
        """
        评分卡特征贡献（logit 空间）

        要求 adapter 实现 get_feature_logit 方法。
        """
        if not hasattr(self.model_adapter, "get_feature_logit"):
            return {}

        try:
            woe_features = self.model_adapter.transformer.transform(X)

            result = {}
            for feat, woe in woe_features.items():
                try:
                    val = self.model_adapter.get_feature_logit(feat, woe)
                    if np.isfinite(val):
                        result[feat] = float(val)
                except Exception:
                    continue

            return result

        except Exception:
            return {}

    # ==================== 背景数据 ====================

    def set_background_data(self, X_batch: List[Dict[str, float]]) -> None:
        """
        设置背景数据（用于 KernelExplainer）

        参数:
            X_batch: 背景样本特征字典列表
        """
        if not X_batch:
            return

        self._background_data = self.model_adapter.to_array_batch(X_batch)

    # ==================== 核心 API ====================

    def explain_logit(self, X: Dict[str, float]) -> Dict[str, float]:
        """
        单条样本解释（logit 空间）

        参数:
            X: 特征字典

        返回:
            特征对 logit 的贡献字典
        """
        try:
            if self.is_scorecard:
                return self._explain_scorecard(X)

            if self._supports_shap():
                arr = self.model_adapter.to_array(X)
                vals = self._compute_shap(arr)
                return self._format_shap_output(vals[0])

            return {}

        except Exception:
            return {}

    def explain_logit_batch(
        self,
        X_batch: List[Dict[str, float]]
    ) -> List[Dict[str, float]]:
        """
        批量解释（logit 空间）

        参数:
            X_batch: 特征字典列表

        返回:
            特征贡献字典列表
        """
        if not X_batch:
            return []

        try:
            if self.is_scorecard:
                return [self._explain_scorecard(x) for x in X_batch]

            if self._supports_shap():
                arr = self.model_adapter.to_array_batch(X_batch)
                vals = self._compute_shap(arr)
                return [self._format_shap_output(row) for row in vals]

        except Exception:
            # 批量失败时降级到单条循环
            return [self.explain_logit(x) for x in X_batch]

        return []

    # ==================== 全局重要性 ====================

    def get_feature_importance(
        self,
        X_batch: Optional[List[Dict[str, float]]] = None
    ) -> Dict[str, float]:
        """
        全局特征重要性（基于 logit |abs mean|）

        参数:
            X_batch: 样本列表（非评分卡模型需要）

        返回:
            特征重要性字典
        """
        if X_batch:
            results = self.explain_logit_batch(X_batch)

            agg = {}
            for r in results:
                for k, v in r.items():
                    agg[k] = agg.get(k, 0.0) + abs(v)

            n = len(results)
            return {k: v / n for k, v in agg.items()}

        return self.model_adapter.get_feature_importance() or {}

    # ==================== SHAP 统计 ====================

    def get_shap_summary(
        self,
        X_batch: List[Dict[str, float]]
    ) -> Dict[str, Any]:
        """
        SHAP 统计摘要（logit 空间）

        计算每个特征的 SHAP 值统计：均值、标准差、最小值、最大值、绝对值均值。

        参数:
            X_batch: 特征字典列表

        返回:
            摘要信息字典
        """
        results = self.explain_logit_batch(X_batch)
        if not results:
            return {}

        summary = {}
        features = set().union(*[r.keys() for r in results])

        for f in features:
            vals = np.array([r.get(f, 0.0) for r in results])

            summary[f] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
                "abs_mean": float(np.mean(np.abs(vals))),
            }

        return summary