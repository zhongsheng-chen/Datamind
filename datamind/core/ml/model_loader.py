# datamind/core/ml/model_loader.py

"""模型加载器

负责模型的动态加载和卸载，支持多种机器学习框架。

核心功能：
  - load_model: 从数据库加载模型到内存
  - unload_model: 从内存卸载模型
  - get_model: 获取已加载的模型实例
  - is_loaded: 检查模型是否已加载
  - get_loaded_models: 获取所有已加载模型信息

特性：
  - 并发安全：使用线程锁防止重复加载
  - 多框架支持：sklearn、xgboost、lightgbm、torch、tensorflow、onnx、catboost
  - 懒加载：按需加载，避免内存浪费
  - 审计日志：记录所有加载/卸载操作
  - 错误处理：详细的异常信息和错误追踪
  - 重试机制：加载失败时自动重试
  - 缓存管理：支持缓存过期和内存监控
  - 并发控制：限制同时加载的模型数量
  - 健康检查：监控模型加载器状态
  - 链路追踪：完整的 span 追踪
"""

import traceback
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from threading import Semaphore

from datamind.core.db import get_db
from datamind.core.db.models import ModelMetadata
from datamind.core.domain.enums import AuditAction
from datamind.core.ml.exceptions import ModelLoadException, UnsupportedFrameworkException
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging.debug import debug_print


