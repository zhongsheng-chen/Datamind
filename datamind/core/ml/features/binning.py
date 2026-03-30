# datamind/core/ml/features/binning.py
"""分箱结构定义

银行评分卡的核心资产，定义每个特征的分箱信息。

核心功能：
  - Bin: 单个分箱的数据结构
  - contains: 判断值是否属于该分箱

特性：
  - 完整分箱信息：边界、WOE、坏账率、样本占比
  - 缺失值处理：独立分箱
  - 可扩展：支持自定义描述
  - 序列化支持：to_dict / from_dict

使用示例：
  >>> from datamind.core.ml.features.binning import Bin
  >>>
  >>> bin_age = Bin(
  ...     id=3,
  ...     lower=40,
  ...     upper=50,
  ...     label="[40, 50)",
  ...     woe=0.12,
  ...     bad_rate=0.08,
  ...     description="中年稳定客群"
  ... )
  >>> bin_age.contains(45)
  True
"""

from dataclasses import dataclass
from typing import Optional, Any


@dataclass
class Bin:
    """分箱结构

    银行评分卡的核心数据结构，代表一个特征的一个分箱区间。

    属性:
        id: 分箱ID（从0开始）
        lower: 下边界（包含），None 表示 -∞
        upper: 上边界（不包含），None 表示 +∞
        label: 分箱标签，如 "[18, 30)"
        woe: WOE值（Weight of Evidence）
        bad_rate: 坏账率（可选）
        sample_ratio: 样本占比（可选）
        description: 分箱描述（可选）
        is_missing: 是否为缺失值分箱
    """
    id: int
    lower: Optional[float]
    upper: Optional[float]
    label: str
    woe: float

    # 可选字段（强烈建议生产带上）
    bad_rate: Optional[float] = None
    sample_ratio: Optional[float] = None
    description: Optional[str] = None
    is_missing: bool = False

    def contains(self, value: Any) -> bool:
        """
        判断值是否属于该分箱

        参数:
            value: 特征值

        返回:
            True 表示属于，False 表示不属于
        """
        # 处理缺失值
        if value is None:
            return self.is_missing

        # 检查下边界
        if self.lower is not None and value < self.lower:
            return False

        # 检查上边界
        if self.upper is not None and value >= self.upper:
            return False

        return True

    def to_dict(self) -> dict:
        """转换为字典（用于序列化）"""
        return {
            'id': self.id,
            'lower': self.lower,
            'upper': self.upper,
            'label': self.label,
            'woe': self.woe,
            'bad_rate': self.bad_rate,
            'sample_ratio': self.sample_ratio,
            'description': self.description,
            'is_missing': self.is_missing
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Bin':
        """从字典创建（用于反序列化）"""
        return cls(
            id=data['id'],
            lower=data.get('lower'),
            upper=data.get('upper'),
            label=data['label'],
            woe=data['woe'],
            bad_rate=data.get('bad_rate'),
            sample_ratio=data.get('sample_ratio'),
            description=data.get('description'),
            is_missing=data.get('is_missing', False)
        )