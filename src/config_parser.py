import os
import re
import yaml
from pathlib import Path

class WorkflowStep:
    """单个工作流步骤"""
    def __init__(self, step_dict):
        self.step_dict = step_dict

    @property
    def name(self):
        return self.step_dict.get("step_name")

    @property
    def rule_categories(self):
        return self.step_dict.get("rule_categories", [])

    @property
    def models(self):
        return self.step_dict.get("models", [])

class BusinessWorkflow:
    """封装业务工作流的访问接口"""
    def __init__(self, wf_dict, config):
        self.wf_dict = wf_dict
        self.config = config

    @property
    def name(self):
        return self.wf_dict.get("business_name")

    @property
    def description(self):
        return self.wf_dict.get("description")

    @property
    def rules(self):
        return self.wf_dict.get("rules", [])

    @property
    def models(self):
        return self.wf_dict.get("models", [])

    def get_rules(self, category=None):
        """按类别筛选规则"""
        if not category:
            return self.rules
        return [r for r in self.rules if category in r.get("enabled_categories", [])]

    def get_models(self, category=None):
        """获取 workflow 对应模型，可按 scoring / fraud 分类"""
        all_models = []
        for m in self.models:
            model_info = self.config.get_model(m["model_name"])
            if not model_info:
                continue
            if not category or model_info.get("model_type") == category:
                all_models.append(model_info)
        return all_models

    def get_steps(self):
        """返回封装的步骤对象"""
        steps = self.wf_dict.get("workflow_steps", [])
        return [WorkflowStep(s) for s in steps]

    def get_ab_test_info(self):
        """返回工作流中模型的AB测试配置"""
        ab_map = {}
        for m in self.models:
            name = m.get("model_name")
            ab_map[name] = m.get("ab_test", {})
        return ab_map
class Config:
    def __init__(self, config_path=None, repr_max_length=10):
        config_path = config_path or os.environ.get("DATAMIND_CONFIG_PATH")
        if not config_path:
            config_path = Path(__file__).resolve().parent.parent / "config/config.yaml"

        self.config_path = Path(config_path)
        self.repr_max_length = repr_max_length
        self._config_data = self._load_config()
        self.databases = self._config_data.get("databases", {})
        self.logging = self._config_data.get("logging", {})
        self.feature_set = self._config_data.get("feature_set", {})
        self.model_catalog = self._config_data.get("model_catalog", {})
        self.business_workflows = self._config_data.get("business_workflows", {})

    def _load_config(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def __repr__(self):
        """安全且可读的 Config 展示"""
        ip_pattern = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")

        def safe_display(value):
            if isinstance(value, str):
                if ip_pattern.match(value) or len(value) <= self.repr_max_length:
                    return value
                return value[:self.repr_max_length] + "..."
            return value

        def sanitize_dict(d):
            safe_d = {}
            for k, v in d.items():
                if any(s in k.lower() for s in ("password", "secret", "key", "token")):
                    safe_d[k] = "***"
                elif isinstance(v, dict):
                    safe_d[k] = sanitize_dict(v)
                elif isinstance(v, list):
                    safe_d[k] = [sanitize_dict(i) if isinstance(i, dict) else safe_display(i) for i in v]
                else:
                    safe_d[k] = safe_display(v)
            return safe_d

        safe_config = sanitize_dict(self._config_data)
        return f"<Config path={self.config_path} sections={safe_config}>"

    def get(self, section, key=None, default=None):
        sec = self._config_data.get(section, {})
        if key:
            return sec.get(key, default)
        return sec

    def get_databases(self, name):
        """获取指定数据库配置"""
        return self.get("databases", {}).get(name)

    def get_logging(self):
        """获取日志配置"""
        return self.get("logging")

    def get_kie_server(self):
        """获取kie server配置"""
        return self.get("kie_server")

    def get_feature_set(self, feature_name):
        """获取特征列表"""
        return self.get("feature_set", {}).get(feature_name, [])

    def get_model(self, model_name):
        """根据名称从 model_catalog 检索模型"""
        model_catalog = self.get("model_catalog", {})
        for category, model_list in model_catalog.items():
            for model in model_list:
                if model.get("model_name") == model_name:
                    return model
        return None

    def get_business_workflow(self, workflow_name):
        """获取指定工作流封装对象"""
        workflows = self.get("business_workflows", {})
        wf_dict = workflows.get(workflow_name)
        if not wf_dict:
            raise KeyError(f"未找到业务工作流: {workflow_name}")
        return BusinessWorkflow(wf_dict, self)

    def list_business_workflows(self):
        """列出所有工作流名称"""
        return list(self.get("business_workflows", {}).keys())

config = Config()
