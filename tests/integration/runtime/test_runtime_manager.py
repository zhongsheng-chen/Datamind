"""运行时管理器生命周期集成测试

通过真实 PostgreSQL、模型制品、BentoML Model Store 与运行时注册表，
验证部署加载、幂等加载、卸载以及关键异常分支的完整边界。

核心功能：
  - test_runtime_manager_loads_reuses_and_unloads_deployment:
    验证运行时管理器的正常生命周期
  - test_runtime_manager_rejects_unknown_deployment:
    验证不存在的部署无法加载
  - test_runtime_manager_rejects_inactive_deployment:
    验证未启用的部署无法加载
  - test_runtime_manager_reports_missing_or_invalid_artifact:
    验证制品缺失或损坏时加载失败
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
import uuid

import bentoml
import joblib
import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression

from datamind.models.errors import (
    BackendError,
    DeploymentNotFoundError,
    InvalidDeploymentStateError,
)
from datamind.runtime.manager import RuntimeManager
from datamind.storage import get_storage


pytestmark = pytest.mark.integration


@pytest.fixture
async def isolated_runtime_environment(
    datamind_database: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[Path]:
    """配置当前测试独享的制品目录与 BentoML Model Store"""
    assert datamind_database is not None

    monkeypatch.setenv("DATAMIND_STORAGE_TYPE", "local")
    monkeypatch.setenv(
        "DATAMIND_STORAGE_LOCAL_BASE_DIR",
        str(tmp_path / "storage"),
    )
    monkeypatch.setenv("BENTOML_HOME", str(tmp_path / "bentoml"))
    get_storage.cache_clear()

    try:
        yield tmp_path
    finally:
        get_storage.cache_clear()


def write_classification_model(path: Path) -> Path:
    """训练并写入可由注册服务加载的真实分类模型"""
    features = np.asarray(
        [
            [-2.0, -1.0],
            [-1.0, -0.5],
            [0.5, 0.8],
            [1.5, 2.0],
        ]
    )
    labels = np.asarray([0, 0, 1, 1])
    model = LogisticRegression(random_state=0).fit(features, labels)

    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    return path


async def create_deployment(
    tmp_path: Path,
    *,
    enabled: bool,
) -> dict[str, str]:
    """通过真实业务服务注册模型并创建部署"""
    from datamind.services import (
        DeploymentLifecycleService,
        ModelLifecycleService,
        ModelRegistrationService,
    )

    name = f"runtime-integration-{uuid.uuid4().hex[:12]}"
    registration = await ModelRegistrationService().register(
        name=name,
        version="1.0.0",
        framework="sklearn",
        model_type="logistic_regression",
        task_type="classification",
        model_path=str(
            write_classification_model(tmp_path / f"{name}.pkl")
        ),
        created_by="integration-test",
    )
    await ModelLifecycleService().activate(
        model_id=registration["model_id"],
        version_id=registration["version_id"],
        updated_by="integration-test",
    )

    deployment = await DeploymentLifecycleService().create_deployment(
        model_id=registration["model_id"],
        version_id=registration["version_id"],
        environment="testing",
        deployed_by="integration-test",
    )

    if enabled:
        await DeploymentLifecycleService().enable_deployment(
            deployment_id=deployment["deployment_id"],
            updated_by="integration-test",
        )

    bentoml.models.delete(registration["bento_tag"])

    return {
        "deployment_id": deployment["deployment_id"],
        "model_key": registration["model_key"],
    }


@pytest.mark.asyncio
async def test_runtime_manager_loads_reuses_and_unloads_deployment(
    isolated_runtime_environment: Path,
) -> None:
    """测试真实部署可加载、重复加载并从注册表卸载"""
    deployment = await create_deployment(
        isolated_runtime_environment,
        enabled=True,
    )
    manager = RuntimeManager(worker_id="integration-worker")

    loaded = await manager.load(
        deployment["deployment_id"],
        operator="integration-test",
    )
    reused = await manager.load(
        deployment["deployment_id"],
        operator="integration-test",
    )

    probability = loaded.model.predict_proba([[0.75, 1.25]])[0, 1]
    status = await manager.get_status(deployment["deployment_id"])

    assert 0.0 <= probability <= 1.0
    assert reused is loaded
    assert manager.registry.get(
        deployment["deployment_id"],
        touch=False,
    ) is loaded
    assert status["loaded_in_memory"] is True
    assert status["runtime"]["status"] == "running"

    unloaded = await manager.unload(
        deployment["deployment_id"],
        operator="integration-test",
    )
    stopped = await manager.get_status(deployment["deployment_id"])

    assert unloaded is loaded
    assert deployment["deployment_id"] not in manager.registry
    assert stopped["loaded_in_memory"] is False
    assert stopped["runtime"]["status"] == "stopped"


@pytest.mark.asyncio
async def test_runtime_manager_rejects_unknown_deployment(
    isolated_runtime_environment: Path,
) -> None:
    """测试运行时管理器拒绝不存在的部署"""
    manager = RuntimeManager(worker_id="integration-worker")

    with pytest.raises(
        DeploymentNotFoundError,
        match="部署不存在",
    ):
        await manager.load("dep_missing")


@pytest.mark.asyncio
async def test_runtime_manager_rejects_inactive_deployment(
    isolated_runtime_environment: Path,
) -> None:
    """测试运行时管理器拒绝未启用的部署"""
    deployment = await create_deployment(
        isolated_runtime_environment,
        enabled=False,
    )
    manager = RuntimeManager(worker_id="integration-worker")

    with pytest.raises(
        InvalidDeploymentStateError,
        match="部署不是启用状态",
    ):
        await manager.load(deployment["deployment_id"])


@pytest.mark.asyncio
@pytest.mark.parametrize("artifact_state", ["missing", "invalid"])
async def test_runtime_manager_reports_missing_or_invalid_artifact(
    isolated_runtime_environment: Path,
    artifact_state: str,
) -> None:
    """测试运行时管理器将制品读取或解析失败包装为后端错误"""
    deployment = await create_deployment(
        isolated_runtime_environment,
        enabled=True,
    )
    storage = get_storage()

    if artifact_state == "missing":
        storage.delete_by_key(
            deployment["model_key"],
            strict=True,
        )
    else:
        storage.save_by_key(
            deployment["model_key"],
            b"not-a-valid-model-artifact",
        )

    manager = RuntimeManager(worker_id="integration-worker")

    with pytest.raises(
        BackendError,
        match="模型加载失败",
    ):
        await manager.load(deployment["deployment_id"])

    assert deployment["deployment_id"] not in manager.registry

    status = await manager.get_status(deployment["deployment_id"])
    assert status["runtime"]["status"] == "failed"
