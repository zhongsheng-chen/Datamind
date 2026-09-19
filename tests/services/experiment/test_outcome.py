"""实验结果回流服务测试

验证结果回流的关联补齐、幂等更新和归属校验。

核心功能：
  - test_submit_creates_outcome_from_decision:
    验证根据原始决策创建结果
  - test_submit_updates_existing_outcome:
    验证相同 outcome_id 幂等更新
  - test_submit_rejects_mismatched_subject:
    验证拒绝主体不一致的结果
  - test_submit_requires_decision_or_request:
    验证必须提供决策或请求标识
  - test_submit_rejects_missing_decision:
    验证原始决策必须存在
  - test_submit_rejects_request_without_decision:
    验证原始请求必须存在决策记录
  - test_submit_rejects_conflicting_links:
    验证决策和请求必须指向同一记录
  - test_submit_rejects_reassigned_outcome:
    验证结果不能重新关联其他决策
  - test_submit_rejects_blank_required_fields:
    验证必填标识不能为空
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

import datamind.services.outcome as outcome_module
from datamind.db.models.decisions import Decision
from datamind.db.models.outcomes import Outcome
from datamind.services import OutcomeService


class FakeUnitOfWork:
    """实验结果服务测试工作单元"""

    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.flush = AsyncMock()
        self.session.refresh = AsyncMock()

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


def create_decision(
        *,
        decision_id: str = "dcs_test",
        request_id: str = "req_test",
) -> Decision:
    """创建原始决策测试对象"""
    return Decision(
        decision_id=decision_id,
        request_id=request_id,
        model_id="mdl_test",
        version_id="ver_test",
        deployment_id="dep_test",
        experiment_id="exp_test",
        variant_id="var_test",
        assignment_id="asn_test",
        subject_key="customer_10001",
        subject_type="customer",
        source="experiment",
    )


def configure_service(
        monkeypatch: pytest.MonkeyPatch,
        *,
        decision: Decision,
        outcome: Outcome | None = None,
) -> tuple[MagicMock, MagicMock]:
    """配置结果服务仓储替身"""
    decision_repo = MagicMock()
    decision_repo.get_by_decision_id = AsyncMock(
        return_value=decision
    )
    decision_repo.get_decision = AsyncMock(
        return_value=decision
    )
    outcome_repo = MagicMock()
    outcome_repo.get_outcome = AsyncMock(
        return_value=outcome
    )

    monkeypatch.setitem(
        vars(outcome_module),
        "UnitOfWork",
        FakeUnitOfWork,
    )
    monkeypatch.setitem(
        vars(outcome_module),
        "DecisionRepository",
        lambda _session: decision_repo,
    )
    monkeypatch.setitem(
        vars(outcome_module),
        "OutcomeRepository",
        lambda _session: outcome_repo,
    )

    return decision_repo, outcome_repo


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", ["decision_id", "request_id"])
async def test_submit_creates_outcome_from_decision(
        monkeypatch: pytest.MonkeyPatch,
        identifier: str,
) -> None:
    """测试根据原始决策创建结果并补齐实验关联"""
    decision = create_decision()
    decision_repo, outcome_repo = configure_service(
        monkeypatch,
        decision=decision,
    )
    outcome = Outcome(
        outcome_id="out_test",
        subject_key="customer_10001",
        decision_id="dcs_test",
        request_id="req_test",
        experiment_id="exp_test",
        variant_id="var_test",
        assignment_id="asn_test",
    )
    outcome_repo.create_outcome.return_value = outcome

    result = await OutcomeService().submit(
        outcome_id="out_test",
        **{identifier: getattr(decision, identifier)},
        subject_key="customer_10001",
        converted=True,
    )

    assert result["created"] is True
    if identifier == "request_id":
        decision_repo.get_decision.assert_awaited_once_with("req_test")
        decision_repo.get_by_decision_id.assert_not_awaited()
    outcome_repo.create_outcome.assert_called_once_with(
        outcome_id="out_test",
        subject_key="customer_10001",
        experiment_id="exp_test",
        variant_id="var_test",
        assignment_id="asn_test",
        decision_id="dcs_test",
        request_id="req_test",
        subject_type="customer",
        approved=None,
        converted=True,
        defaulted=None,
        overdue_days=None,
        amount=None,
        label=None,
        context=None,
        outcome_time=None,
    )


@pytest.mark.asyncio
async def test_submit_updates_existing_outcome(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试相同 outcome_id 幂等更新业务结果"""
    decision = create_decision()
    outcome = Outcome(
        outcome_id="out_test",
        subject_key="customer_10001",
        decision_id="dcs_test",
        request_id="req_test",
    )
    _, outcome_repo = configure_service(
        monkeypatch,
        decision=decision,
        outcome=outcome,
    )
    outcome_repo.update_outcome.return_value = outcome

    result = await OutcomeService().submit(
        outcome_id="out_test",
        request_id="req_test",
        subject_key="customer_10001",
        defaulted=True,
        overdue_days=35,
    )

    assert result["created"] is False
    outcome_repo.create_outcome.assert_not_called()
    outcome_repo.update_outcome.assert_called_once()


