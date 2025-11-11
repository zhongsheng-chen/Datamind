#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
list_model.py

功能：
列出 BentoML 存储的所有模型，格式类似命令行输出
"""

import bentoml
from datetime import timezone, timedelta
from src.logger import get_logger

logger = get_logger()

def human_readable_size(size_bytes):
    for unit in ['B', 'KiB', 'MiB', 'GiB', 'TiB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PiB"

def list_models():
    all_models = bentoml.models.list()
    if not all_models:
        logger.info("当前没有任何模型")
        return

    rows = []
    for m in all_models:
        tag = str(m.tag)
        module = getattr(m.info, "module", "N/A")
        size = human_readable_size(getattr(m, "file_size", 0))
        # creation_time = str(m.creation_time)

        creation_time_utc = m.creation_time
        creation_time_bj = creation_time_utc.astimezone(timezone(timedelta(hours=8)))
        creation_time = creation_time_bj.strftime("%Y-%m-%d %H:%M:%S")
        rows.append([tag, module, size, creation_time])

    # 自动计算每列最大宽度
    headers = ["Tag", "Module", "Size", "Creation Time"]
    col_widths = [max(len(str(row[i])) for row in rows + [headers]) for i in range(4)]

    # 打印表头
    print("  ".join(f"{headers[i]:<{col_widths[i]}}" for i in range(4)))
    print("=" * (sum(col_widths) + 6))

    # 打印每行
    for row in rows:
        print("  ".join(f"{row[i]:<{col_widths[i]}}" for i in range(4)))

def main():
    list_models()

if __name__ == "__main__":
    main()
