# datamind/core/model/loader.py

"""模型加载器

负责模型的动态加载和卸载，支持多种机器学习框架。

核心功能：
  - load_model: 从 BentoML Model Store 加载模型到内存
  - unload_model: 从内存卸载模型
  - get_model: 获取已加载的模型实例
  - is_loaded: 检查模型是否已加载
  - get_loaded_models: 获取所有已加载模型信息

特性：
  - 并发安全：使用线程锁防止重复加载
  - 多框架支持：sklearn、xgboost、lightgbm、torch、tensorflow、onnx、catboost
  - 懒加载：按需加载，避免内存浪费
  - 错误处理：详细的异常信息和错误追踪
  - 缓存管理：支持缓存过期和内存监控
  - 审计日志：记录所有加载/卸载操作
  - 链路追踪：完整的 span 追踪
"""

import threading
import time
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List

import bentoml
from bentoml.exceptions import BentoMLException

from datamind.core.db.database import get_db
from datamind.core.db.models import ModelMetadata
from datamind.core.domain.enums import AuditAction, ModelStatus
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging import get_logger
from datamind.core.common.exceptions import (
    ModelLoadException,
    ModelNotFoundException,
    UnsupportedFrameworkException
)
from datamind.core.common.frameworks import (
    is_framework_supported,
    get_supported_frameworks
)

