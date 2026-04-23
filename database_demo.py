from datamind.db.core import session_scope
from datamind.db.models.metadata import Metadata

# 查询
with session_scope() as session:
    model = session.query(Metadata).filter_by(model_id="mdl_001").first()
    print(model.model_type)

# 插入
with session_scope() as session:
    metadata = Metadata(
        model_id="mdl_002",
        model_type="xgboost",
        task_type="classification",
    )
    session.add(metadata)
    # 自动提交

# 更新
with session_scope() as session:
    session.query(Metadata).filter_by(model_id="mdl_001").update({"is_active": True})

# 删除
with session_scope() as session:
    session.query(Metadata).filter_by(model_id="mdl_002").delete()