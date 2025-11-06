#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unregister_model.py

注销已注册的模型服务。默认情况下，仅将模型状态置为 inactive，
如果指定 --delete，将彻底删除模型。

用法示例:
  按uuid注销指定模型：
      python unregister_model.py --uuid 550e8400-e29b-41d4-a716-446655440000

  按uuid注销指定模型，支持批量逗号分隔：
      python unregister_model.py --uuid 550e8400-e29b-41d4-a716-446655440000,123e4567-e89b-12d3-a456-426614174000

  按tag注销指定模型：
      python unregister_model.py --tags demo_loan_scorecard_lr_20250930:bnx7y63fsn2uqxgq

  按tag注销指定模型，支持批量逗号分隔：
      python unregister_model.py --tags demo_loan_scorecard_lr_20250930:bnx7y63fsn2uqxgq, demo_loan_scorecard_rf_20250930:rweugznuok7v2b3i

  注销全部模型：
      python unregister_model.py --all

  彻底删除指定模型：
      python unregister_model.py --uuid 550e8400-e29b-41d4-a716-446655440000 --delete

  彻底删除所有模型：
      python unregister_model.py --all --delete
"""

import bentoml
import argparse
from sqlalchemy import text
from src.db_engine import postgres_engine
from src.setup import setup_logger

logger = setup_logger()


class ModelUnregistry:
    """模型注销类，支持单个或批量注销"""

    def __init__(self, uuids=None, tags=None, unregister_all=False, delete=False):
        self.uuids = [u.strip() for u in uuids.split(",")] if uuids else []
        self.tags = [t.strip() for t in tags.split(",")] if tags else []
        self.unregister_all = unregister_all
        self.delete = delete

    @staticmethod
    def write_registry_history(conn, model_id, metadata, change_type, remarks=None):
        """写入 registry_history"""
        record = {
            "model_id": model_id,
            "model_name": metadata["model_name"],
            "model_type": metadata["model_type"],
            "model_path": metadata["model_path"],
            "version": metadata["version"],
            "framework": metadata["framework"],
            "task": metadata["task"],
            "hash": metadata["hash"],
            "tag": metadata["tag"],
            "uuid": metadata["uuid"],
            "status": "inactive",
            "change_type": change_type,
            "remarks": remarks,
        }
        conn.execute(text("""
            INSERT INTO registry_history
            (model_id, model_name, model_type, model_path, version,
             framework, task, hash, tag, uuid, status, change_type, changed_by, remarks)
            VALUES (:model_id, :model_name, :model_type, :model_path, :version,
                    :framework, :task, :hash, :tag, :uuid, :status, :change_type, current_user, :remarks)
        """), record)

    @staticmethod
    def mark_inactive(conn, where_clause, params):
        """数据库更新状态为 inactive"""
        conn.execute(text(f"UPDATE registry SET status='inactive' WHERE {where_clause}"), params)

    def _delete(self, conn, record):
        """删除或注销 BentoML 模型，同时可选择删除数据库记录"""
        tag = record["tag"]
        uuid_ = record["uuid"]

        if self.delete:
            # 删除 BentoML 模型
            try:
                m = bentoml.models.get(tag)
                bentoml.models.delete(tag=m.tag)
                logger.info(f"[删除] 模型 {tag} (uuid={uuid_}) 的 BentoML 模型已删除")
            except bentoml.exceptions.NotFound:
                logger.warning(f"[BentoML] 模型 {tag} 不存在或已删除")
            except Exception as e:
                logger.error(f"[失败] 删除 BentoML 模型 {tag} 出错: {e}")

            # 删除数据库记录
            self.write_registry_history(conn,
                                              record["id"],
                                              record,
                                              "Remove",
                                              "模型已清除，从BentoML存储空间彻底移除")
            conn.execute(text("DELETE FROM registry WHERE uuid=:uuid"), {"uuid": uuid_})
            logger.info(f"[删除] 模型 {tag} (uuid={uuid_}) 的数据库记录已删除")
        else:
            # 仅标记为 inactive
            self.mark_inactive(conn, "uuid=:uuid", {"uuid": uuid_})
            logger.info(f"[更新] 模型 {tag} (uuid={uuid_}) 数据库记录标记为 inactive")
            self.write_registry_history(conn,
                                              record["id"],
                                              record,
                                              "Deactivate",
                                              "模型已注销，其状态变更为inactive")

    def unregister_by_uuid(self):
        """根据 uuid 注销模型"""
        if not self.uuids:
            return

        with postgres_engine.connect() as conn:
            total = 0
            for uuid_ in self.uuids:
                record = conn.execute(
                    text("SELECT * FROM registry WHERE uuid = :uuid AND status='active'"),
                    {"uuid": uuid_},
                ).fetchone()
                if not record:
                    logger.warning(f"[未找到] uuid={uuid_} 对应的活跃模型不存在")
                    continue
                self._delete(conn, record)
                total += 1
            if total:
                action = "删除" if self.delete else "注销"
                logger.info(f"共 {total} 个模型通过 uuid 执行操作：{action}")

    def unregister_by_tag(self):
        """根据 tags 注销模型，支持多个逗号分隔"""
        if not self.tags:
            return

        with postgres_engine.connect() as conn:
            total = 0
            for tag in self.tags:
                record = conn.execute(
                    text("SELECT * FROM registry WHERE tag = :tag AND status='active'"),
                    {"tag": tag},
                ).fetchone()
                if not record:
                    logger.warning(f"[未找到] tag={tag} 对应的活跃模型不存在")
                    continue
                self._delete(conn, record)
                total += 1

            if total:
                action = "删除" if self.delete else "注销"
                logger.info(f"共 {total} 个模型通过 tag 执行操作：{action}")

    def unregister_all_models(self):
        """注销全部模型"""
        with postgres_engine.connect() as conn:
            if self.delete:
                # 删除时包含 active 和 inactive
                records = conn.execute(
                    text("SELECT * FROM registry WHERE status IN ('active','inactive')")
                ).fetchall()
            else:
                # 仅标记 active
                records = conn.execute(
                    text("SELECT * FROM registry WHERE status='active'")
                ).fetchall()

            if not records:
                logger.info("[提示] 当前没有已注册的模型可注销")
                return

            total = len(records)
            for record in records:
                self._delete(conn, record)

            action = "已删除" if self.delete else "标记为 inactive"
            logger.info(f"[共 {total} 个模型，全部{action}]")

    def run(self):
        """执行注销逻辑"""
        if self.unregister_all:
            self.unregister_all_models()
        elif self.uuids:
            self.unregister_by_uuid()
        elif self.tags:
            self.unregister_by_tag()
        else:
            logger.warning("请指定 --uuid、--tags 或 --all 参数执行注销操作")


def main():
    parser = argparse.ArgumentParser(description="注销已注册的模型服务")
    parser.add_argument("--uuid", type=str, help="模型标识，支持批量逗号分隔")
    parser.add_argument("--tags", type=str, help="模型标签，支持批量逗号分隔")
    parser.add_argument("--all", action="store_true", help="注销全部模型")
    parser.add_argument("--delete", action="store_true", help="彻底删除模型")
    args = parser.parse_args()

    unreg = ModelUnregistry(
        uuids=args.uuid,
        tags=args.tags,
        unregister_all=args.all,
        delete=args.delete
    )
    unreg.run()


if __name__ == "__main__":
    main()
