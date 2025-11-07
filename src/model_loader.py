# -*- coding: utf-8 -*-
import os
import time
import bentoml
import threading
from typing import Dict
from pathlib import Path
from src.config_parser import config
from src.setup import setup_logger

try:
    import torch
except ImportError:
    torch = None

try:
    import onnx
except ImportError:
    onnx = None

try:
    import tensorflow as tf
    from tensorflow import keras
except ImportError:
    tf = None
    keras = None

logger = setup_logger()

class CachedModel:
    """缓存模型及其元信息"""
    def __init__(self, model, version: str, uuid: str, hash: str):
        self.model = model
        self.version = version
        self.uuid = uuid
        self.hash = hash


class ModelLoader:
    """
    模型加载器负责：
      - 按模型名读取配置
      - 按框架加载模型
      - 模型对象缓存（避免重复加载）
      - 支持热更新功能
    """
    _model_cache: Dict[str, CachedModel] = {}
    _lock = threading.Lock()

    @classmethod
    def _get_model_info(cls, model_name: str) -> dict:
        model_info = config.get_model(model_name)
        if not model_info:
            raise ValueError(f"未找到模型配置: {model_name}")

        model_path = Path(model_info.get("model_path", ""))
        project_root = Path(__file__).resolve().parent.parent

        if not model_path.is_absolute():
            model_path = (project_root / model_path).resolve()

        model_info["model_path"] = model_path.as_posix()
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"模型 {model_name} 配置已读取: {model_info}")
        return model_info

    @classmethod
    def _load_model(cls, model_name: str) -> CachedModel:
        """根据模型名称加载模型，返回 CachedModel"""
        model_info = cls._get_model_info(model_name)
        framework = model_info["framework"].lower()
        version = model_info.get("version", "latest")
        uuid = model_info.get("uuid", "")
        hash = model_info.get("hash", "")
        tag = f"{model_info['model_name']}:{version}"

        logger.info(f"[加载中] 模型 {model_name}(framework={framework}, tag={tag}, uuid={uuid})")

        framework_loaders = {
            "sklearn": lambda t: bentoml.sklearn.load_model(t),
            "lightgbm": lambda t: bentoml.lightgbm.load_model(t),
            "xgboost": lambda t: bentoml.xgboost.load_model(t),
            "catboost": lambda t: bentoml.catboost.load_model(t),
        }

        if onnx:
            framework_loaders["onnx"] = lambda t: bentoml.onnx.load_model(t)
        if torch:
            framework_loaders["pytorch"] = lambda t: bentoml.pytorch.load_model(t)
        if tf and keras:
            framework_loaders["tensorflow"] = lambda t: bentoml.tensorflow.load_model(t)

        loader = framework_loaders.get(framework)
        if not loader:
            raise ValueError(f"不支持的模型框架: {framework}")

        start_time = time.time()
        try:
            model = loader(tag)
            elapsed = time.time() - start_time
            logger.info(f"[成功] 模型 {model_name} 加载完成，耗时 {elapsed:.2f} 秒")
            return CachedModel(model, version, uuid, hash)

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[失败] 模型 {model_name} 加载失败，耗时 {elapsed:.2f} 秒，错误: {e}")
            raise RuntimeError(f"加载模型失败: {model_name}") from e

    @classmethod
    def load_model(cls, model_name: str) -> CachedModel:
        """返回 CachedModel"""
        with cls._lock:
            if model_name not in cls._model_cache:
                logger.info(f"[缓存未命中] 模型 {model_name}，正在加载...")
                cls._model_cache[model_name] = cls._load_model(model_name)
            else:
                logger.info(f"[缓存命中] 使用已缓存的模型: {model_name}")
        return cls._model_cache[model_name]

    @classmethod
    def reload_model(cls, model_name: str) -> CachedModel:
        """
        热加载模型
        """
        with cls._lock:
            start_time = time.time()
            if model_name in cls._model_cache:
                logger.warning(f"重新加载模型 {model_name}")
                del cls._model_cache[model_name]

            try:
                cls._model_cache[model_name] = cls._load_model(model_name)
                elapsed = time.time() - start_time
                logger.info(f"模型 {model_name} 已成功重新加载, 耗时 {elapsed:.2f} 秒")
            except Exception as e:
                elapsed = time.time() - start_time
                logger.error(f"[失败] 模型 {model_name} 热加载失败, 耗时 {elapsed:.2f} 秒, 错误: {e}")
                raise RuntimeError(f"模型 {model_name} 热加载失败") from e
        return cls._model_cache[model_name]

    @classmethod
    def load_all_models(cls):
        """批量加载所有模型"""
        model_list = config.list_models()
        start_time = time.time()
        success_models, failed_models = [], []

        logger.info(f"[全量加载] 开始加载 {len(model_list)} 个模型...")

        for m in model_list:
            try:
                cls.load_model(m)
                success_models.append(m)
            except Exception:
                failed_models.append(m)

        elapsed = time.time() - start_time
        logger.info(f"[全量加载] 成功 {len(success_models)} 个，失败 {len(failed_models)} 个，总耗时 {elapsed:.2f} 秒")
        if failed_models:
            logger.warning(f"[加载失败] 以下模型加载失败: {failed_models}")

    @classmethod
    def get_model(cls, model_name: str):
        """返回模型对象"""
        cached_model = cls._model_cache.get(model_name)
        return cached_model.model if cached_model else None


if __name__ == "__main__":
    model_name = "demo_loan_scorecard_xgb_20250930"
    try:
        logger.info("开始加载所有模型...")
        ModelLoader.load_all_models()
    except Exception as e:
        logger.error(f"加载所有模型失败: {e}")

    try:
        logger.info(f"开始热加载模型 {model_name} ...")
        ModelLoader.reload_model(model_name)
    except Exception as e:
        logger.error(f"热加载模型失败: {e}")