@pytest.mark.asyncio
async def test_submit_rejects_mismatched_subject(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试拒绝主体与原始决策不一致的结果"""
    decision = create_decision()
    configure_service(
        monkeypatch,
        decision=decision,
    )

    with pytest.raises(
            ValueError,
            match="subject_key 与原始决策不一致",
    ):
        await OutcomeService().submit(
            outcome_id="out_test",
            decision_id="dcs_test",
            subject_key="customer_other",
        )


@pytest.mark.asyncio
async def test_submit_requires_decision_or_request() -> None:
    """测试结果回流必须提供决策或请求标识"""
    with pytest.raises(
            ValueError,
            match="至少需要提供一个",
    ):
        await OutcomeService().submit(
            outcome_id="out_test",
            subject_key="customer_10001",
        )


@pytest.mark.asyncio
async def test_submit_rejects_missing_decision(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试原始决策不存在时拒绝结果回流"""
    decision_repo, outcome_repo = configure_service(
        monkeypatch,
        decision=create_decision(),
    )
    decision_repo.get_by_decision_id.return_value = None

    with pytest.raises(
            ValueError,
            match="原始决策不存在",
    ):
        await OutcomeService().submit(
            outcome_id="out_test",
            decision_id="dcs_missing",
            subject_key="customer_10001",
        )

    outcome_repo.get_outcome.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_rejects_request_without_decision(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试原始请求没有决策记录时拒绝结果回流"""
    decision_repo, outcome_repo = configure_service(
        monkeypatch,
        decision=create_decision(),
    )
    decision_repo.get_decision.return_value = None

    with pytest.raises(
            ValueError,
            match="原始请求没有决策记录",
    ):
        await OutcomeService().submit(
            outcome_id="out_test",
            request_id="req_missing",
            subject_key="customer_10001",
        )

    outcome_repo.get_outcome.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_rejects_conflicting_links(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试决策和请求指向不同记录时拒绝回流"""
    decision_repo, outcome_repo = configure_service(
        monkeypatch,
        decision=create_decision(),
    )
    decision_repo.get_decision.return_value = create_decision(
        decision_id="dcs_other",
        request_id="req_other",
    )

    with pytest.raises(
            ValueError,
            match="指向不同决策",
    ):
        await OutcomeService().submit(
            outcome_id="out_test",
            decision_id="dcs_test",
            request_id="req_other",
            subject_key="customer_10001",
        )

    outcome_repo.get_outcome.assert_not_awaited()


@pytest.mark.asyncio
async def test_submit_rejects_reassigned_outcome(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已有结果不能重新关联其他决策"""
    outcome = Outcome(
        outcome_id="out_test",
        subject_key="customer_10001",
        decision_id="dcs_other",
        request_id="req_other",
    )
    _, outcome_repo = configure_service(
        monkeypatch,
        decision=create_decision(),
        outcome=outcome,
    )

    with pytest.raises(
            ValueError,
            match="已关联其他决策",
    ):
        await OutcomeService().submit(
            outcome_id="out_test",
            decision_id="dcs_test",
            subject_key="customer_10001",
        )

    outcome_repo.update_outcome.assert_not_called()


@pytest.mark.asyncio
async def test_submit_rejects_reassigned_subject(
        monkeypatch: pytest.MonkeyPatch,
) -> None:
    """测试已有结果不能重新关联其他主体"""
    outcome = Outcome(
        outcome_id="out_test",
        subject_key="customer_other",
        decision_id="dcs_test",
        request_id="req_test",
    )
    _, outcome_repo = configure_service(
        monkeypatch,
        decision=create_decision(),
        outcome=outcome,
    )

    with pytest.raises(
            ValueError,
            match="已关联其他主体",
    ):
        await OutcomeService().submit(
            outcome_id="out_test",
            decision_id="dcs_test",
            subject_key="customer_10001",
        )

    outcome_repo.update_outcome.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "outcome_id": " ",
                "subject_key": "customer_10001",
                "decision_id": "dcs_test",
            },
            "outcome_id 不能为空",
        ),
        (
            {
                "outcome_id": "out_test",
                "subject_key": " ",
                "decision_id": "dcs_test",
            },
            "subject_key 不能为空",
        ),
    ],
)
async def test_submit_rejects_blank_required_fields(
        kwargs: dict[str, str],
        message: str,
) -> None:
    """测试结果和主体标识不能为空"""
    with pytest.raises(
            ValueError,
            match=message,
    ):
        await OutcomeService().submit(
            **kwargs
        )
