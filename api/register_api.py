# api/register_api.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, validator, Field
from typing import Optional, List, Dict, Any
import os
import json
import shutil
import hashlib
import uuid
from datetime import datetime
import logging

app = FastAPI(title="Datamind Model Registration API")


# 模型注册请求（开发人员提供的参数）
class ModelRegistrationRequest(BaseModel):
    """模型注册请求 - 开发人员提供的信息"""
    model_name: str = Field(..., description="模型名称，例如：'信用评分卡v1'")
    model_type: str = Field(..., description="decision_tree, random_forest, xgboost, lightgbm, logistic_regression")
    framework: str = Field(..., description="sklearn, xgboost, lightgbm, torch, tensorflow, onnx, catboost")
    task_type: str = Field(..., description="scoring, fraud_detection")
    version: str = Field(..., description="版本号，例如：'1.0.0'")
    description: Optional[str] = Field(None, description="模型描述")
    feature_names: List[str] = Field(..., description="特征名称列表")
    tags: Optional[Dict[str, str]] = Field(default={}, description="自定义标签")

    @validator('model_type')
    def validate_model_type(cls, v):
        valid_types = ['decision_tree', 'random_forest', 'xgboost', 'lightgbm', 'logistic_regression']
        if v not in valid_types:
            raise ValueError(f'model_type must be one of {valid_types}')
        return v

    @validator('framework')
    def validate_framework(cls, v):
        valid_frameworks = ['sklearn', 'xgboost', 'lightgbm', 'torch', 'tensorflow', 'onnx', 'catboost']
        if v not in valid_frameworks:
            raise ValueError(f'framework must be one of {valid_frameworks}')
        return v

    @validator('task_type')
    def validate_task_type(cls, v):
        valid_tasks = ['scoring', 'fraud_detection']
        if v not in valid_tasks:
            raise ValueError(f'task_type must be one of {valid_tasks}')
        return v


# 模型注册响应（返回给开发人员的信息）
class ModelRegistrationResponse(BaseModel):
    """模型注册响应"""
    model_id: str = Field(..., description="系统生成的唯一模型ID")
    model_name: str
    version: str
    task_type: str
    model_type: str
    framework: str
    status: str
    registered_at: str
    file_info: Dict[str, Any]


