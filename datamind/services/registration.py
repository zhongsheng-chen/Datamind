# datamind/services/registration.py

"""模型注册服务

负责校验模型制品、生成独立修订并更新版本的当前制品投影。

核心功能：
  - register: 注册模型或制品修订

使用示例：
  from datamind.services.registration import ModelRegistrationService

  service = ModelRegistrationService()

  result = await service.register(
      name="scorecard",
      version="1.0.0",
      framework="sklearn",
      model_type="logistic_regression",
      task_type="scoring",
      model_path="./models/scorecard.pkl",
      description="信用评分卡模型",
      version_description="信用评分卡模型 v1.0.0",
      created_by="system",
  )
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import structlog

from datamind.constants import (
    Framework,
    ModelType,
    TaskType,
)
from datamind.db.core.uow import UnitOfWork
from datamind.db.repositories import (
    ArtifactRepository,
    DeploymentRepository,
    MetadataPatch,
    MetadataRepository,
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
from datamind.utils.generator import (
    generate_id,
    generate_random_id,
)

logger = structlog.get_logger(__name__)


class ModelRegistrationService:
    """模型注册服务"""

    def __init__(self) -> None:
        """初始化模型注册服务"""
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
        """注册模型或模型制品修订

        首次提交创建模型版本及 revision 1 制品。版本已存在时，
        相同摘要按幂等成功返回；不同摘要只有在 force=True、版本处于
        inactive、从未部署且未删除时，才创建新的制品修订。

        参数：
            name: 模型名称
            version: 模型版本号
            framework: 模型框架
            model_type: 模型类型
            task_type: 任务类型
            model_path: 本地模型文件路径
            description: 模型描述（可选）
            version_description: 模型版本描述（可选）
            input_schema: 输入 Schema（可选）
            output_schema: 输出 Schema（可选）
            params: 模型参数（可选）
            metrics: 评估指标（可选）
            created_by: 创建人（可选）
            force: 是否为符合条件的已有版本创建下一制品修订

        返回：
            注册结果及当前制品标识、修订号和完整性摘要

        异常：
            ArtifactError: 模型制品处理失败
            ModelAlreadyExistsError: 版本已存在且未指定 force
            InvalidModelStateError: 已有版本不允许创建新制品修订
            ValueError: 已有模型注册新版本时尝试修改模型描述
        """
        model_id = generate_id(
            prefix="mdl",
            keys=(name,),
        )
        version_id = generate_id(
            prefix="ver",
            keys=(model_id, version),
        )
        path = Path(model_path)
        framework_value = Framework(framework.lower())
        model_type_value = ModelType(model_type.lower())
        task_type_value = TaskType(task_type.lower())
        framework_text = str(framework_value)

        if not path.is_file():
            raise ArtifactError(
                f"模型文件不存在: {model_path}"
            )

        data = self._read_artifact(path)
        model = self._load_artifact(
            data=data,
            framework=framework_text,
        )
        extracted_schema = SchemaExtractor.extract(
            model=model,
            framework=framework_text,
        )

        if input_schema is None:
            input_schema = extracted_schema

        sha256 = hashlib.sha256(data).hexdigest()
        digest = self._build_digest(
            framework=framework_text,
            sha256=sha256,
            input_schema=input_schema,
            output_schema=output_schema,
        )

        logger.info(
            "开始注册模型",
            model_id=model_id,
            version_id=version_id,
            name=name,
            version=version,
            force=force,
        )

        async with UnitOfWork() as uow:
            metadata_repo = MetadataRepository(uow.session)
            version_repo = VersionRepository(uow.session)
            artifact_repo = ArtifactRepository(uow.session)
            deployment_repo = DeploymentRepository(uow.session)

            metadata = await metadata_repo.get_model(
                model_id=model_id
            )
            existing_version = await version_repo.get_version_for_update(
                version_id
            )

            self._validate_metadata(
                metadata=metadata,
                name=name,
                description=description,
                is_new_version=existing_version is None,
            )

            current_artifact = None
            revision = 1

            if existing_version is not None:
                if getattr(
                        existing_version,
                        "deleted_at",
                        None,
                ) is not None:
                    raise InvalidModelStateError(
                        "已删除的模型版本不能重新注册，请先恢复版本"
                    )

                current_artifact = await artifact_repo.get_current_artifact(
                    version_id,
                    for_update=True,
                )
                current_digest = (
                    current_artifact.digest
                    if current_artifact is not None
                    else existing_version.artifact_digest
                )

                if current_digest == digest:
                    return self._build_result(
                        name=name,
                        version=version,
                        version_record=existing_version,
                        artifact=current_artifact,
                        action="unchanged",
                    )

                if not force:
                    raise ModelAlreadyExistsError(
                        "模型版本已存在；如需替换未发布制品，"
                        "请显式指定 force: "
                        f"{name}:{version}"
                    )

                await self._validate_force_registration(
                    version_record=existing_version,
                    deployment_repo=deployment_repo,
                )
                revision = int(
                    existing_version.artifact_revision or 1
                ) + 1

            artifact_id = generate_random_id(
                prefix="art"
            )
            model_key = self._save_artifact_object(
                uow=uow,
                model_id=model_id,
                version=version,
                artifact_id=artifact_id,
                filename=path.name,
                data=data,
            )

            input_schema_key = None

            if input_schema is not None:
                input_schema_key = self._save_artifact_object(
                    uow=uow,
                    model_id=model_id,
                    version=version,
                    artifact_id=artifact_id,
                    filename="input_schema.json",
                    data=self._encode_schema(input_schema),
                )

            output_schema_key = None

            if output_schema is not None:
                output_schema_key = self._save_artifact_object(
                    uow=uow,
                    model_id=model_id,
                    version=version,
                    artifact_id=artifact_id,
                    filename="output_schema.json",
                    data=self._encode_schema(output_schema),
                )

            resolved_model_path = StorageResolver().resolve(
                model_key
            )
            bento_model = self.backend.save(
                name=name,
                framework=framework_text,
                model=model,
                labels={
                    "model_id": model_id,
                    "version_id": version_id,
                    "artifact_id": artifact_id,
                    "revision": str(revision),
                    "model_type": str(model_type_value),
                    "task_type": str(task_type_value),
                    "framework": framework_text,
                    "version": version,
                    "sha256": sha256,
                },
            )
            bento_tag = str(bento_model.tag)
            uow.on_rollback(
                lambda tag=bento_tag: self._delete_bento_model(tag)
            )

            if metadata is None:
                metadata_repo.create_model(
                    model_id=model_id,
                    name=name,
                    model_type=model_type_value,
                    task_type=task_type_value,
                    framework=framework_value,
                    description=description,
                    created_by=created_by,
                )
            elif existing_version is None:
                metadata_repo.update_model(
                    metadata,
                    patch=MetadataPatch(
                        name=name,
                        model_type=model_type_value,
                        task_type=task_type_value,
                        framework=framework_value,
                    ),
                    updated_by=created_by,
                )

            if current_artifact is not None:
                artifact_repo.retire_artifact(
                    current_artifact,
                    retired_by=created_by,
                )
                await uow.session.flush()

            artifact = artifact_repo.create_artifact(
                artifact_id=artifact_id,
                version_id=version_id,
                revision=revision,
                sha256=sha256,
                digest=digest,
                source_path=str(path),
                model_key=model_key,
                input_schema_key=input_schema_key,
                output_schema_key=output_schema_key,
                bento_tag=bento_tag,
                created_by=created_by,
            )

            if existing_version is None:
                version_record = version_repo.create_version(
                    version_id=version_id,
                    model_id=model_id,
                    version=version,
                    framework=framework_value,
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
                    current_artifact_id=artifact_id,
                    artifact_revision=revision,
                    artifact_sha256=sha256,
                    artifact_digest=digest,
                )
                action = "created"
            else:
                version_record = version_repo.set_current_artifact(
                    existing_version,
                    artifact_id=artifact_id,
                    revision=revision,
                    sha256=sha256,
                    digest=digest,
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
                    updated_by=created_by,
                )
                action = "revised"

        logger.info(
            "模型注册完成",
            model_id=model_id,
            version_id=version_id,
            artifact_id=artifact_id,
            revision=revision,
            action=action,
        )

        return self._build_result(
            name=name,
            version=version,
            version_record=version_record,
            artifact=artifact,
            action=action,
        )

    @staticmethod
    def _read_artifact(path: Path) -> bytes:
        """读取模型制品"""
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ArtifactError(
                f"模型文件读取失败: {path}"
            ) from exc

    @staticmethod
    def _load_artifact(
            *,
            data: bytes,
            framework: str,
    ) -> Any:
        """加载并校验模型制品"""
        try:
            return ModelArtifactLoader.load(
                data=data,
                framework=framework,
            )
        except Exception as exc:
            raise ArtifactError(
                "模型文件加载失败"
            ) from exc

    @staticmethod
    def _build_digest(
            *,
            framework: str,
            sha256: str,
            input_schema: dict | None,
            output_schema: dict | None,
    ) -> str:
        """生成模型与 Schema 的组合摘要"""
        content = json.dumps(
            {
                "framework": framework.lower(),
                "sha256": sha256,
                "input_schema": input_schema,
                "output_schema": output_schema,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _encode_schema(schema: dict) -> bytes:
        """编码 Schema 文件"""
        return json.dumps(
            schema,
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

    def _save_artifact_object(
            self,
            *,
            uow: UnitOfWork,
            model_id: str,
            version: str,
            artifact_id: str,
            filename: str,
            data: bytes,
    ) -> str:
        """保存制品对象并注册事务回滚补偿"""
        key = self.storage.save(
            model_id,
            version,
            artifact_id,
            filename,
            data,
        )
        uow.on_rollback(
            lambda saved_key=key: self._delete_storage_key(saved_key)
        )

        return key

    @staticmethod
    def _validate_metadata(
            *,
            metadata: Any,
            name: str,
            description: str | None,
            is_new_version: bool,
    ) -> None:
        """校验模型元数据是否允许注册"""
        if metadata is None:
            return

        if MetadataStatus(metadata.status) == MetadataStatus.ARCHIVED:
            raise InvalidModelStateError(
                f"模型已归档，不允许注册制品: {name}"
            )

        if is_new_version and description is not None:
            raise ValueError(
                "模型已存在，注册新版本时不能修改模型描述"
            )

    @staticmethod
    async def _validate_force_registration(
            *,
            version_record: Any,
            deployment_repo: DeploymentRepository,
    ) -> None:
        """校验已有版本是否允许创建下一制品修订"""
        if VersionStatus(version_record.status) != VersionStatus.INACTIVE:
            raise InvalidModelStateError(
                "只有 inactive 模型版本允许强制注册新制品修订"
            )

        deployments = await deployment_repo.list_deployments(
            version_id=version_record.version_id
        )

        if deployments:
            raise InvalidModelStateError(
                "模型版本已有部署历史，不能强制注册新制品修订"
            )

    @staticmethod
    def _build_result(
            *,
            name: str,
            version: str,
            version_record: Any,
            artifact: Any,
            action: str,
    ) -> dict[str, Any]:
        """构造模型注册结果"""
        return {
            "name": name,
            "model_id": version_record.model_id,
            "version": version,
            "version_id": version_record.version_id,
            "artifact_id": (
                artifact.artifact_id
                if artifact is not None
                else version_record.current_artifact_id
            ),
            "artifact_revision": (
                artifact.revision
                if artifact is not None
                else version_record.artifact_revision
            ),
            "artifact_sha256": (
                artifact.sha256
                if artifact is not None
                else version_record.artifact_sha256
            ),
            "artifact_digest": (
                artifact.digest
                if artifact is not None
                else version_record.artifact_digest
            ),
            "bento_tag": version_record.bento_tag,
            "model_key": version_record.model_key,
            "model_path": version_record.model_path,
            "input_schema_key": version_record.input_schema_key,
            "output_schema_key": version_record.output_schema_key,
            "action": action,
        }

    def _delete_storage_key(self, key: str) -> None:
        """回滚注册过程中写入的存储对象"""
        self.storage.delete_by_key(
            key=key,
            strict=False,
        )

    @staticmethod
    def _delete_bento_model(tag: str) -> None:
        """回滚注册过程中写入的 BentoML 模型"""
        import bentoml

        for model in bentoml.models.list():
            if str(model.tag) == tag:
                bentoml.models.delete(model.tag)
                return
