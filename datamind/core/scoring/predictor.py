# datamind/core/scoring/predictor.py

"""模型预测封装

统一封装模型预测和评分流程：
  - predict_proba: 返回违约概率
  - predict_proba_batch: 返回批量概率
  - predict_score: 单样本概率 → 信用分数
  - predict_score_batch: 批量概率 → 信用分数列表

特性：
  - 支持单样本和批量预测
  - 自动处理特征转换
  - 支持向量化批量预测（性能优化）
  - 异常安全处理
  - 特征验证（可选）
"""

from typing import List, Dict, Any, Optional, Union
import numpy as np

from datamind.core.scoring.adapters.base import BaseModelAdapter
from datamind.core.scoring.capability import ScorecardCapability, has_capability
from datamind.core.scoring.score import Score
from datamind.core.logging import get_logger

logger = get_logger(__name__)


class Predictor:
    """模型预测器

    封装模型预测和评分逻辑，支持单样本和批量。
    """

    def __init__(
        self,
        adapter: BaseModelAdapter,
        pdo: Optional[float] = None,
        base_score: Optional[float] = None,
        base_odds: Optional[float] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        validate_features: bool = False
    ):
        """
        初始化预测器

        参数:
            adapter: 模型适配器实例
            pdo: PDO（分数翻倍点），默认 50
            base_score: 基准分，默认 600
            base_odds: 基准赔率，默认 20
            min_score: 最低分数限制，默认 0
            max_score: 最高分数限制，默认 1000
            validate_features: 是否验证特征完整性
        """
        self.adapter = adapter
        self._validate_features = validate_features

        # 初始化分数转换器
        self.score_converter = Score(
            pdo=pdo,
            base_score=base_score,
            base_odds=base_odds,
            min_score=min_score,
            max_score=max_score
        )

        # 获取模型能力
        self.capabilities = adapter.get_capabilities()

        # 检查是否支持批量预测
        self._supports_batch = has_capability(
            self.capabilities, ScorecardCapability.BATCH_PREDICT
        )

        logger.debug(
            "预测器初始化完成，支持批量: %s, 验证特征: %s",
            self._supports_batch,
            validate_features
        )

    def _validate_features_dict(self, features: Dict[str, Any]) -> None:
        """验证特征完整性"""
        if not self._validate_features:
            return

        missing = self.adapter.validate_features(features)
        if missing:
            logger.debug("缺失特征: %s", missing)

    def predict_proba(self, features: Dict[str, Any]) -> float:
        """
        单样本预测违约概率

        参数:
            features: 特征字典

        返回:
            违约概率 (0-1)

        异常:
            ValueError: 特征转换失败
        """
        try:
            # 特征验证
            self._validate_features_dict(features)

            # 转换为数组并预测
            X = self.adapter.to_array(features)
            proba = self.adapter.predict_proba(X)

            logger.debug("预测概率: %.6f", proba)
            return proba

        except Exception as e:
            logger.error("单样本概率预测失败: %s", e)
            raise

    def predict_proba_batch(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> Union[List[float], List[Optional[float]]]:
        """
        批量预测违约概率

        参数:
            features_list: 特征字典列表
            skip_errors: 是否跳过错误样本（返回 None）

        返回:
            违约概率列表

        异常:
            ValueError: 批量预测失败且 skip_errors=False
        """
        if not features_list:
            logger.debug("输入为空列表，返回空结果")
            return []

        # 使用向量化批量预测（如果支持）
        if self._supports_batch:
            try:
                return self._predict_proba_batch_vectorized(features_list, skip_errors)
            except Exception as e:
                if skip_errors:
                    logger.error("向量化批量预测失败，降级为循环: %s", e)
                else:
                    raise

        # 降级：循环预测
        return self._predict_proba_batch_loop(features_list, skip_errors)

    def _predict_proba_batch_vectorized(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> List[float]:
        """向量化批量概率预测（性能优化）"""
        logger.debug("使用向量化批量预测，样本数: %d", len(features_list))

        # 批量转换为数组
        X_batch = self.adapter.to_array_batch(features_list)

        # 批量预测
        probs = self.adapter.predict_proba_batch(X_batch)

        return probs

    def _predict_proba_batch_loop(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> List[Optional[float]]:
        """循环批量概率预测（降级方案）"""
        logger.debug("使用循环批量预测，样本数: %d", len(features_list))

        results = []
        for i, features in enumerate(features_list):
            try:
                prob = self.predict_proba(features)
                results.append(prob)
            except Exception as e:
                if skip_errors:
                    logger.error("第 %d 条预测失败: %s，返回 None", i, e)
                    results.append(None)
                else:
                    logger.error("第 %d 条预测失败: %s", i, e)
                    raise

        return results

    def predict_score(self, features: Dict[str, Any]) -> float:
        """
        单样本预测信用分

        参数:
            features: 特征字典

        返回:
            信用分数
        """
        try:
            prob = self.predict_proba(features)
            score = self.score_converter.to_score(prob)
            logger.debug("预测分数: %.2f", score)
            return score

        except Exception as e:
            logger.error("单样本分数预测失败: %s", e)
            raise

    def predict_score_batch(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> Union[List[float], List[Optional[float]]]:
        """
        批量预测信用分

        参数:
            features_list: 特征字典列表
            skip_errors: 是否跳过错误样本（返回 None）

        返回:
            信用分数列表
        """
        # 批量预测概率
        probs = self.predict_proba_batch(features_list, skip_errors)

        # 批量转换分数
        if not probs:
            return []

        if skip_errors:
            # 处理可能包含 None 的结果
            scores = []
            for prob in probs:
                if prob is None:
                    scores.append(None)
                else:
                    scores.append(self.score_converter.to_score(prob))
            return scores

        # 正常情况
        return self.score_converter.to_score_batch(probs)  # type: ignore

    def predict_raw(self, features: Dict[str, Any]) -> float:
        """
        获取模型原始输出（对数几率）

        参数:
            features: 特征字典

        返回:
            模型原始输出值
        """
        try:
            X = self.adapter.to_array(features)

            # 如果有 predict_raw 方法则调用，否则从概率反推
            if hasattr(self.adapter, "predict_raw"):
                raw = self.adapter.predict_raw(X)
            else:
                proba = self.adapter.predict_proba(X)
                raw = np.log(proba / (1 - proba))

            logger.debug("原始输出: %.6f", raw)
            return float(raw)

        except Exception as e:
            logger.error("原始输出预测失败: %s", e)
            raise

    def predict_raw_batch(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> Union[List[float], List[Optional[float]]]:
        """
        批量获取模型原始输出（对数几率）

        参数:
            features_list: 特征字典列表
            skip_errors: 是否跳过错误样本（返回 None）

        返回:
            原始输出值列表
        """
        if not features_list:
            return []

        # 使用向量化批量预测（如果支持原始输出）
        if self._supports_batch and hasattr(self.adapter, "predict_raw_batch"):
            try:
                X_batch = self.adapter.to_array_batch(features_list)
                return self.adapter.predict_raw_batch(X_batch)
            except Exception as e:
                if skip_errors:
                    logger.error("向量化批量原始输出失败，降级为循环: %s", e)
                else:
                    raise

        # 降级：循环预测
        results = []
        for i, features in enumerate(features_list):
            try:
                results.append(self.predict_raw(features))
            except Exception as e:
                if skip_errors:
                    logger.error("第 %d 条原始输出预测失败: %s，返回 None", i, e)
                    results.append(None)
                else:
                    raise

        return results

    def predict_with_confidence(
        self,
        features: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        预测并返回置信度信息

        参数:
            features: 特征字典

        返回:
            包含 proba、score、log_odds 的字典
        """
        try:
            proba = self.predict_proba(features)
            score = self.score_converter.to_score(proba)
            log_odds = np.log(proba / (1 - proba))

            return {
                "proba": proba,
                "score": score,
                "log_odds": float(log_odds),
            }

        except Exception as e:
            logger.error("预测置信度失败: %s", e)
            raise