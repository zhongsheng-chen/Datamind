"""模型注册服务测试

验证首次注册、幂等注册、受控制修订和回滚补偿。

核心功能：
  - test_register_creates_model_version_and_artifact:
    验证首次注册及已有模型注册新版本
  - test_register_returns_unchanged_for_same_digest:
    验证相同摘要幂等返回
  - test_save_artifact_registers_rollback_cleanup:
    验证存储写入注册回滚补偿
  - test_register_rejects_existing_version:
    验证拒绝覆盖不符合修订条件的已有版本
  - test_register_force_creates_new_artifact_revision:
    验证 force 为未发布版本创建新制品修订
  - test_force_validation_rejects_deployment_history:
    验证存在部署历史时拒绝 force
  - test_registration_wraps_artifact_errors:
    验证统一转换制品读取和加载异常
  - test_validate_metadata_rejects_invalid_registration:
    验证拒绝归档模型和非法元数据修改
"""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.registration as register_module
from datamind.db.models.versions import Version
from datamind.models.artifact import ModelArtifactLoader
from datamind.models.errors import (
    ArtifactError,
    InvalidModelStateError,
    ModelAlreadyExistsError,
)
from datamind.models.schema import SchemaExtractor
from datamind.models.inspection import ScorecardInspector
from datamind.services import ModelRegistrationService


class FakeUnitOfWork:
    """注册服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.flush = AsyncMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False

    def on_rollback(self, _callback: object) -> None:
        """记录回滚补偿"""


@pytest.fixture(autouse=True)
def configure_scorecard_details(
        monkeypatch: pytest.MonkeyPatch,
) -> MagicMock:
    """配置评分卡详情提取与仓储替身"""
    repository = MagicMock()
    repository.get_scorecard = AsyncMock(return_value=None)
    monkeypatch.setattr(
        ScorecardInspector,
        "extract",
        lambda _model: {"schema": "scorecard"},
    )
    monkeypatch.setitem(
        vars(register_module),
        "ScorecardRepository",
        lambda _session: repository,
    )
    return repository


@pytest.mark.asyncio
async def test_register_rejects_invalid_semantic_version(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝不符合语义化版本规范的模型版本"""
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        MagicMock(),
    )
    with pytest.raises(
            ValueError,
            match=(
                "无效的模型版本「latest」，"
                "请输入主版本.次版本.修订版本，"
                "例如 1.0.0"
            ),
    ):
        await ModelRegistrationService().register(
            name="scorecard",
            version="latest",
            model_path=str(Path(__file__)),
            framework="sklearn",
            model_type="logistic_regression",
            task_type="scoring",
        )


