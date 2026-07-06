# datamind/services/register.py

"""模型注册器

负责模型的注册，完成模型产物加载、存储和注册。

核心功能：
  - ModelRegister.register: 注册模型

使用示例：
  from datamind.services.register import ModelRegister

  register = ModelRegister()

  result = await register.register(
      name="scorecard",
      version="1.0.0",
      framework="sklearn",
      model_type="logistic_regression",
      task_type="scoring",
      model_path="scorecard.pkl",
      description="信用评分卡模型",
      version_description="信用评分卡模型 v1.0.0",
      created_by="system"
  )
"""

import json
import os
from pathlib import Path
from typing import Any

import structlog

from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import (
    MetadataPatch,
    MetadataRepository,
    VersionPatch,
    VersionRepository,
)
from datamind.models.artifact import ModelArtifactLoader
from datamind.models.enums import (
    MetadataStatus,
    VersionStatus,
)
from datamind.models.errors import (
    ArtifactError,
    InvalidModelStateError,
    ModelAlreadyExistsError,
)
from datamind.models.schema import SchemaExtractor
from datamind.runtime.backend import BentoBackend
from datamind.storage import get_storage
from datamind.storage.resolver import StorageResolver
from datamind.utils.generator import generate_id

logger = structlog.get_logger(__name__)


