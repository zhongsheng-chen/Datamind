#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
register_model.py

将模型文件注册为模型服务. 仅会注册 config/config.yaml models 单元列出的所有模型文件
使用 --force 选项强制注册模型，会将状态为 'deactive' 的模型更新为 'active'
用法:
  注册所有模型
  python register_model.py --all

  注册指定模型
  python register_model.py --model_name demo_loan_scorecard_lr_20250930

  强制注册指定模型
  python register_model.py --model_name demo_loan_scorecard_lr_20250930 \
                           --force

"""

import os
import uuid
import joblib
import pickle
import bentoml
import argparse
import pytz
from datetime import datetime
from pathlib import Path
from ruamel.yaml import YAML
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
    """更新 config.yaml 中指定模型的 version 和 uuid，保留注释"""

    yaml = YAML()
    yaml.preserve_quotes = True
    cfg_path = str(config.cfg_path)
    updated = False

    if not os.path.exists(cfg_path):
        logger.warning(f"[配置] 文件不存在: {cfg_path}")
        return

    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.load(f)

    for task, models in data.get("models", {}).items():
        for m in models:
            if m.get("model_name") == model_name:
                m["version"] = version
                m["uuid"] = uuid_str
                updated = True
                break
        if updated:
            break

    if updated:
        tmp_path = cfg_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)
        os.replace(tmp_path, cfg_path)
        logger.info(f"[配置] config.yaml 已更新：{model_name} 的 version 和 uuid")
    else:
        logger.warning(f"[配置] 未找到模型 {model_name}，未更新 config.yaml")

class ModelRegistry:
    """模型注册类"""

    def __init__(self, model_name, model_type, model_path, framework, task, force=False):
        self.model_name = model_name
        self.model_type = model_type
        self.model_path = model_path
        self.framework = framework
        self.task = task
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

    def check_exists(self, hash):
        """检查相同模型名、任务、哈希是否已存在于 registry"""
        SessionLocal = sessionmaker(bind=postgres_engine)
        with SessionLocal() as session:
            result = session.execute(
                text("""
                     SELECT 1
                     FROM registry
                     WHERE model_name = :model_name
                       AND task = :task
                       AND hash = :hash
                       AND status = 'active'
                     """),
                {"model_name": self.model_name, "task": self.task, "hash": hash}
            ).fetchone()
            return result is not None

    def create_identifier(self, hash):
        timestamp = datetime.now(beijing_tz).strftime("%Y%m%d%H%M%S")
        model_str = f"{self.model_name}_{self.model_type}_{self.framework}_{hash}_{timestamp}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, model_str))

    def write_registry_history(self, conn, model_id, metadata, change_type, remarks=None):
        """写入 registry_history"""
        record = {
            "model_id": model_id,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "model_path": self.model_path,
            "version": metadata.get("version"),
            "framework": self.framework,
            "task": self.task,
            "hash": metadata.get("hash"),
            "tag": metadata.get("tag"),
            "uuid": metadata.get("uuid"),
            "status": metadata.get("status", "active"),
            "change_type": change_type,
            "remarks": remarks,
        }

        conn.execute(text("""
                          INSERT INTO registry_history (model_id, model_name, model_type, model_path, version,
                                                              framework,
                                                              task, hash, tag, uuid, status, change_type, changed_by,
                                                              remarks)
                          VALUES (:model_id, :model_name, :model_type, :model_path, :version, :framework,
                                  :task, :hash, :tag, :uuid, :status, :change_type, current_user, :remarks)
                          """), record)

    def write_registry(self, version, hash, tag, uuid_str):
        now = datetime.now(beijing_tz)
        metadata = {
            "version": version,
            "hash": hash,
            "tag": tag,
            "uuid": uuid_str,
            "status": "active"
        }

        with postgres_engine.connect() as conn:
            try:
                # 1. 如果 --force，先将旧版本模型失效
                if self.force:
                    old_models = conn.execute(text("""
                                                   SELECT *
                                                   FROM registry
                                                   WHERE model_name = :model_name
                                                     AND task = :task
                                                     AND hash = :hash
                                                     AND status = 'active'
                                                   """), {"model_name": self.model_name, "task": self.task, "hash": hash}).fetchall()

                    for old in old_models:
                        conn.execute(text("""
                                          UPDATE registry
                                          SET status='inactive'
                                          WHERE id = :id
                                          """), {"id": old["id"]})

                        conn.execute(text("""
                                          UPDATE registry_history
                                          SET status='inactive',
                                              change_type='Force Deactivate',
                                              remarks='模型已强制注销, --force 开关自动强制注销旧模型'
                                          WHERE model_id = :model_id
                                            AND id = (SELECT id
                                                      FROM registry_history
                                                      WHERE model_id = :model_id
                                                      ORDER BY id DESC
                                                      LIMIT 1)
                                          """), {"model_id": old["id"]})

                        logger.info(f"[失效] 旧模型 {old['model_name']} (uuid={old['uuid']}, id={old['id']}) 已失效")

                # 2. 检查当前模型是否已存在
                existing = conn.execute(text("""
                                             SELECT *
                                             FROM registry
                                             WHERE model_name = :model_name
                                               AND task = :task
                                               AND hash = :hash
                                               AND status = 'active'
                                             """), {
                                            "model_name": self.model_name,
                                            "task": self.task,
                                            "hash": metadata.get("hash")
                                        }).fetchone()

                if existing and not self.force:
                    logger.info(f"[跳过] 模型 {self.model_name} 已存在，使用 --force 可覆盖。")
                    return

                # 3. 插入新模型
                result = conn.execute(text("""
                                           INSERT INTO registry
                                           (model_name, model_type, model_path, version, framework, task, hash, tag,
                                            uuid, status, registered_at)
                                           VALUES (:model_name, :model_type, :model_path, :version, :framework, :task,
                                                   :hash, :tag, :uuid, :status, :registered_at)
                                           RETURNING id
                                           """), {
                                          "model_name": self.model_name,
                                          "model_type": self.model_type,
                                          "model_path": self.model_path,
                                          "version": metadata.get("version"),
                                          "framework": self.framework,
                                          "task": self.task,
                                          "hash": metadata.get("hash"),
                                          "tag": metadata.get("tag"),
                                          "uuid": metadata.get("uuid"),
                                          "status": metadata.get("status"),
                                          "registered_at": now
                                      })
                model_id = result.fetchone()[0]
                logger.info(f"[新增] 模型 {self.model_name} (uuid={metadata.get('uuid')}, id={model_id}) 已注册成功")

                self.write_registry_history(
                    conn, model_id, metadata, "Force Recreate" if self.force else "Create", "强制注册成功" if self.force else "注册成功"
                )

                # 4. 更新 config.yaml
                update_config_yaml(self.model_name, version, uuid_str)

            except IntegrityError as e:
                logger.error(f"数据库插入失败: {e}")
            except Exception as e:
                logger.error(f"注册写入失败: {e}")

    def register_model(self):
        # signatures = {"predict": {"batchable": False}, "predict_proba": {"batchable": False}}

        signatures = {"predict": {"batchable": False}}
        if self.framework in ["sklearn", "catboost", "xgboost", "lightgbm"]:
            signatures["predict_proba"] = {"batchable": False}

        hash = self.create_hash()

        if not self.force and self.check_exists(hash):
            logger.info(f"[跳过] 模型已注册: {self.model_name} (task={self.task}, path={self.model_path}, hash={hash})")
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
        uuid_str = self.create_identifier(hash)

        logger.info(
            f"\n{'='*120}\n"
            f"模型注册成功\n"
            f"模型名称 : {self.model_name}\n"
            f"模型类型 : {self.model_type}\n"
            f"框架类型 : {self.framework}\n"
            f"任务类型 : {self.task}\n"
            f"版本编号 : {version}\n"
            f"标签信息 : {tag}\n"
            f"唯一标识 : {uuid_str}\n"
            f"文件路径 : {self.model_path}\n"
            f"文件哈希 : {hash}\n"
            f"{'='*120}\n"
        )

        self.write_registry(version, hash, tag, uuid_str)

    @classmethod
    def register_all_models(cls):
        root = Path(__file__).resolve().parent.parent
        model_conf = config.get("models", {})

        for task, models in model_conf.items():
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
                    model_name,
                    model_type,
                    str(model_path),
                    framework,
                    task,
                    force=info.get("force", False)
                )
                registry.register_model()


def main():
    parser = argparse.ArgumentParser(description="模型注册工具")
    parser.add_argument("--all", action="store_true", help="注册所有模型")
    parser.add_argument("--model_name", type=str, help="模型名称")
    parser.add_argument("--force", action="store_true", help="强制覆盖已存在模型")
    args = parser.parse_args()

    if args.all:
        ModelRegistry.register_all_models()
    elif args.model_name:
        model_conf = config.get("models", {})
        model_info = None
        task = None
        for task, models in model_conf.items():
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
            model_info["model_name"],
            model_info["model_type"],
            str(path),
            model_info.get("framework"),
            task,
            force=args.force
        )
        registry.register_model()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
