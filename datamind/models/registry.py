# datamind/models/registry.py

"""模型注册组件

负责协调模型注册的完整流程，整合存储、反序列化、BentoML注册和元数据持久化。

核心功能：
  - register: 注册模型，将本地模型文件写入存储、注册到 BentoML 并持久化元数据
  - load: 加载模型，从 BentoML Model Store 加载模型
  - unregister: 注销模型，删除 BentoML 和数据库记录

使用示例：
  from datamind.models.registry import ModelRegistry

  registry = ModelRegistry()

  # 注册模型
  result = registry.register(
      name="scorecard",
      version="1.0.0",
      framework="sklearn",
      model_type="logistic_regression",
      task_type="scoring",
      model_path="./models/scorecard.pkl",
      description="信用评分卡模型",
      created_by="admin"
  )

  # 加载模型
  model = registry.load(
      framework="sklearn",
      tag="scorecard:1.0.0"
  )

    # 注销模型指定版本
  registry.unregister(
      model_id="mdl_abc123",
      version="1.0.0"
  )

  # 注销模型所有版本
  registry.unregister(model_id="mdl_abc123")
"""

import os
import hashlib
from pathlib import Path
from typing import Any, Optional, Dict

from datamind.logging import get_logger
from datamind.storage import get_storage
from datamind.models.artifact import ModelArtifact
from datamind.models.backend import BentoBackend
from datamind.db.core.uow import UnitOfWork

logger = get_logger(__name__)


class ModelRegistry:
    """模型注册器"""

    def __init__(self):
        """初始化模型注册器"""
        self.storage = get_storage()
        self.backend = BentoBackend()

    @staticmethod
    def _generate_model_id(name: str) -> str:
        """生成稳定的模型ID

        同一个 name 永远生成相同 model_id，用于唯一标识模型。

        参数：
            name: 模型名称

        返回：
            模型ID，格式：mdl_{8位MD5哈希}
        """
        digest = hashlib.md5(name.encode()).hexdigest()[:8]
        return f"mdl_{digest}"

    def register(
        self,
        *,
        name: str,
        version: str,
        framework: str,
        model_type: str,
        task_type: str,
        model_path: str,
        description: Optional[str] = None,
        params: Optional[Dict] = None,
        metrics: Optional[Dict] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, str]:
        """注册模型

        将本地模型文件写入存储、注册到 BentoML 并持久化元数据

        参数：
            name: 模型名称
            version: 模型版本号
            framework: 模型框架（sklearn/xgboost/lightgbm 等）
            model_type: 模型类型（decision_tree/random_forest/xgboost/lightgbm/logistic_regression）
            task_type: 任务类型（classification/scoring）
            model_path: 本地模型文件路径
            description: 模型描述（可选）
            params: 模型参数（可选）
            metrics: 评估指标（可选）
            created_by: 创建人（可选）

        返回：
            包含 model_id、version、storage_key、bento_tag 的字典

        异常：
            FileNotFoundError: 模型文件不存在
        """
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"模型文件不存在: {model_path}")

        model_id = self._generate_model_id(name)
        filename = os.path.basename(model_path)

        logger.info("开始注册模型",
                   name=name,
                   model_id=model_id,
                   filename=filename,
                   version=version,
                   framework=framework)

        # 读取本地模型文件
        data = path.read_bytes()

        # 生成唯一 storage key
        storage_key = self.storage.save(
            model_id=model_id,
            version=version,
            filename=filename,
            data=data,
        )
        logger.debug("模型已写入存储", storage_key=storage_key)

        # 反序列化模型对象
        model = ModelArtifact.load(framework, data)

        # 注册到 BentoML
        bentoml_model = self.backend.save(
            name=name,
            framework=framework,
            model=model,
            labels={
                "model_id": model_id,
                "model_type": model_type,
                "task_type": task_type,
                "version": version,
            },
            metadata={
                "storage_key": storage_key,
                "filename": filename,
            },
        )
        logger.debug("模型已注册到 BentoML", tag=str(bentoml_model.tag))

        # 写入数据库
        with UnitOfWork() as uow:
            uow.metadata().create(
                model_id=model_id,
                name=name,
                model_type=model_type,
                task_type=task_type,
                framework=framework,
                description=description,
                created_by=created_by,
            )

            uow.version().create(
                model_id=model_id,
                version=version,
                model_path=storage_key,
                params=params,
                metrics=metrics,
                description=description,
                created_by=created_by,
                bento_tag=str(bentoml_model.tag),
            )

        logger.info("模型注册成功",
                   name=name,
                   model_id=model_id,
                   version=version,
                   storage_key=storage_key)

        return {
            "model_id": model_id,
            "version": version,
            "storage_key": storage_key,
            "bento_tag": str(bentoml_model.tag),
        }

    def load(
        self,
        *,
        framework: str,
        tag: str,
    ) -> Any:
        """加载模型

        从 BentoML Model Store 加载模型

        参数：
            framework: 模型框架
            tag: 模型标签（格式：模型名:版本）

        返回：
            加载的模型实例
        """
        logger.debug("加载模型", framework=framework, tag=tag)
        return self.backend.load(framework=framework, tag=tag)

    def unregister(
        self,
        *,
        model_id: str,
        version: Optional[str] = None,
    ) -> bool:
        """注销模型

        删除 BentoML 中的模型和数据库中的记录。

        参数：
            model_id: 模型ID
            version: 版本号（可选，不传则注销所有版本）

        返回：
            注销成功返回 True
        """
        logger.info("开始注销模型",
                    model_id=model_id,
                    version=version)

        with UnitOfWork() as uow:
            if version:
                # 获取版本信息
                version_info = uow.version().get(model_id, version)
                if version_info:
                    # 删除 BentoML 模型
                    self.backend.delete(tag=version_info.bento_tag)
                    # 删除数据库版本记录
                    uow.version().delete(model_id, version)

                # 检查是否还有其他版本
                remaining = uow.version().count(model_id)
                if remaining == 0:
                    uow.metadata().delete(model_id)
            else:
                # 删除所有版本
                versions = uow.version().list(model_id)
                for v in versions:
                    self.backend.delete(tag=v.bento_tag)
                uow.version().delete_all(model_id)
                uow.metadata().delete(model_id)

        logger.info("模型注销成功", model_id=model_id, version=version)
        return True