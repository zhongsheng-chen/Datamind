"""A/B 实验分配.

提供实验曝光判断、稳定 Hash 分组和手工指定分组能力。

核心功能：
  - AssignmentResult: 实验分配结果
  - StableHashAssigner: 按实验 ID 和分桶主体进行稳定 Hash 分组
  - ManualAssigner: 按调用方指定结果进行手工指定分组
  - ExperimentAssigner: 根据 strategy 选择 hash/manual 分配器

说明：
  实验分配包含曝光判断和 Variant 分配两个阶段。

  hash 策略包含两个独立阶段：

  - 曝光判断：
      根据 experiment_id 和 subject_key
      计算稳定曝光分桶值，
      判断主体是否进入实验。

  - 稳定 Hash 分组：
      使用独立的稳定哈希值计算实验内分组位置，
      再按照 Variant 的 weight 分配到固定 Variant。

  manual 策略不执行曝光判断，
  也不按照 weight 自动分配，
  而是由调用方显式指定 variant_id、variant_name，
  或者传入 subject_key 到 Variant 的映射关系。

  曝光判断和稳定 Hash 分组使用独立哈希空间，
  调整 traffic_ratio 只影响实验曝光范围，
  不改变已进入实验主体的 Variant 分配结果。

使用示例：
  from datamind.ab_test.assignment import ExperimentAssigner
  from datamind.models.enums import AssignmentStrategy

  assigner = ExperimentAssigner()

  result = assigner.assign(
      strategy=AssignmentStrategy.HASH,
      experiment_id="exp_0123456789abcdef",
      subject_key="customer_10001",
      traffic_ratio=0.2,
      variants=variants
  )

  result = assigner.assign(
      strategy=AssignmentStrategy.MANUAL,
      experiment_id="exp_0123456789abcdef",
      subject_key="customer_10001",
      variants=variants,
      manual_variant_id="var_control"
  )

  if result:
      variant = result.variant
      bucket = result.bucket
"""

import hashlib
import math
from dataclasses import dataclass
from typing import Any

from datamind.models.enums import AssignmentStrategy


@dataclass(slots=True)
class AssignmentResult:
    """实验分配结果.

    属性：
        variant: 命中的 Variant 对象
        bucket: 曝光分桶标识，手动分配不适用
        bucket_value: 稳定曝光分桶值，取值范围 [0.0, 1.0)，手动分配不适用
        point: 实验内稳定分组位置，取值范围 [0.0, 1.0)，手动分配不适用
        context: 分配上下文
    """

    variant: Any
    bucket: str | None
    bucket_value: float | None
    point: float | None
    context: dict


