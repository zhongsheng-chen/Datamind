#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
register_model.py

将模型文件注册为模型服务. 仅会注册 config/config.yaml model_registry 单元列出的所有模型文件
使用 --force 选项强制注册模型，会将状态为 'deactive' 的模型更新为 'active'
用法:
  注册所有模型
  python register_model.py --all

  注册指定模型
  python register_model.py --model_name demo_loan_scorecard_lr_20250930 \
                           --model_type logistic_regression \
                           --model_path models/demo_loan_scorecard_lr_20250930.pkl \
                           --framework sklearn \
                           --business_name demo_loan
  强制注册指定模型
  python register_model.py --model_name demo_loan_scorecard_lr_20250930 \
                           --model_type logistic_regression \
                           --model_path models/demo_loan_scorecard_lr_20250930.pkl \
                           --framework sklearn \
                           --business_name demo_loan \
                           --force

"""

import os
import uuid
import joblib
import pickle
import bentoml
import argparse
import pytz
import yaml
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from src.config_parser import config
from src.db_engine import postgres_engine
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
    import xgboost as xgb
except ImportError:
    xgb = None

try:
    import lightgbm as lgb
except ImportError:
    lgb = None

try:
    import catboost as cb
except ImportError:
    cb = None

try:
    import tensorflow as tf
    from tensorflow import keras
except ImportError:
    tf = None
    keras = None

# === 初始化 ===
logger = setup_logger()
EXTENSION_MAP = {
    "sklearn": [".pkl", ".joblib"],
    "xgboost": [".json", ".ubj", ".bin", ".pkl"],
    "lightgbm": [".txt", ".lgb", ".pkl"],
    "torch": [".pt", ".pth", ".pkl"],
    "tensorflow": [".h5", ".keras", ".pb"],
    "onnx": [".onnx"],
    "catboost": [".cbm"],
}

Session = sessionmaker(bind=postgres_engine)
session = Session()
beijing_tz = pytz.timezone("Asia/Shanghai")


def update_config_yaml(model_name, version, uuid_str):
    """更新 config.yaml 中指定模型的 version 和 uuid"""
    updated = False
    for category, models in config.get("models", {}).items():
        for m in models:
            if m["model_name"] == model_name:
                m["version"] = version
                m["uuid"] = uuid_str
                updated = True
                break
        if updated:
            break

    if updated:
        with open(config.cfg_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True)
        logger.info(f"[CONFIG] config.yaml 已更新：{model_name} 的 version 和 uuid")


class ModelRegistry:
    """模型注册类"""

    def __init__(self, business_name, model_name, model_type, model_path, framework, force=False):
        self.business_name = business_name
        self.model_name = model_name
        self.model_type = model_type
        self.model_path = model_path
        self.framework = framework
        self.force = force

    @staticmethod
    def detect_framework(model_path):
        ext = os.path.splitext(model_path)[-1].lower()
        for f, exts in EXTENSION_MAP.items():
            if ext in exts:
                return f
        raise ValueError(f"无法识别文件扩展名 {ext} 对应的框架，请手动指定 framework")

    def create_hash(self):
        import hashlib
        sha256 = hashlib.sha256()
        with open(self.model_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def check_exists(hash):
        query = text("SELECT 1 FROM model_registry WHERE hash = :hash AND status = 'active'")
        result = session.execute(query, {"hash": hash}).fetchone()
        session.close()
        return result is not None

    def create_identifier(self, hash, tag):
        model_str = f"{self.model_name}_{self.model_type}_{self.framework}_{hash}_{tag}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, model_str))

    @staticmethod
    def write_model_registry_history(conn, model_id, model_name, model_type, model_path,
                                    version, framework, hash, tag, uuid_str, status, change_type, remarks=None):
        """写入 model_registry_history"""
        conn.execute(text("""
            INSERT INTO model_registry_history
            (model_id, model_name, model_type, model_path, version, framework, hash, tag, uuid, status, change_type, changed_by, remarks)
            VALUES
            (:model_id, :model_name, :model_type, :model_path, :version, :framework, :hash, :tag, :uuid, :status, :change_type, current_user, :remarks)
        """), {
            "model_id": model_id,
            "model_name": model_name,
            "model_type": model_type,
            "model_path": model_path,
            "version": version,
            "framework": framework,
            "hash": hash,
            "tag": tag,
            "uuid": uuid_str,
            "status": status,
            "change_type": change_type,
            "remarks": remarks
        })

    def write_model_registry(self, version, hash, tag, uuid_str):
        now = datetime.now(beijing_tz)
        with postgres_engine.connect() as conn:
            try:
                existing = conn.execute(
                    text("SELECT * FROM model_registry WHERE hash = :hash"),
                    {"hash": hash}
                ).fetchone()

                if existing and not self.force:
                    logger.info(f"[跳过] 模型 {self.model_name} 已存在，使用 --force 可覆盖。")
                    return

                if existing and self.force:
                    conn.execute(text("""
                        UPDATE model_registry
                        SET model_name=:model_name,
                            model_type=:model_type,
                            model_path=:model_path,
                            status=:status,
                            version=:version,
                            framework=:framework,
                            tag=:tag,
                            uuid=:uuid,
                            registered_at=:registered_at
                        WHERE hash = :hash
                    """), {
                        "model_name": self.model_name,
                        "model_type": self.model_type,
                        "model_path": self.model_path,
                        "status": "active",
                        "version": version,
                        "framework": self.framework,
                        "tag": tag,
                        "uuid": uuid_str,
                        "hash": hash,
                        "registered_at": now
                    })
                    logger.info(f"[更新] 模型 {self.model_name} 的注册信息已更新。")
                    model_id = existing["id"]
                    ModelRegistry.write_model_registry_history(
                        conn, model_id, self.model_name, self.model_type, self.model_path,
                        version, self.framework, hash, tag, uuid_str, "active", "update", "force update"
                    )
                else:
                    result = conn.execute(text("""
                        INSERT INTO model_registry
                        (model_name, model_type, model_path, version, framework, hash, tag, uuid, status, registered_at)
                        VALUES (:model_name, :model_type, :model_path, :version, :framework, :hash, :tag, :uuid, :status, :registered_at)
                        RETURNING id
                    """), {
                        "model_name": self.model_name,
                        "model_type": self.model_type,
                        "model_path": self.model_path,
                        "version": version,
                        "framework": self.framework,
                        "hash": hash,
                        "tag": tag,
                        "uuid": uuid_str,
                        "status": "active",
                        "registered_at": now
                    })
                    model_id = result.fetchone()[0]
                    logger.info(f"[新增] 模型 {self.model_name} 已注册成功。")
                    ModelRegistry.write_model_registry_history(
                        conn, model_id, self.model_name, self.model_type, self.model_path,
                        version, self.framework, hash, tag, uuid_str, "active", "new_version"
                    )

                # 更新 config.yaml
                update_config_yaml(self.model_name, version, uuid_str)

            except IntegrityError as e:
                logger.error(f"数据库插入失败: {e}")
            except Exception as e:
                logger.error(f"注册写入失败: {e}")

    def register_model(self):
        signatures = {"predict": {"batchable": False}, "predict_proba": {"batchable": False}}
        hash = self.create_hash()

        if not self.force and self.check_exists(hash):
            logger.info(f"[跳过] 模型已注册: {self.model_name} ({self.model_path})")
            return

        try:
            ext = os.path.splitext(self.model_path)[1].lower()
            if self.framework == "sklearn":
                if ext == ".joblib":
                    model = joblib.load(self.model_path)
                elif ext in [".pkl", ".pickle"]:
                    with open(self.model_path, "rb") as f:
                        model = pickle.load(f)
                else:
                    raise ValueError(f"不支持的 scikit-learn 模型文件格式: {ext}")
                artifact = bentoml.sklearn.save_model(self.model_name, model, signatures=signatures)
            elif self.framework == "torch" and torch:
                model = torch.load(self.model_path, map_location="cpu")
                artifact = bentoml.pytorch.save_model(self.model_name, model, signatures=signatures)
            elif self.framework == "onnx" and onnx:
                model = onnx.load(self.model_path)
                artifact = bentoml.onnx.save_model(self.model_name, model, signatures=signatures)
            elif self.framework == "xgboost" and xgb:
                booster = xgb.Booster()
                booster.load_model(self.model_path)
                artifact = bentoml.xgboost.save_model(self.model_name, booster, signatures=signatures)
            elif self.framework == "lightgbm" and lgb:
                booster = lgb.Booster(model_file=self.model_path)
                artifact = bentoml.lightgbm.save_model(self.model_name, booster, signatures=signatures)
            elif self.framework == "catboost" and cb:
                model = cb.CatBoostClassifier()
                model.load_model(self.model_path)
                artifact = bentoml.catboost.save_model(self.model_name, model, signatures=signatures)
            elif self.framework == "tensorflow" and tf and keras:
                model = keras.models.load_model(self.model_path)
                artifact = bentoml.keras.save_model(self.model_name, model, signatures=signatures)
            else:
                raise ValueError(f"暂不支持的框架: {self.framework}")
        except Exception as e:
            logger.error(f"[失败] 注册模型 {self.model_name} 出错: {e}")
            return

        tag = str(artifact.tag)
        version = artifact.info.version
        uuid_str = self.create_identifier(hash, tag)

        logger.info(
            f"\n{'='*120}\n"
            f"模型注册成功\n"
            f"业务名称 : {self.business_name}\n"
            f"模型名称 : {self.model_name}\n"
            f"模型类型 : {self.model_type}\n"
            f"框架类型 : {self.framework}\n"
            f"版本编号 : {version}\n"
            f"标签信息 : {tag}\n"
            f"唯一标识 : {uuid_str}\n"
            f"文件路径 : {self.model_path}\n"
            f"文件哈希 : {hash}\n"
            f"{'='*120}\n"
        )

        self.write_model_registry(version, hash, tag, uuid_str)

    @classmethod
    def register_all_models(cls):
        root = Path(__file__).resolve().parent.parent
        model_conf = config.get("models", {})

        for category, models in model_conf.items():
            for info in models:
                model_name = info["model_name"]
                model_type = info["model_type"]
                model_path = Path(info["model_path"])
                if not model_path.is_absolute():
                    model_path = root / model_path
                if not model_path.exists():
                    logger.warning(f"[跳过] 模型文件不存在: {model_path}")
                    continue

                framework = info.get("framework")
                if not framework:
                    try:
                        framework = cls.detect_framework(str(model_path))
                    except Exception as e:
                        logger.error(f"[失败] 无法推断框架: {model_name}, 错误: {e}")
                        continue

                registry = cls(
                    info.get("business_name", category),
                    model_name,
                    model_type,
                    str(model_path),
                    framework,
                    force=info.get("force", False)
                )
                registry.register_model()


def main():
    parser = argparse.ArgumentParser(description="模型注册工具")
    parser.add_argument("--all", default=True, action="store_true", help="注册所有模型")
    parser.add_argument("--model_name", type=str, help="模型名称")
    parser.add_argument("--force", action="store_true", help="强制覆盖已存在模型")
    args = parser.parse_args()

    if args.all:
        ModelRegistry.register_all_models()
    elif args.model_name:
        model_conf = config.get("models", {})
        model_info = None
        for category, models in model_conf.items():
            for m in models:
                if m["model_name"] == args.model_name:
                    model_info = m
                    break
            if model_info:
                break

        if not model_info:
            raise ValueError(f"未在 config.yaml 中找到模型 {args.model_name}")

        path = Path(model_info["model_path"])
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path

        registry = ModelRegistry(
            model_info.get("business_name", "default"),
            model_info["model_name"],
            model_info["model_type"],
            str(path),
            model_info.get("framework"),
            force=args.force or model_info.get("force", False)
        )
        registry.register_model()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
