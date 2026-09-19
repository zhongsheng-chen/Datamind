"""评分任务运行时服务

提供评分卡模型的在线评分能力。

核心功能：
  - predict: 单条评分
  - predict_batch: 批量评分

使用示例：
  from datamind.runtime.serving import ScoringService

  service = ScoringService(
      runtime_model=runtime_model,
      threshold=600.0,
  )

  result = service.predict({
      "age": 35,
      "annual_income": 120000,
      "debt_to_income_ratio": 0.32,
      "credit_utilization_ratio": 0.45,
      "delinquency_count": 0,
  })
"""

import math
from typing import Any

import numpy as np
import pandas as pd
from optbinning import Scorecard

from datamind.constants import DataType
from datamind.core.capability import ModelCapability
from datamind.models.enums import DecisionResult
from datamind.models.inspection import ScorecardInspector
from datamind.runtime.registry import RuntimeModel
from datamind.runtime.serving.base import BaseRuntimeService


class ScoringService(BaseRuntimeService):
    """评分任务运行时服务

    基于评分卡模型和评分阈值生成评分结果。

    属性：
        SERVICE_TYPE: 服务类型
        threshold: 评分阈值
    """

    SERVICE_TYPE = "scoring"

    def __init__(
            self,
            *,
            runtime_model: RuntimeModel,
            feature_names: list[str] | None = None,
            data_types: dict[str, DataType] | None = None,
            threshold: float = 600.0,
    ) -> None:
        """初始化评分任务运行时服务

        参数：
            runtime_model: 已加载的运行时模型
            feature_names: 特征名称列表（可选）
            data_types: 特征类型映射（可选）
            threshold: 评分阈值，默认值为 600

        异常：
            TypeError: 模型类型不匹配
            ValueError: 评分阈值、评分表、评分刻度或分箱转换配置无效
        """
        model = runtime_model.model

        if not isinstance(model, Scorecard):
            raise TypeError(
                "模型类型不匹配："
                f"期望 {Scorecard.__name__}，实际 "
                f"{type(model).__name__}"
            )

        super().__init__(
            runtime_model=runtime_model,
            feature_names=feature_names,
            data_types=data_types,
        )
        self.model = model
        self.threshold = float(threshold)

        if not math.isfinite(self.threshold):
            raise ValueError("threshold 必须是有限数值")

        self._prepare_scorecard()

    def get_capabilities(
            self,
    ) -> ModelCapability:
        """获取服务能力集"""
        return (
            ModelCapability.PREDICT_PROBA
            | ModelCapability.BATCH_PREDICT
        )

    def predict(
            self,
            features: dict[str, Any],
    ) -> dict[str, Any]:
        """单条评分

        参数：
            features: 特征字典

        返回：
            评分结果，包含违约概率、信用分、决策、评分阈值、
            评分截距、特征评分明细和模型运行信息

        异常：
            ValueError: 输入特征或评分结果无效
            TypeError: 特征类型无效
            RuntimeError: 评分卡运行数据结构不一致
        """
        if not features:
            raise ValueError("features 不能为空")

        self._validate_feature_types(features)

        prediction = self._evaluate([features])[0]
        self.touch()

        return self.build_result(prediction)

    def predict_batch(
            self,
            features_list: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """批量评分

        参数：
            features_list: 特征字典列表

        返回：
            批量评分结果，包含评分结果列表、样本数量和模型运行信息。
            每条评分结果包含违约概率、信用分、决策、评分阈值、
            评分截距和特征评分明细。
            输入为空列表时，返回空结果列表，样本数量为 0。

        异常：
            ValueError: 输入特征或评分结果无效
            TypeError: 特征类型无效
            RuntimeError: 评分卡运行数据结构不一致
            NotImplementedError: 模型不支持批量推理
        """
        self.require_capability(ModelCapability.BATCH_PREDICT)

        if not features_list:
            return self.build_result({
                "count": 0,
                "predictions": [],
            })

        self._validate_batch_feature_types(features_list)

        predictions = self._evaluate(features_list)
        self.touch()

        return self.build_result({
            "count": len(predictions),
            "predictions": predictions,
        })

    def _evaluate(
            self,
            features_list: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """计算评分结果

        参数：
            features_list: 特征字典列表

        返回：
            按样本顺序排列的评分结果列表

        异常：
            ValueError: 特征、违约概率或信用分无效，或无法计算特征分
            RuntimeError: WoE 转换结果与特征表不一致
        """
        frame = pd.DataFrame(
            features_list,
            columns=self.feature_names,
        )

        probabilities = self._extract_probabilities(
            self.model.predict_proba(frame),
            expected_count=len(frame),
        )
        feature_details = self._extract_features(
            frame,
            features_list,
        )
        scores = np.array([
            sum(
                item["points"]
                for item in items.values()
            ) + self._score_intercept
            for items in feature_details
        ])

        if not np.all(np.isfinite(scores)):
            raise ValueError("评分卡分数必须是有限数值")

        return [
            {
                "probability": probability,
                "score": float(score),
                "decision": self._decide(
                    float(score)
                ),
                "threshold": self.threshold,
                "score_intercept": self._score_intercept,
                "features": items,
            }
            for probability, score, items in zip(
                probabilities,
                scores,
                feature_details,
            )
        ]

    def _prepare_scorecard(
            self,
    ) -> None:
        """准备评分卡数据

        读取评分截距、分箱数据和 WoE 转换配置，校验分箱规则，
        并准备特征分转换参数。

        异常：
            ValueError: 评分截距、评分表、评分刻度或分箱转换配置无效
        """
        # TODO: 待 OptBinning 提供公开接口后，替换私有属性读取。
        self._metric_special = getattr(
            self.model,
            "_metric_special",
        )
        self._metric_missing = getattr(
            self.model,
            "_metric_missing",
        )
        self._score_intercept = float(self.model.intercept_)

        if not math.isfinite(self._score_intercept):
            raise ValueError("评分截距必须是有限数值")

        process = self.model.binning_process_
        names = [
            str(name)
            for name in process.get_support(names=True)
        ]
        transform_params = process.binning_transform_params or {}

        self._metric_special_by_feature: dict[str, str | float] = {}
        self._metric_missing_by_feature: dict[str, str | float] = {}
        self._transform_override_bins: dict[str, np.ndarray] = {}

        for name in names:
            params = transform_params.get(name, {})
            if params.get("metric") not in (None, "woe"):
                raise ValueError(
                    f"评分卡特征 {name} 必须使用 WoE 转换，"
                    f"实际 metric={params['metric']!r}"
                )
            self._metric_special_by_feature[name] = params.get(
                "metric_special",
                self._metric_special,
            )
            self._metric_missing_by_feature[name] = params.get(
                "metric_missing",
                self._metric_missing,
            )

        details = ScorecardInspector.extract(self.model)
        variables = {
            item["name"]: item
            for item in details["variables"]
        }
        self._feature_bins = {
            name: variables[name]["bins"]
            for name in names
        }

        if not names:
            raise ValueError("评分卡没有入模特征")

        self._bin_woe: dict[str, np.ndarray] = {}

        for name in names:
            variable = process.get_binned_variable(name)
            bins = self._feature_bins[name]
            n_regular = len(variable.splits) + (variable.dtype == "numerical")
            n_special = (
                len(variable.special_codes)
                if isinstance(variable.special_codes, dict)
                else 1
            )

            if (
                    len(bins) != n_regular + n_special + 1
                    or [row["Bin id"] for row in bins] != list(range(len(bins)))
            ):
                raise ValueError(
                    f"评分卡特征 {name} 的分箱规则与评分表不匹配"
                )

            # 按训练配置确定特殊箱和缺失箱的实际 WoE，保持与评分表分值一致。
            values = np.array(
                [row["WoE"] for row in bins],
                dtype=float,
            )

            metric_special = self._metric_special_by_feature[name]
            metric_missing = self._metric_missing_by_feature[name]
            override_bins = np.zeros(len(bins), dtype=bool)

            if metric_special != "empirical":
                values[n_regular:n_regular + n_special] = metric_special
            if metric_missing != "empirical":
                values[-1] = metric_missing
            if "metric_special" in transform_params.get(name, {}):
                override_bins[n_regular:n_regular + n_special] = True
            if "metric_missing" in transform_params.get(name, {}):
                override_bins[-1] = True

            self._bin_woe[name] = values
            self._transform_override_bins[name] = override_bins

        self._prepare_point_conversion()

    def _prepare_point_conversion(
            self,
    ) -> None:
        """准备 WoE 到特征分的转换参数

        根据模型系数和评分刻度计算转换参数，并校验评分表分值。

        异常：
            ValueError: 评分刻度或评分表无效
        """
        coefficients = {
            name: float(rows[0]["Coefficient"])
            for name, rows in self._feature_bins.items()
        }
        raw_points = {
            name: self._bin_woe[name] * coefficient
            for name, coefficient in coefficients.items()
        }
        n_features = len(raw_points)
        slope, offset = 1.0, 0.0
        method = self.model.scaling_method
        params = self.model.scaling_method_params or {}

        if method is not None:
            intercepts = np.asarray(
                self.model.estimator_.intercept_,
                dtype=float,
            ).reshape(-1)

            if (
                    len(intercepts) != 1
                    or not np.all(np.isfinite(intercepts))
            ):
                raise ValueError(
                    "评分卡估计器必须有唯一的有限截距"
                )

            intercept = float(intercepts[0])
            sense = -1 if self.model.reverse_scorecard else 1

            if method == "pdo_odds":
                factor = float(params["pdo"]) / math.log(2)
                slope = -sense * factor
                offset = (
                    float(params["scorecard_points"])
                    - factor * math.log(float(params["odds"]))
                    - factor * intercept
                ) / n_features
            elif method == "min_max":
                low = intercept + sum(
                    float(values.min())
                    for values in raw_points.values()
                )
                high = intercept + sum(
                    float(values.max())
                    for values in raw_points.values()
                )

                if not high > low:
                    raise ValueError(
                        "评分卡原始分值范围无效，无法应用 min_max 刻度"
                    )

                slope = (
                    sense * (float(params["min"]) - float(params["max"]))
                    / (high - low)
                )
                endpoint = (
                    params["min"]
                    if self.model.reverse_scorecard
                    else params["max"]
                )
                offset = (
                    float(endpoint) - slope * low + slope * intercept
                ) / n_features
            else:
                raise ValueError(f"不支持的评分刻度：{method}")

        self._point_conversion: dict[str, tuple[float, float]] = {}
        self._use_table_points: dict[str, np.ndarray] = {}

        for name, values in raw_points.items():
            scaled = slope * values + offset
            shift = (
                float(scaled.min())
                if self.model.intercept_based
                else 0.0
            )
            self._point_conversion[name] = (
                slope * coefficients[name],
                offset - shift,
            )

            expected = scaled - shift
            actual = np.array(
                [row["Points"] for row in self._feature_bins[name]],
                dtype=float,
            )

            if (
                    not np.all(np.isfinite(expected))
                    or not np.all(np.isfinite(actual))
            ):
                raise ValueError(
                    f"评分卡特征 {name} 的分值必须是有限数值"
                )

            # min_max 启用取整时使用优化后的分值，跳过逐项取整的一致性校验。
            if self.model.rounding and method == "min_max":
                raw_woe = np.array(
                    [row["WoE"] for row in self._feature_bins[name]],
                    dtype=float,
                )
                overridden = self._transform_override_bins[name]
                self._use_table_points[name] = (
                    ~overridden
                    | np.isclose(
                        self._bin_woe[name],
                        raw_woe,
                        rtol=1e-10,
                        atol=1e-12,
                    )
                )
                continue
            if self.model.rounding:
                expected = np.rint(expected)

            matches = np.isclose(
                expected,
                actual,
                rtol=1e-10,
                atol=1e-8,
            )
            self._use_table_points[name] = matches

            if np.any(
                    ~matches
                    & ~self._transform_override_bins[name]
            ):
                raise ValueError(
                    f"评分卡特征 {name} 的评分表与模型刻度不一致"
                )

    def _get_bin_indices(
            self,
            name: str,
            column: pd.Series,
    ) -> np.ndarray:
        """获取特征分箱索引

        根据已拟合规则匹配普通箱、特殊箱和缺失箱。

        参数：
            name: 特征名称
            column: 特征值序列

        返回：
            与输入顺序一致的分箱索引，未知类别对应 -1
        """
        # TODO: 待 OptBinning 修复 WoE 与分箱索引冲突后，评估是否移除独立分箱匹配。
        variable = self.model.binning_process_.get_binned_variable(name)
        splits = variable.splits
        n_regular = len(splits) + (variable.dtype == "numerical")
        special_codes = variable.special_codes
        groups = (
            list(special_codes.values())
            if isinstance(special_codes, dict)
            else [special_codes]
        )
        indices = np.full(
            len(column),
            -1,
            dtype=int,
        )

        for index, group in enumerate(groups):
            if group is not None:
                codes = (
                    group
                    if isinstance(group, (list, np.ndarray))
                    else [group]
                )
                indices[column.isin(codes).to_numpy()] = n_regular + index

        missing = column.isna().to_numpy()
        indices[missing] = n_regular + len(groups)
        clean = (indices == -1) & ~missing

        if variable.dtype == "numerical":
            indices[clean] = np.searchsorted(
                splits,
                column[clean].to_numpy(dtype=float),
                side="right",
            )
        else:
            for index, categories in enumerate(splits):
                indices[clean & column.isin(categories).to_numpy()] = index

        return indices

    def _convert_woe_points(
            self,
            name: str,
            woe: float,
    ) -> float:
        """将 WoE 转换为特征分

        用于无法直接采用评分表分值的情况。

        参数：
            name: 特征名称
            woe: 模型概率预测实际使用的 WoE

        返回：
            按评分刻度计算的特征分

        异常：
            ValueError: 无法计算特征分，或特征分不是有限数值
        """
        if (
                self.model.rounding
                and self.model.scaling_method == "min_max"
        ):
            raise ValueError(
                f"特征 {name} 的 WoE 没有对应的评分表条目，"
                "min_max 整数评分卡无法确定回退分值"
            )

        slope, offset = self._point_conversion[name]
        points = slope * woe + offset

        if self.model.rounding:
            points = float(np.rint(points))

        if not math.isfinite(points):
            raise ValueError(
                f"评分卡特征 {name} 的分值必须是有限数值"
            )

        return points

    def _extract_features(
            self,
            frame: pd.DataFrame,
            features_list: list[dict[str, Any]],
    ) -> list[dict[str, dict[str, Any]]]:
        """提取各样本的特征评分明细

        按已拟合规则匹配分箱，并使用与概率预测相同的配置计算 WoE。
        命中分箱且 WoE 与评分表对应值一致时使用表中分值，否则按评分刻度计算。
        未知类别的分箱标签为 Unknown，特征值统一转换为可序列化的标量。

        参数：
            frame: 评分使用的特征表
            features_list: 原始特征字典列表

        返回：
            按样本顺序排列的特征评分明细列表，每条明细以入模特征名称为键，
            每项包含 value、bin、woe 和 points

        异常：
            ValueError: 特征值无法序列化、WoE 无效，或无法计算有效的特征分
            RuntimeError: WoE 转换结果与特征表不一致
        """
        process = self.model.binning_process_
        names = list(self._feature_bins)

        woe = process.transform(
            X=frame[process.variable_names],
            metric=None,
            metric_special=self._metric_special,
            metric_missing=self._metric_missing,
        )

        if (
                not isinstance(woe, pd.DataFrame)
                or woe.shape != (len(frame), len(names))
                or list(woe.columns) != names
                or not woe.index.equals(frame.index)
        ):
            raise RuntimeError(
                "评分卡 WoE 转换结果与特征表不匹配"
            )

        woe_values = woe.to_numpy(dtype=float)

        if not np.all(np.isfinite(woe_values)):
            raise ValueError("评分卡 WoE 必须是有限数值")

        result: list[dict[str, dict[str, Any]]] = [
            {} for _ in range(len(frame))
        ]

        for column_index, (name, bins) in enumerate(self._feature_bins.items()):
            values = self._get_bin_indices(
                name,
                frame[name],
            )

            for index, value in enumerate(values):
                bin_index = int(value)
                actual_woe = float(woe_values[index, column_index])
                label = "Unknown"

                if bin_index >= 0:
                    row = bins[bin_index]
                    label = row["Bin"]

                if bin_index >= 0 and math.isclose(
                        actual_woe,
                        self._bin_woe[name][bin_index],
                        rel_tol=1e-10,
                        abs_tol=1e-12,
                ) and self._use_table_points[name][bin_index]:
                    points = float(bins[bin_index]["Points"])
                else:
                    points = self._convert_woe_points(
                        name,
                        actual_woe,
                    )

                result[index][name] = {
                    "value": self._convert_feature_value(
                        features_list[index].get(name)
                    ),
                    "bin": label,
                    "woe": actual_woe,
                    "points": points,
                }

        return result

    @staticmethod
    def _convert_feature_value(
            value: Any,
    ) -> str | bool | int | float | None:
        """转换响应中的特征值

        将 NumPy 标量转为 Python 标量，缺失值统一转为 None。

        参数：
            value: 请求中的特征值

        返回：
            可直接序列化的标量值

        异常：
            ValueError: 特征值为无穷值或不是受支持的标量
        """
        if value is None or value is pd.NA or value is pd.NaT:
            return None

        if isinstance(value, np.generic):
            value = value.item()

        if isinstance(value, float):
            if math.isnan(value):
                return None

            if not math.isfinite(value):
                raise ValueError(
                    "响应中的特征值不能为无穷值"
                )

        if value is None or isinstance(value, (str, bool, int, float)):
            return value

        raise ValueError(
            "响应中的特征值必须为字符串、布尔值、数值或空值"
        )

    def _extract_probabilities(
            self,
            values: Any,
            *,
            expected_count: int,
    ) -> list[float]:
        """提取评分卡违约概率

        参数：
            values: 模型概率预测结果
            expected_count: 期望样本数

        返回：
            按样本顺序排列的违约概率列表

        异常：
            ValueError: 违约概率或模型类别无效
        """
        probabilities = np.asarray(
            values,
            dtype=float,
        )

        expected_shape = (expected_count, 2)

        if probabilities.shape != expected_shape:
            raise ValueError(
                "评分卡概率预测结果形状不正确："
                f"期望 {expected_shape}，"
                f"实际 {probabilities.shape}"
            )

        if (
                not np.all(np.isfinite(probabilities))
                or np.any(probabilities < 0)
                or np.any(probabilities > 1)
        ):
            raise ValueError(
                "评分卡概率预测结果必须是 0 到 1 之间的有限数值"
            )

        classes = np.asarray(
            self.model.estimator_.classes_,
            dtype=object,
        ).reshape(-1)
        positive_indices = np.flatnonzero(
            classes == 1
        )

        if len(positive_indices) != 1:
            raise ValueError(
                "评分卡模型类别中不存在唯一的违约标签 1"
            )

        positive_index = int(
            positive_indices[0]
        )

        return [
            float(value)
            for value in probabilities[
                :,
                positive_index,
            ]
        ]

    def _decide(
            self,
            score: float,
    ) -> str:
        """根据评分阈值生成业务决策

        参数：
            score: 信用分

        返回：
            信用分大于或等于评分阈值时返回 approve，否则返回 reject
        """
        return (
            DecisionResult.APPROVE.value
            if score >= self.threshold
            else DecisionResult.REJECT.value
        )
