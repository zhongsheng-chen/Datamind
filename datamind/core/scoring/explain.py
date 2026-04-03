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

import numpy as np
from typing import Dict, List, Optional, Any

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability, has_capability
from datamind.core.logging import get_logger

try:
    import shap
except ImportError:
    shap = None

logger = get_logger(__name__)


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

        logger.debug("特征贡献解释器初始化完成，评分卡模型: %s, 支持SHAP: %s",
                    self.is_scorecard, self._supports_shap())

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
            logger.debug("使用缓存的 SHAP explainer: %s", model_id)
            return self._explainer_cache[model_id]

        # TreeExplainer 优先
        try:
            explainer = shap.TreeExplainer(self.model_adapter.model)
            logger.debug("创建 TreeExplainer 成功: %s", model_id)
        except Exception as e:
            # 如果 TreeExplainer 失败，尝试 KernelExplainer
            if self._background_data is None:
                logger.error("TreeExplainer 失败且未设置背景数据: %s", e)
                raise RuntimeError(
                    "当前模型不支持 TreeExplainer，请先调用 set_background_data"
                ) from e

            logger.debug("TreeExplainer 失败，使用 KernelExplainer: %s", e)
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
            logger.debug("模型不支持 get_feature_logit，无法解释评分卡")
            return {}

        try:
            woe_features = self.model_adapter.transformer.transform(X)

            result = {}
            for feat, woe in woe_features.items():
                try:
                    val = self.model_adapter.get_feature_logit(feat, woe)
                    if np.isfinite(val):
                        result[feat] = float(val)
                except Exception as e:
                    logger.debug("获取特征 %s 的 logit 贡献失败: %s", feat, e)
                    continue

            return result

        except Exception as e:
            logger.error("评分卡解释失败: %s", e)
            return {}

    # ==================== 背景数据 ====================

    def set_background_data(self, X_batch: List[Dict[str, float]]) -> None:
        """
        设置背景数据（用于 KernelExplainer）

        参数:
            X_batch: 背景样本特征字典列表
        """
        if not X_batch:
            logger.debug("背景数据为空，跳过设置")
            return

        self._background_data = self.model_adapter.to_array_batch(X_batch)
        logger.info("背景数据设置完成，样本数: %d", len(X_batch))

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

            logger.debug("模型不支持任何解释方式")
            return {}

        except Exception as e:
            logger.error("单条解释失败: %s", e)
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
            logger.debug("批量解释输入为空")
            return []

        try:
            if self.is_scorecard:
                logger.debug("使用评分卡批量解释，样本数: %d", len(X_batch))
                return [self._explain_scorecard(x) for x in X_batch]

            if self._supports_shap():
                logger.debug("使用 SHAP 批量解释，样本数: %d", len(X_batch))
                arr = self.model_adapter.to_array_batch(X_batch)
                vals = self._compute_shap(arr)
                return [self._format_shap_output(row) for row in vals]

        except Exception as e:
            # 批量失败时降级到单条循环
            logger.warning("批量解释失败，降级为单条循环: %s", e)
            return [self.explain_logit(x) for x in X_batch]

        logger.debug("模型不支持任何解释方式")
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
            if n > 0:
                importance = {k: v / n for k, v in agg.items()}
                logger.info("基于 SHAP 计算特征重要性完成，特征数: %d", len(importance))
                return importance
            return {}

        importance = self.model_adapter.get_feature_importance() or {}
        if importance:
            logger.info("从适配器获取特征重要性，特征数: %d", len(importance))
        return importance

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
            logger.debug("SHAP 统计摘要无数据")
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

        logger.debug("SHAP 统计摘要计算完成，特征数: %d", len(summary))
        return summary