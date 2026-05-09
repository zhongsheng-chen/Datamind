# datamind/db/writer/version_writer.py

"""模型版本写入器

记录模型的具体版本信息，每个模型可拥有多个版本。

使用示例：
    writer = VersionWriter(session)

    await writer.create(
        model_id="mdl_a1b2c3d4",
        version="1.0.0",
        framework="sklearn",
        bento_tag="scorecard:abc123def",
        model_path="s3://models/mdl_a1b2c3d4/1.0.0/scorecard.pkl",
        params={"C": 1.0, "max_iter": 100},
        metrics={"accuracy": 0.85, "auc": 0.92}
    )
"""

from datamind.db.models.versions import Version
from datamind.db.writers.base_writer import BaseWriter


class VersionWriter(BaseWriter):
    """模型版本写入器"""

    async def create(
        self,
        *,
        model_id: str,
        version: str,
        framework: str,
        bento_tag: str,
        model_path: str,
        params: dict = None,
        metrics: dict = None,
        description: str = None,
        created_by: str = None,
    ) -> Version:
        """创建模型版本

        参数：
            model_id: 所属模型ID
            version: 版本号
            framework: 模型框架
            bento_tag: BentoML 标签
            model_path: 模型文件存储路径
            params: 模型参数
            metrics: 模型评估指标
            description: 版本说明
            created_by: 创建人

        返回：
            模型版本对象
        """
        obj = Version(
            model_id=model_id,
            version=version,
            framework=framework,
            bento_tag=bento_tag,
            model_path=model_path,
            params=params,
            metrics=metrics,
            description=description,
            created_by=created_by,
        )

        self.add(obj)

        return obj

    async def update(
        self,
        obj: Version,
        **fields,
    ) -> Version:
        """更新模型版本

        参数：
            obj: 模型版本对象
            **fields: 待更新字段

        返回：
            更新后的模型版本对象
        """
        for key, value in fields.items():
            setattr(obj, key, value)

        await self.flush()

        return obj