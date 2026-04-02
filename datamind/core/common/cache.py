# datamind/core/ml/common/cache.py

"""缓存工具模块

提供 LRU 缓存实现和缓存键生成器，用于模型推理结果缓存。

核心功能：
  - LRUCache: 线程安全的 LRU 缓存实现
  - CacheKeyGenerator: 缓存键生成器，支持预测缓存和模型缓存

LRUCache 特性：
  - 线程安全：使用可重入锁保护并发访问
  - TTL 支持：支持缓存过期时间（默认 3600 秒）
  - 自动淘汰：超过最大容量时淘汰最久未使用的条目
  - 深拷贝：返回缓存值的副本，避免外部修改
  - 前缀删除：支持按前缀批量删除缓存
  - 统计信息：提供缓存大小、容量等统计信息

CacheKeyGenerator 特性：
  - 预测缓存键：pred:{model_id}:{feature_hash}
  - 模型缓存前缀：pred:{model_id}:
  - 模型ID提取：从缓存键中反向提取模型ID
"""

import threading
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import OrderedDict


class LRUCache:
    """LRU 缓存实现（线程安全）

    LRU（Least Recently Used）缓存策略：
      - 最近使用的条目会被移动到末尾
      - 超出容量时淘汰头部（最久未使用）的条目
      - 支持 TTL 过期时间，过期条目自动失效

    使用场景：
      - 模型推理结果缓存
      - 特征计算结果缓存
      - 高频查询结果缓存
    """

    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        """
        初始化 LRU 缓存

        参数:
            max_size: 最大缓存数量
            ttl: 缓存过期时间（秒）
        """
        self._cache = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值

        如果缓存存在且未过期，返回值的副本；
        否则返回 None 并删除过期条目。

        参数:
            key: 缓存键

        返回:
            缓存值的副本，不存在或过期返回 None
        """
        with self._lock:
            if key not in self._cache:
                return None

            value, timestamp = self._cache[key]
            if (datetime.now() - timestamp).total_seconds() > self._ttl:
                del self._cache[key]
                return None

            # 移动到末尾（最近使用）
            self._cache.move_to_end(key)
            return self._deep_copy(value)

    def set(self, key: str, value: Any):
        """
        设置缓存值

        如果键已存在，先删除后重新插入（更新位置）；
        如果超出容量，淘汰最久未使用的条目。

        参数:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                # 淘汰最久未使用的条目（第一个）
                self._cache.popitem(last=False)

            self._cache[key] = (self._deep_copy(value), datetime.now())

    def delete(self, key: str) -> bool:
        """
        删除指定缓存

        参数:
            key: 缓存键

        返回:
            True 表示删除成功，False 表示键不存在
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def delete_by_prefix(self, prefix: str) -> int:
        """
        删除指定前缀的缓存

        参数:
            prefix: 键前缀

        返回:
            删除的缓存数量
        """
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """
        获取缓存数量

        返回:
            当前缓存的条目数量
        """
        with self._lock:
            return len(self._cache)

    def keys(self) -> List[str]:
        """
        获取所有缓存键（用于调试）

        返回:
            缓存键列表
        """
        with self._lock:
            return list(self._cache.keys())

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        返回:
            统计信息字典，包含 size, max_size, ttl, keys_sample
        """
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'ttl': self._ttl,
                'keys_sample': list(self._cache.keys())[:10]
            }

    def _deep_copy(self, obj: Any) -> Any:
        """
        深拷贝（针对常见类型优化）

        对于基本类型直接返回，对于容器类型递归拷贝，
        对于自定义对象尝试调用 copy 方法。

        参数:
            obj: 要拷贝的对象

        返回:
            拷贝后的对象
        """
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_copy(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(self._deep_copy(v) for v in obj)
        if isinstance(obj, set):
            return {self._deep_copy(v) for v in obj}
        if hasattr(obj, 'copy'):
            return obj.copy()
        return obj


class CacheKeyGenerator:
    """缓存键生成器

    提供统一的缓存键生成规则，确保键的一致性和可追溯性。
    """

    @staticmethod
    def for_prediction(model_id: str, features: Dict[str, Any]) -> str:
        """
        生成预测缓存键

        格式: pred:{model_id}:{feature_hash}

        参数:
            model_id: 模型ID
            features: 特征字典

        返回:
            缓存键，如 "pred:MDL_001:a1b2c3d4e5f6g7h8"
        """
        sorted_features = json.dumps(features, sort_keys=True)
        feature_hash = hashlib.md5(sorted_features.encode()).hexdigest()
        return f"pred:{model_id}:{feature_hash}"

    @staticmethod
    def for_model(model_id: str) -> str:
        """
        生成模型相关的缓存前缀

        用于批量删除某个模型的所有缓存。

        参数:
            model_id: 模型ID

        返回:
            缓存前缀，如 "pred:MDL_001:"
        """
        return f"pred:{model_id}:"

    @staticmethod
    def extract_model_id(key: str) -> Optional[str]:
        """
        从缓存键中提取模型ID

        参数:
            key: 缓存键

        返回:
            模型ID，如果无法提取则返回 None
        """
        if key.startswith("pred:"):
            parts = key.split(":")
            if len(parts) >= 2:
                return parts[1]
        return None