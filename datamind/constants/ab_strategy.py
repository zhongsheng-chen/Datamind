# datamind/constants/ab_strategy.py

"""AB测试策略常量

定义AB测试的分流策略类型，用于流量分配决策。

核心功能：
  - ABStrategy: 策略类型常量类
  - SUPPORTED_AB_STRATEGIES: 支持的策略集合

使用示例：
  from datamind.constants.ab_strategy import ABStrategy, SUPPORTED_AB_STRATEGIES

  if strategy == ABStrategy.RANDOM:
      return RANDOM.choice(groups)
  elif strategy == ABStrategy.HASH:
      return hash_based_select(request_id, groups)
"""


class ABStrategy:
    """AB测试策略常量"""

    RANDOM: str = "random"
    HASH: str = "hash"


SUPPORTED_AB_STRATEGIES = frozenset({
    ABStrategy.RANDOM,
    ABStrategy.HASH,
})