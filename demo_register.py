# main.py
from datamind.config import get_settings
from datamind.logging import setup_logging, get_logger
from datamind.models import ModelRegistry
from datamind.db.core.uow import UnitOfWork


def main():
    # 1. 初始化日志
    settings = get_settings()
    setup_logging(settings.logging)
    print(__name__)
    logger = get_logger("datamind")
    logger.info("开始注册模型")

    # 2. 创建 registry
    registry = ModelRegistry()

    # 3. 使用 UoW 注册模型
    with UnitOfWork() as uow:

        registry.register(
            uow=uow,

            model_id="mdl_8888",
            name="贷款评分卡模型",
            model_type="logistic_regression",
            task_type="scoring",
            framework="sklearn",

            version="v1",
            model_path="datamind/demo/scorecard.pkl",

            description="首版评分卡",
            created_by="risk_team",
        )

    logger.info("模型注册完成")


if __name__ == "__main__":
    main()