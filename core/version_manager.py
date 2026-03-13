# core/version_manager.py

import os
import json

class ModelVersionManager:
    """模型版本管理器"""

    def __init__(self, base_path: str):
        self.base_path = base_path

    def list_versions(self, model_id: str, task_type: str) -> List[Dict]:
        """列出模型的所有版本"""
        model_dir = os.path.join(self.base_path, task_type, model_id)
        versions_file = os.path.join(model_dir, "versions.json")

        if os.path.exists(versions_file):
            with open(versions_file, 'r') as f:
                return json.load(f)
        return []

    def get_version_info(
            self,
            model_id: str,
            task_type: str,
            version: str
    ) -> Dict:
        """获取特定版本的信息"""
        model_dir = os.path.join(self.base_path, task_type, model_id)
        meta_path = os.path.join(model_dir, f"{model_id}_{version}.meta.json")

        if not os.path.exists(meta_path):
            raise ValueError(f"Version {version} not found")

        with open(meta_path, 'r') as f:
            return json.load(f)

    def delete_version(
            self,
            model_id: str,
            task_type: str,
            version: str
    ):
        """删除特定版本"""
        model_dir = os.path.join(self.base_path, task_type, model_id)

        # 删除模型文件
        for ext in ['.pkl', '.joblib', '.onnx', '.model']:
            model_path = os.path.join(model_dir, f"{model_id}_{version}{ext}")
            if os.path.exists(model_path):
                os.remove(model_path)

        # 删除元数据
        meta_path = os.path.join(model_dir, f"{model_id}_{version}.meta.json")
        if os.path.exists(meta_path):
            os.remove(meta_path)

        # 更新versions.json
        versions_file = os.path.join(model_dir, "versions.json")
        if os.path.exists(versions_file):
            with open(versions_file, 'r') as f:
                versions = json.load(f)

            versions = [v for v in versions if v['version'] != version]

            with open(versions_file, 'w') as f:
                json.dump(versions, f, indent=2)