#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
delete_model.py

删除 BentoML 模型。
支持 dry-run 模式，只打印将删除的模型而不执行实际删除。
支持保留最新版本、按日期删除、删除指定模型（单个或批量）。

用法：
   删除所有模型：
       python delete_model.py

   dry-run 模式，只打印将要删除的模型：
       python delete_model.py --dry-run

   保留最新版本，删除历史旧模型：
       python delete_model.py --keep-latest

   删除早于指定日期的模型：
       python delete_model.py --before 2025-09-01

   删除单个或多个指定模型：
       python delete_model.py --tag name1:version1,name2:version2

   删除单个或多个指定模型中早于指定日期的模型：
       python delete_model.py --tag name1:version1,name2:version2 --before 2025-09-01
"""

import pytz
import argparse
import bentoml
from dateutil.parser import parse
from src.setup import setup_logger

logger = setup_logger()
beijing_tz = pytz.timezone("Asia/Shanghai")


def human_size(size: int) -> str:
    """将字节大小转为可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def to_local_time(dt):
    """转换 datetime 到北京时间"""
    return dt.astimezone(beijing_tz) if dt.tzinfo else beijing_tz.localize(dt)


def delete_models(dry_run=False, keep_latest=False, before=None, tag=None):
    """删除指定模型，或早于指定日期的 BentoML 模型"""
    target_models = []

    # 获取目标模型列表
    if tag:
        tags = [t.strip() for t in tag.split(",") if t.strip()]
        for t in tags:
            try:
                m = bentoml.models.get(t)
                target_models.append(m)
            except Exception as e:
                logger.error(f"未找到模型 {t}: {e}")
        if not target_models:
            logger.warning("没有找到任何指定的模型，操作结束")
            return
    else:
        all_models = bentoml.models.list()
        if not all_models:
            logger.info("当前没有任何模型可以删除")
            return
        target_models = all_models

    # 按日期过滤
    if before:
        try:
            cutoff = parse(before)
            cutoff = to_local_time(cutoff)
        except Exception:
            logger.error(f"无法解析日期: {before}, 格式应为 YYYY-MM-DD")
            return
        target_models = [m for m in target_models if to_local_time(m.creation_time) < cutoff]
        if not target_models:
            logger.warning("没有符合日期条件的模型可删除")
            return

    if not target_models:
        logger.warning("没有符合条件的模型可删除")
        return

    # 按创建时间排序（新 -> 旧）
    target_models.sort(key=lambda m: m.creation_time, reverse=True)

    # 保留最新版本（仅在批量删除或未指定 tag 时）
    if keep_latest and not tag and target_models:
        latest = target_models[0]
        logger.info(
            f"保留最新模型: {latest.tag}, 创建于: {to_local_time(latest.creation_time)}, 大小: {human_size(latest.file_size)}"
        )
        target_models = target_models[1:]
    elif keep_latest and tag:
        logger.info("keep-latest 选项忽略，因为指定了具体 tag")

    if not target_models:
        logger.warning("没有符合条件的模型可删除")
        return

    # 操作确认
    if not dry_run:
        confirm = input(f"确定要删除 {len(target_models)} 个模型吗？(yes/no): ").strip().lower()
        if confirm != "yes":
            logger.info("操作已取消")
            return

    # 遍历删除
    deleted_count = 0
    for m in target_models:
        local_time = to_local_time(m.creation_time)
        info = f"{m.tag.name}:{m.tag.version}, 创建于: {local_time}, 大小: {human_size(m.file_size)}"
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
    parser.add_argument("--dry-run", action="store_true", help="仅打印，不实际删除")
    parser.add_argument("--keep-latest", action="store_true", help="保留最新版本，不删除最新的模型")
    parser.add_argument("--before", type=str, default=None, help="删除早于该日期的模型，格式：YYYY-MM-DD")
    parser.add_argument("--tag", type=str, default=None, help="删除指定模型，格式：model_name:version, 支持批量逗号分隔",
    )
    args = parser.parse_args()

    delete_models(
        dry_run=args.dry_run,
        keep_latest=args.keep_latest,
        before=args.before,
        tag=args.tag,
    )


if __name__ == "__main__":
    main()
