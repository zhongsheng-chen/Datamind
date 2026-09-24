"""实验手动分配配置测试.

验证客户映射更新时的字段校验和手动分配实验的启动约束。

核心功能：
  - test_update_manual_assignments:
    验证客户标识与目标分组校验及映射配置更新
  - test_start_rejects_invalid_manual_mapping:
    验证缺失、为空或格式无效的客户映射不能用于启动实验
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.experiment as module
from datamind.models.errors import InvalidExperimentConfigError
from datamind.services.experiment import ExperimentLifecycleService


@pytest.mark.asyncio
@pytest.mark.parametrize("mapping,valid", [
    ({"customer_001": "var_enabled"}, True),
    ({}, True),
    ({"": "var_enabled"}, False),
    ({" customer_001": "var_enabled"}, False),
    ({"customer_001": "var_foreign"}, False),
    ({"customer_001": "var_disabled"}, False),
])
async def test_update_manual_assignments(monkeypatch, mapping, valid):
    """测试草稿实验更新客户映射时校验客户标识和目标分组."""
    experiment = SimpleNamespace(
        experiment_id="exp_test", model_id="mdl_test", environment="development",
        name="manual-test", status="draft", config={"strategy": "manual"},
        effective_from=None, effective_to=None, description=None,
    )
    repository = MagicMock()
    repository.get_experiment = AsyncMock(return_value=experiment)
    def update(current, patch, **_kwargs):
        """模拟仓储更新实验配置."""
        current.config = patch.config
    repository.update_experiment.side_effect = update
    variants = MagicMock()
    variants.list_active_variants = AsyncMock(return_value=[SimpleNamespace(variant_id="var_enabled")])
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setitem(vars(module), "UnitOfWork", lambda: uow)
    monkeypatch.setitem(vars(module), "ExperimentRepository", lambda _session: repository)
    monkeypatch.setitem(vars(module), "VariantRepository", lambda _session: variants)
    service = ExperimentLifecycleService()
    if valid:
        result = await service.update_experiment(experiment_id="exp_test", manual_assignments=mapping)
        assert result["config"]["manual_assignments"] == mapping
    else:
        with pytest.raises(InvalidExperimentConfigError):
            await service.update_experiment(experiment_id="exp_test", manual_assignments=mapping)
        repository.update_experiment.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mapping", [None, {}, [], ["customer_001"], "var_enabled", 1])
async def test_start_rejects_invalid_manual_mapping(monkeypatch, mapping):
    """测试手动分配实验启动时拒绝缺失、为空或格式无效的客户映射."""
    repository = MagicMock()
    repository.get_experiment = AsyncMock(return_value=SimpleNamespace(
        experiment_id="exp_test", model_id="mdl_test", environment="development",
        status="draft", config={"strategy": "manual", "manual_assignments": mapping},
    ))
    repository.get_running_experiment = AsyncMock(return_value=None)
    variants = MagicMock()
    variants.list_active_variants = AsyncMock(return_value=[SimpleNamespace(variant_id="var_enabled")])
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setitem(vars(module), "UnitOfWork", lambda: uow)
    monkeypatch.setitem(vars(module), "ExperimentRepository", lambda _session: repository)
    monkeypatch.setitem(vars(module), "VariantRepository", lambda _session: variants)
    with pytest.raises(InvalidExperimentConfigError, match="指定客户|必须为"):
        await ExperimentLifecycleService().transition_experiment(
            experiment_id="exp_test", action="start",
        )
    repository.start_experiment.assert_not_called()
