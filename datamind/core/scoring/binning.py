# datamind/core/scoring/binning.py

"""分箱对象定义

存储单个特征的分箱信息，包括边界、WOE 值、坏账率、样本占比等。

核心功能：
  - contains: 判断值是否属于该分箱
  - get_range_str: 获取分箱范围字符串表示
  - is_valid: 验证分箱有效性
  - __repr__: 打印分箱信息
"""

from typing import Any, Optional


class Bin:
    """单个特征分箱对象"""

    def __init__(
        self,
        lower: Optional[float] = None,
        upper: Optional[float] = None,
        woe: float = 0.0,
        bin_id: Optional[int] = None,
        label: Optional[str] = None,
        is_missing: bool = False,
        bad_rate: Optional[float] = None,
        sample_ratio: Optional[float] = None,
        description: str = ""
    ):
        """
        初始化分箱对象

        参数:
            lower: 下边界
            upper: 上边界（开区间）
            woe: WOE 值
            bin_id: 分箱 ID
            label: 分箱标签
            is_missing: 是否缺失值分箱
            bad_rate: 坏账率
            sample_ratio: 样本占比
            description: 分箱描述信息
        """
        self.lower = lower
        self.upper = upper
        self.woe = woe
        self.id = bin_id
        self.label = label
        self.is_missing = is_missing
        self.bad_rate = bad_rate
        self.sample_ratio = sample_ratio
        self.description = description

    def contains(self, value: Any) -> bool:
        """
        判断值是否属于该分箱

        参数:
            value: 待判断的值

        返回:
            True 表示属于该分箱，False 表示不属于
        """
        # 缺失值分箱
        if self.is_missing:
            return value is None

        # 非缺失值分箱，处理 None
        if value is None:
            return False

        # 数值比较
        if self.lower is not None and value < self.lower:
            return False
        if self.upper is not None and value >= self.upper:
            return False

        return True

    def get_range_str(self) -> str:
        """
        获取分箱范围字符串表示

        返回:
            分箱范围字符串，如 "[0, 10)"、"[20, +∞)"、"缺失值"、"(-∞, 0)"
        """
        if self.is_missing:
            return "缺失值"

        lower_str = f"{self.lower:.2f}" if self.lower is not None else "-∞"
        upper_str = f"{self.upper:.2f}" if self.upper is not None else "+∞"

        if self.lower is None:
            return f"(-∞, {upper_str})"
        elif self.upper is None:
            return f"[{lower_str}, +∞)"
        else:
            return f"[{lower_str}, {upper_str})"

    def is_valid(self) -> bool:
        """
        验证分箱有效性

        返回:
            True 表示分箱有效，False 表示无效
        """
        # 缺失值分箱总是有效的
        if self.is_missing:
            return True

        # 非缺失值分箱：边界必须有效
        if self.lower is not None and self.upper is not None:
            if self.lower >= self.upper:
                return False

        # WOE 值可以是任意实数
        return True

    def to_dict(self) -> dict:
        """
        转换为字典格式

        返回:
            分箱信息字典
        """
        result = {
            "lower": self.lower,
            "upper": self.upper,
            "woe": self.woe,
            "bin_id": self.id,
            "label": self.label,
            "is_missing": self.is_missing,
            "bad_rate": self.bad_rate,
            "sample_ratio": self.sample_ratio,
            "description": self.description,
        }
        # 移除 None 值
        return {k: v for k, v in result.items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> 'Bin':
        """
        从字典创建分箱对象

        参数:
            data: 分箱信息字典

        返回:
            Bin 实例
        """
        return cls(
            lower=data.get("lower"),
            upper=data.get("upper"),
            woe=data.get("woe", 0.0),
            bin_id=data.get("bin_id"),
            label=data.get("label"),
            is_missing=data.get("is_missing", False),
            bad_rate=data.get("bad_rate"),
            sample_ratio=data.get("sample_ratio"),
            description=data.get("description", ""),
        )

    def __repr__(self) -> str:
        return (
            f"Bin(id={self.id}, label={self.label}, range={self.get_range_str()}, "
            f"woe={self.woe:.4f}, is_missing={self.is_missing})"
        )