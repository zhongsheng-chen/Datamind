# datamind/core/scoring/binning_example.py
"""分箱配置示例

提供 WOETransformer 可用的分箱配置示例
"""

from datamind.core.scoring.binning import Bin

# 示例：年龄分箱
age_bins = [
    Bin(
        id=0,
        label="缺失",
        lower=None,
        upper=None,
        is_missing=True,
        woe=0.0,
        bad_rate=0.2,
        sample_ratio=0.05,
        description="缺失值"
    ),
    Bin(
        id=1,
        label="18-25",
        lower=18,
        upper=25,
        is_missing=False,
        woe=-0.5,
        bad_rate=0.05,
        sample_ratio=0.15,
        description="年轻人"
    ),
    Bin(
        id=2,
        label="26-35",
        lower=26,
        upper=35,
        is_missing=False,
        woe=0.1,
        bad_rate=0.08,
        sample_ratio=0.25,
        description="青年"
    ),
    Bin(
        id=3,
        label="36-50",
        lower=36,
        upper=50,
        is_missing=False,
        woe=0.3,
        bad_rate=0.12,
        sample_ratio=0.35,
        description="中年"
    ),
    Bin(
        id=4,
        label="51以上",
        lower=51,
        upper=99,
        is_missing=False,
        woe=0.7,
        bad_rate=0.18,
        sample_ratio=0.20,
        description="老年"
    )
]

# 示例：收入分箱
income_bins = [
    Bin(
        id=0,
        label="缺失",
        lower=None,
        upper=None,
        is_missing=True,
        woe=0.0,
        bad_rate=0.25,
        sample_ratio=0.03,
        description="缺失值"
    ),
    Bin(
        id=1,
        label="0-30000",
        lower=0,
        upper=30000,
        is_missing=False,
        woe=0.8,
        bad_rate=0.2,
        sample_ratio=0.10,
        description="低收入"
    ),
    Bin(
        id=2,
        label="30001-70000",
        lower=30001,
        upper=70000,
        is_missing=False,
        woe=0.2,
        bad_rate=0.1,
        sample_ratio=0.40,
        description="中等收入"
    ),
    Bin(
        id=3,
        label="70001以上",
        lower=70001,
        upper=None,
        is_missing=False,
        woe=-0.3,
        bad_rate=0.05,
        sample_ratio=0.47,
        description="高收入"
    )
]

# 完整分箱配置字典
binning_config = {
    "age": age_bins,
    "income": income_bins,
}