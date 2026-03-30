# datamind/core/ml/strategy/challenger.py
"""陪跑模型管理

管理陪跑模型（挑战者模型）列表。

核心功能：
  - list: 获取陪跑模型列表
  - add: 添加陪跑模型
  - remove: 移除陪跑模型
  - clear_cache: 清除缓存

特性：
  - 缓存支持：减少数据库查询
  - 线程安全：使用 RLock 保证并发安全
  - 环境隔离：支持多环境（开发/测试/生产）
  - 任务隔离：支持多任务类型（评分/反欺诈）

使用示例：
  >>> from datamind.core.ml.strategy.challenger import ChallengerStrategy
  >>>
  >>> challenger = ChallengerStrategy()
  >>> models = challenger.list("scoring", "production")
  >>> for model in models:
  >>>     print(model['model_id'])
  >>>
  >>> challenger.add("MDL_003", "scoring", "production")
  >>> challenger.remove("MDL_003", "scoring", "production")
"""

from typing import List, Dict, Any
import threading

from datamind.core.db.database import get_db
from datamind.core.db.models import ModelDeployment
from datamind.core.domain.enums import TaskType, DeploymentEnvironment


class ChallengerStrategy:
    """陪跑模型管理器

    负责：
        - 获取陪跑模型列表
        - 添加/移除陪跑模型
        - 管理陪跑模型缓存

    属性:
        _cache: 缓存字典，键为 "{task_type}:{environment}"
        _lock: 线程锁
    """

    def __init__(self):
        """初始化陪跑模型管理器"""
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._lock = threading.RLock()

    def list(self, task_type: str, environment: str) -> List[Dict]:
        """
        获取陪跑模型列表

        参数:
            task_type: 任务类型（scoring/fraud_detection）
            environment: 环境（development/testing/staging/production）

        返回:
            陪跑模型信息列表，每项包含：
                - model_id: 模型ID
                - model_version: 模型版本
                - task_type: 任务类型
                - environment: 环境

        示例:
            >>> challenger = ChallengerStrategy()
            >>> models = challenger.list("scoring", "production")
            >>> for model in models:
            >>>     print(model['model_id'])
        """
        cache_key = f"{task_type}:{environment}"

        with self._lock:
            # 检查缓存
            if cache_key in self._cache:
                return self._cache[cache_key]

            # 从数据库查询
            with get_db() as session:
                deployments = session.query(ModelDeployment).filter(
                    ModelDeployment.task_type == task_type,
                    ModelDeployment.environment == environment,
                    ModelDeployment.is_champion == False,
                    ModelDeployment.is_active == True
                ).all()

                result = [
                    {
                        'model_id': d.model_id,
                        'model_version': d.model_version,
                        'task_type': task_type,
                        'environment': environment
                    }
                    for d in deployments
                ]
                self._cache[cache_key] = result
                return result

    def add(self, model_id: str, task_type: str, environment: str):
        """
        添加陪跑模型

        参数:
            model_id: 模型ID
            task_type: 任务类型（scoring/fraud_detection）
            environment: 环境（development/testing/staging/production）

        示例:
            >>> challenger = ChallengerStrategy()
            >>> challenger.add("MDL_003", "scoring", "production")
        """
        with self._lock:
            with get_db() as session:
                deployment = session.query(ModelDeployment).filter_by(
                    model_id=model_id,
                    environment=environment
                ).first()
                if deployment:
                    deployment.is_champion = False
                    deployment.is_active = True
                    session.commit()

            # 清除缓存
            cache_key = f"{task_type}:{environment}"
            self._cache.pop(cache_key, None)

    def remove(self, model_id: str, task_type: str, environment: str):
        """
        移除陪跑模型

        参数:
            model_id: 模型ID
            task_type: 任务类型（scoring/fraud_detection）
            environment: 环境（development/testing/staging/production）

        示例:
            >>> challenger = ChallengerStrategy()
            >>> challenger.remove("MDL_003", "scoring", "production")
        """
        with self._lock:
            with get_db() as session:
                deployment = session.query(ModelDeployment).filter_by(
                    model_id=model_id,
                    environment=environment
                ).first()
                if deployment:
                    deployment.is_active = False
                    session.commit()

            # 清除缓存
            cache_key = f"{task_type}:{environment}"
            self._cache.pop(cache_key, None)

    def clear_cache(self):
        """清除缓存"""
        with self._lock:
            self._cache.clear()