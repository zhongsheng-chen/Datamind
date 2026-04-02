# datamind/core/scoring/engine.py

"""评分引擎

提供统一接口进行模型评分和特征解释。

核心功能：
  - score: 单条样本评分
  - score_batch: 批量样本评分
  - explain: 单条样本特征贡献解释（返回对数几率贡献和评分贡献）
  - explain_batch: 批量特征贡献解释
  - get_feature_importance: 获取全局特征重要性

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
from datamind.core.scoring.predictor import Predictor
from datamind.core.scoring.score import Score
from datamind.core.scoring.transform import WOETransformer
from datamind.core.logging import get_logger

logger = get_logger(__name__)


class ScoringEngine:
    """评分引擎主入口

    统一封装模型预测和特征解释功能。

    属性:
        model_adapter: 模型适配器实例
        transformer: WOE转换器（评分卡模型使用）
        predictor: 预测器
        score_converter: 分数转换器
        capabilities: 模型能力集
    """

    def __init__(
        self,
        model_adapter: BaseModelAdapter,
        transformer: Optional[WOETransformer] = None,
        pdo: Optional[float] = None,
        base_score: Optional[float] = None,
        base_odds: Optional[float] = None,
        min_score: Optional[float] = None,
        max_score: Optional[float] = None,
        validate_features: bool = False
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
            validate_features: 是否验证特征完整性
        """
        self.model_adapter = model_adapter
        self.transformer = transformer
        self._validate_features = validate_features

        # 初始化预测器（只负责预测概率和原始输出）
        self.predictor = Predictor(
            adapter=model_adapter,
            validate_features=validate_features
        )

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

        logger.info("评分引擎初始化完成，模型能力: %s, 支持批量预测: %s",
                   get_capability_list(self.capabilities),
                   self._supports_batch)

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
                logger.error("特征转换失败: %s", e)
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
            proba = self.predictor.predict_proba(transformed)
            logger.debug("预测概率: %.6f", proba)

            result = {
                "score": self.score_converter.to_score(proba),
            }
            if return_proba:
                result["proba"] = proba

            return result

        except Exception as e:
            logger.error("单条评分失败: %s", e)
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
            logger.debug("输入为空列表，返回空结果")
            return []

        # 使用批量预测（如果支持）
        if self._supports_batch:
            try:
                return self._score_batch_vectorized(features_list, return_proba, skip_errors)
            except Exception as e:
                if skip_errors:
                    logger.warning("批量预测失败，降级为循环预测: %s", e)
                else:
                    raise

        # 降级为循环预测
        return self._score_batch_loop(features_list, return_proba, skip_errors)

    def _score_batch_vectorized(
            self,
            features_list: List[Dict[str, Any]],
            return_proba: bool = True,
            skip_errors: bool = False
    ) -> List[Dict[str, Optional[float]]]:
        """
        向量化批量评分（性能优化）

        参数:
            features_list: 特征字典列表
            return_proba: 是否返回预测概率
            skip_errors: 是否跳过错误样本

        返回:
            评分结果列表
        """
        logger.debug("使用向量化批量评分，样本数: %d", len(features_list))

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
                    logger.error("第 %d 条特征转换失败: %s", i, e)
                else:
                    raise

        # 初始化结果列表
        results: List[Dict[str, Optional[float]]] = []
        for _ in features_list:
            result: Dict[str, Optional[float]] = {"score": None}
            if return_proba:
                result["proba"] = None
            results.append(result)

        # 如果没有有效样本，返回空结果
        if not transformed_list:
            return results

        # 批量预测概率
        probs = self.predictor.predict_proba_batch(transformed_list)

        # 批量转换分数
        scores = self.score_converter.to_score_batch(probs)

        # 填充有效结果
        for idx, i in enumerate(valid_indices):
            results[i]["score"] = scores[idx]
            if return_proba:
                results[i]["proba"] = probs[idx]

        return results

    def _score_batch_loop(
            self,
            features_list: List[Dict[str, Any]],
            return_proba: bool = True,
            skip_errors: bool = False
    ) -> List[Dict[str, Optional[float]]]:
        """
        循环批量评分（降级方案）

        参数:
            features_list: 特征字典列表
            return_proba: 是否返回预测概率
            skip_errors: 是否跳过错误样本

        返回:
            评分结果列表
        """
        logger.debug("使用循环批量评分，样本数: %d", len(features_list))

        results: List[Dict[str, Optional[float]]] = []
        for i, features in enumerate(features_list):
            try:
                result = self.score(features, return_proba=return_proba)
                # 确保 result 是预期的类型
                typed_result: Dict[str, Optional[float]] = {
                    "score": result.get("score"),
                }
                if return_proba:
                    typed_result["proba"] = result.get("proba")
                results.append(typed_result)
            except Exception as e:
                if skip_errors:
                    logger.error("第 %d 条评分失败: %s，返回 None", i, e)
                    result_dict: Dict[str, Optional[float]] = {"score": None}
                    if return_proba:
                        result_dict["proba"] = None
                    results.append(result_dict)
                else:
                    logger.error("第 %d 条评分失败: %s", i, e)
                    raise

        return results

    def explain(self, features: Dict[str, Any], return_score_scale: bool = True) -> Dict[str, Any]:
        """
        获取单条样本特征贡献解释

        对于评分卡模型（逻辑回归）：
            逻辑回归输出: log_odds_raw = intercept + Σ(coefficient × WOE) = log(p/(1-p))  # 坏/好空间
            评分卡 odds: odds = (1-p)/p = exp(-log_odds_raw)  # 好/坏空间
            信用评分: score = offset + factor × log(odds) = offset - factor × log_odds_raw

            因此：
                - log_odds_contributions: 特征的对数几率贡献（坏/好空间）
                - score_contributions: 特征的评分贡献 = -factor × log_odds_contributions
                - 总评分: score = offset + Σ(score_contributions)

        对于黑盒模型（XGBoost、RandomForest等）：
            返回 SHAP 值解释

        参数:
            features: 特征字典
            return_score_scale: 是否返回评分尺度贡献（默认True）

        返回:
            字典，包含：
                "explain_type": 解释类型 ("scorecard" 或 "blackbox" 或 "unsupported")
                "log_odds_contributions": 特征对数几率贡献（坏/好空间）
                "intercept_log_odds": 截距对数几率（坏/好空间）
                "total_log_odds": 总对数几率（坏/好空间）
                "score_contributions": 特征评分贡献（可选，评分尺度）
                "intercept_score": 截距评分贡献（可选）
                "total_score": 总评分（可选）
        """
        # 评分卡模型：使用特征分数
        if has_capability(self.capabilities, ScorecardCapability.FEATURE_SCORE):
            try:
                logger.debug("使用评分卡模型解释")

                if self.transformer is None:
                    logger.debug("评分卡模型没有WOE转换器，将使用原始特征值计算（可能不准确）")
                    transformed = features
                else:
                    transformed = self._transform_features(features)
                    logger.debug("WOE转换完成，特征数: %d", len(transformed))

                # 获取评分参数
                factor = self.score_converter.factor
                offset = self.score_converter.offset

                # 计算贡献
                log_odds_contributions = {}
                score_contributions = {}
                total_log_odds = 0.0
                total_score = offset

                for feat_name, woe in transformed.items():
                    try:
                        coefficient = self.model_adapter.get_coef(feat_name)
                        # 对数几率贡献（坏/好空间）
                        log_odds_contrib = coefficient * woe
                        log_odds_contributions[feat_name] = log_odds_contrib
                        total_log_odds += log_odds_contrib

                        # 评分贡献（评分尺度）
                        score_contrib = None
                        if return_score_scale:
                            score_contrib = -factor * log_odds_contrib
                            score_contributions[feat_name] = score_contrib
                            total_score += score_contrib

                        logger.debug("特征 %s: WOE=%.4f, 系数=%.4f, 对数几率贡献=%.4f, 评分贡献=%.4f",
                                    feat_name, woe, coefficient, log_odds_contrib,
                                    score_contrib if return_score_scale else 0)
                    except (RuntimeError, ValueError, AttributeError) as e:
                        logger.debug("获取特征 %s 系数失败: %s", feat_name, e)

                # 添加截距贡献
                intercept_log_odds = 0.0
                intercept_score = 0.0
                try:
                    intercept_log_odds = self.model_adapter.get_intercept()
                    total_log_odds += intercept_log_odds

                    if return_score_scale:
                        intercept_score = -factor * intercept_log_odds
                        total_score += intercept_score
                    logger.debug("截距: 对数几率=%.4f, 评分贡献=%.4f", intercept_log_odds, intercept_score)
                except NotImplementedError:
                    logger.debug("模型不支持截距提取")
                except Exception as e:
                    logger.debug("获取截距失败: %s", e)

                # 构建返回结果
                result = {
                    "explain_type": "scorecard",
                    "log_odds_contributions": log_odds_contributions,
                    "intercept_log_odds": intercept_log_odds,
                    "total_log_odds": total_log_odds
                }

                if return_score_scale:
                    result["score_contributions"] = score_contributions
                    result["intercept_score"] = intercept_score
                    result["total_score"] = total_score

                logger.debug("解释完成: 总对数几率=%.4f, 总评分=%.4f",
                            total_log_odds, total_score if return_score_scale else 0)
                return result

            except Exception as e:
                logger.error("特征贡献解释失败: %s", e)
                import traceback
                traceback.print_exc()
                return {
                    "explain_type": "scorecard",
                    "log_odds_contributions": {},
                    "total_log_odds": 0.0
                }

        # SHAP 解释（非评分卡模型）
        if has_capability(self.capabilities, ScorecardCapability.SHAP):
            logger.debug("使用 SHAP 解释")
            try:
                X_array = self.model_adapter.to_array(features)

                if hasattr(self.model_adapter, "get_shap_values"):
                    shap_values = self.model_adapter.get_shap_values(X_array)
                    if shap_values:
                        return {
                            "explain_type": "blackbox",
                            "shap_values": shap_values,
                            "base_value": 0.0,
                            "expected_value": 0.0
                        }
            except Exception as e:
                logger.error("SHAP 解释失败: %s", e)

        # 模型不支持解释
        logger.debug("模型不支持特征贡献解释")
        return {
            "explain_type": "unsupported",
            "message": "模型不支持特征贡献解释"
        }

    def explain_batch(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> List[Dict[str, Any]]:
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
                    logger.error("第 %d 条解释失败: %s，返回空字典", i, e)
                    results.append({})
                else:
                    logger.error("第 %d 条解释失败: %s", i, e)
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
                max_woe = max(abs(b.woe) for b in bins)
                importance[feature] = max_woe
            logger.debug("从 transformer 获取特征重要性，特征数: %d", len(importance))
            return importance

        # 其他模型：从适配器获取
        importance = self.model_adapter.get_feature_importance()
        if importance:
            logger.debug("从适配器获取特征重要性，特征数: %d", len(importance))
        return importance

    def get_score_range(self) -> Tuple[float, float]:
        """
        获取有效分数范围

        返回:
            (min_score, max_score) 元组
        """
        min_score, max_score = self.score_converter.get_score_range()
        return min_score, max_score

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