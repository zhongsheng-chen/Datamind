# -*- coding: utf-8 -*-
import os
import bentoml
import threading
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from src.config_parser import config
from src.db_engine import postgres_engine
from src.setup import setup_logger

logger = setup_logger()

class CachedModel:
    """缓存模型对象及其元信息"""
    def __init__(self, model, framework: str=None, version: str=None, uuid: str=None, hash: str=None, task: str=None, path: str=None):
        self.model = model
        self.framework = framework
        self.version = version
        self.uuid = uuid
        self.hash = hash
        self.task = task
        self.path = path

class ModelLoader:
    """
    统一模型加载器
    支持：
        - 从 config.yaml 加载
        - 从数据库加载
        - 缓存模型对象，避免重复加载
    """
    _model_cache: Dict[str, CachedModel] = {}
    _lock = threading.Lock()

    @classmethod
    def _load_from_config(cls, model_name: str) -> CachedModel:
        model_info = config.get_model(model_name)
        if not model_info:
            raise ValueError(f"未找到模型配置: {model_name}")

        framework = model_info["framework"].lower()
        version = model_info.get("version", "latest")
        task = model_info.get("uuid", "")
        path = model_info.get("hash", "")
        uuid_val = model_info.get("uuid", "")
        hash_val = model_info.get("hash", "")

        tag = f"{model_info['model_name']}:{version}"

        framework_loaders = {
            "sklearn": lambda t: bentoml.sklearn.load_model(t),
            "lightgbm": lambda t: bentoml.lightgbm.load_model(t),
            "xgboost": lambda t: bentoml.xgboost.load_model(t),
            "catboost": lambda t: bentoml.catboost.load_model(t),
        }

        loader = framework_loaders.get(framework)
        if not loader:
            raise ValueError(f"不支持的模型框架: {framework}")

        model = loader(tag)
        return CachedModel(model, version, uuid_val, hash_val)

    @classmethod
    def _load_from_db(cls, model_name: str) -> CachedModel:
        sql = "SELECT model_path, framework, version, uuid, hash, tag FROM registry WHERE model_name=:model_name AND status='active'"
        with postgres_engine.begin() as conn:
            result = conn.execute(sql, {"model_name": model_name}).fetchone()
            if not result:
                raise ValueError(f"数据库中未找到 active 模型: {model_name}")

            framework = result["framework"].lower()
            version = result["version"]
            uuid_val = result["uuid"]
            model_hash = result["hash"]
            tag = result["tag"]

            framework_loaders = {
                "sklearn": lambda t: bentoml.sklearn.load_model(t),
                "lightgbm": lambda t: bentoml.lightgbm.load_model(t),
                "xgboost": lambda t: bentoml.xgboost.load_model(t),
                "catboost": lambda t: bentoml.catboost.load_model(t),
            }

            loader = framework_loaders.get(framework)
            if not loader:
                raise ValueError(f"不支持的模型框架: {framework}")

            model_obj = loader(tag)
            return CachedModel(model_obj, version, uuid_val, model_hash)

    @classmethod
    def load_model(cls, model_name: str, source: str = "config") -> CachedModel:
        """
        加载模型并缓存
        source: "config" 或 "db"
        """
        with cls._lock:
            if model_name in cls._model_cache:
                return cls._model_cache[model_name]

            if source == "config":
                cached_model = cls._load_from_config(model_name)
            elif source == "db":
                cached_model = cls._load_from_db(model_name)
            else:
                raise ValueError(f"未知 source: {source}")

            cls._model_cache[model_name] = cached_model
            logger.info(f"已加载模型: {model_name} (version={cached_model.version}, uuid={cached_model.uuid}, hash={cached_model.hash})")
            return cached_model

    @classmethod
    def get_model(cls, model_name: str) -> Optional[CachedModel]:
        return cls._model_cache.get(model_name)

    @classmethod
    def reload_model(cls, model_name: str, source: str = "config") -> CachedModel:
        with cls._lock:
            if model_name in cls._model_cache:
                del cls._model_cache[model_name]
            return cls.load_model(model_name, source=source)

    @classmethod
    def load_all_models(cls, source: str = "config"):
        model_list = config.list_models() if source == "config" else cls._list_models_from_db()
        for m in model_list:
            try:
                cls.load_model(m, source=source)
            except Exception as e:
                logger.exception(f"加载模型 {m} 失败: {e}")
        logger.info(f"已加载所有模型: {list(cls._model_cache.keys())}")

    @classmethod
    def _list_models_from_db(cls):
        sql = "SELECT model_name FROM models WHERE status='active'"
        with postgres_engine.begin() as conn:
            result = conn.execute(sql).fetchall()
            return [row["model_name"] for row in result]
