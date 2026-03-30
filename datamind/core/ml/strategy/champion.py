# datamind/core/ml/strategy/champion.py
"""主模型管理

管理当前生产环境使用的主模型（冠军模型）。

核心功能：
  - get: 获取当前主模型
  - set: 设置主模型
  - clear_cache: 清除缓存

特性：
  - 缓存支持：减少数据库查询
  - 线程安全：使用 RLock 保证并发安全
  - 环境隔离：支持多环境（开发/测试/生产）
  - 任务隔离：支持多任务类型（评分/反欺诈）

使用示例：
  >>> from datamind.core.ml.strategy.champion import ChampionStrategy
  >>>
  >>> champion = ChampionStrategy()
  >>> model = champion.get("scoring", "production")
  >>> print(model['model_id'])
  MDL_001
  >>>
  >>> champion.set("MDL_002", "scoring", "production")
"""

from typing import Optional, Dict, Any
import threading

from datamind.core.db.database import get_db
from datamind.core.db.models import ModelDeployment
from datamind.core.domain.enums import TaskType, DeploymentEnvironment


class ChampionStrategy:
    """主模型管理器

    负责：
        - 获取当前主模型
        - 设置主模型
        - 管理主模型缓存

    属性:
        _cache: 缓存字典，键为 "{task_type}:{environment}"
        _lock: 线程锁
    """

    def __init__(self):
        """初始化主模型管理器"""
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def get(self, task_type: str, environment: str) -> Optional[Dict]:
        """
        获取当前主模型

        参数:
            task_type: 任务类型（scoring/fraud_detection）
            environment: 环境（development/testing/staging/production）

        返回:
            主模型信息字典，包含：
                - model_id: 模型ID
                - model_version: 模型版本
                - task_type: 任务类型
                - environment: 环境
            如果未找到则返回 None

        示例:
            >>> champion = ChampionStrategy()
            >>> model = champion.get("scoring", "production")
            >>> if model:
            >>>     print(model['model_id'])
        """
        cache_key = f"{task_type}:{environment}"

        with self._lock:
            # 检查缓存
            if cache_key in self._cache:
                return self._cache[cache_key]

            # 从数据库查询
            with get_db() as session:
                deployment = session.query(ModelDeployment).filter(
                    ModelDeployment.task_type == task_type,
                    ModelDeployment.environment == environment,
                    ModelDeployment.is_champion == True,
                    ModelDeployment.is_active == True
                ).first()

                if deployment:
                    result = {
                        'model_id': deployment.model_id,
                        'model_version': deployment.model_version,
                        'task_type': task_type,
                        'environment': environment
                    }
                    self._cache[cache_key] = result
                    return result

            return None

    def set(self, model_id: str, task_type: str, environment: str):
        """
        设置主模型

        参数:
            model_id: 模型ID
            task_type: 任务类型（scoring/fraud_detection）
            environment: 环境（development/testing/staging/production）

        示例:
            >>> champion = ChampionStrategy()
            >>> champion.set("MDL_002", "scoring", "production")
        """
        with self._lock:
            with get_db() as session:
                # 清除同任务同环境的旧主模型
                session.query(ModelDeployment).filter(
                    ModelDeployment.task_type == task_type,
                    ModelDeployment.environment == environment,
                    ModelDeployment.is_champion == True
                ).update({'is_champion': False})

                # 设置新主模型
                deployment = session.query(ModelDeployment).filter_by(
                    model_id=model_id,
                    environment=environment
                ).first()
                if deployment:
                    deployment.is_champion = True
                    session.commit()

            # 清除缓存
            cache_key = f"{task_type}:{environment}"
            self._cache.pop(cache_key, None)

    def clear_cache(self):
        """清除缓存"""
        with self._lock:
            self._cache.clear()