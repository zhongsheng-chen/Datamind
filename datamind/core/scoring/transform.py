# datamind/core/scoring/transform.py

"""WOE 特征转换器

将原始特征转换为 WOE 值，并提供完整分箱元信息。

核心功能：
  - transform_with_meta: 转换并返回完整分箱信息
  - to_woe_vector: 提取 WOE 向量用于模型预测
  - transform: 简化版转换（仅 WOE 值）

特性：
  - 支持缺失值分箱
  - 支持数值型和分类型特征
  - 返回分箱元信息，包括 bin_id、bin_label、边界、WOE、坏账率、样本占比和描述
  - 异常值处理：值不在任何分箱中时抛出异常
  - 支持批量转换优化

使用示例：
  >>> from datamind.core.scoring.transform import WOETransformer
  >>>
  >>> transformer = WOETransformer(...)
  >>> meta = transformer.transform_with_meta({"age": 45, "income": 50000})
  >>> woe_vector = transformer.to_woe_vector(meta)
"""

from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

from datamind.core.scoring.binning import Bin
from datamind.core.logging import get_logger

logger = get_logger(__name__)


class MissingStrategy(Enum):
    """缺失值处理策略"""
    RAISE = "raise"           # 抛出异常
    SKIP = "skip"             # 跳过缺失特征（返回空）
    DEFAULT = "default"       # 使用默认分箱（需要配置缺失值分箱）


