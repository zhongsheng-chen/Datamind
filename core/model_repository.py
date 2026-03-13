# core/model_repository.py
import os
import json
import shutil
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging


class ModelRepository:
    """模型仓库 - 只管理模型文件"""

    def __init__(self, storage_path: str = "/data/models"):
        self.storage_path = storage_path
        self.logger = logging.getLogger(__name__)

        # 创建任务类型目录
        os.makedirs(f"{storage_path}/scoring", exist_ok=True)
        os.makedirs(f"{storage_path}/fraud_detection", exist_ok=True)

    def register(
            self,
            task_type: str,  # 'scoring' or 'fraud_detection'
            model_id: str,
            model_type: str,  # decision_tree, random_forest, xgboost, lightgbm, logistic_regression
            framework: str,  # sklearn, xgboost, lightgbm, torch, tensorflow, onnx, catboost
            version: str,
            model_file: str,
            feature_names: List[str],  # 输入特征名称列表
            metadata: Optional[Dict] = None
    ) -> Dict:
        """注册模型"""

        # 验证task_type
        if task_type not in ['scoring', 'fraud_detection']:
            raise ValueError(f"task_type must be 'scoring' or 'fraud_detection', got {task_type}")

        # 验证model_type
        valid_model_types = ['decision_tree', 'random_forest', 'xgboost', 'lightgbm', 'logistic_regression']
        if model_type not in valid_model_types:
            raise ValueError(f"model_type must be one of {valid_model_types}, got {model_type}")

        # 验证framework
        valid_frameworks = ['sklearn', 'xgboost', 'lightgbm', 'torch', 'tensorflow', 'onnx', 'catboost']
        if framework not in valid_frameworks:
            raise ValueError(f"framework must be one of {valid_frameworks}, got {framework}")

        # 构建模型路径
        model_dir = f"{self.storage_path}/{task_type}/{model_id}"
        os.makedirs(model_dir, exist_ok=True)

        model_filename = f"{model_id}_{version}.pkl"
        model_path = os.path.join(model_dir, model_filename)

        # 复制模型文件
        shutil.copy2(model_file, model_path)

        # 计算文件hash
        file_hash = self._calculate_hash(model_path)

        # 模型元数据
        model_info = {
            "task_type": task_type,
            "model_id": model_id,
            "model_type": model_type,
            "framework": framework,
            "version": version,
            "file_path": model_path,
            "file_hash": file_hash,
            "feature_names": feature_names,
            "metadata": metadata or {},
            "registered_at": datetime.now().isoformat(),
            "status": "active"
        }

        # 保存元数据
        meta_path = os.path.join(model_dir, f"{model_id}_{version}.meta.json")
        with open(meta_path, 'w') as f:
            json.dump(model_info, f, indent=2)

        # 更新latest指针
        latest_link = os.path.join(model_dir, "latest")
        if os.path.exists(latest_link):
            os.remove(latest_link)
        os.symlink(model_filename, latest_link)

        self.logger.info(f"模型注册成功: {task_type}/{model_id}:{version}")
        return model_info