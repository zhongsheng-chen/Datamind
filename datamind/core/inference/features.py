"""推理特征转换.

根据模型特征顺序和数据类型，将请求特征转换为模型输入矩阵。

本模块只负责推理输入整理，不执行拟合、分箱、编码或特征工程。
类别值保持字符串形式，缺失值转换为 np.nan，输出矩阵使用
object 类型以兼容数值变量与类别变量。

核心功能：
  - transform: 转换单条特征
  - transform_batch: 转换批量特征
  - validate: 验证单条特征
  - validate_batch: 验证批量特征
  - ensure_2d: 规范化二维数组

使用示例：
  from datamind.core.inference.features import FeatureTransformer

  transformer = FeatureTransformer(
      feature_names=["age", "employment_type"],
      data_types={
          "age": DataType.NUMERIC,
          "employment_type": DataType.CATEGORICAL,
      },
  )

  matrix = transformer.transform({
      "age": 35,
      "employment_type": "salaried",
  })
"""

from typing import Any

import numpy as np
import structlog

from datamind.constants import DataType

logger = structlog.get_logger(__name__)


class FeatureTransformer:
    """模型推理特征转换器.

    根据预设的特征顺序和数据类型，将特征字典转换为模型输入矩阵。

    该转换器不执行拟合、分箱、编码或其他特征工程；类别值保持
    字符串形式，缺失值转换为 np.nan。

    属性：
        feature_names: 模型特征顺序
        data_types: 特征名称到数据类型的映射
    """

    def __init__(
            self,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
    ) -> None:
        """初始化特征转换器.

        参数：
            feature_names: 模型特征顺序（可选）；为空时不限定特征顺序
            data_types: 特征名称到数据类型的映射（可选）

        异常：
            ValueError: 特征名称为空白或包含重复值
        """
        self.feature_names = self._normalize_names(feature_names)
        self.data_types = dict(data_types or {})
        self._feature_index = {
            name: index
            for index, name in enumerate(self.feature_names or [])
        }

    def transform(
            self,
            features: dict[str, Any],
    ) -> np.ndarray:
        """转换单条特征.

        参数：
            features: 特征名称到特征值的映射

        返回：
            形状为 (1, n_features) 的 object 类型模型输入矩阵

        异常：
            ValueError: 特征为空或未配置特征名称
        """
        if not features:
            raise ValueError("features 不能为空")

        if not self.feature_names:
            raise ValueError("feature_names 不能为空")

        values: list[Any] = [
            np.nan
            for _ in self.feature_names
        ]

        for name, value in features.items():
            index = self._feature_index.get(name)

            if index is not None:
                values[index] = self._to_value_or_nan(value, name)

        return np.asarray([values], dtype=object)

    def transform_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> np.ndarray:
        """转换批量特征.

        参数：
            features_list: 多条特征映射

        返回：
            形状为 (n_samples, n_features) 的 object 类型模型输入矩阵

        异常：
            TypeError: 批量输入包含非字典元素
            ValueError: 批量输入为空或无法解析特征名称
        """
        if not features_list:
            raise ValueError("features_list 不能为空")

        self.validate_batch(features_list)
        names = self._resolve_batch_names(features_list)

        return np.asarray(
            [
                [
                    self._to_value_or_nan(
                        features.get(name),
                        name,
                    )
                    for name in names
                ]
                for features in features_list
            ],
            dtype=object,
        )

    def validate(
            self,
            features: dict[str, Any],
    ) -> tuple[
        list[str],
        list[tuple[str, str, str]],
    ]:
        """验证单条特征.

        参数：
            features: 特征名称到特征值的映射

        返回：
            缺失特征名称列表，以及由特征名称、期望类型和实际类型
            组成的类型错误列表
        """
        missing: list[str] = []
        type_errors: list[tuple[str, str, str]] = []

        if not self.feature_names:
            return missing, type_errors

        for name in self.feature_names:
            value = features.get(name)

            if value is None:
                missing.append(name)
                continue

            valid, expected = self._validate_value(
                value,
                self.data_types.get(name, DataType.ANY),
            )

            if not valid:
                type_errors.append((
                    name,
                    expected,
                    type(value).__name__,
                ))

        return missing, type_errors

    @staticmethod
    def validate_batch(
            features_list: list[Any],
    ) -> None:
        """验证批量特征.

        参数：
            features_list: 待校验的批量输入

        异常：
            TypeError: 批量输入包含非字典元素
        """
        invalid_index = next(
            (
                index
                for index, features in enumerate(features_list)
                if not isinstance(features, dict)
            ),
            None,
        )

        if invalid_index is not None:
            raise TypeError(
                "批量输入必须全部为特征字典，"
                f"第 {invalid_index} 个元素类型为 "
                f"{type(features_list[invalid_index]).__name__}"
            )

    @staticmethod
    def ensure_2d(X: np.ndarray) -> np.ndarray:
        """将一维或二维数组规范化为二维数组.

        参数：
            X: 一维或二维模型输入数组

        返回：
            二维模型输入数组；一维输入增加样本维度，二维输入原样返回

        异常：
            ValueError: 输入不是一维或二维数组
        """
        array = np.asarray(X)

        if array.ndim == 1:
            return array.reshape(1, -1)

        if array.ndim != 2:
            raise ValueError(
                "仅支持 1D / 2D numpy 输入，"
                f"当前 ndim={array.ndim}"
            )

        return array

    @staticmethod
    def _validate_value(
            value: Any,
            data_type: DataType,
    ) -> tuple[bool, str]:
        """返回特征值是否匹配数据类型及期望类型名称."""
        if data_type == DataType.NUMERIC:
            return (
                not isinstance(value, bool)
                and isinstance(value, (int, float, np.number)),
                DataType.NUMERIC.value,
            )

        if data_type == DataType.BOOLEAN:
            return (
                isinstance(value, bool)
                or (
                    isinstance(value, (int, float, np.number))
                    and value in (0, 1)
                ),
                DataType.BOOLEAN.value,
            )

        if data_type == DataType.CATEGORICAL:
            return (
                isinstance(value, str),
                DataType.CATEGORICAL.value,
            )

        return True, DataType.ANY.value

    @staticmethod
    def _to_value_or_nan(
            value: Any,
            feature_name: str | None = None,
    ) -> Any:
        """规范化单个模型输入值.

        None 转换为 np.nan，布尔值和数值转换为 float，字符串及
        其他对象保持原值。
        """
        if value is None:
            return np.nan

        if isinstance(value, bool):
            return float(value)

        if isinstance(
                value,
                (int, float, np.integer, np.floating),
        ):
            return float(value)

        if isinstance(value, str):
            return value

        logger.debug(
            "特征类型未标准化",
            feature=feature_name,
            value_type=type(value).__name__,
        )
        return value

    def _resolve_batch_names(
            self,
            features_list: list[dict[str, Any]],
    ) -> list[str]:
        """解析批量转换使用的特征顺序."""
        if self.feature_names:
            return self.feature_names

        names = sorted({
            name
            for features in features_list
            for name in features
        })

        if not names:
            raise ValueError("批量特征中不存在可用字段")

        return names

    @staticmethod
    def _normalize_names(
            feature_names: list[str] | None,
    ) -> list[str] | None:
        """校验并复制特征名称列表."""
        if feature_names is None:
            return None

        normalized = list(feature_names)

        if not normalized:
            return None

        if any(
                not isinstance(name, str)
                or not name.strip()
                for name in normalized
        ):
            raise ValueError(
                "feature_names 必须是非空字符串列表"
            )

        if len(normalized) != len(set(normalized)):
            raise ValueError(
                "feature_names 不能包含重复名称"
            )

        return normalized