@pytest.mark.asyncio
async def test_register_rejects_invalid_model_name(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试在处理制品前拒绝无效的模型机器名称"""
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        MagicMock(),
    )
    with pytest.raises(
            ValueError,
            match="无效的模型名称",
    ):
        await ModelRegistrationService().register(
            name="中文模型",
            version="1.0.0",
            framework="sklearn",
            model_type="logistic_regression",
            task_type="scoring",
            model_path="missing.pkl",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "existing_model",
    [
        False,
        True,
    ],
)
async def test_register_creates_model_version_and_artifact(
        monkeypatch: pytest.MonkeyPatch,
        existing_model: bool,
        configure_scorecard_details: MagicMock,
) -> None:
    """测试注册创建模型版本及制品记录"""
    model_path = Path(__file__)
    storage = MagicMock()
    storage.save.return_value = (
        "models/mdl_test/1.0.0/"
        "artifacts/art_test/test_registration.py"
    )
    backend = MagicMock()
    backend.save.return_value = SimpleNamespace(
        tag="scorecard:created"
    )
    metadata_repo = MagicMock()
    metadata_repo.get_model = AsyncMock(
        return_value=(
            SimpleNamespace(status="active")
            if existing_model
            else None
        )
    )
    version_repo = MagicMock()
    version_repo.get_version_for_update = AsyncMock(
        return_value=None
    )
    version_repo.create_version.side_effect = (
        lambda **values: SimpleNamespace(**values)
    )
    artifact_repo = MagicMock()
    artifact_repo.create_artifact.side_effect = (
        lambda **values: SimpleNamespace(**values)
    )
    deployment_repo = MagicMock()

    monkeypatch.setitem(
        vars(register_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(register_module),
        "BentoBackend",
        lambda: backend,
    )
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        SchemaExtractor,
        "extract",
        lambda **_kwargs: None,
    )
    monkeypatch.setitem(
        vars(register_module),
        "generate_id",
        lambda *, prefix, keys: (
            "mdl_test"
            if prefix == "mdl"
            else "ver_test"
        ),
    )
    monkeypatch.setitem(
        vars(register_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_test",
    )
    monkeypatch.setitem(
        vars(register_module),
        "MetadataRepository",
        lambda _session: metadata_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "VersionRepository",
        lambda _session: version_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "ArtifactRepository",
        lambda _session: artifact_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "StorageResolver",
        lambda: SimpleNamespace(
            resolve=lambda key: f"storage://{key}"
        ),
    )

    result = await ModelRegistrationService().register(
        name="scorecard",
        version="1.0.0",
        framework="sklearn",
        model_type="logistic_regression",
        task_type="scoring",
        model_path=str(model_path),
        created_by="operator",
    )

    assert result["action"] == "created"
    assert result["model_id"] == "mdl_test"
    assert result["version_id"] == "ver_test"
    assert result["artifact_id"] == "art_test"
    assert result["artifact_revision"] == 1
    if existing_model:
        metadata_repo.create_model.assert_not_called()
        metadata_repo.update_model.assert_called_once()
    else:
        metadata_repo.create_model.assert_called_once()
        metadata_repo.update_model.assert_not_called()

    version_repo.create_version.assert_called_once()
    artifact_repo.create_artifact.assert_called_once()
    configure_scorecard_details.create_scorecard.assert_called_once_with(
        scorecard_id="scr_test",
        version_id="ver_test",
        details={"schema": "scorecard"},
    )
    assert [
        call.args[3]
        for call in storage.save.call_args_list
    ] == [
        "test_registration.py",
    ]
    backend.save.assert_called_once()
    save_kwargs = backend.save.call_args.kwargs
    assert save_kwargs["name"] == "scorecard"
    assert "name" not in save_kwargs["labels"]


@pytest.mark.parametrize(
    "force",
    [False, True],
)
@pytest.mark.asyncio
async def test_register_returns_unchanged_for_same_digest(
        monkeypatch: pytest.MonkeyPatch,
        force: bool,
) -> None:
    """测试已有版本制品摘要相同时始终幂等返回"""
    model_path = Path(__file__)
    storage = MagicMock()
    backend = MagicMock()
    metadata = SimpleNamespace(status="active")
    version_record = SimpleNamespace(
        model_id="mdl_test",
        version_id="ver_test",
        deleted_at=None,
        artifact_digest="same-digest",
        current_artifact_id="art_test",
        artifact_revision=1,
        artifact_sha256="sha256",
        bento_tag="scorecard:existing",
        model_key="models/model.pkl",
        model_path="storage://models/model.pkl",
    )
    artifact = SimpleNamespace(
        artifact_id="art_test",
        revision=1,
        sha256="sha256",
        digest="same-digest",
    )
    metadata_repo = MagicMock()
    metadata_repo.get_model = AsyncMock(
        return_value=metadata
    )
    version_repo = MagicMock()
    version_repo.get_version_for_update = AsyncMock(
        return_value=version_record
    )
    artifact_repo = MagicMock()
    artifact_repo.get_current_artifact = AsyncMock(
        return_value=artifact
    )

    monkeypatch.setitem(
        vars(register_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(register_module),
        "BentoBackend",
        lambda: backend,
    )
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        SchemaExtractor,
        "extract",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        ModelRegistrationService,
        "_build_digest",
        staticmethod(
            lambda **_kwargs: "same-digest"
        ),
    )
    monkeypatch.setitem(
        vars(register_module),
        "generate_id",
        lambda *, prefix, keys: (
            "mdl_test"
            if prefix == "mdl"
            else "ver_test"
        ),
    )
    monkeypatch.setitem(
        vars(register_module),
        "MetadataRepository",
        lambda _session: metadata_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "VersionRepository",
        lambda _session: version_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "ArtifactRepository",
        lambda _session: artifact_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "DeploymentRepository",
        lambda _session: MagicMock(),
    )

    result = await ModelRegistrationService().register(
        name="scorecard",
        version="1.0.0",
        framework="sklearn",
        model_type="logistic_regression",
        task_type="scoring",
        model_path=str(model_path),
        force=force,
    )

    assert result["action"] == "unchanged"
    assert result["artifact_id"] == "art_test"
    storage.save.assert_not_called()
    backend.save.assert_not_called()
    artifact_repo.create_artifact.assert_not_called()


def test_save_artifact_registers_rollback_cleanup(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试保存制品后注册存储回滚补偿"""
    storage = MagicMock()
    storage.save.return_value = "models/model.pkl"
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(register_module),
        "BentoBackend",
        MagicMock(),
    )
    service = ModelRegistrationService()
    uow = MagicMock()

    key = service._save_artifact_object(
        uow=uow,
        model_name="scorecard",
        version="1.0.0",
        artifact_id="art_test",
        filename="model.pkl",
        data=b"model",
    )

    assert key == "models/model.pkl"
    rollback_call = uow.on_rollback.call_args
    assert rollback_call is not None
    callback = rollback_call.args[0]
    assert callable(callback)
    callback()
    storage.delete_by_key.assert_called_once_with(
        key="models/model.pkl",
        strict=False,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "force",
        "status",
        "deleted_at",
        "message",
    ),
    [
        (
            False,
            "inactive",
            None,
            "请创建新的制品修订",
        ),
        (
            True,
            "active",
            None,
            "inactive",
        ),
        (
            True,
            "inactive",
            object(),
            "已删除",
        ),
    ],
)
async def test_register_rejects_existing_version(
        monkeypatch: pytest.MonkeyPatch,
        force: bool,
        status: str,
        deleted_at: object | None,
        message: str,
) -> None:
    """测试拒绝覆盖不符合制品修订条件的已有版本"""
    model_path = Path(__file__)
    storage = MagicMock()
    backend = MagicMock()
    metadata_repo = MagicMock()
    metadata_repo.get_model = AsyncMock(
        return_value=SimpleNamespace(status="active")
    )
    version_repo = MagicMock()
    version_repo.get_version_for_update = AsyncMock(
        return_value=SimpleNamespace(
            version_id="ver_test",
            status=status,
            deleted_at=deleted_at,
            artifact_digest="old-digest",
        )
    )
    artifact_repo = MagicMock()
    artifact_repo.get_current_artifact = AsyncMock(return_value=None)
    deployment_repo = MagicMock()

    monkeypatch.setitem(
        vars(register_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(register_module),
        "BentoBackend",
        lambda: backend,
    )
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        SchemaExtractor,
        "extract",
        lambda **_kwargs: None,
    )
    monkeypatch.setitem(
        vars(register_module),
        "MetadataRepository",
        lambda _session: metadata_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "VersionRepository",
        lambda _session: version_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "ArtifactRepository",
        lambda _session: artifact_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )

    service = ModelRegistrationService()

    error_type = (
        InvalidModelStateError
        if force
        else ModelAlreadyExistsError
    )

    with pytest.raises(error_type, match=message):
        await service.register(
            name="scorecard",
            version="1.0.0",
            framework="sklearn",
            model_type="logistic_regression",
            task_type="scoring",
            model_path=str(model_path),
            force=force,
        )

    storage.save.assert_not_called()
    backend.save.assert_not_called()