logger = get_logger(__name__)


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
        logger.debug("初始化模型加载器: cache_ttl=%d秒", cache_ttl)

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
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        lock = self.get_lock(model_id)
        with lock:
            if not force_reload and self.is_loaded(model_id):
                if not self._is_cache_expired(model_id):
                    logger.debug("模型已加载: %s", model_id)
                    return True

            if self.is_loaded(model_id) and self._is_cache_expired(model_id):
                logger.debug("模型缓存已过期，重新加载: %s", model_id)
                self.unload_model(model_id, operator, ip_address)

            try:
                # 在 session 内提取所有需要的属性，避免 detached 对象问题
                with get_db() as session:
                    model_metadata = session.query(ModelMetadata).filter_by(
                        model_id=model_id,
                        status=ModelStatus.ACTIVE.value
                    ).first()

                    if not model_metadata:
                        raise ModelNotFoundException(f"模型不存在或未激活: {model_id}")

                    if not is_framework_supported(model_metadata.framework):
                        raise UnsupportedFrameworkException(
                            f"不支持的框架: {model_metadata.framework}. "
                            f"支持的框架: {get_supported_frameworks()}"
                        )

                    # 提取所有需要的属性到本地变量
                    framework = model_metadata.framework
                    model_name = model_metadata.model_name
                    model_version = model_metadata.model_version
                    task_type = model_metadata.task_type
                    model_type = model_metadata.model_type
                    file_path = model_metadata.file_path
                    file_hash = model_metadata.file_hash
                    file_size = model_metadata.file_size
                    input_features = model_metadata.input_features
                    output_schema = model_metadata.output_schema
                    model_params = model_metadata.model_params
                    status = model_metadata.status
                    is_production = model_metadata.is_production
                    ab_test_group = model_metadata.ab_test_group
                    created_by = model_metadata.created_by
                    created_at = model_metadata.created_at.isoformat() if model_metadata.created_at else None
                    description = model_metadata.description
                    tags = model_metadata.tags

                # 从 BentoML 加载模型（使用 framework 和 file_path，不再传递 detached 对象）
                model = self._load_from_bentoml(model_id, framework, file_path)

                if not model:
                    raise ModelLoadException(f"从 BentoML 加载模型失败: {model_id}")

                metadata_dict = {
                    'model_id': model_id,
                    'model_name': model_name,
                    'model_version': model_version,
                    'task_type': task_type,
                    'model_type': model_type,
                    'framework': framework,
                    'file_path': file_path,
                    'file_hash': file_hash,
                    'file_size': file_size,
                    'input_features': input_features,
                    'output_schema': output_schema,
                    'model_params': model_params,
                    'status': status,
                    'is_production': is_production,
                    'ab_test_group': ab_test_group,
                    'created_by': created_by,
                    'created_at': created_at,
                    'description': description,
                    'tags': tags
                }

                self._loaded_models[model_id] = {
                    'model': model,
                    'metadata': metadata_dict,
                    'loaded_at': datetime.now(),
                    'load_count': self._loaded_models.get(model_id, {}).get('load_count', 0) + 1,
                }

                duration = (datetime.now() - start_time).total_seconds() * 1000

                log_performance(
                    operation=AuditAction.MODEL_LOAD.value,
                    duration_ms=duration,
                    extra={
                        "model_id": model_id,
                        "model_name": model_name,
                        "framework": framework,
                        "request_id": request_id,
                        "trace_id": trace_id,
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
                        "model_name": model_name,
                        "model_version": model_version,
                        "framework": framework,
                        "duration_ms": round(duration, 2),
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                logger.debug("模型加载成功: %s, 耗时: %.2f毫秒", model_id, duration)
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
                        "request_id": request_id,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    reason=str(e),
                    request_id=request_id
                )
                raise ModelLoadException(f"模型加载失败: {model_id}, {str(e)}")

    def _load_from_bentoml(self, model_id: str, framework: str, file_path: str = None) -> Optional[Any]:
        """
        从 BentoML Model Store 加载模型

        参数:
            model_id: 模型ID
            framework: 模型框架
            file_path: 模型文件路径（用于调试）

        返回:
            加载的模型实例
        """
        framework_lower = framework.lower()

        for attempt in range(1, self._max_retries + 1):
            try:
                bento_model = bentoml.models.get(model_id)

                if not bento_model:
                    logger.debug("BentoML 模型不存在: %s", model_id)
                    return None

                if framework_lower == 'sklearn':
                    model = bentoml.sklearn.load_model(bento_model.tag)
                elif framework_lower == 'xgboost':
                    model = bentoml.xgboost.load_model(bento_model.tag)
                elif framework_lower == 'lightgbm':
                    model = bentoml.lightgbm.load_model(bento_model.tag)
                elif framework_lower == 'catboost':
                    model = bentoml.catboost.load_model(bento_model.tag)
                elif framework_lower in ['torch', 'pytorch']:
                    model = bentoml.pytorch.load_model(bento_model.tag)
                elif framework_lower == 'tensorflow':
                    model = bentoml.tensorflow.load_model(bento_model.tag)
                elif framework_lower == 'onnx':
                    model = bentoml.onnx.load_model(bento_model.tag)
                else:
                    model = bentoml.pickle.load_model(bento_model.tag)

                logger.debug("从 BentoML 加载模型成功: %s", bento_model.tag)
                return model

            except BentoMLException as e:
                if attempt < self._max_retries:
                    wait_time = 2 ** attempt
                    logger.debug("加载失败，%d秒后重试 (%d/%d): %s", wait_time, attempt, self._max_retries, e)
                    time.sleep(wait_time)
                else:
                    raise ModelLoadException(f"从 BentoML 加载模型失败: {model_id}, {str(e)}")
            except Exception as e:
                raise ModelLoadException(f"从 BentoML 加载模型失败: {model_id}, {str(e)}")

        return None

    def unload_model(self, model_id: str, operator: str = "system", ip_address: str = None):
        """
        卸载模型

        参数:
            model_id: 模型ID
            operator: 操作人
            ip_address: IP地址
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
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
                            "request_id": request_id,
                            "trace_id": trace_id,
                            "span_id": span_id,
                            "parent_span_id": parent_span_id
                        },
                        request_id=request_id
                    )

                    logger.debug("模型卸载成功: %s", model_id)

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
            logger.debug("模型缓存已过期: %s", model_id)
            return None

        model_info = self._loaded_models.get(model_id)
        return model_info['model'] if model_info else None

    def get_model_metadata(self, model_id: str) -> Optional[Dict]:
        """
        获取已加载模型的元数据

        参数:
            model_id: 模型ID

        返回:
            模型元数据字典，如果未加载返回None
        """
        model_info = self._loaded_models.get(model_id)
        return model_info.get('metadata') if model_info else None

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """
        获取已加载模型的完整信息

        参数:
            model_id: 模型ID

        返回:
            模型完整信息字典，如果未加载返回None
        """
        model_info = self._loaded_models.get(model_id)
        if not model_info:
            return None

        return {
            'model': model_info['model'],
            'metadata': model_info['metadata'],
            'loaded_at': model_info['loaded_at'],
            'load_count': model_info['load_count'],
        }

    def get_model_instance(self, model_id: str) -> Optional[Any]:
        """
        获取已加载的模型实例

        参数:
            model_id: 模型ID

        返回:
            模型实例，如果未加载返回None
        """
        model_info = self._loaded_models.get(model_id)
        return model_info['model'] if model_info else None

    def get_model_load_count(self, model_id: str) -> int:
        """
        获取模型加载次数

        参数:
            model_id: 模型ID

        返回:
            加载次数，如果未加载返回0
        """
        model_info = self._loaded_models.get(model_id)
        return model_info.get('load_count', 0) if model_info else 0

    def get_loaded_model_ids(self) -> List[str]:
        """
        获取所有已加载的模型ID列表

        返回:
            模型ID列表
        """
        return list(self._loaded_models.keys())

    def is_loaded(self, model_id: str) -> bool:
        """
        检查模型是否已加载

        参数:
            model_id: 模型ID

        返回:
            是否已加载
        """
        return model_id in self._loaded_models

    def get_loaded_models(self) -> List[Dict]:
        """
        获取所有已加载的模型信息

        返回:
            已加载模型信息列表
        """
        return [
            {
                'model_id': mid,
                'model_name': info['metadata']['model_name'],
                'model_version': info['metadata']['model_version'],
                'framework': info['metadata']['framework'],
                'loaded_at': info['loaded_at'].isoformat(),
                'load_count': info['load_count'],
            }
            for mid, info in self._loaded_models.items()
        ]

    def get_lock(self, model_id: str) -> threading.RLock:
        """
        获取模型的线程锁

        参数:
            model_id: 模型ID

        返回:
            线程锁对象
        """
        if model_id not in self._model_locks:
            self._model_locks[model_id] = threading.RLock()
        return self._model_locks[model_id]

    def warm_up_model(self, model_id: str, sample_data: Any = None) -> bool:
        """
        预热模型

        参数:
            model_id: 模型ID
            sample_data: 样本数据

        返回:
            是否预热成功
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        model = self.get_model(model_id)
        if not model:
            logger.debug("模型未加载，无法预热: %s", model_id)
            return False

        start_time = datetime.now()
        framework = self._loaded_models[model_id]['metadata']['framework']

        try:
            import numpy as np

            if framework in ['sklearn', 'xgboost', 'lightgbm', 'catboost']:
                if sample_data is None:
                    sample_data = np.random.randn(1, 10)

                if framework == 'sklearn':
                    model.predict(sample_data)
                elif framework == 'xgboost':
                    import xgboost as xgb
                    model.predict(xgb.DMatrix(sample_data))
                elif framework in ['lightgbm', 'catboost']:
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

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_performance(
                operation=AuditAction.MODEL_WARM_UP.value,
                duration_ms=duration,
                extra={
                    "model_id": model_id,
                    "framework": framework,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            logger.debug("模型预热成功: %s, 耗时: %.2f毫秒", model_id, duration)
            return True

        except Exception as e:
            logger.debug("模型预热失败: %s, %s", model_id, e)
            return False

    def _is_cache_expired(self, model_id: str) -> bool:
        """
        检查模型缓存是否过期

        参数:
            model_id: 模型ID

        返回:
            是否过期
        """
        model_info = self._loaded_models.get(model_id)
        if not model_info:
            return True
        elapsed = (datetime.now() - model_info['loaded_at']).total_seconds()
        return elapsed > self._cache_ttl

    def clear_expired_cache(self) -> int:
        """
        清除过期的模型缓存

        返回:
            清除的模型数量
        """
        expired_count = 0
        for model_id in list(self._loaded_models.keys()):
            if self._is_cache_expired(model_id):
                self.unload_model(model_id)
                expired_count += 1
                logger.debug("清除过期缓存: %s", model_id)
        return expired_count

    def health_check(self) -> Dict[str, Any]:
        """
        模型加载器健康检查

        返回:
            健康检查结果
        """
        health_status = {
            'status': 'healthy',
            'loaded_models_count': len(self._loaded_models),
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
                    })
            except Exception as e:
                health_status['status'] = 'unhealthy'
                health_status['models'].append({
                    'model_id': model_id,
                    'status': 'error',
                    'error': str(e)
                })

        return health_status


# ==================== 工厂函数 ====================

def get_model_loader():
    """
    获取模型加载器实例

    返回:
        ModelLoader 实例
    """
    return ModelLoader()