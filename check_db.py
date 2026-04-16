from datamind.core.db.database import db_manager, get_db
from datamind.core.db.models import ModelMetadata
import json

# 先初始化数据库连接
db_manager.initialize()

with get_db() as session:
    # 查看最新的两个模型
    models = session.query(ModelMetadata).order_by(
        ModelMetadata.created_at.desc()
    ).limit(2).all()
    
    for model in models:
        print("=" * 60)
        print(f"模型ID: {model.model_id}")
        print(f"模型名称: {model.model_name}")
        print(f"模型版本: {model.model_version}")
        print(f"创建时间: {model.created_at}")
        print(f"\n--- metadata_json ---")
        if model.metadata_json:
            print(json.dumps(model.metadata_json, indent=2, ensure_ascii=False))
        else:
            print("null")
        print(f"\n--- model_params ---")
        if model.model_params:
            print(json.dumps(model.model_params, indent=2, ensure_ascii=False))
        else:
            print("null")
        print()
