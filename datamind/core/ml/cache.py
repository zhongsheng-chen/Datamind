# datamind/core/ml/cache.py

"""缓存工具模块"""

import threading
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import OrderedDict


class LRUCache:
    """LRU 缓存实现（线程安全）"""

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
        获取缓存值（返回副本）

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

            self._cache.move_to_end(key)
            return self._deep_copy(value)

    def set(self, key: str, value: Any):
        """
        设置缓存值

        参数:
            key: 缓存键
            value: 缓存值
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            self._cache[key] = (self._deep_copy(value), datetime.now())

    def delete(self, key: str) -> bool:
        """
        删除指定缓存

        参数:
            key: 缓存键

        返回:
            是否删除成功
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
        """获取缓存数量"""
        with self._lock:
            return len(self._cache)

    def keys(self) -> List[str]:
        """获取所有缓存键（用于调试）"""
        with self._lock:
            return list(self._cache.keys())

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
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
    """缓存键生成器"""

    @staticmethod
    def for_prediction(model_id: str, features: Dict[str, Any]) -> str:
        """
        生成预测缓存键

        格式: pred:{model_id}:{feature_hash}

        参数:
            model_id: 模型ID
            features: 特征字典

        返回:
            缓存键
        """
        sorted_features = json.dumps(features, sort_keys=True)
        feature_hash = hashlib.md5(sorted_features.encode()).hexdigest()
        return f"pred:{model_id}:{feature_hash}"

    @staticmethod
    def for_model(model_id: str) -> str:
        """
        生成模型相关的缓存前缀

        参数:
            model_id: 模型ID

        返回:
            缓存前缀
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