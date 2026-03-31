# datamind/core/scoring/engine.py

"""评分引擎

提供统一接口进行模型评分和特征解释。

核心功能：
  - score: 单条样本评分
  - score_batch: 批量样本评分
  - explain: 单条样本特征贡献解释
  - explain_batch: 批量特征贡献解释

特性：
  - 支持多种模型类型（评分卡/非评分卡）
  - 自动处理特征转换（WOE、缺失值处理）
  - 输出概率和分数，支持批量计算
  - 异常安全处理，保证评分流程稳定
"""

from typing import Dict, List, Optional, Any, Tuple

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import (
    ScorecardCapability,
    has_capability,
    get_capability_list
)
from datamind.core.scoring.score import Score
from datamind.core.scoring.transform import WOETransformer
from datamind.core.logging.manager import LogManager


class ScoringEngine:
    """评分引擎主入口"""

    def __init__(
        self,
        model_adapter: BaseModelAdapter,
        transformer: Optional[WOETransformer] = None,
        pdo: Optional[float] = None,
        base_score: Optional[float] = None,
        base_odds: Optional[float] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        debug: bool = False
    ):
        """
        初始化评分引擎

        参数:
            model_adapter: 已加载的模型适配器实例
            transformer: 可选特征转换器（评分卡模型使用）
            pdo: 分数翻倍点，默认 50
            base_score: 基础分数，默认 600
            base_odds: 基准赔率，默认 20
            min_score: 最低分数限制，默认 0
            max_score: 最高分数限制，默认 1000
            debug: 是否启用调试日志
        """
        self.model_adapter = model_adapter
        self.transformer = transformer
        self._debug_enabled = debug

        # 获取日志器
        self._log_manager = LogManager()
        self.logger = self._log_manager.app_logger

        # 初始化概率到分数的转换器
        self.score_converter = Score(
            pdo=pdo,
            base_score=base_score,
            base_odds=base_odds,
            min_score=min_score,
            max_score=max_score
        )

        # 获取模型能力
        self.capabilities = model_adapter.get_capabilities()

        # 检查是否支持批量预测
        self._supports_batch = has_capability(
            self.capabilities, ScorecardCapability.BATCH_PREDICT
        )

        self._debug(
            "评分引擎初始化完成，能力: %s, 支持批量: %s",
            get_capability_list(self.capabilities),
            self._supports_batch
        )

    def _debug(self, msg: str, *args) -> None:
        """调试输出"""
        if self._debug_enabled and self.logger:
            self.logger.debug(msg, *args)

    def _error(self, msg: str, *args) -> None:
        """错误输出"""
        if self.logger:
            self.logger.error(msg, *args)

    def _transform_features(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        转换特征（处理缺失值和 WOE）

        参数:
            features: 原始特征字典

        返回:
            转换后的特征字典
        """
        if self.transformer:
            try:
                return self.transformer.transform(features)
            except ValueError as e:
                self._error("特征转换失败: %s", e)
                raise
        return features

    def score(self, features: Dict[str, Any], return_proba: bool = True) -> Dict[str, Optional[float]]:
        """
        单条样本评分

        参数:
            features: 特征字典
            return_proba: 是否返回预测概率

        返回:
            字典，包括：
                "score": 信用分
                "proba": 违约概率（可选）
        """
        try:
            # 特征转换
            transformed = self._transform_features(features)

            # 预测概率
            X_array = self.model_adapter.to_array(transformed)
            proba = self.model_adapter.predict_proba(X_array)
            self._debug("预测概率: %.6f", proba)

            result = {
                "score": self.score_converter.to_score(proba),
            }
            if return_proba:
                result["proba"] = proba

            return result

        except Exception as e:
            self._error("单条评分失败: %s", e)
            return {"score": None, "proba": None if return_proba else None}

    def score_batch(
        self,
        features_list: List[Dict[str, Any]],
        return_proba: bool = True,
        skip_errors: bool = False
    ) -> List[Dict[str, Optional[float]]]:
        """
        批量样本评分

        参数:
            features_list: 特征字典列表
            return_proba: 是否返回预测概率
            skip_errors: 是否跳过错误样本（返回 None）

        返回:
            字典列表
        """
        if not features_list:
            self._debug("输入为空列表，返回空结果")
            return []

        # 优化：使用批量预测（如果支持）
        if self._supports_batch:
            try:
                return self._score_batch_vectorized(features_list, return_proba, skip_errors)
            except Exception as e:
                if skip_errors:
                    self._error("批量预测失败，降级为循环预测: %s", e)
                else:
                    raise

        # 降级：循环预测
        return self._score_batch_loop(features_list, return_proba, skip_errors)

    def _score_batch_vectorized(
        self,
        features_list: List[Dict[str, Any]],
        return_proba: bool = True,
        skip_errors: bool = False
    ) -> List[Dict[str, Optional[float]]]:
        """向量化批量评分（性能优化）"""
        self._debug("使用向量化批量评分，样本数: %d", len(features_list))

        # 批量特征转换
        transformed_list = []
        valid_indices = []
        for i, features in enumerate(features_list):
            try:
                transformed = self._transform_features(features)
                transformed_list.append(transformed)
                valid_indices.append(i)
            except Exception as e:
                if skip_errors:
                    self._error("第 %d 条特征转换失败: %s", i, e)
                else:
                    raise

        if not transformed_list:
            return [{"score": None, "proba": None if return_proba else None} for _ in features_list]

        # 批量转换为数组
        X_batch = self.model_adapter.to_array_batch(transformed_list)

        # 批量预测概率
        probs = self.model_adapter.predict_proba_batch(X_batch)

        # 批量转换分数
        scores = self.score_converter.to_score_batch(probs)

        # 构建结果
        results = [{"score": None, "proba": None if return_proba else None} for _ in features_list]
        for idx, i in enumerate(valid_indices):
            results[i] = {"score": scores[idx]}
            if return_proba:
                results[i]["proba"] = probs[idx]

        return results

    def _score_batch_loop(
        self,
        features_list: List[Dict[str, Any]],
        return_proba: bool = True,
        skip_errors: bool = False
    ) -> List[Dict[str, Optional[float]]]:
        """循环批量评分（降级方案）"""
        self._debug("使用循环批量评分，样本数: %d", len(features_list))

        results = []
        for i, features in enumerate(features_list):
            try:
                result = self.score(features, return_proba=return_proba)
                results.append(result)
            except Exception as e:
                if skip_errors:
                    self._error("第 %d 条评分失败: %s，返回 None", i, e)
                    results.append({"score": None, "proba": None if return_proba else None})
                else:
                    self._error("第 %d 条评分失败: %s", i, e)
                    raise

        return results

    def explain(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        获取单条样本特征贡献解释

        参数:
            features: 特征字典

        返回:
            特征贡献字典
        """
        # 评分卡模型：使用特征分数
        if has_capability(self.capabilities, ScorecardCapability.FEATURE_SCORE):
            try:
                # 特征转换
                transformed = self._transform_features(features)

                # 计算特征贡献
                scores = {}
                for feat_name, woe in transformed.items():
                    try:
                        scores[feat_name] = self.model_adapter.get_feature_score(feat_name, woe)
                    except (RuntimeError, ValueError) as e:
                        self._debug("获取特征 %s 分数失败: %s", feat_name, e)

                self._debug("特征贡献计算完成，特征数: %d", len(scores))
                return scores

            except Exception as e:
                self._error("特征贡献解释失败: %s", e)
                return {}

        # SHAP 解释（非评分卡模型）
        if has_capability(self.capabilities, ScorecardCapability.SHAP):
            self._debug("使用 SHAP 解释")
            try:
                X_array = self.model_adapter.to_array(features)

                # 需要 model_adapter 支持 SHAP
                if hasattr(self.model_adapter, "get_shap_values"):
                    shap_values = self.model_adapter.get_shap_values(X_array)
                    if shap_values:
                        return shap_values
            except Exception as e:
                self._error("SHAP 解释失败: %s", e)

        # 模型不支持解释
        self._debug("模型不支持特征贡献解释")
        return {}

    def explain_batch(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> List[Dict[str, float]]:
        """
        批量获取特征贡献解释

        参数:
            features_list: 特征字典列表
            skip_errors: 是否跳过错误样本（返回空字典）

        返回:
            特征贡献字典列表
        """
        results = []
        for i, features in enumerate(features_list):
            try:
                results.append(self.explain(features))
            except Exception as e:
                if skip_errors:
                    self._error("第 %d 条解释失败: %s，返回空字典", i, e)
                    results.append({})
                else:
                    self._error("第 %d 条解释失败: %s", i, e)
                    raise

        return results

    def get_feature_importance(self) -> Dict[str, float]:
        """
        获取全局特征重要性

        返回:
            特征重要性字典
        """
        # 评分卡模型：从 transformer 获取
        if self.transformer and hasattr(self.transformer, 'binning'):
            importance = {}
            for feature, bins in self.transformer.binning.items():
                # 取 WOE 最大绝对值作为特征重要性
                max_woe = max(abs(b.woe) for b in bins)
                importance[feature] = max_woe
            self._debug("从 transformer 获取特征重要性，特征数: %d", len(importance))
            return importance

        # 其他模型：从适配器获取
        importance = self.model_adapter.get_feature_importance()
        if importance:
            self._debug("从适配器获取特征重要性，特征数: %d", len(importance))
        return importance

    def get_score_range(self) -> Tuple[float, float]:
        """
        获取有效分数范围

        返回:
            (min_score, max_score) 元组
        """
        return self.score_converter.get_score_range()

    def is_scorecard_model(self) -> bool:
        """
        检查是否为评分卡模型

        返回:
            True 表示是评分卡模型，False 表示不是
        """
        return has_capability(self.capabilities, ScorecardCapability.FEATURE_SCORE)

    def get_model_capabilities(self) -> List[str]:
        """
        获取模型能力列表

        返回:
            能力名称列表
        """
        return get_capability_list(self.capabilities)