#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
unregister_model.py

用于注销已注册的模型服务。

用法:
  注销指定模型（通过 uuid）：
      python unregister_model.py --uuid 550e8400-e29b-41d4-a716-446655440000

  注销指定模型（通过 uuid）,支持批量逗号分隔：
      python unregister_model.py --uuid 550e8400-e29b-41d4-a716-446655440000,123e4567-e89b-12d3-a456-426614174000

  注销指定模型（通过 tag）：
      python unregister_model.py --tag demo_loan_scorecard_lr_20250930:bnx7y63fsn2uqxgq

  注销全部模型：
      python unregister_model.py --all
"""

import bentoml
import argparse
from sqlalchemy import text
from src.db_engine import postgres_engine
from src.setup import setup_logger

logger = setup_logger()


class ModelUnregistry:
    """模型注销类，支持单个或批量注销"""

    def __init__(self, uuids=None, tag=None, unregister_all=False):
        # 支持批量 UUID，用逗号分隔
        self.uuids = [u.strip() for u in uuids.split(",")] if uuids else []
        self.tag = tag
        self.unregister_all = unregister_all

    @staticmethod
    def mark_inactive(conn, where_clause, params):
        """数据库更新状态为 inactive"""
        conn.execute(text(f"UPDATE model_registry SET status='inactive' WHERE {where_clause}"), params)

    def unregister_by_uuid(self):
        """根据 uuid 注销模型"""
        with postgres_engine.connect() as conn:
            for uuid_ in self.uuids:
                record = conn.execute(
                    text("SELECT tag FROM model_registry WHERE uuid = :uuid AND status = 'active'"),
                    {"uuid": uuid_},
                ).fetchone()
                if not record:
                    logger.warning(f"[未找到] uuid={uuid_} 对应的模型记录不存在或已失效。")
                    continue

                tag = record[0]
                try:
                    m = bentoml.models.get(tag)
                    bentoml.models.delete(tag=m.tag)
                    self.mark_inactive(conn, "uuid=:uuid", {"uuid": uuid_})
                    logger.info(f"[成功] 模型 {tag} (uuid={uuid_}) 已注销。")
                except bentoml.exceptions.NotFound:
                    logger.warning(f"[BentoML] 模型 {tag} 不存在或已删除。")
                    self.mark_inactive(conn, "uuid=:uuid", {"uuid": uuid_})
                except Exception as e:
                    logger.error(f"[失败] 注销模型 {tag} 出错: {e}")

    def unregister_by_tag(self):
        """根据 tag 注销模型"""
        with postgres_engine.connect() as conn:
            record = conn.execute(
                text("SELECT uuid FROM model_registry WHERE tag = :tag AND status = 'active'"),
                {"tag": self.tag},
            ).fetchone()
            if not record:
                logger.warning(f"[未找到] tag={self.tag} 对应的模型记录不存在或已失效。")
                return

            uuid_ = record[0]
            try:
                m = bentoml.models.get(self.tag)
                bentoml.models.delete(tag=m.tag)
                self.mark_inactive(conn, "tag=:tag", {"tag": self.tag})
                logger.info(f"[成功] 模型 {self.tag} (uuid={uuid_}) 已注销。")
            except bentoml.exceptions.NotFound:
                logger.warning(f"[BentoML] 模型 {self.tag} 不存在或已删除。")
                self.mark_inactive(conn, "tag=:tag", {"tag": self.tag})
            except Exception as e:
                logger.error(f"[失败] 注销模型 {self.tag} 出错: {e}")

    def unregister_all_models(self):
        """注销全部 BentoML 模型"""
        with postgres_engine.connect() as conn:
            try:
                models = bentoml.models.list()
                if not models:
                    logger.info("[提示] 当前没有已注册的 BentoML 模型可注销。")
                    return
                for m in models:
                    try:
                        bentoml.models.delete(tag=m.tag)
                        self.mark_inactive(conn, "tag=:tag", {"tag": str(m.tag)})
                        logger.info(f"[成功] 已注销模型: {m.tag}")
                    except bentoml.exceptions.NotFound:
                        logger.warning(f"[BentoML] 模型 {m.tag} 不存在或已删除。")
                        self.mark_inactive(conn, "tag=:tag", {"tag": str(m.tag)})
            except Exception as e:
                logger.error(f"[失败] 注销全部模型出错: {e}")

    def run(self):
        """执行注销逻辑"""
        if self.unregister_all:
            self.unregister_all_models()
        elif self.uuids:
            self.unregister_by_uuid()
        elif self.tag:
            self.unregister_by_tag()
        else:
            logger.warning("请指定 --uuid、--tag 或 --all 参数执行注销操作。")


def main():
    parser = argparse.ArgumentParser(description="注销已注册的模型服务")
    parser.add_argument("--uuid", type=str, help="模型标识，支持批量逗号（,）分隔")
    parser.add_argument("--tag", type=str, help="模型标签，格式 name:version")
    parser.add_argument("--all", action="store_true", help="注销全部模型")
    args = parser.parse_args()

    unreg = ModelUnregistry(uuids=args.uuid, tag=args.tag, unregister_all=args.all)
    unreg.run()


if __name__ == "__main__":
    main()
