# datamind/db/writer/experiment_writer.py

"""实验写入器

记录 A/B 实验或灰度策略的配置信息。

使用示例：
    writer = ExperimentWriter(session)

    await writer.write(
        experiment_id="exp_001",
        model_id="mdl_001",
        name="模型对比实验",
        config={"strategy": "WEIGHTED", "variants": [...]},
        created_by="system"
    )
"""

from datetime import datetime

from datamind.db.models.experiments import Experiment
from datamind.db.writer.base_writer import BaseWriter


class ExperimentWriter(BaseWriter):
    """实验写入器"""

    async def write(
        self,
        *,
        experiment_id: str,
        model_id: str,
        name: str,
        description: str = None,
        status: str = "running",
        config: dict = None,
        effective_from: datetime = None,
        effective_to: datetime = None,
        created_by: str = None,
    ) -> Experiment:
        """写入实验记录

        参数：
            experiment_id: 实验唯一标识
            model_id: 模型ID
            name: 实验名称
            description: 实验描述
            status: 实验状态
            config: 实验配置
            effective_from: 生效开始时间
            effective_to: 生效结束时间
            created_by: 创建人

        返回：
            实验对象
        """
        obj = Experiment(
            experiment_id=experiment_id,
            model_id=model_id,
            name=name,
            description=description,
            status=status,
            config=config,
            effective_from=effective_from,
            effective_to=effective_to,
            created_by=created_by,
        )

        self.add(obj)

        return obj