# datamind/core/ml/strategy/router.py
"""策略路由器

根据请求参数和配置，决定使用主模型还是陪跑模型。

核心功能：
  - route: 决定使用哪个模型
  - get_champion: 获取主模型
  - get_challengers: 获取陪跑模型列表

特性：
  - 自动降级：主模型不可用时自动使用陪跑
  - 权重支持：支持陪跑模型权重配置
  - 可扩展：支持自定义路由策略

使用示例：
  >>> from datamind.core.ml.strategy.router import StrategyRouter
  >>>
  >>> router = StrategyRouter()
  >>> result = router.route("scoring", "production", user_id="user_001")
  >>> print(result['model_id'])
"""

from typing import Dict, Any, Optional, List
import random
import threading

from datamind.core.ml.strategy.champion import ChampionStrategy
from datamind.core.ml.strategy.challenger import ChallengerStrategy
from datamind.core.ml.capability import ModelCapability, has_capability


class StrategyRouter:
    """策略路由器

    负责：
        - 决定使用主模型还是陪跑模型
        - 支持权重配置
        - 支持用户级分流
    """

    def __init__(self):
        """初始化策略路由器"""
        self._champion = ChampionStrategy()
        self._challenger = ChallengerStrategy()
        self._lock = threading.RLock()

    def route(
        self,
        task_type: str,
        environment: str,
        user_id: Optional[str] = None,
        challenger_weight: float = 0.0
    ) -> Dict[str, Any]:
        """
        决定使用哪个模型

        参数:
            task_type: 任务类型（scoring/fraud_detection）
            environment: 环境（development/testing/staging/production）
            user_id: 用户ID（用于一致性分流）
            challenger_weight: 陪跑模型流量权重（0-1），0表示全部走主模型

        返回:
            {
                "model_id": str,
                "model_version": str,
                "type": "champion" | "challenger"
            }

        示例:
            >>> router = StrategyRouter()
            >>> result = router.route("scoring", "production", user_id="user_001")
            >>> if result['type'] == 'champion':
            >>>     print("使用主模型")
        """
        # 检查是否使用陪跑模型
        use_challenger = False
        if challenger_weight > 0:
            if user_id:
                # 一致性分流：基于用户ID哈希
                hash_val = hash(user_id) % 100
                use_challenger = hash_val < challenger_weight * 100
            else:
                # 随机分流
                use_challenger = random.random() < challenger_weight

        if use_challenger:
            # 获取陪跑模型列表
            challengers = self._challenger.list(task_type, environment)
            if challengers:
                # 随机选择一个陪跑模型
                selected = random.choice(challengers)
                return {
                    "model_id": selected["model_id"],
                    "model_version": selected["model_version"],
                    "type": "challenger"
                }

        # 默认返回主模型
        champion = self._champion.get(task_type, environment)
        if champion:
            return {
                "model_id": champion["model_id"],
                "model_version": champion["model_version"],
                "type": "champion"
            }

        # 无可用模型
        raise ValueError(f"No champion model found for {task_type}/{environment}")

    def get_champion(self, task_type: str, environment: str) -> Optional[Dict]:
        """获取主模型"""
        return self._champion.get(task_type, environment)

    def get_challengers(self, task_type: str, environment: str) -> List[Dict]:
        """获取陪跑模型列表"""
        return self._challenger.list(task_type, environment)

    def add_challenger(self, model_id: str, task_type: str, environment: str):
        """添加陪跑模型"""
        self._challenger.add(model_id, task_type, environment)

    def remove_challenger(self, model_id: str, task_type: str, environment: str):
        """移除陪跑模型"""
        self._challenger.remove(model_id, task_type, environment)

    def set_champion(self, model_id: str, task_type: str, environment: str):
        """设置主模型"""
        self._champion.set(model_id, task_type, environment)

    def clear_cache(self):
        """清除所有缓存"""
        self._champion.clear_cache()
        self._challenger.clear_cache()