@pytest.mark.asyncio
async def test_register_force_creates_new_artifact_revision(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试 force 为内容变化的未发布版本创建新制品修订"""
    model_path = Path(__file__)
    current_digest = "old-digest"
    metadata = SimpleNamespace(status="active")
    version = SimpleNamespace(
        model_id="mdl_test",
        version_id="ver_test",
        status="inactive",
        deleted_at=None,
        artifact_revision=1,
        artifact_digest=current_digest,
    )
    current = SimpleNamespace(
        artifact_id="art_old",
        digest=current_digest,
        status="active",
    )
    storage = MagicMock()
    storage.save.side_effect = (
        lambda model_id, model_version, artifact_id, filename, _data: (
            "model_registry/"
            f"{model_id}/{model_version}/artifacts/"
            f"{artifact_id}/{filename}"
        )
    )
    backend = MagicMock()
    backend.save.return_value = SimpleNamespace(
        tag="scorecard:new"
    )
    metadata_repo = MagicMock()
    metadata_repo.get_model = AsyncMock(return_value=metadata)
    version_repo = MagicMock()
    version_repo.get_version_for_update = AsyncMock(return_value=version)
    artifact_repo = MagicMock()
    artifact_repo.get_current_artifact = AsyncMock(return_value=current)
    artifact_repo.create_artifact.side_effect = (
        lambda **values: SimpleNamespace(**values)
    )
    deployment_repo = MagicMock()
    deployment_repo.list_deployments = AsyncMock(return_value=[])

    def set_current_artifact(
            record: Any,
            **values: Any,
    ) -> Any:
        record.current_artifact_id = values["artifact_id"]
        record.artifact_revision = values["revision"]
        record.artifact_sha256 = values["sha256"]
        record.artifact_digest = values["digest"]
        record.bento_tag = values["bento_tag"]
        record.model_key = values["model_key"]
        record.model_path = values["model_path"]
        return record

    version_repo.set_current_artifact.side_effect = set_current_artifact
    monkeypatch.setitem(
        vars(register_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        lambda: storage,
    )
    monkeypatch.setitem(
        vars(register_module),
        "BentoBackend",
        lambda: backend,
    )
    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        SchemaExtractor,
        "extract",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        ModelRegistrationService,
        "_build_digest",
        staticmethod(
            lambda **_kwargs: "same-digest"
        ),
    )
    monkeypatch.setitem(
        vars(register_module),
        "generate_id",
        lambda *, prefix, keys: (
            "mdl_test" if prefix == "mdl" else "ver_test"
        ),
    )
    monkeypatch.setitem(
        vars(register_module),
        "generate_random_id",
        lambda *, prefix: f"{prefix}_new",
    )
    monkeypatch.setitem(
        vars(register_module),
        "MetadataRepository",
        lambda _session: metadata_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "VersionRepository",
        lambda _session: version_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "ArtifactRepository",
        lambda _session: artifact_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "DeploymentRepository",
        lambda _session: deployment_repo,
    )
    monkeypatch.setitem(
        vars(register_module),
        "StorageResolver",
        lambda: SimpleNamespace(resolve=lambda key: f"storage://{key}"),
    )

    result = await ModelRegistrationService().register(
        name="scorecard",
        version="1.0.0",
        framework="sklearn",
        model_type="logistic_regression",
        task_type="scoring",
        model_path=str(model_path),
        force=True,
    )

    assert result["action"] == "revised"
    assert result["artifact_id"] == "art_new"
    assert result["artifact_revision"] == 2
    artifact_repo.retire_artifact.assert_called_once_with(
        current,
        retired_by=None,
    )
    deployment_repo.list_deployments.assert_awaited_once_with(
        version_id="ver_test"
    )
    assert storage.save.call_count == 1
    saved_call = storage.save.call_args
    assert saved_call is not None
    assert saved_call.args[:4] == (
            "scorecard",
        "1.0.0",
        "art_new",
        "test_registration.py",
    )


@pytest.mark.asyncio
async def test_force_validation_rejects_deployment_history() -> None:
    """测试存在部署历史时拒绝强制注册"""
    deployment_repo = MagicMock()
    deployment_repo.list_deployments = AsyncMock(
        return_value=[SimpleNamespace(deployment_id="dep_test")]
    )
    version = Version(
        version_id="ver_test",
        status="inactive",
    )

    with pytest.raises(InvalidModelStateError, match="部署历史"):
        await ModelRegistrationService._validate_force_registration(
            version_record=version,
            deployment_repo=deployment_repo,
        )


@pytest.mark.asyncio
async def test_register_rejects_missing_model_file(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试注册前拒绝不存在的模型文件"""
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        MagicMock(),
    )
    monkeypatch.setitem(
        vars(register_module),
        "BentoBackend",
        MagicMock(),
    )

    with pytest.raises(
            ArtifactError,
            match="模型文件不存在",
    ):
        await ModelRegistrationService().register(
            name="scorecard",
            version="1.0.0",
            framework="sklearn",
            model_type="logistic_regression",
            task_type="scoring",
            model_path=str(tmp_path / "missing.pkl"),
        )


