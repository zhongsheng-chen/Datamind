# datamind/models/registry.py

"""模型注册组件

负责协调模型注册的完整流程，整合存储、反序列化、BentoML注册和元数据持久化。

核心功能：
  - register: 注册模型，将本地模型文件写入存储、注册到 BentoML 并持久化元数据
  - load: 加载模型，从 BentoML Model Store 加载模型
  - retire: 模型下线，关闭部署并记录审计日志

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

  # 模型下线
  registry.retire(
      model_id="mdl_abc123",
      version="1.0.0",
      reason="模型已过期"
  )
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
from datamind.context.scope import context_scope

logger = get_logger(__name__)


class ModelRegistry:
    """模型注册器"""

    def __init__(self):
        self.storage = get_storage()
        self.backend = BentoBackend()

    @staticmethod
    def _generate_model_id(name: str) -> str:
        """生成模型ID

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

        logger.info(
            "开始注册模型",
            name=name,
            model_id=model_id,
            version=version,
            framework=framework,
        )

        # 读取本地模型文件
        data = path.read_bytes()

        # 写入存储层
        storage_key = self.storage.save(
            model_id=model_id,
            version=version,
            filename=filename,
            data=data,
        )

        # 反序列化模型对象
        model = ModelArtifact.load(framework, data)

        # 注册到 BentoML
        bento_model = self.backend.save(
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
                bento_tag=str(bento_model.tag),
                model_path=storage_key,
                params=params,
                metrics=metrics,
                description=description,
                created_by=created_by,
            )

        logger.info(
            "模型注册成功",
            model_id=model_id,
            version=version,
            storage_key=storage_key,
        )

        return {
            "model_id": model_id,
            "version": version,
            "storage_key": storage_key,
            "bento_tag": str(bento_model.tag),
        }

    def load(self, *, framework: str, tag: str) -> Any:
        """加载模型

        参数：
            framework: 模型框架
            tag: 模型标签（格式：模型名:版本）

        返回：
            加载的模型实例
        """
        return self.backend.load(
            framework=framework,
            tag=tag,
        )

    def retire(
            self,
            *,
            model_id: str,
            version: str,
            reason: str = None,
            user: str = None,
            ip: str = None,
    ) -> Dict[str, Any]:
        """模型下线

        参数：
            model_id: 模型ID
            version: 版本号
            reason: 下线原因（可选）
            user: 操作用户（可选）
            ip: 操作IP（可选）

        返回：
            包含 model_id、version、status 的字典
        """
        with context_scope(user=user, ip=ip):
            logger.info(
                "模型下线",
                model_id=model_id,
                version=version,
                reason=reason,
            )

            with UnitOfWork() as uow:
                # 审计记录
                uow.audit().write(
                    action="model.retire",
                    target_type="deployment",
                    target_id=f"{model_id}:{version}",
                    after={
                        "status": "retired",
                        "reason": reason,
                    },
                )

                # 关闭部署
                uow.deployment().write(
                    model_id=model_id,
                    version=version,
                    status="inactive",
                    traffic_ratio=0.0,
                    description="retired",
                )

            logger.info(
                "模型已下线",
                model_id=model_id,
                version=version,
            )

            return {
                "model_id": model_id,
                "version": version,
                "status": "retired",
            }