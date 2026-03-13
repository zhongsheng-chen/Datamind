# api/model_info_api.py
from fastapi import APIRouter, HTTPException
from typing import Optional, List
import os
import json

router = APIRouter(prefix="/v1/models", tags=["models"])


class ModelInfoResponse(BaseModel):
    """模型信息响应"""
    model_id: str
    model_name: str
    task_type: str
    model_type: str
    framework: str
    current_version: str
    versions: List[Dict]
    registered_at: str
    status: str
    description: Optional[str] = None
    tags: Dict[str, str]


@router.get("/{model_id}", response_model=ModelInfoResponse)
async def get_model_info(model_id: str):
    """根据model_id获取模型信息"""
    try:
        # 查找模型目录
        for task_type in ['scoring', 'fraud_detection']:
            model_path = os.path.join("/data/models", task_type, model_id)
            if os.path.exists(model_path):
                metadata_path = os.path.join(model_path, "metadata.json")
                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)

                    # 获取所有版本
                    versions_dir = os.path.join(model_path, "versions")
                    versions = []
                    if os.path.exists(versions_dir):
                        for v_file in os.listdir(versions_dir):
                            if v_file.endswith('.json'):
                                with open(os.path.join(versions_dir, v_file), 'r') as vf:
                                    versions.append(json.load(vf))

                    return ModelInfoResponse(
                        model_id=metadata['model_id'],
                        model_name=metadata['model_name'],
                        task_type=metadata['task_type'],
                        model_type=metadata['model_type'],
                        framework=metadata['framework'],
                        current_version=metadata['version'],
                        versions=versions,
                        registered_at=metadata['registered_at'],
                        status=metadata['status'],
                        description=metadata.get('description'),
                        tags=metadata.get('tags', {})
                    )

        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def list_models(
        task_type: Optional[str] = None,
        model_type: Optional[str] = None,
        limit: int = 100
):
    """列出所有模型"""
    models = []
    base_path = "/data/models"

    # 遍历任务类型目录
    tasks = [task_type] if task_type else ['scoring', 'fraud_detection']

    for task in tasks:
        task_path = os.path.join(base_path, task)
        if not os.path.exists(task_path):
            continue

        # 遍历模型目录
        for model_id in os.listdir(task_path):
            model_dir = os.path.join(task_path, model_id)
            if not os.path.isdir(model_dir):
                continue

            metadata_path = os.path.join(model_dir, "metadata.json")
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

                    # 按model_type过滤
                    if model_type and metadata['model_type'] != model_type:
                        continue

                    models.append({
                        "model_id": metadata['model_id'],
                        "model_name": metadata['model_name'],
                        "task_type": metadata['task_type'],
                        "model_type": metadata['model_type'],
                        "framework": metadata['framework'],
                        "current_version": metadata['version'],
                        "registered_at": metadata['registered_at'],
                        "status": metadata['status']
                    })

    return {"models": models[:limit], "total": len(models)}