# datamind/ab_test/assignment.py

"""A/B 实验分配

提供实验曝光判断和稳定进组能力。

核心功能：
  - AssignmentResult: 实验分配结果
  - StableHashAssigner: 按实验 ID 和分桶主体进行稳定进组分配

说明：
  实验分配包含曝光判断和实验分组两个独立阶段。

  - 曝光判断：
      根据 experiment_id 和 subject_key
      计算稳定曝光分桶值，
      判断主体是否进入实验。

  - 实验分组：
      使用独立的稳定哈希值计算实验内分组位置，
      再按照 Variant 的 weight 分配到固定分组。

  曝光判断和实验分组使用独立哈希空间，
  调整 traffic_ratio 只影响实验曝光范围，
  不改变已进入实验主体的 Variant 分组结果。

使用示例：
  from datamind.ab_test.assignment import StableHashAssigner

  assigner = StableHashAssigner()

  result = assigner.assign(
      experiment_id="exp_a1b2c3d4",
      subject_key="customer_10001",
      traffic_ratio=0.2,
      variants=variants
  )

  if result:
      variant = result.variant
      bucket = result.bucket
"""

import hashlib
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AssignmentResult:
    """实验分配结果

    属性：
        variant: 命中的实验分组对象
        bucket: 曝光分桶标识，例如 bucket_0089
        bucket_value: 稳定曝光分桶值，取值范围 [0.0, 1.0)
        point: 实验内稳定分组位置，取值范围 [0.0, 1.0)
        context: 分配上下文
    """

    variant: Any
    bucket: str
    bucket_value: float
    point: float
    context: dict


class StableHashAssigner:
    """稳定哈希分配器

    根据 experiment_id 和 subject_key 进行稳定实验分配。

    首先计算曝光分桶值，判断主体是否进入实验；
    进入实验后，再使用独立哈希值计算实验内分组位置，
    按照实验分组的 weight 分配到固定 Variant。

    说明：
      - traffic_ratio 表示实验曝光比例，必须大于 0 且小于等于 1
      - weight 表示实验内分组权重
      - weight 总和必须等于 1
      - 如果未命中实验曝光比例，返回 None
      - 同一个实验下，同一个 subject_key 会稳定命中同一个结果
      - 实验创建后，traffic_ratio 和各分组 weight 应保持不变
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
        """分配实验分组

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体，例如客户号、订单号、申请单号
            traffic_ratio: 实验曝光比例，取值范围为 (0, 1]
            variants: 实验分组列表，要求对象包含 weight 字段

        返回：
            实验分配结果；如果未进入实验，返回 None

        异常：
            ValueError: 实验曝光比例、分组权重非法
        """
        if not experiment_id:
            raise ValueError("实验 ID 不能为空")

        if not subject_key:
            raise ValueError("分桶主体不能为空")

        if traffic_ratio <= 0:
            raise ValueError("实验曝光比例必须大于 0")

        if traffic_ratio > 1:
            raise ValueError("实验曝光比例不能大于 1")

        active_variants = [
            item for item in variants
            if float(getattr(item, "weight", 0) or 0) > 0
        ]

        if not active_variants:
            raise ValueError("实验没有可用分组")

        active_variants.sort(
            key=self._variant_sort_key
        )

        total_weight = sum(
            float(item.weight)
            for item in active_variants
        )

        if abs(total_weight - 1.0) > 1e-8:
            raise ValueError("实验分组权重总和必须等于 1")

        bucket_value = self._exposure_value(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

        bucket = self._bucket_label(bucket_value)

        if bucket_value >= traffic_ratio:
            return None

        point = self._variant_point(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

        cumulative = 0.0

        for variant in active_variants:
            weight = float(variant.weight)
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
            weight=float(variant.weight),
            bucket=bucket,
            bucket_value=bucket_value,
            point=point,
        )

    @classmethod
    def _exposure_value(
            cls,
            *,
            experiment_id: str,
            subject_key: str,
    ) -> float:
        """计算稳定曝光分桶值

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
        """计算稳定实验内分组位置

        Variant 哈希与曝光哈希相互独立，
        仅用于实验内部的 Variant 分配。

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体

        返回：
            [0.0, 1.0) 范围内的稳定实验内分组位置
        """
        raw = f"{experiment_id}:{subject_key}:variant"

        return cls._hash_value(raw)

    @staticmethod
    def _hash_value(
            raw: str,
    ) -> float:
        """计算稳定哈希值

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
        """生成曝光分桶标识

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
        """生成实验分组稳定排序键

        优先按照 variant_id 排序，
        variant_id 相同时使用 name 辅助排序。

        参数：
            variant: 实验分组对象

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
        """构建实验分配结果

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体
            traffic_ratio: 实验曝光比例
            variant: 命中的实验分组对象
            weight: 命中分组的权重
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
                "strategy": "hash",
            },
        )
