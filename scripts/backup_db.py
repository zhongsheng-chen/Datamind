#!/usr/bin/env python3
# datamind/scripts/backup_db.py
"""
数据库备份脚本
支持全量备份和增量备份
"""

import os
import sys
import gzip
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
import argparse
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseBackup:
    """数据库备份工具"""

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # 解析数据库URL
        self.db_url = settings.DATABASE_URL
        self._parse_db_url()

    def _parse_db_url(self):
        """解析数据库连接URL"""
        # postgresql://user:pass@host:port/dbname
        import re
        pattern = r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)'
        match = re.match(pattern, self.db_url)

        if match:
            self.user, self.password, self.host, self.port, self.dbname = match.groups()
        else:
            raise ValueError(f"无法解析数据库URL: {self.db_url}")

    def backup(self, backup_type: str = "full") -> Path:
        """
        执行备份

        Args:
            backup_type: 备份类型 (full/incremental)

        Returns:
            Path: 备份文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"{self.dbname}_{backup_type}_{timestamp}.sql.gz"

        logger.info(f"开始{backup_type}备份: {backup_file}")

        # 构建pg_dump命令
        env = os.environ.copy()
        env["PGPASSWORD"] = self.password

        cmd = [
            "pg_dump",
            "-h", self.host,
            "-p", self.port,
            "-U", self.user,
            "-d", self.dbname,
            "--format=custom",  # 自定义格式，支持选择性恢复
            "--verbose"
        ]

        if backup_type == "schema-only":
            cmd.append("--schema-only")
        elif backup_type == "data-only":
            cmd.append("--data-only")

        try:
            # 执行备份
            with gzip.open(backup_file, 'wb') as f:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )

                stdout, stderr = process.communicate()

                if process.returncode != 0:
                    raise Exception(f"备份失败: {stderr}")

                f.write(process.stdout.read())

            # 计算文件大小
            file_size = backup_file.stat().st_size
            logger.info(f"备份完成: {backup_file} ({file_size / 1024 / 1024:.2f} MB)")

            # 创建最新备份的符号链接
            latest_link = self.backup_dir / f"{self.dbname}_latest.sql.gz"
            if latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(backup_file.name)

            return backup_file

        except Exception as e:
            logger.error(f"备份失败: {e}")
            raise

    def restore(self, backup_file: Path):
        """
        恢复备份

        Args:
            backup_file: 备份文件路径
        """
        if not backup_file.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_file}")

        logger.info(f"开始恢复备份: {backup_file}")

        # 构建pg_restore命令
        env = os.environ.copy()
        env["PGPASSWORD"] = self.password

        cmd = [
            "pg_restore",
            "-h", self.host,
            "-p", self.port,
            "-U", self.user,
            "-d", self.dbname,
            "--clean",  # 清理现有对象
            "--if-exists",
            "--verbose"
        ]

        try:
            with gzip.open(backup_file, 'rb') as f:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True
                )

                stdout, stderr = process.communicate(input=f.read().decode())

                if process.returncode != 0:
                    raise Exception(f"恢复失败: {stderr}")

            logger.info("恢复完成")

        except Exception as e:
            logger.error(f"恢复失败: {e}")
            raise

    def list_backups(self) -> list:
        """列出所有备份"""
        backups = []
        for f in self.backup_dir.glob(f"{self.dbname}_*.sql.gz"):
            backups.append({
                "file": f.name,
                "size": f.stat().st_size,
                "modified": datetime.fromtimestamp(f.stat().st_mtime),
                "type": f.name.split('_')[1] if len(f.name.split('_')) > 2 else "unknown"
            })

        return sorted(backups, key=lambda x: x['modified'], reverse=True)

    def cleanup_old_backups(self, keep_days: int = 30):
        """清理旧备份"""
        cutoff = datetime.now().timestamp() - (keep_days * 24 * 3600)
        deleted = 0

        for f in self.backup_dir.glob(f"{self.dbname}_*.sql.gz"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
                logger.info(f"删除旧备份: {f}")

        logger.info(f"清理完成，删除了 {deleted} 个旧备份")
        return deleted


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据库备份工具")
    parser.add_argument("action", choices=["backup", "restore", "list", "cleanup"],
                        help="操作类型")
    parser.add_argument("--type", choices=["full", "schema-only", "data-only"],
                        default="full", help="备份类型")
    parser.add_argument("--file", help="恢复时指定的备份文件")
    parser.add_argument("--keep-days", type=int, default=30,
                        help="保留备份的天数")
    parser.add_argument("--backup-dir", default="backups",
                        help="备份目录")

    args = parser.parse_args()

    backup_tool = DatabaseBackup(args.backup_dir)

    if args.action == "backup":
        backup_tool.backup(args.type)

    elif args.action == "restore":
        if not args.file:
            # 使用最新的备份
            backups = backup_tool.list_backups()
            if backups:
                args.file = backups[0]['file']
            else:
                logger.error("没有可用的备份")
                sys.exit(1)

        backup_file = Path(args.backup_dir) / args.file
        backup_tool.restore(backup_file)

    elif args.action == "list":
        backups = backup_tool.list_backups()
        print(f"\n{'文件名':<50} {'大小':<10} {'修改时间':<20} {'类型'}")
        print("-" * 90)
        for b in backups:
            size_mb = b['size'] / 1024 / 1024
            print(f"{b['file']:<50} {size_mb:>5.2f} MB  {b['modified'].strftime('%Y-%m-%d %H:%M'):<20} {b['type']}")

    elif args.action == "cleanup":
        backup_tool.cleanup_old_backups(args.keep_days)


if __name__ == "__main__":
    main()