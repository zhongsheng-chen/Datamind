# datamind/core/scoring/adapters/sklearn.py

"""Sklearn 模型适配器

支持 Scikit-learn 模型和 Pipeline 的适配器实现。

核心功能：
  - predict_proba: 预测违约概率
  - predict_proba_batch: 批量预测概率
  - decision_function: 获取原始 logit 值
  - decision_function_batch: 批量获取 logit 值
  - get_feature_importance: 获取特征重要性
  - get_capabilities: 获取模型能力集
  - get_coef: 获取特征系数（仅逻辑回归模型）
  - get_intercept: 获取截距项（仅逻辑回归模型）
  - get_feature_logit: 获取特征对 logit 的贡献（仅逻辑回归模型）

特性：
  - Pipeline 支持：自动处理 Pipeline 模型，提取最终估算器
  - 特征名提取：从 Pipeline 中自动提取特征名
  - 多模型支持：支持分类器和回归器
  - 重要性提取：支持 feature_importances_ 和 coef_
  - 批量预测优化：重写 predict_proba_batch 提升性能
"""

import numpy as np
from typing import Dict, List, Optional, Any

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability, infer_capabilities
from datamind.core.logging import get_logger

_logger = get_logger(__name__)


class SklearnAdapter(BaseModelAdapter):
    """Sklearn 模型适配器"""

    SUPPORTED_CAPABILITIES: ScorecardCapability = (
        ScorecardCapability.PREDICT_CLASS |
        ScorecardCapability.BATCH_PREDICT
    )

    def __init__(
        self,
        model,
        feature_names: Optional[List[str]] = None,
        data_types: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化适配器

        参数:
            model: sklearn 模型或 Pipeline
            feature_names: 特征名称列表（可选，不提供时尝试从模型提取）
            data_types: 特征数据类型映射，用于类型验证
        """
        super().__init__(model, feature_names, data_types)

        self.capabilities = infer_capabilities(self)

        # 如果是 Pipeline，尝试自动提取特征名
        if hasattr(model, 'named_steps') and feature_names is None:
            self._extract_feature_names_from_pipeline()

        # 预计算系数映射（用于逻辑回归模型）
        self._coef_map = self._build_coef_map()

        # 根据模型实际能力动态扩展实例能力
        self._adjust_capabilities_by_model()

    def get_capabilities(self) -> ScorecardCapability:
        """
        获取模型能力集

        返回:
            ScorecardCapability 位掩码
        """
        return self.capabilities

    def _adjust_capabilities_by_model(self) -> None:
        """根据模型实际能力动态扩展实例能力"""
        estimator = self._get_estimator()
        estimator_name = estimator.__class__.__name__.lower()

        # 逻辑回归（评分卡）额外支持的能力
        if 'logisticregression' in estimator_name or 'logistic' in estimator_name:
            if hasattr(estimator, 'coef_'):
                self.capabilities |= (
                    ScorecardCapability.PREDICT_SCORE |
                    ScorecardCapability.FEATURE_SCORE |
                    ScorecardCapability.EXPORT_SCORECARD
                )
                _logger.debug("检测到逻辑回归模型，启用评分卡能力")

        # 树模型额外支持的能力
        if hasattr(estimator, 'feature_importances_'):
            self.capabilities |= (
                ScorecardCapability.SHAP |
                ScorecardCapability.FEATURE_IMPORTANCE
            )
            _logger.debug("检测到树模型，启用特征重要性能力")

    def _get_estimator(self):
        """获取最终估算器"""
        if hasattr(self.model, 'named_steps'):
            return list(self.model.named_steps.values())[-1]
        return self.model

    def _build_coef_map(self) -> Optional[Dict[str, float]]:
        """构建特征系数映射（仅逻辑回归模型）"""
        estimator = self._get_estimator()

        if not hasattr(estimator, 'coef_'):
            return None

        coef = estimator.coef_
        if coef.ndim > 1:
            coef = coef[0]

        if self.feature_names:
            return {
                name: float(coef[i])
                for i, name in enumerate(self.feature_names)
                if i < len(coef)
            }
        else:
            return {
                f"feature_{i}": float(val)
                for i, val in enumerate(coef)
            }

    def _get_intercept(self) -> float:
        """获取截距项"""
        estimator = self._get_estimator()

        if hasattr(estimator, 'intercept_'):
            intercept = estimator.intercept_
            if isinstance(intercept, np.ndarray):
                return float(intercept[0]) if len(intercept) > 0 else 0.0
            return float(intercept)

        return 0.0

    def _extract_feature_names_from_pipeline(self):
        """从 Pipeline 中自动提取特征名"""
        try:
            last_step = list(self.model.named_steps.values())[-1]

            if hasattr(last_step, 'feature_names_in_'):
                self.feature_names = list(last_step.feature_names_in_)
                _logger.debug("从 Pipeline 提取特征名成功，数量: %d", len(self.feature_names))
            elif hasattr(self.model, 'get_feature_names_out'):
                try:
                    self.feature_names = list(self.model.get_feature_names_out())
                    _logger.debug("从 Pipeline get_feature_names_out 提取特征名成功，数量: %d", len(self.feature_names))
                except Exception:
                    pass

            if not self.feature_names:
                _logger.debug("无法提取特征名，将使用默认命名")

        except Exception as e:
            _logger.debug("从 Pipeline 提取特征名失败: %s", e)

    # ==================== 核心预测方法 ====================

    def predict_proba(self, X: np.ndarray) -> float:
        """
        预测违约概率

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            违约概率 (0-1)
        """
        try:
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X)[0][1]
            else:
                proba = float(self.model.predict(X)[0])
            return float(proba)
        except Exception as e:
            _logger.error("Sklearn 单条预测失败: %s", e)
            raise

    def predict_proba_batch(self, X: np.ndarray) -> List[float]:
        """
        批量预测概率

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            概率列表，长度 n_samples
        """
        try:
            if hasattr(self.model, "predict_proba"):
                return self.model.predict_proba(X)[:, 1].tolist()
            return self.model.predict(X).tolist()
        except Exception as e:
            _logger.error("Sklearn 批量预测失败: %s", e)
            raise

    def decision_function(self, X: np.ndarray) -> float:
        """
        获取原始 logit 值

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            logit 值
        """
        if hasattr(self.model, "decision_function"):
            return float(self.model.decision_function(X)[0])
        # 降级：从概率反推（不推荐，但作为 fallback）
        proba = self.predict_proba(X)
        proba = np.clip(proba, 1e-15, 1 - 1e-15)
        return float(np.log(proba / (1 - proba)))

    def decision_function_batch(self, X: np.ndarray) -> List[float]:
        """
        批量获取 logit 值

        参数:
            X: 输入特征数组，形状为 (n_samples, n_features)

        返回:
            logit 值列表
        """
        if hasattr(self.model, "decision_function"):
            return self.model.decision_function(X).tolist()
        return super().decision_function_batch(X)

    # ==================== 评分卡专用方法 ====================

    def predict_score(self, X: np.ndarray) -> float:
        """
        预测信用评分（仅逻辑回归模型）

        参数:
            X: 输入特征数组，形状为 (1, n_features)

        返回:
            对数几率（原始值，评分转换由 scoring.engine 负责）
        """
        if hasattr(self.model, "decision_function"):
            return float(self.model.decision_function(X)[0])

        proba = self.predict_proba(X)
        return float(np.log(proba / (1 - proba)))

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取特征重要性

        返回:
            特征重要性字典，键为特征名，值为重要性权重（已归一化）
        """
        estimator = self._get_estimator()
        importance = {}

        if hasattr(estimator, 'feature_importances_'):
            values = estimator.feature_importances_
        elif hasattr(estimator, 'coef_'):
            coef = estimator.coef_
            if coef.ndim > 1:
                coef = coef[0]
            values = np.abs(coef)
        else:
            _logger.debug("模型不支持特征重要性提取")
            return {}

        if self.feature_names:
            for i, name in enumerate(self.feature_names):
                if i < len(values):
                    importance[name] = float(values[i])
        else:
            for i, val in enumerate(values):
                importance[f"feature_{i}"] = float(val)

        total = sum(importance.values())
        if total > 0:
            for name in importance:
                importance[name] = importance[name] / total

        return importance

    def get_feature_score(self, feature_name: str, value: float) -> float:
        """
        获取单个特征对评分的贡献（仅逻辑回归模型）

        参数:
            feature_name: 特征名称
            value: 特征值

        返回:
            特征贡献分数

        异常:
            RuntimeError: 非逻辑回归模型
            ValueError: 特征不存在
        """
        if self._coef_map is None:
            raise RuntimeError("当前模型不支持特征分计算，仅逻辑回归模型支持")

        if feature_name not in self._coef_map:
            raise ValueError(f"特征 '{feature_name}' 不存在")

        return self._coef_map[feature_name] * value

    def get_all_feature_scores(self, features: Dict[str, float]) -> Dict[str, float]:
        """
        获取所有特征对评分的贡献（仅逻辑回归模型）

        参数:
            features: 特征字典

        返回:
            特征名到贡献分数的映射

        异常:
            RuntimeError: 非逻辑回归模型
        """
        if self._coef_map is None:
            raise RuntimeError("当前模型不支持特征分计算，仅逻辑回归模型支持")

        result = {}
        for feature_name, value in features.items():
            if feature_name in self._coef_map:
                result[feature_name] = self._coef_map[feature_name] * value

        return result

    def export_scorecard(self) -> Dict[str, any]:
        """
        导出评分卡配置（仅逻辑回归模型）

        返回:
            评分卡配置字典

        异常:
            RuntimeError: 非逻辑回归模型
        """
        if self._coef_map is None:
            raise RuntimeError("当前模型不支持评分卡导出，仅逻辑回归模型支持")

        return {
            "coefficients": self._coef_map.copy(),
            "intercept": self._get_intercept(),
            "feature_names": self.feature_names.copy() if self.feature_names else [],
        }

    def get_coef(self, feature_name: str) -> float:
        """
        获取特征系数（仅逻辑回归模型）

        参数:
            feature_name: 特征名称

        返回:
            特征系数

        异常:
            RuntimeError: 非逻辑回归模型
            ValueError: 特征不存在
        """
        if self._coef_map is None:
            raise RuntimeError("当前模型不支持系数提取，请确保模型类型为逻辑回归")

        if feature_name not in self._coef_map:
            raise ValueError(f"特征 '{feature_name}' 不存在")

        return self._coef_map[feature_name]

    def get_intercept(self) -> float:
        """
        获取截距项

        返回:
            截距值
        """
        return self._get_intercept()

    def get_feature_logit(self, feature_name: str, woe: float) -> float:
        """
        获取特征对 logit 的贡献（仅逻辑回归模型）

        对于逻辑回归模型，贡献 = coefficient × woe。

        参数:
            feature_name: 特征名称
            woe: 特征的 WOE 值

        返回:
            特征对 logit 的贡献值

        异常:
            RuntimeError: 非逻辑回归模型
            ValueError: 特征不存在
        """
        if self._coef_map is None:
            raise RuntimeError("当前模型不支持 get_feature_logit，仅逻辑回归模型支持")

        if feature_name not in self._coef_map:
            raise ValueError(f"特征 '{feature_name}' 不存在")

        return self._coef_map[feature_name] * woe