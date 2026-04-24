# datamind/models/base.py

"""模型基础定义"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ModelSpec:
    """模型注册信息（核心元数据）

    属性：
        model_id: 模型唯一标识
        framework: 模型框架
        model_type: 模型类型
        version: 模型版本号
        bento_tag: BentoML 标签（格式：模型名:版本）
        model_path: 模型文件路径
        description: 模型描述
        metadata: 扩展元数据（参数、指标等）
    """

    model_id: str
    framework: str
    model_type: str
    version: str
    bento_tag: str
    model_path: str
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None