#!/usr/bin/env python3
# datamind/scripts/migrate_data.py
"""
数据迁移脚本
用于在不同环境之间迁移数据
"""

import os
import sys
import json
import csv
from pathlib import Path
from datetime import datetime
import argparse
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from core.db.models import (
    ModelMetadata, ModelVersionHistory, ApiCallLog,
    AuditLog, ABTestConfig, ABTestAssignment, SystemConfig
)
from core.db.database import get_db
from config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DataMigrator:
    """数据迁移工具"""

    def __init__(self, source_url: str = None, target_url: str = None):
        self.source_url = source_url or settings.DATABASE_URL
        self.target_url = target_url or settings.DATABASE_URL

        self.source_engine = create_engine(self.source_url)
        self.target_engine = create_engine(self.target_url)

        self.SourceSession = sessionmaker(bind=self.source_engine)
        self.TargetSession = sessionmaker(bind=self.target_engine)

    def export_models(self, output_dir: Path, format: str = "json"):
        """导出模型数据"""
        logger.info(f"导出模型数据到 {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

        session = self.SourceSession()

        try:
            # 导出模型元数据
            models = session.query(ModelMetadata).all()
            self._export_data(
                models,
                output_dir / f"models.{format}",
                format
            )

            # 导出版本历史
            history = session.query(ModelVersionHistory).all()
            self._export_data(
                history,
                output_dir / f"version_history.{format}",
                format
            )

            # 导出系统配置
            configs = session.query(SystemConfig).all()
            self._export_data(
                configs,
                output_dir / f"system_configs.{format}",
                format
            )

            logger.info(f"导出完成，共导出 {len(models)} 个模型")

        finally:
            session.close()

    def _export_data(self, objects, output_file: Path, format: str):
        """导出数据到文件"""
        data = []
        for obj in objects:
            # 转换为字典
            item = {}
            for column in obj.__table__.columns:
                value = getattr(obj, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                item[column.name] = value
            data.append(item)

        if format == "json":
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        elif format == "csv":
            if data:
                with open(output_file, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)

    def import_models(self, input_dir: Path, format: str = "json"):
        """导入模型数据"""
        logger.info(f"从 {input_dir} 导入模型数据")

        session = self.TargetSession()

        try:
            # 导入模型元数据
            models_file = input_dir / f"models.{format}"
            if models_file.exists():
                models = self._import_data(models_file, format)
                for model_data in models:
                    # 检查是否已存在
                    existing = session.query(ModelMetadata).filter_by(
                        model_id=model_data['model_id']
                    ).first()

                    if not existing:
                        model = ModelMetadata(**model_data)
                        session.add(model)

                session.commit()
                logger.info(f"导入 {len(models)} 个模型")

        finally:
            session.close()

    def _import_data(self, input_file: Path, format: str) -> list:
        """从文件导入数据"""
        if format == "json":
            with open(input_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        elif format == "csv":
            data = []
            with open(input_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            return data

    def migrate_schema(self):
        """迁移数据库结构"""
        logger.info("开始迁移数据库结构")

        from sqlalchemy import MetaData

        # 获取源数据库结构
        source_meta = MetaData()
        source_meta.reflect(bind=self.source_engine)

        # 获取目标数据库结构
        target_meta = MetaData()
        target_meta.reflect(bind=self.target_engine)

        # 比较并生成迁移语句
        with self.target_engine.connect() as conn:
            for table_name in source_meta.tables:
                if table_name not in target_meta.tables:
                    # 表不存在，创建
                    source_table = source_meta.tables[table_name]
                    source_table.create(bind=self.target_engine)
                    logger.info(f"创建表: {table_name}")
                else:
                    # 比较列
                    source_table = source_meta.tables[table_name]
                    target_table = target_meta.tables[table_name]

                    for column in source_table.columns:
                        if column.name not in target_table.columns:
                            # 添加列
                            col_type = column.type.compile(self.target_engine.dialect)
                            conn.execute(text(
                                f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type}"
                            ))
                            logger.info(f"添加列: {table_name}.{column.name}")

        logger.info("数据库结构迁移完成")

    def migrate_data(self, tables: list = None):
        """迁移数据"""
        logger.info("开始迁移数据")

        if not tables:
            tables = ['model_metadata', 'system_configs']

        source_session = self.SourceSession()
        target_session = self.TargetSession()

        try:
            for table_name in tables:
                logger.info(f"迁移表: {table_name}")

                # 获取源数据
                result = source_session.execute(text(f"SELECT * FROM {table_name}"))
                rows = result.fetchall()

                if rows:
                    # 清空目标表
                    target_session.execute(text(f"TRUNCATE {table_name} CASCADE"))

                    # 插入数据
                    columns = result.keys()
                    for row in rows:
                        placeholders = ','.join(['?'] * len(columns))
                        target_session.execute(
                            text(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"),
                            row
                        )

                    target_session.commit()
                    logger.info(f"迁移 {len(rows)} 条记录到 {table_name}")

        finally:
            source_session.close()
            target_session.close()

        logger.info("数据迁移完成")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="数据迁移工具")
    parser.add_argument("action", choices=["export", "import", "migrate-schema", "migrate-data"],
                        help="操作类型")
    parser.add_argument("--source", help="源数据库URL")
    parser.add_argument("--target", help="目标数据库URL")
    parser.add_argument("--dir", default="./migrations/data",
                        help="数据文件目录")
    parser.add_argument("--format", choices=["json", "csv"], default="json",
                        help="导出格式")
    parser.add_argument("--tables", nargs="+",
                        help="要迁移的表名")

    args = parser.parse_args()

    migrator = DataMigrator(args.source, args.target)
    data_dir = Path(args.dir)

    if args.action == "export":
        migrator.export_models(data_dir, args.format)

    elif args.action == "import":
        migrator.import_models(data_dir, args.format)

    elif args.action == "migrate-schema":
        migrator.migrate_schema()

    elif args.action == "migrate-data":
        migrator.migrate_data(args.tables)


if __name__ == "__main__":
    main()