class ModelLoader:
    """模型加载器"""

    def __init__(
            self,
            cache_ttl: int = 3600,
            max_concurrent_loads: int = 5,
            max_retries: int = 3
    ):
        """
        初始化模型加载器

        参数:
            cache_ttl: 缓存过期时间（秒），默认1小时
            max_concurrent_loads: 最大并发加载数
            max_retries: 最大重试次数
        """
        self._loaded_models: Dict[str, Dict[str, Any]] = {}
        self._model_locks: Dict[str, threading.RLock] = {}
        self._cache_ttl = cache_ttl
        self._max_concurrent_loads = max_concurrent_loads
        self._max_retries = max_retries
        self._load_semaphore = Semaphore(max_concurrent_loads)
        debug_print("ModelLoader", f"初始化模型加载器: cache_ttl={cache_ttl}s, max_concurrent={max_concurrent_loads}")

    # ==================== 静态加载方法 ====================

    @staticmethod
    def _load_sklearn_model(file_path: Path):
        """加载sklearn模型"""
        try:
            import joblib
            return joblib.load(file_path)
        except ImportError as e:
            raise UnsupportedFrameworkException(f"sklearn未安装: {e}")
        except Exception as e:
            raise ModelLoadException(f"加载sklearn模型失败: {e}")

    @staticmethod
    def _load_xgboost_model(file_path: Path):
        """加载xgboost模型"""
        try:
            import xgboost as xgb
            model = xgb.Booster()
            model.load_model(str(file_path))
            return model
        except ImportError as e:
            raise UnsupportedFrameworkException(f"xgboost未安装: {e}")
        except Exception as e:
            raise ModelLoadException(f"加载xgboost模型失败: {e}")

    @staticmethod
    def _load_lightgbm_model(file_path: Path):
        """加载lightgbm模型"""
        try:
            import lightgbm as lgb
            return lgb.Booster(model_file=str(file_path))
        except ImportError as e:
            raise UnsupportedFrameworkException(f"lightgbm未安装: {e}")
        except Exception as e:
            raise ModelLoadException(f"加载lightgbm模型失败: {e}")

    @staticmethod
    def _load_torch_model(file_path: Path):
        """加载pytorch模型"""
        try:
            import torch
            return torch.load(file_path, map_location='cpu')
        except ImportError as e:
            raise UnsupportedFrameworkException(f"pytorch未安装: {e}")
        except Exception as e:
            raise ModelLoadException(f"加载pytorch模型失败: {e}")

    @staticmethod
    def _load_tensorflow_model(file_path: Path):
        """加载tensorflow模型"""
        try:
            import tensorflow as tf
            return tf.keras.models.load_model(file_path)
        except ImportError as e:
            raise UnsupportedFrameworkException(f"tensorflow未安装: {e}")
        except Exception as e:
            raise ModelLoadException(f"加载tensorflow模型失败: {e}")

    @staticmethod
    def _load_onnx_model(file_path: Path):
        """加载onnx模型"""
        try:
            import onnxruntime as ort
            return ort.InferenceSession(str(file_path))
        except ImportError as e:
            raise UnsupportedFrameworkException(f"onnxruntime未安装: {e}")
        except Exception as e:
            raise ModelLoadException(f"加载onnx模型失败: {e}")

    @staticmethod
    def _load_catboost_model(file_path: Path):
        """加载catboost模型"""
        try:
            from catboost import CatBoost
            model = CatBoost()
            model.load_model(str(file_path))
            return model
        except ImportError as e:
            raise UnsupportedFrameworkException(f"catboost未安装: {e}")
        except Exception as e:
            raise ModelLoadException(f"加载catboost模型失败: {e}")

    # ==================== 私有辅助方法 ====================

    def _get_framework_loader(self, framework: str):
        """获取框架对应的加载方法"""
        loaders = {
            'sklearn': self._load_sklearn_model,
            'xgboost': self._load_xgboost_model,
            'lightgbm': self._load_lightgbm_model,
            'torch': self._load_torch_model,
            'pytorch': self._load_torch_model,
            'tensorflow': self._load_tensorflow_model,
            'onnx': self._load_onnx_model,
            'catboost': self._load_catboost_model,
        }
        loader = loaders.get(framework.lower())
        if not loader:
            raise UnsupportedFrameworkException(f"不支持的框架: {framework}")
        return loader

    def _retry_load(self, loader_func, file_path: Path, max_retries: int = 3):
        """带重试的模型加载"""
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                return loader_func(file_path)
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    debug_print("ModelLoader", f"加载失败，{wait_time}秒后重试 ({attempt}/{max_retries}): {e}")
                    time.sleep(wait_time)
        raise last_exception

    def _is_cache_expired(self, model_id: str) -> bool:
        """检查模型缓存是否过期"""
        model_info = self._loaded_models.get(model_id)
        if not model_info:
            return True
        elapsed = (datetime.now() - model_info['loaded_at']).total_seconds()
        return elapsed > self._cache_ttl

    # ==================== 公共方法 ====================

    def load_model(
            self,
            model_id: str,
            operator: str = "system",
            ip_address: str = None,
            force_reload: bool = False
    ) -> bool:
        """
        加载模型到内存

        参数:
            model_id: 模型ID
            operator: 操作人
            ip_address: IP地址
            force_reload: 是否强制重新加载

        返回:
            bool: 是否加载成功
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        lock = self.get_lock(model_id)
        with lock:
            if not force_reload and self.is_loaded(model_id) and not self._is_cache_expired(model_id):
                debug_print("ModelLoader", f"模型已加载且未过期: {model_id}")
                return True

            if self.is_loaded(model_id) and self._is_cache_expired(model_id):
                debug_print("ModelLoader", f"模型缓存已过期，重新加载: {model_id}")
                self.unload_model(model_id, operator, ip_address)

            with self._load_semaphore:
                try:
                    with get_db() as session:
                        model = session.query(ModelMetadata).filter_by(
                            model_id=model_id,
                            status='active'
                        ).first()

                        if not model:
                            raise ModelLoadException(f"模型不存在或未激活: {model_id}")

                        file_path = Path(model.file_path)
                        if not file_path.exists():
                            raise ModelLoadException(f"模型文件不存在: {file_path}")

                        loader = self._get_framework_loader(model.framework)
                        loaded_model = self._retry_load(loader, file_path, self._max_retries)

                        # 将 ORM 对象转换为字典，避免 session 问题
                        metadata_dict = {
                            'model_id': model.model_id,
                            'model_name': model.model_name,
                            'model_version': model.model_version,
                            'task_type': model.task_type,
                            'model_type': model.model_type,
                            'framework': model.framework,
                            'file_path': model.file_path,
                            'file_hash': model.file_hash,
                            'file_size': model.file_size,
                            'input_features': model.input_features,
                            'output_schema': model.output_schema,
                            'model_params': model.model_params,
                            'status': model.status,
                            'is_production': model.is_production,
                            'ab_test_group': model.ab_test_group,
                            'created_by': model.created_by,
                            'created_at': model.created_at.isoformat() if model.created_at else None,
                            'description': model.description,
                            'tags': model.tags
                        }

                        self._loaded_models[model_id] = {
                            'model': loaded_model,
                            'metadata': metadata_dict,
                            'loaded_at': datetime.now(),
                            'load_count': self._loaded_models.get(model_id, {}).get('load_count', 0) + 1,
                            'file_size_mb': round(file_path.stat().st_size / 1024 / 1024, 2)
                        }

                    duration = (datetime.now() - start_time).total_seconds() * 1000

                    log_performance(
                        operation=AuditAction.MODEL_LOAD.value,
                        duration_ms=duration,
                        extra={
                            "model_id": model_id,
                            "model_name": model.model_name,
                            "framework": model.framework,
                            "file_size_mb": self._loaded_models[model_id]['file_size_mb'],
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        }
                    )

                    log_audit(
                        action=AuditAction.MODEL_LOAD.value,
                        user_id=operator,
                        ip_address=ip_address,
                        details={
                            "model_id": model_id,
                            "model_name": model.model_name,
                            "model_version": model.model_version,
                            "framework": model.framework,
                            "duration_ms": round(duration, 2),
                            "file_size_mb": self._loaded_models[model_id]['file_size_mb'],
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )

                    debug_print("ModelLoader", f"模型加载成功: {model_id}, 耗时: {duration:.2f}ms")
                    return True

                except Exception as e:
                    duration = (datetime.now() - start_time).total_seconds() * 1000
                    log_audit(
                        action=AuditAction.MODEL_LOAD.value,
                        user_id=operator,
                        ip_address=ip_address,
                        details={
                            "model_id": model_id,
                            "error": str(e),
                            "traceback": traceback.format_exc(),
                            "duration_ms": round(duration, 2),
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        reason=str(e),
                        request_id=request_id
                    )
                    raise

    def unload_model(self, model_id: str, operator: str = "system", ip_address: str = None):
        """卸载模型"""
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        if model_id in self._loaded_models:
            lock = self.get_lock(model_id)
            with lock:
                if model_id in self._loaded_models:
                    del self._loaded_models[model_id]
                    if model_id in self._model_locks:
                        del self._model_locks[model_id]

                    log_audit(
                        action=AuditAction.MODEL_UNLOAD.value,
                        user_id=operator,
                        ip_address=ip_address,
                        details={
                            "model_id": model_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )

                    debug_print("ModelLoader", f"模型卸载成功: {model_id}")

    def get_model(self, model_id: str, refresh: bool = False) -> Optional[Any]:
        """
        获取已加载的模型

        参数:
            model_id: 模型ID
            refresh: 是否强制刷新缓存

        返回:
            模型实例，如果未加载返回None
        """
        if refresh:
            self.unload_model(model_id)
            return None

        if self._is_cache_expired(model_id):
            debug_print("ModelLoader", f"模型缓存已过期: {model_id}")
            return None

        model_info = self._loaded_models.get(model_id)
        return model_info['model'] if model_info else None

    def is_loaded(self, model_id: str) -> bool:
        """检查模型是否已加载"""
        return model_id in self._loaded_models

    def get_loaded_models(self) -> List[Dict]:
        """获取所有已加载的模型信息"""
        return [
            {
                'model_id': mid,
                'model_name': info['metadata']['model_name'],
                'model_version': info['metadata']['model_version'],
                'framework': info['metadata']['framework'],
                'loaded_at': info['loaded_at'].isoformat(),
                'load_count': info['load_count'],
                'file_size_mb': info.get('file_size_mb', 0)
            }
            for mid, info in self._loaded_models.items()
        ]

    def get_lock(self, model_id: str) -> threading.RLock:
        """获取模型的线程锁"""
        if model_id not in self._model_locks:
            self._model_locks[model_id] = threading.RLock()
        return self._model_locks[model_id]

    def warm_up_model(self, model_id: str, sample_data: Any = None) -> bool:
        """预热模型"""
        model = self.get_model(model_id)
        if not model:
            debug_print("ModelLoader", f"模型未加载，无法预热: {model_id}")
            return False

        start_time = datetime.now()
        framework = self._loaded_models[model_id]['metadata']['framework']
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            import numpy as np

            if framework in ['sklearn', 'xgboost', 'lightgbm']:
                if sample_data is None:
                    sample_data = np.random.randn(1, 10)

                if framework == 'sklearn':
                    model.predict(sample_data)
                elif framework == 'xgboost':
                    import xgboost as xgb
                    model.predict(xgb.DMatrix(sample_data))
                elif framework == 'lightgbm':
                    model.predict(sample_data)

            elif framework in ['torch', 'pytorch']:
                import torch
                if sample_data is None:
                    sample_data = torch.randn(1, 10)
                model.eval()
                with torch.no_grad():
                    model(sample_data)

            elif framework == 'tensorflow':
                if sample_data is None:
                    sample_data = np.random.randn(1, 10)
                model.predict(sample_data)

            elif framework == 'onnx':
                if sample_data is None:
                    sample_data = np.random.randn(1, 10).astype(np.float32)
                model.run(None, {'input': sample_data})

            elif framework == 'catboost':
                if sample_data is None:
                    sample_data = np.random.randn(1, 10)
                model.predict(sample_data)

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_performance(
                operation=AuditAction.MODEL_WARM_UP.value,
                duration_ms=duration,
                extra={
                    "model_id": model_id,
                    "framework": framework,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            debug_print("ModelLoader", f"模型预热成功: {model_id}, 耗时: {duration:.2f}ms")
            return True

        except Exception as e:
            debug_print("ModelLoader", f"模型预热失败: {model_id}, {e}")
            return False

    def get_memory_usage(self) -> Dict[str, Any]:
        """获取模型内存使用情况"""
        import psutil
        import os
        import pickle

        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()

        model_memory = {}
        for model_id, info in self._loaded_models.items():
            try:
                model_size = len(pickle.dumps(info['model']))
                model_memory[model_id] = {
                    'model_name': info['metadata']['model_name'],
                    'framework': info['metadata']['framework'],
                    'size_mb': round(model_size / 1024 / 1024, 2),
                    'loaded_at': info['loaded_at'].isoformat(),
                    'load_count': info['load_count']
                }
            except Exception as e:
                model_memory[model_id] = {'error': str(e)}

        return {
            'total_models': len(self._loaded_models),
            'process_memory_mb': round(memory_info.rss / 1024 / 1024, 2),
            'models': model_memory
        }

    def health_check(self) -> Dict[str, Any]:
        """模型加载器健康检查"""
        health_status = {
            'status': 'healthy',
            'loaded_models_count': len(self._loaded_models),
            'max_concurrent_loads': self._max_concurrent_loads,
            'cache_ttl': self._cache_ttl,
            'models': []
        }

        for model_id, info in self._loaded_models.items():
            try:
                model = info['model']
                if model is None:
                    health_status['status'] = 'unhealthy'
                    health_status['models'].append({
                        'model_id': model_id,
                        'status': 'model_is_none'
                    })
                else:
                    is_expired = self._is_cache_expired(model_id)
                    health_status['models'].append({
                        'model_id': model_id,
                        'model_name': info['metadata']['model_name'],
                        'status': 'expired' if is_expired else 'healthy',
                        'loaded_at': info['loaded_at'].isoformat(),
                        'load_count': info['load_count'],
                        'file_size_mb': info.get('file_size_mb', 0)
                    })
            except Exception as e:
                health_status['status'] = 'unhealthy'
                health_status['models'].append({
                    'model_id': model_id,
                    'status': 'error',
                    'error': str(e)
                })

        return health_status

    def clear_expired_cache(self) -> int:
        """清除过期的模型缓存"""
        expired_count = 0
        for model_id in list(self._loaded_models.keys()):
            if self._is_cache_expired(model_id):
                self.unload_model(model_id)
                expired_count += 1
                debug_print("ModelLoader", f"清除过期缓存: {model_id}")
        return expired_count


# 全局模型加载器实例
model_loader = ModelLoader()