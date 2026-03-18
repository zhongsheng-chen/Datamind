# datamind/core/ml/model_loader.py
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

from datamind.core.db.database import get_db
from datamind.core.db.models import ModelMetadata
from datamind.core.logging import log_manager, get_request_id, debug_print
from datamind.core.ml.exceptions import ModelLoadException, UnsupportedFrameworkException


class ModelLoader:
    """模型加载器 - 动态加载和卸载模型"""

    def __init__(self):
        self._loaded_models: Dict[str, Dict[str, Any]] = {}
        self._model_locks: Dict[str, threading.RLock] = {}
        debug_print("ModelLoader", "初始化模型加载器")

    def load_model(self, model_id: str, operator: str = "system", ip_address: str = None) -> bool:
        """
        加载模型到内存

        Args:
            model_id: 模型ID
            operator: 操作人
            ip_address: IP地址

        Returns:
            bool: 是否加载成功
        """
        request_id = get_request_id()
        start_time = datetime.now()

        try:
            # 从数据库获取模型信息
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

                # 根据框架加载模型
                framework = model.framework
                if framework == 'sklearn':
                    loaded_model = self._load_sklearn_model(file_path)
                elif framework == 'xgboost':
                    loaded_model = self._load_xgboost_model(file_path)
                elif framework == 'lightgbm':
                    loaded_model = self._load_lightgbm_model(file_path)
                elif framework == 'torch':
                    loaded_model = self._load_torch_model(file_path)
                elif framework == 'tensorflow':
                    loaded_model = self._load_tensorflow_model(file_path)
                elif framework == 'onnx':
                    loaded_model = self._load_onnx_model(file_path)
                elif framework == 'catboost':
                    loaded_model = self._load_catboost_model(file_path)
                else:
                    raise UnsupportedFrameworkException(framework)

                # 存储模型
                self._loaded_models[model_id] = {
                    'model': loaded_model,
                    'metadata': model,
                    'loaded_at': datetime.now(),
                    'load_count': self._loaded_models.get(model_id, {}).get('load_count', 0) + 1
                }

            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_manager.log_audit(
                action="MODEL_LOAD",
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "model_name": model.model_name,
                    "model_version": model.model_version,
                    "framework": model.framework,
                    "duration_ms": round(duration, 2)
                },
                request_id=request_id
            )

            debug_print("ModelLoader", f"模型加载成功: {model_id}")
            return True

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_manager.log_audit(
                action="MODEL_LOAD",
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "duration_ms": round(duration, 2)
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    def _load_sklearn_model(self, file_path: Path):
        """加载sklearn模型"""
        import joblib
        return joblib.load(file_path)

    def _load_xgboost_model(self, file_path: Path):
        """加载xgboost模型"""
        import xgboost as xgb
        model = xgb.Booster()
        model.load_model(str(file_path))
        return model

    def _load_lightgbm_model(self, file_path: Path):
        """加载lightgbm模型"""
        import lightgbm as lgb
        return lgb.Booster(model_file=str(file_path))

    def _load_torch_model(self, file_path: Path):
        """加载pytorch模型"""
        import torch
        return torch.load(file_path)

    def _load_tensorflow_model(self, file_path: Path):
        """加载tensorflow模型"""
        import tensorflow as tf
        return tf.keras.models.load_model(file_path)

    def _load_onnx_model(self, file_path: Path):
        """加载onnx模型"""
        import onnxruntime as ort
        return ort.InferenceSession(str(file_path))

    def _load_catboost_model(self, file_path: Path):
        """加载catboost模型"""
        from catboost import CatBoost
        model = CatBoost()
        model.load_model(str(file_path))
        return model

    def unload_model(self, model_id: str, operator: str = "system", ip_address: str = None):
        """卸载模型"""
        if model_id in self._loaded_models:
            del self._loaded_models[model_id]

            log_manager.log_audit(
                action="MODEL_UNLOAD",
                user_id=operator,
                ip_address=ip_address,
                details={"model_id": model_id},
                request_id=get_request_id()
            )

            debug_print("ModelLoader", f"模型卸载成功: {model_id}")

    def get_model(self, model_id: str) -> Optional[Any]:
        """获取已加载的模型"""
        model_info = self._loaded_models.get(model_id)
        if model_info:
            return model_info['model']
        return None

    def is_loaded(self, model_id: str) -> bool:
        """检查模型是否已加载"""
        return model_id in self._loaded_models

    def get_loaded_models(self) -> List[Dict]:
        """获取所有已加载的模型信息"""
        return [
            {
                'model_id': mid,
                'model_name': info['metadata'].model_name,
                'model_version': info['metadata'].model_version,
                'loaded_at': info['loaded_at'].isoformat(),
                'load_count': info['load_count']
            }
            for mid, info in self._loaded_models.items()
        ]


# 全局模型加载器实例
model_loader = ModelLoader()