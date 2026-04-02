# datamind/demo/binning_config.py

"""示例分箱配置

定义评分卡模型的分箱规则，用于 WOE 转换。
"""

from datamind.core.scoring.binning import Bin

# 年龄分箱
age_bins = [
    Bin(lower=None, upper=25, woe=-0.5, bin_id=0, label="年轻", bad_rate=0.08, sample_ratio=0.15),
    Bin(lower=25, upper=35, woe=-0.2, bin_id=1, label="青年", bad_rate=0.06, sample_ratio=0.25),
    Bin(lower=35, upper=45, woe=0.0, bin_id=2, label="中年", bad_rate=0.05, sample_ratio=0.30),
    Bin(lower=45, upper=55, woe=0.3, bin_id=3, label="中老年", bad_rate=0.10, sample_ratio=0.20),
    Bin(lower=55, upper=None, woe=0.8, bin_id=4, label="老年", bad_rate=0.15, sample_ratio=0.10),
]

# 收入分箱
income_bins = [
    Bin(lower=None, upper=30000, woe=0.5, bin_id=0, label="低收入", bad_rate=0.12, sample_ratio=0.20),
    Bin(lower=30000, upper=50000, woe=0.2, bin_id=1, label="中低收入", bad_rate=0.08, sample_ratio=0.25),
    Bin(lower=50000, upper=80000, woe=0.0, bin_id=2, label="中等收入", bad_rate=0.05, sample_ratio=0.30),
    Bin(lower=80000, upper=120000, woe=-0.3, bin_id=3, label="中高收入", bad_rate=0.03, sample_ratio=0.15),
    Bin(lower=120000, upper=None, woe=-0.6, bin_id=4, label="高收入", bad_rate=0.02, sample_ratio=0.10),
]

# 负债率分箱
debt_ratio_bins = [
    Bin(lower=None, upper=0.2, woe=-0.8, bin_id=0, label="低负债", bad_rate=0.02, sample_ratio=0.20),
    Bin(lower=0.2, upper=0.4, woe=-0.3, bin_id=1, label="较低负债", bad_rate=0.04, sample_ratio=0.25),
    Bin(lower=0.4, upper=0.6, woe=0.0, bin_id=2, label="中等负债", bad_rate=0.06, sample_ratio=0.30),
    Bin(lower=0.6, upper=0.8, woe=0.5, bin_id=3, label="较高负债", bad_rate=0.12, sample_ratio=0.15),
    Bin(lower=0.8, upper=None, woe=1.0, bin_id=4, label="高负债", bad_rate=0.20, sample_ratio=0.10),
]

# 信用历史分箱
credit_history_bins = [
    Bin(lower=None, upper=500, woe=1.2, bin_id=0, label="很差", bad_rate=0.25, sample_ratio=0.10),
    Bin(lower=500, upper=600, woe=0.6, bin_id=1, label="较差", bad_rate=0.15, sample_ratio=0.15),
    Bin(lower=600, upper=700, woe=0.0, bin_id=2, label="一般", bad_rate=0.08, sample_ratio=0.25),
    Bin(lower=700, upper=800, woe=-0.5, bin_id=3, label="良好", bad_rate=0.04, sample_ratio=0.30),
    Bin(lower=800, upper=None, woe=-1.0, bin_id=4, label="优秀", bad_rate=0.02, sample_ratio=0.20),
]

# 工作年限分箱
employment_years_bins = [
    Bin(lower=None, upper=1, woe=0.6, bin_id=0, label="新手", bad_rate=0.12, sample_ratio=0.15),
    Bin(lower=1, upper=3, woe=0.2, bin_id=1, label="初级", bad_rate=0.08, sample_ratio=0.20),
    Bin(lower=3, upper=5, woe=0.0, bin_id=2, label="中级", bad_rate=0.06, sample_ratio=0.25),
    Bin(lower=5, upper=10, woe=-0.2, bin_id=3, label="资深", bad_rate=0.04, sample_ratio=0.25),
    Bin(lower=10, upper=None, woe=-0.5, bin_id=4, label="专家", bad_rate=0.03, sample_ratio=0.15),
]

# 贷款金额分箱
loan_amount_bins = [
    Bin(lower=None, upper=50000, woe=-0.4, bin_id=0, label="小额", bad_rate=0.04, sample_ratio=0.20),
    Bin(lower=50000, upper=100000, woe=-0.1, bin_id=1, label="中小额", bad_rate=0.06, sample_ratio=0.25),
    Bin(lower=100000, upper=200000, woe=0.1, bin_id=2, label="中等额", bad_rate=0.08, sample_ratio=0.30),
    Bin(lower=200000, upper=500000, woe=0.4, bin_id=3, label="大额", bad_rate=0.12, sample_ratio=0.15),
    Bin(lower=500000, upper=None, woe=0.8, bin_id=4, label="巨额", bad_rate=0.18, sample_ratio=0.10),
]

# 完整分箱配置
BINNING_CONFIG = {
    "age": age_bins,
    "income": income_bins,
    "debt_ratio": debt_ratio_bins,
    "credit_history": credit_history_bins,
    "employment_years": employment_years_bins,
    "loan_amount": loan_amount_bins,
}