class StableHashAssigner:
    """稳定 Hash 分配器.

    根据 experiment_id 和 subject_key 进行稳定实验分配。

    首先计算曝光分桶值，判断主体是否进入实验；
    进入实验后，再使用独立哈希值计算实验内分组位置，
    按照 Variant 的 weight 分配到固定 Variant。

    说明：
      - traffic_ratio 表示实验曝光比例，必须大于 0 且小于等于 1
      - weight 表示实验内 Variant 权重
      - weight 总和必须等于 1
      - 如果未命中实验曝光比例，返回 None
      - 同一个实验下，同一个 subject_key 会稳定命中同一个结果
      - 实验创建后，traffic_ratio 和各 Variant weight 应保持不变
      - 如需调整实验曝光比例或分组权重，应创建新的实验
    """

    def assign(
            self,
            *,
            experiment_id: str,
            subject_key: str,
            traffic_ratio: float,
            variants: list[Any],
    ) -> AssignmentResult | None:
        """执行稳定 Hash 分组.

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体，例如客户号、订单号、申请单号
            traffic_ratio: 实验曝光比例，取值范围为 (0, 1]
            variants: 实验 Variant 列表，要求对象包含 weight 字段

        返回：
            实验分配结果；如果未进入实验，返回 None

        异常：
            ValueError: 实验曝光比例、Variant 权重非法
        """
        if not experiment_id:
            raise ValueError("实验 ID 不能为空")

        if not subject_key:
            raise ValueError("分桶主体不能为空")

        if not math.isfinite(traffic_ratio):
            raise ValueError("实验曝光比例必须是有限数值")

        if traffic_ratio <= 0:
            raise ValueError("实验曝光比例必须大于 0")

        if traffic_ratio > 1:
            raise ValueError("实验曝光比例不能大于 1")

        variant_weights = [
            (item, _variant_weight(item))
            for item in variants
        ]

        if any(
                not math.isfinite(weight)
                for _, weight in variant_weights
        ):
            raise ValueError("实验 Variant 权重必须是有限数值")

        if any(
                weight < 0
                for _, weight in variant_weights
        ):
            raise ValueError("实验 Variant 权重不能小于 0")

        active_variants = [
            item for item, weight in variant_weights
            if weight > 0
        ]

        if not active_variants:
            raise ValueError("实验没有可用 Variant")

        active_variants.sort(
            key=self._variant_sort_key
        )

        total_weight = sum(
            _variant_weight(item)
            for item in active_variants
        )

        if abs(total_weight - 1.0) > 1e-8:
            raise ValueError("实验 Variant 权重总和必须等于 1")

        bucket_value = self.exposure_value(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

        bucket = self.bucket_label(bucket_value)

        if bucket_value >= traffic_ratio:
            return None

        point = self.variant_point(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

        cumulative = 0.0

        for variant in active_variants:
            weight = _variant_weight(variant)
            cumulative += weight

            if point < cumulative:
                return self._build_result(
                    experiment_id=experiment_id,
                    subject_key=subject_key,
                    traffic_ratio=traffic_ratio,
                    variant=variant,
                    weight=weight,
                    bucket=bucket,
                    bucket_value=bucket_value,
                    point=point,
                )

        variant = active_variants[-1]

        return self._build_result(
            experiment_id=experiment_id,
            subject_key=subject_key,
            traffic_ratio=traffic_ratio,
            variant=variant,
            weight=_variant_weight(variant),
            bucket=bucket,
            bucket_value=bucket_value,
            point=point,
        )

    @classmethod
    def exposure_value(
            cls,
            *,
            experiment_id: str,
            subject_key: str,
    ) -> float:
        """计算稳定曝光分桶值.

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体

        返回：
            [0.0, 1.0) 范围内的稳定曝光分桶值
        """
        return cls._exposure_value(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

    @classmethod
    def variant_point(
            cls,
            *,
            experiment_id: str,
            subject_key: str,
    ) -> float:
        """计算稳定 Hash 分组位置.

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体

        返回：
            [0.0, 1.0) 范围内的稳定分组位置
        """
        return cls._variant_point(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

    @classmethod
    def bucket_label(
            cls,
            bucket_value: float,
    ) -> str:
        """生成曝光分桶标识.

        参数：
            bucket_value: 稳定曝光分桶值

        返回：
            分桶标识，例如 bucket_0089
        """
        return cls._bucket_label(
            bucket_value
        )

    @classmethod
    def _exposure_value(
            cls,
            *,
            experiment_id: str,
            subject_key: str,
    ) -> float:
        """计算稳定曝光分桶值.

        曝光哈希仅用于判断主体是否进入实验。

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体

        返回：
            [0.0, 1.0) 范围内的稳定曝光分桶值
        """
        raw = f"{experiment_id}:{subject_key}"

        return cls._hash_value(raw)

    @classmethod
    def _variant_point(
            cls,
            *,
            experiment_id: str,
            subject_key: str,
    ) -> float:
        """计算稳定 Hash 分组位置.

        Variant 哈希与曝光哈希相互独立，
        仅用于实验内部的 Variant 分配。

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体

        返回：
            [0.0, 1.0) 范围内的稳定分组位置
        """
        raw = f"{experiment_id}:{subject_key}:variant"

        return cls._hash_value(raw)

    @staticmethod
    def _hash_value(
            raw: str,
    ) -> float:
        """计算稳定哈希值.

        参数：
            raw: 哈希输入字符串

        返回：
            [0.0, 1.0) 范围内的稳定哈希值
        """
        digest = hashlib.sha256(
            raw.encode("utf-8")
        ).digest()

        value = int.from_bytes(
            digest[:8],
            byteorder="big",
            signed=False,
        )

        return value / float(1 << 64)

    @staticmethod
    def _bucket_label(
            bucket_value: float,
    ) -> str:
        """生成曝光分桶标识.

        参数：
            bucket_value: 稳定曝光分桶值

        返回：
            分桶标识，例如 bucket_0089
        """
        bucket_no = int(bucket_value * 10000)

        return f"bucket_{bucket_no:04d}"

    @staticmethod
    def _variant_sort_key(
            variant: Any,
    ) -> tuple[str, str]:
        """生成 Variant 稳定排序键.

        优先按照 variant_id 排序，
        variant_id 相同时使用 name 辅助排序。

        参数：
            variant: 实验 Variant 对象

        返回：
            稳定排序键
        """
        variant_id = str(
            getattr(variant, "variant_id", "") or ""
        )

        name = str(
            getattr(variant, "name", "") or ""
        )

        return variant_id, name

    @staticmethod
    def _build_result(
            *,
            experiment_id: str,
            subject_key: str,
            traffic_ratio: float,
            variant: Any,
            weight: float,
            bucket: str,
            bucket_value: float,
            point: float,
    ) -> AssignmentResult:
        """构建实验分配结果.

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体
            traffic_ratio: 实验曝光比例
            variant: 命中的 Variant 对象
            weight: 命中 Variant 的权重
            bucket: 曝光分桶标识
            bucket_value: 稳定曝光分桶值
            point: 实验内稳定分组位置

        返回：
            实验分配结果
        """
        return AssignmentResult(
            variant=variant,
            bucket=bucket,
            bucket_value=bucket_value,
            point=point,
            context={
                "experiment_id": experiment_id,
                "subject_key": subject_key,
                "bucket": bucket,
                "bucket_value": bucket_value,
                "traffic_ratio": traffic_ratio,
                "point": point,
                "variant_id": getattr(
                    variant,
                    "variant_id",
                    None,
                ),
                "variant_name": getattr(
                    variant,
                    "name",
                    None,
                ),
                "variant_weight": weight,
                "strategy": str(AssignmentStrategy.HASH),
            },
        )


class ManualAssigner:
    """手工指定分配器.

    根据调用方显式传入的 variant_id、variant_name，
    或 subject_key 到 Variant 的映射关系进行实验分配。

    说明：
      - manual 策略不执行 traffic_ratio 曝光判断
      - manual 策略不按照 weight 自动分配
      - 未提供手工指定目标时返回 None
      - 指定的 Variant 必须存在于 variants 中
      - 指定的 Variant weight 必须大于 0
    """

    def assign(
            self,
            *,
            experiment_id: str,
            subject_key: str,
            variants: list[Any],
            manual_variant_id: str | None = None,
            manual_variant_name: str | None = None,
            manual_assignments: dict[str, Any] | None = None,
    ) -> AssignmentResult | None:
        """执行手工指定分组.

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体，例如客户号、订单号、申请单号
            variants: 实验 Variant 列表
            manual_variant_id: 手工指定的 Variant ID
            manual_variant_name: 手工指定的 Variant 名称
            manual_assignments: subject_key 到 Variant 的映射关系

        返回：
            实验分配结果；如果未找到手工指定目标，返回 None

        异常：
            ValueError: 指定 Variant 不存在或不可用
        """
        if not experiment_id:
            raise ValueError("实验 ID 不能为空")

        if not subject_key:
            raise ValueError("分桶主体不能为空")

        active_variants = [
            item for item in variants
            if _variant_weight(item) > 0
        ]

        if not active_variants:
            raise ValueError("实验没有可用 Variant")

        target = self._resolve_manual_target(
            subject_key=subject_key,
            manual_variant_id=manual_variant_id,
            manual_variant_name=manual_variant_name,
            manual_assignments=manual_assignments,
        )

        if target is None:
            return None

        variant = self._find_variant(
            variants=active_variants,
            target=target,
        )

        if variant is None:
            raise ValueError(
                f"手工指定 Variant 不存在或不可用: {target}"
            )

        weight = _variant_weight(variant)

        return AssignmentResult(
            variant=variant,
            bucket=None,
            bucket_value=None,
            point=None,
            context={
                "experiment_id": experiment_id,
                "subject_key": subject_key,
                "variant_id": getattr(
                    variant,
                    "variant_id",
                    None,
                ),
                "variant_name": getattr(
                    variant,
                    "name",
                    None,
                ),
                "variant_weight": weight,
                "manual_target": target,
                "strategy": str(AssignmentStrategy.MANUAL),
            },
        )

    @staticmethod
    def _resolve_manual_target(
            *,
            subject_key: str,
            manual_variant_id: str | None,
            manual_variant_name: str | None,
            manual_assignments: dict[str, Any] | None,
    ) -> str | None:
        """获取手工指定 Variant 目标.

        参数：
            subject_key: 分桶主体
            manual_variant_id: 手工指定的 Variant ID
            manual_variant_name: 手工指定的 Variant 名称
            manual_assignments: subject_key 到 Variant 的映射关系

        返回：
            Variant ID 或 Variant 名称
        """
        if manual_variant_id:
            return manual_variant_id

        if manual_variant_name:
            return manual_variant_name

        if not manual_assignments:
            return None

        value = manual_assignments.get(subject_key)

        if value is None:
            return None

        if isinstance(value, dict):
            for key in (
                    "variant_id",
                    "variant_name",
                    "name",
                ):
                target = value.get(key)

                if isinstance(target, str) and target:
                    return target

            return None

        if isinstance(value, str) and value:
            return value

        return None

    @staticmethod
    def _find_variant(
            *,
            variants: list[Any],
            target: str,
    ) -> Any | None:
        """查找手工指定 Variant.

        参数：
            variants: 实验 Variant 列表
            target: Variant ID 或 Variant 名称

        返回：
            命中的 Variant 对象
        """
        target = str(target)

        for variant in variants:
            variant_id = str(
                getattr(variant, "variant_id", "") or ""
            )

            name = str(
                getattr(variant, "name", "") or ""
            )

            if target in (variant_id, name):
                return variant

        return None


class ExperimentAssigner:
    """实验分配器.

    根据 strategy 选择稳定 Hash 分组或手工指定分组。
    """

    def __init__(
            self,
            *,
            hash_assigner: StableHashAssigner | None = None,
            manual_assigner: ManualAssigner | None = None,
    ):
        """初始化实验分配器.

        参数：
            hash_assigner: 稳定 Hash 分配器，默认使用 StableHashAssigner
            manual_assigner: 手工指定分配器，默认使用 ManualAssigner
        """
        self.hash_assigner = hash_assigner or StableHashAssigner()
        self.manual_assigner = manual_assigner or ManualAssigner()

    def assign(
            self,
            *,
            strategy: AssignmentStrategy | str,
            experiment_id: str,
            subject_key: str,
            variants: list[Any],
            traffic_ratio: float = 1.0,
            manual_variant_id: str | None = None,
            manual_variant_name: str | None = None,
            manual_assignments: dict[str, Any] | None = None,
    ) -> AssignmentResult | None:
        """分配实验 Variant.

        参数：
            strategy: 分配策略，可选 hash/manual
            experiment_id: 实验 ID
            subject_key: 分桶主体，例如客户号、订单号、申请单号
            variants: 实验 Variant 列表
            traffic_ratio: 实验曝光比例，hash 策略使用
            manual_variant_id: 手工指定的 Variant ID，manual 策略使用
            manual_variant_name: 手工指定的 Variant 名称，manual 策略使用
            manual_assignments: subject_key 到 Variant 的映射关系，manual 策略使用

        返回：
            实验分配结果；如果未进入实验或未找到手工指定目标，返回 None
        """
        strategy_value = _assignment_strategy_value(strategy)

        if strategy_value == AssignmentStrategy.HASH:
            return self.hash_assigner.assign(
                experiment_id=experiment_id,
                subject_key=subject_key,
                traffic_ratio=traffic_ratio,
                variants=variants,
            )

        if strategy_value == AssignmentStrategy.MANUAL:
            return self.manual_assigner.assign(
                experiment_id=experiment_id,
                subject_key=subject_key,
                variants=variants,
                manual_variant_id=manual_variant_id,
                manual_variant_name=manual_variant_name,
                manual_assignments=manual_assignments,
            )

        raise ValueError(f"不支持的实验分配策略: {strategy_value}")


def _assignment_strategy_value(
        strategy: AssignmentStrategy | str,
) -> str:
    """获取实验分配策略值."""
    return str(strategy).lower()


def _variant_weight(
        variant: Any,
) -> float:
    """获取 Variant 权重."""
    return float(
        getattr(variant, "weight", 0) or 0
    )
