# datamind/ab_test/assignment.py

"""A/B 实验分配

提供实验曝光判断和稳定进组能力。

核心功能：
  - AssignmentResult: 实验分配结果
  - StableHashAssigner: 按实验 ID 和分桶主体进行稳定进组分配

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
        bucket: 分桶标识，用于落库，例如 bucket_0089
        bucket_value: 稳定哈希分桶值，取值范围 0.0 ~ 1.0
        point: 实验内分组位置，取值范围 0.0 ~ 1.0
        context: 分配上下文
    """

    variant: Any
    bucket: str
    bucket_value: float
    point: float
    context: dict


class StableHashAssigner:
    """稳定哈希分配器

    根据 experiment_id 和 subject_key 计算稳定哈希值，
    先判断请求是否进入实验，再按照实验分组的 weight 分配到固定分组。

    说明：
      - traffic_ratio 表示实验曝光比例，必须大于 0 且小于等于 1
      - weight 表示实验内分组权重
      - weight 总和必须等于 1
      - 如果未命中实验曝光比例，返回 None
      - 同一个实验下，同一个 subject_key 会稳定命中同一个结果
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

        total_weight = sum(
            float(item.weight)
            for item in active_variants
        )

        if abs(total_weight - 1.0) > 1e-8:
            raise ValueError("实验分组权重总和必须等于 1")

        bucket_value = self._bucket_value(
            experiment_id=experiment_id,
            subject_key=subject_key,
        )

        bucket = self._bucket_label(bucket_value)

        if bucket_value >= traffic_ratio:
            return None

        point = bucket_value / traffic_ratio
        cumulative = 0.0

        for variant in active_variants:
            weight = float(variant.weight)
            cumulative += weight

            if point <= cumulative:
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
                        "variant_id": getattr(variant, "variant_id", None),
                        "variant_name": getattr(variant, "name", None),
                        "variant_weight": weight,
                        "strategy": "hash",
                    },
                )

        variant = active_variants[-1]

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
                "variant_id": getattr(variant, "variant_id", None),
                "variant_name": getattr(variant, "name", None),
                "variant_weight": float(variant.weight),
                "strategy": "hash",
            },
        )

    @staticmethod
    def _bucket_value(
        *,
        experiment_id: str,
        subject_key: str,
    ) -> float:
        """计算稳定分桶值

        参数：
            experiment_id: 实验 ID
            subject_key: 分桶主体

        返回：
            0 到 1 之间的稳定分桶值
        """
        raw = f"{experiment_id}:{subject_key}".encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        value = int(digest[:16], 16)

        return value / float(0xFFFFFFFFFFFFFFFF)

    @staticmethod
    def _bucket_label(bucket_value: float) -> str:
        """生成分桶标识

        参数：
            bucket_value: 稳定哈希分桶值

        返回：
            分桶标识，例如 bucket_0089
        """
        bucket_no = int(bucket_value * 10000)

        return f"bucket_{bucket_no:04d}"