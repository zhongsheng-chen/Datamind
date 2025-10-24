#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
delete_model.py

删除指定业务或所有业务的 BentoML 模型版本。
支持 dry-run 模式，只打印将删除的模型而不执行实际删除。
支持保留最新版本、按日期删除、删除指定模型。

用法：
   删除指定业务的所有模型：
   python delete_model.py --business_name business_name

   删除所有模型：
   python delete_model.py

   dry-run 模式，只打印将要删除的模型：
   python delete_model.py --business_name business_name --dry-run

   保留最新版本，删除历史旧模型：
   python delete_model.py --business_name business_name --keep-latest

   删除早于指定日期的模型：
   python delete_model.py --before 2025-09-01

   删除指定模型：
   python delete_model.py --model_tag name:version
"""

import pytz
import argparse
import bentoml
from dateutil.parser import parse
from src.setup import setup_logger

logger = setup_logger()

beijing_tz = pytz.timezone("Asia/Shanghai")

def delete_models(
    business_name: str = None,
    dry_run: bool = False,
    keep_latest: bool = False,
    before: str = None,
    model_tag: str = None,
):
    """
    删除指定业务、所有业务、某个模型，或早于指定日期的 BentoML 模型
    """
    all_models = bentoml.models.list()

    # 如果指定单个模型
    if model_tag:
        try:
            m = bentoml.models.get(model_tag)
        except Exception as e:
            logger.error(f"未找到模型 {model_tag}: {e}")
            return
        target_models = [m]

    # 如果指定业务
    elif business_name:
        target_models = [m for m in all_models if business_name in m.tag.name]
        if not target_models:
            logger.info(f"未找到业务 '{business_name}' 的模型")
            return

    # 默认删除所有
    else:
        target_models = all_models
        if not target_models:
            logger.info("当前没有任何模型可以删除")
            return

    # 按创建时间排序（新 -> 旧）
    target_models.sort(key=lambda m: m.creation_time, reverse=True)

    # 保留最新版本
    if keep_latest and len(target_models) > 0 and not model_tag:
        latest = target_models[0]
        logger.info(
            f"保留最新模型: {latest.tag}, 创建于: {latest.creation_time}, 大小: {latest.file_size} 字节"
        )
        target_models = target_models[1:]
    elif keep_latest and model_tag:
        logger.info("keep-latest 选项忽略，因为指定了单个 model_tag")

    # 按日期过滤
    if before:
        try:
            cutoff = parse(before)
            if cutoff.tzinfo is None:
                cutoff = beijing_tz.localize(cutoff)
        except Exception:
            logger.error(f"无法解析日期: {before}, 格式应为 YYYY-MM-DD")
            return
        target_models = [m for m in target_models if m.creation_time < cutoff]

    if not target_models:
        logger.warning("没有符合条件的模型可删除")
        return

    # 遍历删除
    deleted_count = 0
    for m in target_models:
        info = f"{m.tag.name}:{m.tag.version}, 创建于: {m.creation_time}, 大小: {m.file_size} 字节"
        if dry_run:
            logger.info(f"[dry-run] 将删除模型: {info}")
        else:
            logger.info(f"删除模型 {info} ...")
            try:
                bentoml.models.delete(tag=m.tag)
                deleted_count += 1
            except Exception as e:
                logger.error(f"删除模型 {m.tag} 失败: {e}")

    if dry_run:
        logger.info(f"dry-run 完成，未执行实际删除，共 {len(target_models)} 个模型符合条件")
    else:
        logger.info(f"模型删除完成，本次操作共删除 {deleted_count} 个模型")


def main():
    parser = argparse.ArgumentParser(description="删除 BentoML 模型")
    parser.add_argument("--business_name", type=str, default=None, help="指定业务名称")
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不实际删除")
    parser.add_argument("--keep-latest", action="store_true", help="保留最新版本，不删除最新的模型")
    parser.add_argument("--before", type=str, default=None, help="删除早于该日期的模型，格式：YYYY-MM-DD")
    parser.add_argument("--model_tag", type=str, default=None, help="删除指定模型，格式：model_name:version")
    args = parser.parse_args()

    delete_models(
        business_name=args.business_name,
        dry_run=args.dry_run,
        keep_latest=args.keep_latest,
        before=args.before,
        model_tag=args.model_tag,
    )

if __name__ == "__main__":
    main()