class ModelRegistrar:
    """模型注册器 - 处理模型文件存储和注册"""

    def __init__(self, base_path: str = "/data/models"):
        self.base_path = base_path
        self.logger = logging.getLogger(__name__)

        # 创建目录结构
        self._init_directories()

    def _init_directories(self):
        """初始化目录结构"""
        # 按任务类型分目录
        for task in ['scoring', 'fraud_detection']:
            task_path = os.path.join(self.base_path, task)
            os.makedirs(task_path, exist_ok=True)

    def _generate_model_id(self) -> str:
        """生成唯一的模型ID"""
        # 格式: mod_ + 时间戳 + 随机字符串
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = str(uuid.uuid4())[:8]
        return f"mod_{timestamp}_{random_part}"

    def register(
            self,
            model_file: UploadFile,
            registration_info: ModelRegistrationRequest
    ) -> ModelRegistrationResponse:
        """注册模型"""

        try:
            # 1. 生成唯一的模型ID
            model_id = self._generate_model_id()

            # 2. 构建模型存储路径（使用生成的model_id）
            model_dir = os.path.join(
                self.base_path,
                registration_info.task_type,
                model_id  # 使用系统生成的ID作为目录名
            )
            os.makedirs(model_dir, exist_ok=True)

            # 3. 生成模型文件名
            file_ext = os.path.splitext(model_file.filename)[1]
            model_filename = f"model_{registration_info.version}{file_ext}"
            model_path = os.path.join(model_dir, model_filename)

            # 4. 保存上传的模型文件
            with open(model_path, "wb") as buffer:
                shutil.copyfileobj(model_file.file, buffer)

            # 5. 验证模型文件
            validation_result = self._validate_model(
                model_path,
                registration_info
            )

            if not validation_result['valid']:
                # 验证失败，删除已保存的文件
                os.remove(model_path)
                os.rmdir(model_dir)  # 删除空目录
                raise ValueError(f"模型验证失败: {validation_result['error']}")

            # 6. 计算文件hash和大小
            file_hash = self._calculate_file_hash(model_path)
            file_size = os.path.getsize(model_path)

            # 7. 创建模型元数据（包含系统生成的model_id）
            metadata = {
                "model_id": model_id,
                "model_name": registration_info.model_name,
                "model_type": registration_info.model_type,
                "framework": registration_info.framework,
                "task_type": registration_info.task_type,
                "version": registration_info.version,
                "description": registration_info.description,
                "feature_names": registration_info.feature_names,
                "tags": registration_info.tags or {},
                "file_info": {
                    "original_filename": model_file.filename,
                    "stored_filename": model_filename,
                    "path": model_path,
                    "size_bytes": file_size,
                    "hash": file_hash,
                    "format": file_ext[1:] if file_ext else "unknown"
                },
                "registered_at": datetime.now().isoformat(),
                "status": "active",
                "versions": [{
                    "version": registration_info.version,
                    "registered_at": datetime.now().isoformat(),
                    "status": "active",
                    "file_info": {
                        "filename": model_filename,
                        "hash": file_hash,
                        "size_bytes": file_size
                    }
                }]
            }

            # 8. 保存元数据文件
            meta_path = os.path.join(model_dir, "metadata.json")
            with open(meta_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # 9. 创建versions目录（用于存储多个版本）
            versions_dir = os.path.join(model_dir, "versions")
            os.makedirs(versions_dir, exist_ok=True)

            # 10. 保存版本信息
            version_info = {
                "version": registration_info.version,
                "registered_at": datetime.now().isoformat(),
                "file_info": {
                    "filename": model_filename,
                    "hash": file_hash,
                    "size_bytes": file_size
                },
                "status": "active"
            }

            version_path = os.path.join(versions_dir, f"{registration_info.version}.json")
            with open(version_path, 'w') as f:
                json.dump(version_info, f, indent=2)

            # 11. 创建或更新latest符号链接
            latest_link = os.path.join(model_dir, "latest")
            if os.path.exists(latest_link):
                os.remove(latest_link)
            os.symlink(model_filename, latest_link)

            self.logger.info(
                f"模型注册成功: model_id={model_id}, name={registration_info.model_name}, version={registration_info.version}")

            # 12. 返回注册响应
            return ModelRegistrationResponse(
                model_id=model_id,
                model_name=registration_info.model_name,
                version=registration_info.version,
                task_type=registration_info.task_type,
                model_type=registration_info.model_type,
                framework=registration_info.framework,
                status="active",
                registered_at=metadata['registered_at'],
                file_info=metadata['file_info']
            )

        except Exception as e:
            self.logger.error(f"模型注册失败: {str(e)}")
            raise

    def _validate_model(
            self,
            model_path: str,
            info: ModelRegistrationRequest
    ) -> Dict[str, Any]:
        """验证模型文件是否可加载"""
        try:
            # 根据框架尝试加载模型
            if info.framework == 'sklearn':
                import joblib
                model = joblib.load(model_path)
                # 验证模型类型
                if info.model_type == 'logistic_regression':
                    if not hasattr(model, 'coef_'):
                        return {'valid': False, 'error': 'Not a logistic regression model'}
                elif info.model_type in ['decision_tree', 'random_forest']:
                    if not hasattr(model, 'predict'):
                        return {'valid': False, 'error': 'Not a tree model'}

            elif info.framework == 'xgboost':
                import xgboost as xgb
                model = xgb.Booster()
                model.load_model(model_path)

            elif info.framework == 'lightgbm':
                import lightgbm as lgb
                model = lgb.Booster(model_file=model_path)

            # 可以添加更多框架的验证

            return {'valid': True}

        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件SHA256 hash"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                sha256.update(chunk)
        return sha256.hexdigest()


# 初始化注册器
registrar = ModelRegistrar()


@app.post("/v1/models/register", response_model=ModelRegistrationResponse)
async def register_model(
        background_tasks: BackgroundTasks,
        model_file: UploadFile = File(..., description="模型文件"),
        model_name: str = Form(..., description="模型名称"),
        model_type: str = Form(..., description="模型类型"),
        framework: str = Form(..., description="模型框架"),
        task_type: str = Form(..., description="任务类型"),
        version: str = Form(..., description="版本号"),
        feature_names: str = Form(..., description="特征名称列表(JSON数组)"),
        description: Optional[str] = Form(None, description="模型描述"),
        tags: Optional[str] = Form("{}", description="自定义标签(JSON对象)")
):
    """
    注册新模型

    开发人员上传模型文件并填写模型信息，系统返回唯一的model_id
    """
    try:
        # 解析JSON字段
        feature_names_list = json.loads(feature_names)
        tags_dict = json.loads(tags)

        # 创建注册请求
        registration = ModelRegistrationRequest(
            model_name=model_name,
            model_type=model_type,
            framework=framework,
            task_type=task_type,
            version=version,
            description=description,
            feature_names=feature_names_list,
            tags=tags_dict
        )

        # 注册模型
        response = registrar.register(model_file, registration)

        # 可选：后台任务进行更深入的验证
        background_tasks.add_task(
            deep_validate_model,
            response.model_id,
            registration
        )

        return response

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON解析错误: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注册失败: {str(e)}")


async def deep_validate_model(model_id: str, registration: ModelRegistrationRequest):
    """后台深度验证模型"""
    # 这里可以进行更复杂的验证
    pass