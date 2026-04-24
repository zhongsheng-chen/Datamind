from datamind.models import ModelRegistry
from datamind.db.core.uow import UnitOfWork

registry = ModelRegistry()

with UnitOfWork() as uow:

    registry.register(
        uow=uow,

        model_id="mdl_8888",
        name="贷款评分卡模型",
        model_type="logistic_regression",
        task_type="scoring",
        framework="sklearn",

        version="v1",
        model_path="scorecard.pkl",

        description="首版评分卡",
        created_by="risk_team",
    )