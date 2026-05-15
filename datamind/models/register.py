# datamind/models/register.py

"""模型注册器

负责模型的注册，完成模型产物加载、存储和注册。

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
import structlog
from pathlib import Path
from typing import Optional, Dict

from datamind.utils.generator import generate_id
from datamind.storage import get_storage
from datamind.storage.resolver import StorageResolver
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import MetadataRepository, MetadataPatch, VersionRepository, VersionPatch
from datamind.models.backend import BentoBackend
from datamind.models.artifact import ModelArtifactLoader
from datamind.models.guard import ModelGuard
from datamind.models.enums import MetadataStatus, VersionStatus
from datamind.models.errors import ArtifactError, ModelAlreadyExistsError

logger = structlog.get_logger(__name__)


class ModelRegister:
    """模型注册器"""

    def __init__(self):
        self.storage = get_storage()
        self.backend = BentoBackend()

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
        force: bool = False,
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
            updated_by: 更新人（可选）
            force: 是否强制覆盖已有版本（可选）

        返回：
            包含 model_id、version、storage_key、storage_location、bento_tag 的字典

        异常：
            ArtifactError: 模型产物处理错误
            ModelAlreadyExistsError: 模型已存在
        """
        model_id = generate_id(prefix="mdl", keys=(name,))
        version_id = generate_id(prefix="ver", keys=(model_id, version))

        logger.info(
            "开始注册模型",
            model_id=model_id,
            version_id=version_id,
            name=name,
            version=version,
        )

        path = Path(model_path)
        if not path.exists():
            raise ArtifactError(f"模型文件不存在: {model_path}")

        filename = os.path.basename(model_path)

        async with UnitOfWork() as uow:
            session = uow.session

            metadata_repo = MetadataRepository(session)
            version_repo = VersionRepository(session)

            # 检查元数据
            existing_metadata = await metadata_repo.get_model(model_id=model_id)

            if existing_metadata:
                logger.debug(
                    "模型元数据已存在",
                    model_id=model_id,
                    status=existing_metadata.status,
                )

                current = MetadataStatus(existing_metadata.status)

                if current != MetadataStatus.ARCHIVED:
                    ModelGuard.validate_metadata_transition(
                        current=current,
                        target=MetadataStatus.ARCHIVED,
                    )

            # 检查版本
            existing_version = await version_repo.get_version(version_id=version_id)

            if existing_version and not force:
                raise ModelAlreadyExistsError(f"模型版本已存在: {name}:{version}")

            if existing_version and force:
                logger.warning(
                    "检测到重复版本，执行强制覆盖",
                    model_id=model_id,
                    version=version,
                )

                current = VersionStatus(existing_version.status)

                if current != VersionStatus.ARCHIVED:
                    ModelGuard.validate_version_transition(
                        current=current,
                        target=VersionStatus.ARCHIVED,
                    )

            # 读取模型文件
            logger.debug("开始读取模型文件", model_path=model_path)

            try:
                data = path.read_bytes()
            except Exception as e:
                raise ArtifactError(f"模型文件读取失败: {model_path}") from e

            logger.debug("模型文件读取成功")

            # 上传模型文件
            storage_key = self.storage.save(
                model_id=model_id,
                version=version,
                filename=filename,
                data=data,
            )

            storage_location = StorageResolver().resolve(storage_key)

            logger.debug(
                "模型文件上传成功",
                storage_key=storage_key,
                storage_location=storage_location,
            )

            # 加载模型
            try:
                model = ModelArtifactLoader.load(
                    data=data,
                    framework=framework,
                )
            except Exception as e:
                raise ArtifactError("模型文件加载失败") from e

            logger.debug("模型文件加载成功", framework=framework)

            # 注册到 BentoML
            bento_model = self.backend.save(
                name=name,
                framework=framework,
                model=model,
                labels={
                    "model_id": model_id,
                    "version_id": version_id,
                    "model_type": model_type,
                    "task_type": task_type,
                    "version": version,
                },
            )

            bento_tag = str(bento_model.tag)

            logger.debug("模型注册到 BentoML 成功", bento_tag=bento_tag)

            # 创建或更新元数据
            if not existing_metadata:
                metadata_repo.create_model(
                    model_id=model_id,
                    name=name,
                    model_type=model_type,
                    task_type=task_type,
                    framework=framework,
                    description=description,
                    created_by=created_by,
                )

                logger.debug(
                    "模型元数据创建成功",
                    model_id=model_id,
                    name=name,
                )

            else:
                metadata_repo.update_model(
                    existing_metadata,
                    patch=MetadataPatch(
                        name=name,
                        model_type=model_type,
                        task_type=task_type,
                        framework=framework,
                        description=description,
                        updated_by=created_by,
                    ),
                )

                logger.debug(
                    "模型元数据更新成功",
                    model_id=model_id,
                    name=name,
                )

            # 创建或更新版本
            if not existing_version:
                version_repo.create_version(
                    version_id=version_id,
                    model_id=model_id,
                    version=version,
                    framework=framework,
                    bento_tag=bento_tag,
                    model_path=storage_location,
                    storage_key=storage_key,
                    params=params,
                    metrics=metrics,
                    description=description,
                    created_by=created_by,
                )

                logger.debug(
                    "模型版本创建成功",
                    model_id=model_id,
                    version_id=version_id,
                    version=version,
                )

            else:
                version_repo.update_version(
                    existing_version,
                    patch=VersionPatch(
                        framework=framework,
                        bento_tag=bento_tag,
                        model_path=storage_location,
                        storage_key=storage_key,
                        params=params,
                        metrics=metrics,
                        description=description,
                    ),
                    updated_by=created_by,
                )

                logger.debug(
                    "模型版本更新成功",
                    model_id=model_id,
                    version_id=version_id,
                    version=version,
                )

        logger.info(
            "模型注册完成",
            model_id=model_id,
            version_id=version_id,
            version=version,
        )

        return {
            "model_id": model_id,
            "version_id": version_id,
            "name": name,
            "version": version,
            "bento_tag": bento_tag,
            "storage_key": storage_key,
            "model_path": storage_location,
        }