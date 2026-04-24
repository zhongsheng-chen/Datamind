# datamind/models/registry.py

"""模型注册中心

负责模型的完整注册流程：存储、BentoML 注册、数据库记录。

核心功能：
  - register: 注册模型（存储文件 -> BentoML -> 数据库）

使用示例：
  from datamind.models.registry import ModelRegistry
  from datamind.db.core.uow import UnitOfWork

  with UnitOfWork() as uow:
      registry = ModelRegistry()
      tag = registry.register(
          uow=uow,
          model_id="scorecard_v1",
          name="信用评分卡",
          version="1.0.0",
          framework="sklearn",
          model_type="logistic_regression",
          task_type="scoring",
          model_path="./models/model.pkl",
          created_by="admin",
      )
"""

from pathlib import Path
import joblib

from datamind.storage import get_storage
from datamind.models.backend import BentoBackend
from datamind.db.models import Metadata, Version


class ModelRegistry:
    """模型注册中心"""

    def __init__(self):
        self.storage = get_storage()
        self.backend = BentoBackend()

    def register(
        self,
        uow,
        *,
        model_id: str,
        name: str,
        version: str,
        framework: str,
        model_type: str,
        task_type: str,
        model_path: str,
        description: str | None = None,
        signatures=None,
        labels=None,
        metadata=None,
        params=None,
        metrics=None,
        created_by: str | None = None,
    ) -> str:
        """注册模型

        参数：
            uow: 工作单元（事务管理）
            model_id: 模型唯一标识
            name: 模型名称
            version: 模型版本
            framework: 模型框架
            model_type: 模型类型
            task_type: 任务类型
            model_path: 本地模型文件路径
            description: 模型描述
            signatures: BentoML 签名配置
            labels: BentoML 标签
            metadata: BentoML 元数据
            params: 模型参数
            metrics: 模型评估指标
            created_by: 创建人

        返回：
            BentoML 模型 tag

        流程：
            1. 保存模型文件到 storage
            2. 加载模型对象
            3. 注册到 BentoML
            4. 写 metadata 表（如果不存在）
            5. 写 version 表
        """
        model_file = Path(model_path)
        filename = model_file.name

        # 1. 保存模型文件到 storage
        data = model_file.read_bytes()
        storage_key = self.storage.save(model_id, version, filename, data)

        # 2. 加载模型对象
        model = joblib.load(model_path)

        # 3. 注册到 BentoML
        tag = self.backend.save(
            framework=framework,
            name=f"{model_id}_{version}",
            model=model,
            signatures=signatures,
            labels=labels,
            metadata=metadata,
        )

        # 4. 写数据库
        with uow:
            # metadata（如果不存在则创建）
            meta = (
                uow.session.query(Metadata)
                .filter_by(model_id=model_id)
                .one_or_none()
            )

            if not meta:
                uow.session.add(
                    Metadata(
                        model_id=model_id,
                        name=name,
                        description=description,
                        model_type=model_type,
                        task_type=task_type,
                        framework=framework,
                        created_by=created_by,
                    )
                )

            # version（每次注册都添加）
            uow.session.add(
                Version(
                    model_id=model_id,
                    version=version,
                    bento_tag=str(tag),
                    model_path=storage_key,
                    params=params,
                    metrics=metrics,
                    created_by=created_by,
                )
            )

        return str(tag)