class ModelRegister:
    """模型注册器"""

    def __init__(self) -> None:
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
            description: str | None = None,
            version_description: str | None = None,
            input_schema: dict | None = None,
            output_schema: dict | None = None,
            params: dict | None = None,
            metrics: dict | None = None,
            created_by: str | None = None,
            force: bool = False,
    ) -> dict[str, Any]:
        """注册模型

        参数：
            name:
                模型名称

            version:
                模型版本号

            framework:
                模型框架

            model_type:
                模型类型

            task_type:
                任务类型

            model_path:
                本地模型文件路径

            description:
                模型描述

                首次注册模型时用于创建模型描述。

                已有版本通过 force 强制覆盖时，
                显式传入该参数可更新模型描述。

                已有模型注册新版本时不允许修改
                模型描述。

            version_description:
                模型版本描述

                创建新版本时用于设置版本描述。

                已有版本通过 force 强制覆盖时，
                显式传入该参数可更新版本描述。

            input_schema:
                输入 Schema

            output_schema:
                输出 Schema

            params:
                模型参数

            metrics:
                评估指标

            created_by:
                创建人

            force:
                是否强制覆盖已有版本

        返回：
            注册信息字典，包含：
              - name
              - model_id
              - version
              - version_id
              - bento_tag
              - model_key
              - model_path
              - input_schema_key
              - output_schema_key

        异常：
            ArtifactError:
                模型产物处理错误

            ModelAlreadyExistsError:
                模型版本已存在

            InvalidModelStateError:
                模型或版本状态不允许注册

            ValueError:
                已有模型注册新版本时尝试修改
                模型描述
        """
        model_id = generate_id(
            prefix="mdl",
            keys=(name,),
        )

        version_id = generate_id(
            prefix="ver",
            keys=(
                model_id,
                version,
            ),
        )

        logger.info(
            "开始注册模型",
            model_id=model_id,
            version_id=version_id,
            name=name,
            version=version,
        )

        path = Path(
            model_path
        )

        if not path.exists():
            raise ArtifactError(
                f"模型文件不存在: {model_path}"
            )

        filename = os.path.basename(
            model_path
        )

        async with UnitOfWork() as uow:
            session = uow.session

            metadata_repo = MetadataRepository(
                session
            )

            version_repo = VersionRepository(
                session
            )

            # 检查模型元数据
            existing_metadata = (
                await metadata_repo.get_model(
                    model_id=model_id
                )
            )

            if existing_metadata:
                logger.debug(
                    "模型元数据已存在",
                    model_id=model_id,
                    status=existing_metadata.status,
                )

                current_metadata_status = MetadataStatus(
                    existing_metadata.status
                )

                if (
                        current_metadata_status
                        == MetadataStatus.ARCHIVED
                ):
                    raise InvalidModelStateError(
                        "模型已归档，不允许直接注册新版本: "
                        f"{name}"
                    )

            # 检查模型版本
            existing_version = (
                await version_repo.get_version(
                    version_id=version_id
                )
            )

            # 已有模型注册新版本时不允许修改模型级描述
            if (
                    existing_metadata is not None
                    and existing_version is None
                    and description is not None
            ):
                raise ValueError(
                    "模型已存在，注册新版本时"
                    "不能修改模型描述"
                )

            # 已存在版本但未指定 force
            if (
                    existing_version is not None
                    and not force
            ):
                raise ModelAlreadyExistsError(
                    f"模型版本已存在: {name}:{version}"
                )

            # 已存在版本且指定 force
            if (
                    existing_version is not None
                    and force
            ):
                logger.warning(
                    "检测到重复版本，执行强制覆盖",
                    model_id=model_id,
                    version_id=version_id,
                    version=version,
                    status=existing_version.status,
                )

                current_version_status = VersionStatus(
                    existing_version.status
                )

                if (
                        current_version_status
                        == VersionStatus.ARCHIVED
                ):
                    raise InvalidModelStateError(
                        "模型版本已归档，不允许覆盖: "
                        f"{name}:{version}"
                    )

            # 读取模型文件
            logger.debug(
                "开始读取模型文件",
                model_path=model_path,
            )

            try:
                data = path.read_bytes()

            except Exception as exc:
                raise ArtifactError(
                    f"模型文件读取失败: {model_path}"
                ) from exc

            logger.debug(
                "模型文件读取成功"
            )

            # 上传模型文件
            model_key = self.storage.save(
                model_id=model_id,
                version=version,
                filename=filename,
                data=data,
            )

            resolved_model_path = (
                StorageResolver().resolve(
                    model_key
                )
            )

            logger.debug(
                "模型文件上传成功",
                model_key=model_key,
                model_path=resolved_model_path,
            )

            # 加载模型
            try:
                model = ModelArtifactLoader.load(
                    data=data,
                    framework=framework,
                )

            except Exception as exc:
                raise ArtifactError(
                    "模型文件加载失败"
                ) from exc

            logger.debug(
                "模型文件加载成功",
                framework=framework,
            )

            # 提取 Schema
            schema = SchemaExtractor.extract(
                model=model,
                framework=framework,
            )

            if schema is None:
                logger.warning(
                    "无法自动提取模型 Schema",
                    framework=framework,
                    model_id=model_id,
                )

            input_schema = (
                    input_schema
                    or schema
            )

            logger.debug(
                "模型 Schema 提取完成",
                schema=input_schema,
            )

            # 保存输入 Schema
            input_schema_key = None

            if input_schema is not None:
                input_schema_key = self.storage.save(
                    model_id=model_id,
                    version=version,
                    filename="input_schema.json",
                    data=json.dumps(
                        input_schema,
                        ensure_ascii=False,
                        indent=2,
                    ).encode(
                        "utf-8"
                    ),
                )

            # 保存输出 Schema
            output_schema_key = None

            if output_schema is not None:
                output_schema_key = self.storage.save(
                    model_id=model_id,
                    version=version,
                    filename="output_schema.json",
                    data=json.dumps(
                        output_schema,
                        ensure_ascii=False,
                        indent=2,
                    ).encode(
                        "utf-8"
                    ),
                )

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
                    "framework": framework,
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

            # 创建或更新模型元数据
            if existing_metadata is None:
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
                        description=(
                            description
                            if (
                                    existing_version is not None
                                    and force
                            )
                            else None
                        ),
                    ),
                    updated_by=created_by,
                )

                logger.debug(
                    "模型元数据更新成功",
                    model_id=model_id,
                    name=name,
                )

            # 创建或更新模型版本
            if existing_version is None:
                version_repo.create_version(
                    version_id=version_id,
                    model_id=model_id,
                    version=version,
                    framework=framework,
                    bento_tag=bento_tag,
                    model_path=resolved_model_path,
                    model_key=model_key,
                    input_schema=input_schema,
                    output_schema=output_schema,
                    input_schema_key=input_schema_key,
                    output_schema_key=output_schema_key,
                    params=params,
                    metrics=metrics,
                    description=version_description,
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
                        model_path=resolved_model_path,
                        model_key=model_key,
                        input_schema=input_schema,
                        output_schema=output_schema,
                        input_schema_key=input_schema_key,
                        output_schema_key=output_schema_key,
                        params=params,
                        metrics=metrics,
                        description=version_description,
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
            "name": name,
            "model_id": model_id,
            "version": version,
            "version_id": version_id,
            "bento_tag": bento_tag,
            "model_key": model_key,
            "model_path": resolved_model_path,
            "input_schema_key": input_schema_key,
            "output_schema_key": output_schema_key,
        }
