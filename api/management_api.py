# api/management_api.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from typing import Optional, List
import tempfile
import os
import json

app = FastAPI(title="Datamind Model Management API")


@app.post("/v1/models/register")
async def register_model(
        task_type: str = Form(...),  # 'scoring' or 'fraud_detection'
        model_id: str = Form(...),
        model_type: str = Form(...),  # decision_tree, random_forest, xgboost, lightgbm, logistic_regression
        framework: str = Form(...),  # sklearn, xgboost, lightgbm, torch, tensorflow, onnx, catboost
        version: str = Form(...),
        feature_names: str = Form(...),  # JSON array string
        metadata: Optional[str] = Form("{}"),
        model_file: UploadFile = File(...)
):
    """注册模型"""
    try:
        # 保存上传的文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pkl") as tmp:
            content = await model_file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 解析feature_names
        feature_names_list = json.loads(feature_names)

        # 解析metadata
        metadata_dict = json.loads(metadata)

        # 注册模型
        model_info = model_repo.register(
            task_type=task_type,
            model_id=model_id,
            model_type=model_type,
            framework=framework,
            version=version,
            model_file=tmp_path,
            feature_names=feature_names_list,
            metadata=metadata_dict
        )

        # 清理临时文件
        os.unlink(tmp_path)

        return model_info

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/v1/models/{task_type}/{model_id}/{version}")
async def unregister_model(
        task_type: str,
        model_id: str,
        version: str
):
    """注销模型"""
    try:
        model_repo.unregister(task_type, model_id, version)
        return {"message": "模型注销成功"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/v1/models")
async def list_models(task_type: Optional[str] = None):
    """列出所有模型"""
    models = model_repo.list_models(task_type)
    return models


@app.get("/v1/models/{task_type}/{model_id}")
async def get_model_info(
        task_type: str,
        model_id: str,
        version: Optional[str] = "latest"
):
    """获取模型信息"""
    try:
        model_info = model_repo.get_model_info(task_type, model_id, version)
        return model_info
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))