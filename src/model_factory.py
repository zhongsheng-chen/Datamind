# src/model_registry.py
# -*- coding: utf-8 -*-

import bentoml
import threading
from typing import Dict
from pathlib import Path
from src.config_parser import config
from src.setup import setup_logger

logger = setup_logger()

class ModelFactory:
    """
    ModelFactory 负责：
      - 按模型名读取配置
      - 按框架加载模型
      - 模型对象缓存（避免重复加载）
      - 支持热更新功能
    """

    _model_cache: Dict[str, object] = {}
    _lock = threading.Lock()

    @classmethod
    def _get_model_info(cls, model_name: str) -> dict:
        """
        根据模型名称，读取模型配置信息，并返回完整路径。
        """
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
    def _load_model(cls, model_name: str) -> object:
        """
        根据模型名称，加载模型。
        """
        model_info = cls._get_model_info(model_name)

        framework = model_info["framework"].lower()
        version = model_info.get("version", "latest")
        uuid = model_info.get("uuid", "")

        tag = f"{model_info['model_name']}:{version}"

        logger.info(f"正在加载模型: {model_name} (framework={framework}, tag={tag}, uuid={uuid})")

        try:
            if framework == "sklearn":
                return bentoml.sklearn.load_model(tag)
            elif framework == "lightgbm":
                return bentoml.lightgbm.load_model(tag)
            elif framework == "xgboost":
                return bentoml.xgboost.load_model(tag)
            elif framework == "catboost":
                return bentoml.catboost.load_model(tag)
            else:
                raise ValueError(f"不支持的模型框架: {framework}")
        except Exception as e:
            logger.error(f"加载模型 {model_name} 失败: {e}")
            raise RuntimeError(f"模型加载失败: {model_name}")

    @classmethod
    def load_model(cls, model_name: str) -> object:
        """
        获取模型。如果模型不在缓存中，则加载并缓存。
        """
        if model_name not in cls._model_cache:
            logger.info(f"缓存中没有模型 {model_name}，正在加载...")
            cls._model_cache[model_name] = cls._load_model(model_name)
        else:
            logger.info(f"使用缓存中的模型: {model_name}")
        return cls._model_cache[model_name]

    @classmethod
    def reload_model(cls, name: str):
        """
        🔥 热更新：当线上配置文件更新模型版本时调用
        示例：运维发布新模型后执行 /reload
        """
        with cls._lock:
            if name in cls._model_cache:
                logger.warning(f"[模型热更新] 正在重新加载模型: {name}")
                del cls._model_cache[name]  # 删除旧的模型缓存

            try:
                cls._model_cache[name] = cls._load_model(name)
                logger.info(f"[模型热更新] 模型 {name} 已成功重新加载")
            except Exception as e:
                logger.error(f"[模型热更新] 加载模型 {name} 失败: {e}")
                raise RuntimeError(f"热更新模型失败: {name}")
        return cls._model_cache[name]

    @classmethod
    def load_all_models(cls):
        """
        启动时加载全部模型。
        """
        model_list = config.list_models()
        for m in model_list:
            try:
                cls.load_model(m)
            except Exception as e:
                logger.error(f"加载模型 {m} 失败: {e}")
        logger.info(f"已加载模型: {list(cls._model_cache.keys())}")

# 如果需要本地调试，可以通过运行该模块来加载所有模型
if __name__ == "__main__":
    try:
        logger.info("开始加载所有模型...")
        ModelFactory.load_all_models()
    except Exception as e:
        logger.error(f"加载所有模型失败: {e}")

    try:
        logger.info("开始热加载模型 demo_loan_scorecard_xgb_20250930...")
        ModelFactory.reload_model("demo_loan_scorecard_xgb_20250930")
    except Exception as e:
        logger.error(f"热加载模型失败: {e}")