class WOETransformer:
    """WOE 特征转换器

    将原始特征值转换为 WOE 值，同时返回完整的分箱元信息。
    """

    def __init__(
        self,
        binning_config: Dict[str, List[Bin]],
        missing_strategy: MissingStrategy = MissingStrategy.RAISE
    ):
        """
        初始化 WOE 转换器

        参数:
            binning_config: 分箱配置字典
                格式：{"feature_name": [Bin(), Bin(), ...], ...}
            missing_strategy: 缺失值处理策略
        """
        self.binning = binning_config
        self.missing_strategy = missing_strategy

        # 验证分箱配置
        self._validate_binning_config()

        total_bins = sum(len(bins) for bins in self.binning.values())
        logger.debug("WOE转换器初始化完成，特征数: %d，分箱总数: %d", len(self.binning), total_bins)

    def _validate_binning_config(self) -> None:
        """验证分箱配置的完整性"""
        for feature, bins in self.binning.items():
            if not bins:
                logger.error("特征 %s 的分箱配置为空", feature)
                raise ValueError(f"特征 {feature} 的分箱配置为空")

            # 检查分箱 ID 是否重复
            bin_ids = [b.id for b in bins if b.id is not None]
            if len(bin_ids) != len(set(bin_ids)):
                logger.error("特征 %s 存在重复的分箱 ID", feature)
                raise ValueError(f"特征 {feature} 存在重复的分箱 ID")

            # 检查缺失值分箱配置
            has_missing_bin = any(b.is_missing for b in bins)
            if not has_missing_bin and self.missing_strategy == MissingStrategy.DEFAULT:
                logger.error("特征 %s 缺少缺失值分箱", feature)
                raise ValueError(f"特征 {feature} 缺少缺失值分箱")

        logger.debug("分箱配置验证通过")

    def _find_bin(self, feature: str, value: Any) -> Optional[Bin]:
        """
        查找值对应的分箱

        参数:
            feature: 特征名称
            value: 特征值

        返回:
            匹配的分箱对象，如果策略为 SKIP 且值为缺失则返回 None

        异常:
            ValueError: 值不在任何分箱中（且策略为 RAISE 或 DEFAULT 但无缺失分箱）
        """
        bins = self.binning.get(feature)
        if not bins:
            raise ValueError(f"特征 {feature} 没有分箱配置")

        # 查找匹配的分箱
        for b in bins:
            if b.contains(value):
                return b

        # 处理缺失值策略
        if value is None:
            if self.missing_strategy == MissingStrategy.SKIP:
                logger.debug("特征 %s 的值为缺失，已跳过", feature)
                return None
            elif self.missing_strategy == MissingStrategy.DEFAULT:
                # 查找缺失值分箱
                for b in bins:
                    if b.is_missing:
                        return b

        raise ValueError(f"特征 {feature} 的值 {value} 不在任何分箱中")

    def transform_with_meta(self, data: Dict[str, Any]) -> Dict[str, Dict]:
        """
        转换特征并返回完整分箱信息

        参数:
            data: 原始特征字典，格式 {"feature_name": value, ...}

        返回:
            特征元信息字典，格式：
            {
                "feature_name": {
                    "value": 原始值,
                    "woe": WOE值,
                    "bin_id": 分箱ID,
                    "bin_label": 分箱标签,
                    "lower": 下边界,
                    "upper": 上边界,
                    "is_missing": 是否缺失,
                    "bad_rate": 坏账率,
                    "sample_ratio": 样本占比,
                    "description": 分箱描述
                }
            }

        异常:
            ValueError: 特征没有分箱配置或值不在任何分箱中
        """
        result = {}

        for feature, value in data.items():
            try:
                matched_bin = self._find_bin(feature, value)

                if matched_bin is None:
                    # 跳过该特征（缺失值策略为 SKIP）
                    continue

                # 构建结果
                result[feature] = {
                    "value": value,
                    "woe": matched_bin.woe,
                    "bin_id": matched_bin.id,
                    "bin_label": matched_bin.label,
                    "lower": matched_bin.lower,
                    "upper": matched_bin.upper,
                    "is_missing": matched_bin.is_missing,
                    "bad_rate": matched_bin.bad_rate,
                    "sample_ratio": matched_bin.sample_ratio,
                    "description": matched_bin.description,
                }

                logger.debug("特征 %s 转换完成: value=%s, woe=%.4f, bin_id=%s",
                             feature, value, matched_bin.woe, matched_bin.id)

            except ValueError as e:
                logger.error("特征 %s 转换失败: %s", feature, e)
                raise

        return result

    @staticmethod
    def to_woe_vector(feature_meta: Dict[str, Dict]) -> Dict[str, float]:
        """
        从特征元信息中提取 WOE 向量

        参数:
            feature_meta: transform_with_meta 返回的特征元信息

        返回:
            WOE 向量字典，格式 {"feature_name": woe_value, ...}
        """
        return {feature: meta["woe"] for feature, meta in feature_meta.items()}

    def transform(self, features: Dict[str, Any]) -> Dict[str, float]:
        """
        简化版转换（仅返回 WOE 值）

        参数:
            features: 原始特征字典

        返回:
            WOE 值字典
        """
        logger.debug("开始转换特征，特征数: %d", len(features))

        meta = self.transform_with_meta(features)
        woe_vector = self.to_woe_vector(meta)

        logger.debug("转换完成，WOE 向量数: %d", len(woe_vector))

        return woe_vector

    def transform_batch(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> List[Dict[str, float]]:
        """
        批量转换特征（仅返回 WOE 值）

        参数:
            features_list: 原始特征字典列表
            skip_errors: 是否跳过错误样本（返回空字典）

        返回:
            WOE 值字典列表
        """
        logger.debug("开始批量转换，样本数: %d", len(features_list))

        results = []
        for i, features in enumerate(features_list):
            try:
                results.append(self.transform(features))
            except Exception as e:
                if skip_errors:
                    logger.error("批量转换第 %d 条失败: %s，返回空字典", i, e)
                    results.append({})
                else:
                    logger.error("批量转换第 %d 条失败: %s", i, e)
                    raise

        logger.debug("批量转换完成，成功: %d", len(results))

        return results

    def transform_batch_with_meta(
        self,
        features_list: List[Dict[str, Any]],
        skip_errors: bool = False
    ) -> List[Dict[str, Dict]]:
        """
        批量转换特征并返回完整分箱信息

        参数:
            features_list: 原始特征字典列表
            skip_errors: 是否跳过错误样本（返回空字典）

        返回:
            特征元信息字典列表
        """
        logger.debug("开始批量转换（带元信息），样本数: %d", len(features_list))

        results = []
        for i, features in enumerate(features_list):
            try:
                results.append(self.transform_with_meta(features))
            except Exception as e:
                if skip_errors:
                    logger.error("批量转换第 %d 条失败: %s，返回空字典", i, e)
                    results.append({})
                else:
                    logger.error("批量转换第 %d 条失败: %s", i, e)
                    raise

        logger.debug("批量转换完成（带元信息），成功: %d", len(results))

        return results

    def get_feature_bins(self, feature_name: str) -> Optional[List[Bin]]:
        """
        获取指定特征的分箱配置

        参数:
            feature_name: 特征名称

        返回:
            分箱列表，如果特征不存在则返回 None
        """
        return self.binning.get(feature_name)

    def get_all_features(self) -> List[str]:
        """
        获取所有已配置的特征名称

        返回:
            特征名称列表
        """
        return list(self.binning.keys())

    def get_bin_count(self, feature_name: str) -> int:
        """
        获取指定特征的分箱数量

        参数:
            feature_name: 特征名称

        返回:
            分箱数量，如果特征不存在则返回 0
        """
        bins = self.binning.get(feature_name)
        return len(bins) if bins else 0

    def get_bin_summary(self, feature_name: str) -> Dict[str, Any]:
        """
        获取特征的分箱摘要信息

        参数:
            feature_name: 特征名称

        返回:
            分箱摘要字典
        """
        bins = self.binning.get(feature_name)
        if not bins:
            return {}

        return {
            "feature": feature_name,
            "bin_count": len(bins),
            "has_missing_bin": any(b.is_missing for b in bins),
            "woe_range": (min(b.woe for b in bins), max(b.woe for b in bins)),
            "bad_rate_range": (
                min(b.bad_rate for b in bins if b.bad_rate is not None),
                max(b.bad_rate for b in bins if b.bad_rate is not None)
            ) if any(b.bad_rate is not None for b in bins) else (None, None),
        }

    def get_all_bin_summaries(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有特征的分箱摘要信息

        返回:
            特征名到摘要的映射
        """
        return {feature: self.get_bin_summary(feature) for feature in self.binning}

    def validate_features(self, features: Dict[str, Any]) -> Tuple[List[str], List[str]]:
        """
        验证特征的有效性

        参数:
            features: 特征字典

        返回:
            (缺失特征列表, 无效值特征列表)
        """
        missing = []
        invalid = []

        for feature, value in features.items():
            bins = self.binning.get(feature)
            if not bins:
                missing.append(feature)
                continue

            # 检查值是否在分箱中
            matched = False
            for b in bins:
                if b.contains(value):
                    matched = True
                    break

            if not matched:
                invalid.append(feature)

        return missing, invalid