def test_registration_wraps_artifact_errors(
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
) -> None:
    """测试统一转换模型文件读取和加载异常"""
    test_logger = MagicMock()
    monkeypatch.setattr(
        register_module,
        "logger",
        test_logger,
    )

    with pytest.raises(
            ArtifactError,
            match="模型文件读取失败",
    ):
        ModelRegistrationService._read_artifact(
            tmp_path
        )

    def raise_load_error(**_kwargs: Any) -> object:
        raise ValueError("invalid artifact")

    monkeypatch.setattr(
        ModelArtifactLoader,
        "load",
        raise_load_error,
    )

    with pytest.raises(
            ArtifactError,
            match="模型文件加载失败",
    ):
        ModelRegistrationService._load_artifact(
            data=b"invalid",
            framework="sklearn",
        )

    read_log = test_logger.exception.call_args_list[0]
    assert read_log.args == ("模型文件读取失败",)
    assert read_log.kwargs["model_path"] == str(tmp_path)
    assert read_log.kwargs["error_type"] in {
        "IsADirectoryError",
        "PermissionError",
    }
    assert read_log.kwargs["error_message"]

    load_log = test_logger.exception.call_args_list[1]
    assert load_log.args == ("模型文件加载失败",)
    assert load_log.kwargs == {
        "framework": "sklearn",
        "error_type": "ValueError",
        "error_message": "invalid artifact",
    }


