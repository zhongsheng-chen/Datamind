import os
import re
import yaml
from typing import Union
from pathlib import Path
from typing import Any, Optional, List, Dict


class WorkflowStep:
    """单个工作流步骤封装"""
    def __init__(self, step_conf: dict):
        self.step_conf = step_conf

    @property
    def name(self) -> str:
        return self.step_conf.get("step_name", "")

    @property
    def modules(self) -> list:
        return self.step_conf.get("modules", [])

    @property
    def models(self) -> list:
        return self.step_conf.get("models", [])


class BusinessWorkflow:
    """业务工作流封装"""
    def __init__(self, workflow_conf: dict, cfg: "Config"):
        self.workflow_conf = workflow_conf
        self.cfg = cfg

    @property
    def name(self) -> str:
        return self.workflow_conf.get("business_name", "")

    @property
    def description(self) -> str:
        return self.workflow_conf.get("description", "")

    @property
    def steps(self) -> List[WorkflowStep]:
        return [WorkflowStep(step) for step in self.workflow_conf.get("workflow_steps", [])]

    @property
    def models(self) -> list:
        return self.workflow_conf.get("models", [])

    def get_models(self, model_type: Optional[str] = None) -> List[dict]:
        """返回 workflow 中的模型信息，可按 model_type 过滤"""
        resolved_models = []
        for model_entry in self.models:
            model_conf = self.cfg.get_model(model_entry["model_name"])
            if not model_conf:
                continue
            if not model_type or model_conf.get("model_type") == model_type:
                resolved_models.append(model_conf)
        return resolved_models

    def get_ab_test_info(self) -> Dict[str, dict]:
        """返回 workflow 中模型的 AB 测试配置"""
        ab_map = {}
        for model_entry in self.models:
            ab_map[model_entry["model_name"]] = model_entry.get("ab_test", {})
        return ab_map


class Config:
    """配置文件解析与访问封装"""
    def __init__(self, cfg_path: Optional[str] = None, max_repr_len: int = 10):
        cfg_path = cfg_path or os.environ.get("DATAMIND_CONFIG_PATH")
        if not cfg_path:
            cfg_path = Path(__file__).resolve().parent.parent / "config/config.yaml"

        self.cfg_path = Path(cfg_path)
        self.max_repr_len = max_repr_len
        self._cfg_data = self._load_config()
        self.databases = self._cfg_data.get("databases", {})
        self.logging = self._cfg_data.get("logging", {})
        self.features = self._cfg_data.get("features", {})
        self.models = self._cfg_data.get("models", {})
        self.workflows = self._cfg_data.get("workflows", {})

    def _load_config(self) -> dict:
        if not self.cfg_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.cfg_path}")
        with open(self.cfg_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def __repr__(self) -> str:
        """安全且可读的 Config 展示"""
        ip_pattern = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

        def safe_display(value: Any) -> Any:
            if isinstance(value, str):
                if ip_pattern.match(value) or len(value) <= self.max_repr_len:
                    return value
                return value[:self.max_repr_len] + "..."
            return value

        def sanitize_dict(d: dict) -> dict:
            sanitized_dict = {}
            for k, v in d.items():
                if any(s in k.lower() for s in ("password", "secret", "key", "token")):
                    sanitized_dict[k] = "***"
                elif isinstance(v, dict):
                    sanitized_dict[k] = sanitize_dict(v)
                elif isinstance(v, list):
                    sanitized_dict[k] = [
                        sanitize_dict(i) if isinstance(i, dict) else safe_display(i) for i in v
                    ]
                else:
                    sanitized_dict[k] = safe_display(v)
            return sanitized_dict

        safe_cfg = sanitize_dict(self._cfg_data)
        return f"<Config path={self.cfg_path} sections={safe_cfg}>"

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        section_data = self._cfg_data.get(section, {})
        if key:
            return section_data.get(key, default)
        return section_data

    def get_databases(self, db_name: str) -> dict:
        return self.get("databases", {}).get(db_name, {})

    def get_logging(self) -> dict:
        return self.get("logging", {})

    def get_kie_server(self) -> dict:
        return self.get("kie_server", {})

    def get_features(self, feature_name: str) -> list:
        return self.get("features", {}).get(feature_name, [])

    def get_model(self, model_name: str) -> Optional[dict]:
        for category, model_list in self.models.items():
            for model_entry in model_list:
                if model_entry.get("model_name") == model_name:
                    return model_entry
        return None

    def list_models(self, flatten: bool = True) -> Union[List[str], Dict[str, List[str]]]:
        """
        列出所有模型名称

        参数:
            flatten (bool): 是否返回扁平化列表（默认 True）
                            False 时按分类返回 dict {category: [model_name,...]}

        返回:
            list 或 dict: 模型名称列表或按分类的字典
        """
        if flatten:
            model_names = []
            for category, model_list in self.models.items():
                model_names.extend([m.get("model_name") for m in model_list])
            return model_names
        else:
            categorized = {}
            for category, model_list in self.models.items():
                categorized[category] = [m.get("model_name") for m in model_list]
            return categorized

    def get_business_workflow(self, workflow_name: str) -> BusinessWorkflow:
        wf_conf = self.workflows.get(workflow_name)
        if not wf_conf:
            raise KeyError(f"未找到业务工作流: {workflow_name}")
        return BusinessWorkflow(wf_conf, self)

    def list_business_workflows(self) -> list:
        return list(self.workflows.keys())


# 全局配置实例
config = Config()
