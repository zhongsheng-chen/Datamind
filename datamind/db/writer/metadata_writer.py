# datamind/db/writer/metadata_writer.py

"""模型元数据写入器

记录模型的元数据定义信息。

使用示例：
    writer = MetadataWriter(session)

    await writer.create(
        model_id="mdl_a1b2c3d4",
        name="demo_scorecard",
        model_type="logistic_regression",
        task_type="scoring",
        framework="sklearn",
        description="基于逻辑回归的信用评分模型"
    )
"""

from datamind.db.models.metadata import Metadata
from datamind.db.writer.base_writer import BaseWriter


class MetadataWriter(BaseWriter):
    """模型元数据写入器"""

    async def create(
        self,
        *,
        model_id: str,
        name: str,
        model_type: str,
        task_type: str,
        framework: str,
        description: str = None,
        input_schema: dict = None,
        output_schema: dict = None,
        created_by: str = None,
    ) -> Metadata:
        """创建模型元数据

        参数：
            model_id: 模型唯一标识
            name: 模型名称
            model_type: 模型类型
            task_type: 任务类型
            framework: 模型框架
            description: 模型描述
            input_schema: 输入 Schema
            output_schema: 输出 Schema
            created_by: 创建人

        返回：
            模型元数据对象
        """
        obj = Metadata(
            model_id=model_id,
            name=name,
            model_type=model_type,
            task_type=task_type,
            framework=framework,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            created_by=created_by,
        )

        self.add(obj)

        return obj