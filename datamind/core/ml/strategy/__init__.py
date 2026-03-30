# datamind/core/ml/strategy/__init__.py
"""策略模块

管理主模型和陪跑模型的策略。

模块组成：
  - champion: 主模型管理（冠军模型）
  - challenger: 陪跑模型管理（挑战者模型）
  - router: 策略路由器，决定使用哪个模型

使用示例：
  >>> from datamind.core.ml.strategy import ChampionStrategy, ChallengerStrategy, StrategyRouter
  >>>
  >>> champion = ChampionStrategy()
  >>> champion.set("MDL_001", "scoring", "production")
  >>>
  >>> router = StrategyRouter()
  >>> model = router.route("scoring", "production", challenger_weight=0.1)
"""

from .champion import ChampionStrategy
from .challenger import ChallengerStrategy
from .router import StrategyRouter

__all__ = [
    'ChampionStrategy',
    'ChallengerStrategy',
    'StrategyRouter',
]