@pytest.mark.parametrize(
    (
        "status",
        "description",
        "is_new_version",
        "error_type",
        "message",
    ),
    [
        (
            "archived",
            None,
            False,
            InvalidModelStateError,
            "模型已归档，不允许注册模型版本",
        ),
        (
            "active",
            "新描述",
            True,
            ValueError,
            "不能修改模型描述",
        ),
    ],
)
def test_validate_metadata_rejects_invalid_registration(
        status: str,
        description: str | None,
        is_new_version: bool,
        error_type: type[Exception],
        message: str,
) -> None:
    """测试拒绝归档模型和已有模型描述变更"""
    metadata = SimpleNamespace(
        status=status,
        description=None,
    )

    with pytest.raises(error_type, match=message):
        ModelRegistrationService._validate_metadata(
            metadata=metadata,
            name="scorecard",
            description=description,
            is_new_version=is_new_version,
        )


def test_validate_metadata_accepts_unchanged_description() -> None:
    """测试注册新版本时允许重复提供相同模型描述"""
    ModelRegistrationService._validate_metadata(
        metadata=SimpleNamespace(
            status="inactive",
            description="信用评分卡模型",
        ),
        name="scorecard",
        description="信用评分卡模型",
        is_new_version=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "framework, model_type",
    [
        ("sklearn", "decision_tree"),
        ("sklearn", "random_forest"),
        ("xgboost", "xgboost"),
        ("lightgbm", "lightgbm"),
        ("catboost", "catboost"),
    ],
)
async def test_register_rejects_scoring_for_non_logistic_model(
        monkeypatch: pytest.MonkeyPatch,
        framework: str,
        model_type: str,
) -> None:
    """测试只有逻辑回归模型允许注册评分任务"""
    monkeypatch.setitem(
        vars(register_module),
        "get_storage",
        MagicMock(),
    )

    with pytest.raises(
            ValueError,
            match=(
                "只有逻辑回归模型支持评分任务，"
                f"模型类型 {model_type} 只能执行分类任务"
            ),
    ):
        await ModelRegistrationService().register(
            name="risk-model",
            version="1.0.0",
            framework=framework,
            model_type=model_type,
            task_type="scoring",
            model_path="missing.model",
        )


@pytest.mark.parametrize(
    "matching_model",
    [
        False,
        True,
    ],
)
def test_delete_bento_model_is_idempotent(
        monkeypatch: pytest.MonkeyPatch,
        matching_model: bool,
) -> None:
    """测试回滚时幂等删除匹配的 BentoML 模型"""
    model = SimpleNamespace(
        tag=(
            "scorecard:target"
            if matching_model
            else "scorecard:other"
        )
    )
    delete_model = MagicMock()
    bento_module = ModuleType(
        "bentoml"
    )
    setattr(
        bento_module,
        "models",
        SimpleNamespace(
            list=MagicMock(return_value=[model]),
            delete=delete_model,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "bentoml",
        bento_module,
    )

    ModelRegistrationService._delete_bento_model(
        "scorecard:target"
    )

    if matching_model:
        delete_model.assert_called_once_with(
            model.tag
        )
    else:
        delete_model.assert_not_called()
