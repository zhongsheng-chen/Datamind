# datamind/models/register.py

"""模型注册器

负责模型的注册流程，整合存储、反序列化、BentoML 注册和元数据持久化。

核心功能：
  - ModelRegister.register: 注册模型

使用示例：
  from datamind.models.register import ModelRegister

  register = ModelRegister()

  result = await register.register(
      name="scorecard",
      version="1.0.0",
      framework="sklearn",
      model_type="logistic_regression",
      task_type="scoring",
      model_path="./models/scorecard.pkl",
      description="信用评分卡模型",
      created_by="admin"
  )
"""

import os
import hashlib
import structlog
from pathlib import Path
from typing import Optional, Dict

from datamind.audit import audit
from datamind.storage import get_storage
from datamind.db.core.uow import UnitOfWork
from datamind.db.writers import MetadataWriter, VersionWriter
from datamind.db.readers import MetadataReader, VersionReader
from datamind.models.backend import BentoBackend
from datamind.models.artifact import ModelArtifactLoader
from datamind.models.enums import MetadataStatus
from datamind.models.errors import (
    ArtifactError,
    ModelAlreadyExistsError,
)

logger = structlog.get_logger(__name__)


class ModelRegister:
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

    @audit(
        action="model.register",
        target_type="model",
        target_id_func=lambda params, result: result["model_id"],
    )
    async def register(
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
            framework: 模型框架
            model_type: 模型类型
            task_type: 任务类型
            model_path: 本地模型文件路径
            description: 模型描述（可选）
            params: 模型参数（可选）
            metrics: 评估指标（可选）
            created_by: 创建人（可选）

        返回：
            包含 model_id、version、storage_key、bento_tag 的字典

        异常：
            ArtifactError: 模型产物处理错误
            ModelAlreadyExistsError: 模型版本已存在
        """
        model_id = self._generate_model_id(name)

        logger.info(
            "开始注册模型",
            model_id=model_id,
            name=name,
            version=version,
        )

        # 校验模型文件是否存在
        path = Path(model_path)

        if not path.exists():
            raise ArtifactError(f"模型文件不存在: {model_path}")

        filename = os.path.basename(model_path)

        async with UnitOfWork() as uow:
            session = uow.session

            metadata_reader = MetadataReader(session)
            version_reader = VersionReader(session)

            metadata_writer = MetadataWriter(session)
            version_writer = VersionWriter(session)

            # 查询模型元数据
            existing_metadata = await metadata_reader.get_model(
                model_id
            )

            if existing_metadata:
                logger.debug(
                    "模型元数据已存在",
                    model_id=model_id,
                    status=existing_metadata.status,
                )

            # 检查版本是否已存在
            latest_version = await version_reader.get_latest_version(
                model_id
            )

            if latest_version:
                logger.debug(
                    "当前最新模型版本",
                    model_id=model_id,
                    latest_version=latest_version.version,
                )

                if latest_version.version == version:
                    raise ModelAlreadyExistsError(
                        f"模型版本已存在: {name}:{version}"
                    )

            # 读取本地模型文件
            logger.debug(
                "开始读取模型文件",
                model_path=model_path,
            )

            try:
                data = path.read_bytes()
            except Exception as e:
                raise ArtifactError(
                    f"模型文件读取失败: {model_path}"
                ) from e

            logger.debug("模型文件读取成功")

            # 上传模型文件
            storage_key = self.storage.save(
                model_id=model_id,
                version=version,
                filename=filename,
                data=data,
            )

            logger.debug(
                "模型文件上传成功",
                storage_key=storage_key,
            )

            # 加载模型
            try:
                model = ModelArtifactLoader.load(
                    data=data,
                    framework=framework,
                )
            except Exception as e:
                raise ArtifactError(
                    "模型文件加载失败"
                ) from e

            logger.debug(
                "模型文件加载成功",
                framework=framework,
            )

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
            )

            bento_tag = str(
                bento_model.tag
            )

            logger.debug(
                "模型注册到 BentoML 成功",
                bento_tag=bento_tag,
            )

            # 首次注册才创建 metadata
            if not existing_metadata:
                await metadata_writer.create(
                    model_id=model_id,
                    name=name,
                    description=description,
                    model_type=model_type,
                    task_type=task_type,
                    framework=framework,
                    status=MetadataStatus.ACTIVE,
                    created_by=created_by,
                )

                logger.debug(
                    "模型元数据创建成功",
                    model_id=model_id,
                )
            else:
                logger.debug(
                    "模型元数据已存在，跳过创建",
                    model_id=model_id,
                )

            # 创建版本记录
            await version_writer.create(
                model_id=model_id,
                version=version,
                framework=framework,
                bento_tag=bento_tag,
                model_path=storage_key,
                params=params,
                metrics=metrics,
                description=description,
                created_by=created_by,
            )

            logger.debug(
                "模型版本创建成功",
                model_id=model_id,
                version=version,
            )

        logger.info(
            "模型注册完成",
            model_id=model_id,
            version=version,
        )

        return {
            "model_id": model_id,
            "version": version,
            "storage_key": storage_key,
            "bento_tag": bento_tag,
        }