# datamind/db/reader/experiment_reader.py

"""实验读取器

用于查询 A/B 实验或灰度策略的配置信息。

使用示例：
    reader = ExperimentReader(session)

    experiments = await reader.get_running_experiments("mdl_a1b2c3d4")
"""

from sqlalchemy import select

from datamind.db.models.experiments import Experiment
from datamind.db.readers.base_reader import BaseReader


class ExperimentReader(BaseReader):
    """实验读取器"""

    async def get_running_experiments(self, model_id: str) -> list[Experiment]:
        """获取运行中的实验

        参数：
            model_id: 模型 ID

        返回：
            运行中的实验列表
        """
        stmt = select(Experiment).where(
            Experiment.model_id == model_id,
            Experiment.status == "running",
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())