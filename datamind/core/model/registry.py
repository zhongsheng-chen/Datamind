# datamind/core/model/registry.py

"""模型注册中心

负责模型的注册、版本管理、状态管理和配置管理。

核心功能：
  - register_model: 注册新模型，保存模型文件到 BentoML Model Store
  - activate_model: 激活模型（设置为 active 状态）
  - deactivate_model: 停用模型（设置为 inactive 状态）
  - promote_to_production: 提升模型为生产模型（允许多个生产模型共存）
  - get_model_info: 获取模型详细信息
  - list_models: 列出模型（支持多维度筛选）
  - get_model_history: 获取模型操作历史
  - update_model_params: 更新模型参数（评分卡/反欺诈配置）
  - get_production_models: 获取生产模型列表

特性：
  - 版本管理：支持模型版本控制和历史追溯
  - 生产环境管理：允许多个生产模型共存（支持A/B测试、灰度发布）
  - 配置验证：自动验证评分卡参数和反欺诈配置
  - BentoML 集成：模型存储在 BentoML Model Store
  - 完整审计：记录所有模型操作到版本历史表
  - 链路追踪：完整的 span 追踪
"""

import os
import threading
import tempfile
import shutil
import hashlib
import uuid
import pickle
from enum import Enum
from sqlalchemy import desc
from pathlib import Path
from typing import Dict, Optional, List, Any, BinaryIO, Union
from datetime import datetime
from dataclasses import dataclass, asdict

import bentoml
from bentoml.exceptions import BentoMLException

from datamind import PROJECT_ROOT
from datamind.core.db.database import get_db
from datamind.core.db.models import ModelMetadata, ModelVersionHistory
from datamind.core.domain.enums import ModelStatus, AuditAction, PerformanceOperation, TaskType, ModelType, Framework
from datamind.core.domain.validation import validate_or_raise
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging import get_logger
from datamind.core.common.exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelFileException,
    UnsupportedFrameworkException
)
from datamind.core.common.frameworks import (
    get_bentoml_backend,
    get_framework_signatures,
    is_framework_supported,
    get_supported_frameworks
)

_logger = get_logger(__name__)


def _format_file_size(size_bytes: int) -> str:
    """
    将字节数格式化为人类可读的文件大小

    参数:
        size_bytes: 文件大小（字节）

    返回:
        格式化后的字符串，如 "1.21KB", "2.34MB", "1.12GB"
    """
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{round(size_bytes / 1024, 2)}KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{round(size_bytes / 1024 / 1024, 2)}MB"
    else:
        return f"{round(size_bytes / 1024 / 1024 / 1024, 2)}GB"


def _convert_enum_to_str(obj: Any) -> Any:
    """
    递归将枚举转换为字符串

    BentoML 的 metadata 不支持枚举类型，需要在保存前转换。

    参数:
        obj: 待转换的对象

    返回:
        转换后的对象（枚举转换为字符串，其他类型保持不变）
    """
    if isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: _convert_enum_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_enum_to_str(v) for v in obj]
    return obj


@dataclass
class BentoMLMetadata:
    """BentoML 模型元数据"""
    model_id: str
    model_name: str
    model_version: str
    task_type: TaskType
    model_type: ModelType
    framework: Framework
    input_features: List[str]
    output_schema: Dict[str, str]
    model_params: Dict[str, Any]
    created_by: str
    created_at: str
    description: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    scorecard_config: Optional[Dict[str, Any]] = None
    fraud_config: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，自动过滤 None 值，并将枚举转换为字符串"""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return _convert_enum_to_str(data)


class ModelRegistry:
    """模型注册中心"""

    def __init__(self, settings=None):
        """
        初始化模型注册中心

        参数:
            settings: 配置对象
        """
        from datamind.config import get_settings

        if settings is None:
            settings = get_settings()

        model_config = settings.model

        models_path = model_config.models_path
        if os.path.isabs(models_path):
            self.cache_path = Path(models_path)
        else:
            self.cache_path = PROJECT_ROOT / models_path
        self.cache_path.mkdir(parents=True, exist_ok=True)

        _logger.debug("模型注册中心初始化完成，存储路径: %s", self.cache_path.absolute())

    @staticmethod
    def _clean_none_values(obj: Any) -> Any:
        """递归清理对象中的 None 值"""
        if obj is None:
            return None
        if isinstance(obj, dict):
            return {k: ModelRegistry._clean_none_values(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [ModelRegistry._clean_none_values(v) for v in obj if v is not None]
        return obj

    def register_model(
            self,
            model_name: str,
            model_version: str,
            task_type: TaskType,
            model_type: ModelType,
            framework: Framework,
            input_features: List[str],
            output_schema: Dict[str, str],
            created_by: str,
            model_file: BinaryIO,
            description: Optional[str] = None,
            model_params: Optional[Dict] = None,
            tags: Optional[Dict] = None,
            ip_address: Optional[str] = None,
            scorecard_config: Optional[Dict] = None,
            fraud_config: Optional[Dict] = None
    ) -> str:
        """
        注册新模型

        参数:
            model_name: 模型名称
            model_version: 模型版本
            task_type: 任务类型 (scoring/fraud_detection)
            model_type: 模型类型
            framework: 模型框架
            input_features: 输入特征列表
            output_schema: 输出格式定义
            created_by: 创建人
            model_file: 模型文件对象
            description: 描述
            model_params: 模型参数
            tags: 标签
            ip_address: IP地址
            scorecard_config: 评分卡配置参数（task_type=scoring 时使用）
            fraud_config: 反欺诈配置参数（task_type=fraud_detection 时使用）

        返回:
            模型ID
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        # 生成模型ID
        model_id = f"MDL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8].upper()}"

        try:
            # 验证框架是否支持
            if not is_framework_supported(framework):
                raise UnsupportedFrameworkException(
                    f"不支持的框架: {framework}. 支持的框架: {get_supported_frameworks()}"
                )

            # 验证框架和模型类型兼容性
            try:
                framework_enum = Framework(framework)
                model_type_enum = ModelType(model_type)
                validate_or_raise(framework_enum, model_type_enum)
            except ValueError as e:
                raise ModelValidationException(f"无效的框架或模型类型: {e}")

            # 验证任务类型特定的配置
            self._validate_task_specific_config(
                task_type=task_type,
                scorecard_config=scorecard_config,
                fraud_config=fraud_config
            )

            # 合并配置到 model_params
            merged_model_params = self._merge_model_params(
                model_params=model_params,
                scorecard_config=scorecard_config,
                fraud_config=fraud_config,
                task_type=task_type
            )

            # 清理 merged_model_params 中的 None 值
            merged_model_params = self._clean_none_values(merged_model_params)

            # 检查模型是否已存在
            with get_db() as session:
                existing = session.query(ModelMetadata).filter_by(
                    model_name=model_name,
                    model_version=model_version
                ).first()
                if existing:
                    raise ModelAlreadyExistsException(
                        model_name=model_name,
                        version=model_version
                    )

            # 保存模型文件到临时文件
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                content = model_file.read()
                tmp_file.write(content)
                tmp_path = Path(tmp_file.name)

            try:
                # 获取文件信息
                file_size = tmp_path.stat().st_size
                file_hash = self._calculate_file_hash(tmp_path)

                # 构建元数据
                metadata_obj = BentoMLMetadata(
                    model_id=model_id,
                    model_name=model_name,
                    model_version=model_version,
                    task_type=task_type,
                    model_type=model_type,
                    framework=framework,
                    input_features=input_features,
                    output_schema=output_schema,
                    model_params=merged_model_params,
                    created_by=created_by,
                    created_at=datetime.now().isoformat(),
                    description=description,
                    tags=tags,
                    scorecard_config=scorecard_config,
                    fraud_config=fraud_config
                )
                metadata = metadata_obj.to_dict()

                labels = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "model_version": model_version,
                    "task_type": task_type.value if isinstance(task_type, TaskType) else task_type,
                    "model_type": model_type.value if isinstance(model_type, ModelType) else model_type,
                    "framework": framework.value if isinstance(framework, Framework) else framework,
                    "created_by": created_by
                }

                # 保存到 BentoML Model Store
                bento_model = self._save_to_bentoml(
                    name=model_id,
                    model_path=tmp_path,
                    framework=framework,
                    metadata=metadata,
                    labels=labels
                )

                # 保存到本地缓存
                cached_path = self.cache_path / model_id / 'versions' / f"model_{model_version}"
                cached_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(tmp_path, cached_path)

                # 创建最新版本软链接
                latest_link = self.cache_path / model_id / 'latest'
                if latest_link.exists() or latest_link.is_symlink():
                    latest_link.unlink()
                latest_link.symlink_to(f"versions/model_{model_version}")

                # 构建 metadata_json
                metadata_json: Dict[str, Any] = {
                    "bentoml_tag": str(bento_model.tag),
                    "bentoml_name": bento_model.tag.name,
                    "bentoml_version": bento_model.tag.version
                }

                if scorecard_config:
                    metadata_json["scorecard_config"] = scorecard_config
                    _logger.debug("评分卡配置已保存到 metadata_json: %s", model_id)

                if fraud_config:
                    metadata_json["fraud_config"] = fraud_config
                    _logger.debug("反欺诈配置已保存到 metadata_json: %s", model_id)

                # 创建元数据记录
                with get_db() as session:
                    metadata_record = ModelMetadata(
                        model_id=model_id,
                        model_name=model_name,
                        model_version=model_version,
                        task_type=task_type,
                        model_type=model_type,
                        framework=framework,
                        file_path=str(cached_path),
                        file_hash=file_hash,
                        file_size=file_size,
                        input_features=input_features,
                        output_schema=output_schema,
                        model_params=merged_model_params,
                        status=ModelStatus.INACTIVE.value,
                        created_by=created_by,
                        description=description,
                        tags=tags,
                        metadata_json=metadata_json
                    )
                    session.add(metadata_record)
                    session.flush()

                    # 记录版本历史
                    history_details: Dict[str, Any] = {
                        'input_features_count': len(input_features),
                        'output_schema_keys': list(output_schema.keys()),
                        'file_size': file_size,
                        'file_hash': file_hash[:8],
                        'bentoml_tag': str(bento_model.tag),
                        'request_id': request_id,
                        'trace_id': trace_id,
                        'span_id': span_id,
                        'parent_span_id': parent_span_id
                    }

                    if scorecard_config:
                        history_details['scorecard_config'] = scorecard_config
                    if fraud_config:
                        history_details['fraud_config'] = fraud_config

                    history = ModelVersionHistory(
                        model_id=model_id,
                        model_version=model_version,
                        operation=AuditAction.MODEL_CREATE.value,
                        operator=created_by,
                        operator_ip=ip_address,
                        metadata_snapshot=self._create_snapshot(metadata_record),
                        details=history_details
                    )
                    session.add(history)
                    session.commit()

                duration = (datetime.now() - start_time).total_seconds() * 1000

                # 性能日志
                log_performance(
                    operation=PerformanceOperation.MODEL_SAVE,
                    duration_ms=duration,
                    model_id=model_id,
                    request_id=request_id,
                    extra={
                        "model_name": model_name,
                        "model_version": model_version,
                        "framework": framework,
                        "file_size": file_size,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    }
                )

                # 审计日志
                audit_details = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "model_version": model_version,
                    "task_type": task_type.value if isinstance(task_type, TaskType) else task_type,
                    "model_type": model_type.value if isinstance(model_type, ModelType) else model_type,
                    "framework": framework.value if isinstance(framework, Framework) else framework,
                    "bentoml_tag": str(bento_model.tag),
                    "file_size": file_size,
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }

                if scorecard_config:
                    audit_details["scorecard_config"] = scorecard_config
                if fraud_config:
                    audit_details["fraud_config"] = fraud_config

                log_audit(
                    action=AuditAction.MODEL_CREATE.value,
                    user_id=created_by,
                    ip_address=ip_address,
                    resource_type="model",
                    resource_id=model_id,
                    resource_name=model_name,
                    details=audit_details,
                    request_id=request_id
                )

                human_size = _format_file_size(file_size)
                _logger.info("模型注册成功: %s v%s, 模型ID: %s, BentoML标签: %s, 文件大小: %s",
                             model_name, model_version, model_id, bento_model.tag, human_size)
                return model_id

            finally:
                # 清理临时文件
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_CREATE.value,
                user_id=created_by,
                ip_address=ip_address,
                resource_type="model",
                details={
                    "model_name": model_name,
                    "model_version": model_version,
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            _logger.error("模型注册失败: %s v%s, 错误: %s", model_name, model_version, str(e), exc_info=True)
            raise

    @staticmethod
    def _save_to_bentoml(
            name: str,
            model_path: Path,
            framework: Framework,
            metadata: Dict,
            labels: Dict
    ) -> bentoml.Model:
        """
        保存模型到 BentoML Model Store

        参数:
            name: 模型名称（使用 model_id）
            model_path: 模型文件路径
            framework: 模型框架
            metadata: 元数据
            labels: 标签

        返回:
            BentoML 模型对象
        """
        # 获取框架字符串
        framework_str = framework.value.lower() if isinstance(framework, Framework) else str(framework).lower()

        bentoml_backend = get_bentoml_backend(framework_str)
        signatures = get_framework_signatures(framework_str)

        try:
            # 根据框架加载模型
            if framework_str == 'sklearn':
                import joblib
                model = joblib.load(model_path)
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework_str == 'xgboost':
                import xgboost as xgb
                model = xgb.Booster()
                model.load_model(str(model_path))
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework_str == 'lightgbm':
                import lightgbm as lgb
                model = lgb.Booster(model_file=str(model_path))
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework_str == 'catboost':
                from catboost import CatBoost
                model = CatBoost()
                model.load_model(str(model_path))
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework_str in ['torch', 'pytorch']:
                import torch
                model = torch.load(model_path, map_location='cpu')
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework_str == 'tensorflow':
                import tensorflow as tf
                model = tf.keras.models.load_model(model_path)
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework_str == 'onnx':
                import onnxruntime as ort
                model = ort.InferenceSession(str(model_path))
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )
            else:
                # 使用 pickle 保存
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
                return bentoml_backend.save_model(
                    name=name.lower(),
                    model=model,
                    labels=labels,
                    metadata=metadata
                )

        except Exception as e:
            raise ModelFileException(f"保存到 BentoML 失败: {str(e)}")

    @staticmethod
    def _calculate_file_hash(file_path: Path) -> str:
        """计算文件 SHA256 哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def activate_model(self, model_id: str, operator: str, reason: str = None, ip_address: str = None):
        """
        激活模型

        参数:
            model_id: 模型ID
            operator: 操作人
            reason: 操作原因
            ip_address: IP地址
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                before_status = model.status
                model.status = ModelStatus.ACTIVE.value
                model.updated_at = datetime.now()

                model_name = model.model_name
                model_version = model.model_version

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model_version,
                    operation=AuditAction.MODEL_ACTIVATE.value,
                    operator=operator,
                    operator_ip=ip_address,
                    reason=reason,
                    metadata_snapshot=self._create_snapshot(model),
                    details={
                        'before_status': before_status,
                        'request_id': request_id,
                        'trace_id': trace_id,
                        'span_id': span_id,
                        'parent_span_id': parent_span_id
                    }
                )
                session.add(history)
                session.commit()

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_performance(
                operation=PerformanceOperation.MODEL_LOAD,
                duration_ms=duration,
                model_id=model_id,
                request_id=request_id,
                extra={
                    "model_name": model_name,
                    "model_version": model_version,
                    "action": "activate",
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            log_audit(
                action=AuditAction.MODEL_ACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                resource_name=model_name,
                details={
                    "before_status": before_status,
                    "after_status": ModelStatus.ACTIVE.value,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            _logger.info("模型激活成功: %s v%s", model_name, model_version)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_ACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            _logger.error("模型激活失败: %s, 错误: %s", model_id, str(e), exc_info=True)
            raise

    def deactivate_model(self, model_id: str, operator: str, reason: str = None, ip_address: str = None):
        """
        停用模型

        参数:
            model_id: 模型ID
            operator: 操作人
            reason: 操作原因
            ip_address: IP地址
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                before_status = model.status
                model.status = ModelStatus.INACTIVE.value
                model.updated_at = datetime.now()

                model_name = model.model_name
                model_version = model.model_version

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model_version,
                    operation=AuditAction.MODEL_DEACTIVATE.value,
                    operator=operator,
                    operator_ip=ip_address,
                    reason=reason,
                    metadata_snapshot=self._create_snapshot(model),
                    details={
                        'before_status': before_status,
                        'request_id': request_id,
                        'trace_id': trace_id,
                        'span_id': span_id,
                        'parent_span_id': parent_span_id
                    }
                )
                session.add(history)
                session.commit()

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_audit(
                action=AuditAction.MODEL_DEACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                resource_name=model_name,
                details={
                    "before_status": before_status,
                    "after_status": ModelStatus.INACTIVE.value,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            _logger.info("模型停用成功: %s v%s", model_name, model_version)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_DEACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            _logger.error("模型停用失败: %s, 错误: %s", model_id, str(e), exc_info=True)
            raise

    def promote_to_production(self, model_id: str, operator: str, reason: str = None, ip_address: str = None):
        """
        将模型提升为生产模型（允许多个生产模型共存）

        注意：此方法不会降级其他生产模型，同一任务类型下可以有多个生产模型，
        用于支持 A/B 测试、灰度发布等场景。

        参数:
            model_id: 模型ID
            operator: 操作人
            reason: 提升原因
            ip_address: IP地址
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                model_name = model.model_name
                model_version = model.model_version
                task_type = model.task_type

                # 记录提升前的状态
                before_prod = model.is_production

                # 设置为生产模型
                model.is_production = True
                model.deployed_at = datetime.now()

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model_version,
                    operation=AuditAction.MODEL_PROMOTE.value,
                    operator=operator,
                    operator_ip=ip_address,
                    reason=reason,
                    metadata_snapshot=self._create_snapshot(model),
                    details={
                        'before_production': before_prod,
                        'after_production': True,
                        'task_type': task_type,
                        'request_id': request_id,
                        'trace_id': trace_id,
                        'span_id': span_id,
                        'parent_span_id': parent_span_id
                    }
                )
                session.add(history)
                session.commit()

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_audit(
                action=AuditAction.MODEL_PROMOTE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                resource_name=model_name,
                details={
                    "task_type": task_type,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            _logger.info("生产模型设置成功: %s v%s, 任务类型: %s", model_name, model_version, task_type)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_PROMOTE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            _logger.error("生产模型设置失败: %s, 错误: %s", model_id, str(e), exc_info=True)
            raise

    @staticmethod
    def get_production_models(
            task_type: Optional[str] = None,
            model_name: Optional[str] = None,
            include_details: bool = False
    ) -> Union[List[str], List[Dict[str, Any]]]:
        """
        获取生产模型列表

        参数:
            task_type: 可选，按任务类型筛选
            model_name: 可选，按模型名称筛选
            include_details: 是否返回详细信息（默认 False 只返回 ID 列表）

        返回:
            include_details=False 时返回 List[str]（模型ID列表）
            include_details=True 时返回 List[Dict]（模型详细信息）
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with get_db() as session:
                query = session.query(ModelMetadata).filter(
                    ModelMetadata.is_production == True,
                    ModelMetadata.status == ModelStatus.ACTIVE.value
                )

                if task_type:
                    query = query.filter(ModelMetadata.task_type == task_type)

                if model_name:
                    query = query.filter(ModelMetadata.model_name == model_name)

                models = query.order_by(desc(ModelMetadata.updated_at)).all()

                log_audit(
                    action=AuditAction.MODEL_QUERY.value,
                    user_id="system",
                    ip_address=None,
                    resource_type="model",
                    details={
                        "task_type": task_type,
                        "model_name": model_name,
                        "count": len(models),
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                if include_details:
                    return [{
                        'model_id': m.model_id,
                        'model_name': m.model_name,
                        'model_version': m.model_version,
                        'task_type': m.task_type,
                        'model_type': m.model_type,
                        'framework': m.framework,
                        'status': m.status,
                        'is_production': m.is_production,
                        'updated_at': m.updated_at.isoformat() if m.updated_at else None,
                        'deployed_at': m.deployed_at.isoformat() if m.deployed_at else None
                    } for m in models]
                else:
                    return [m.model_id for m in models]

        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_QUERY.value,
                user_id="system",
                ip_address=None,
                resource_type="model",
                details={
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            _logger.error("获取生产模型列表失败: %s", e)
            return []

    @staticmethod
    def get_model_info(model_id: str) -> Optional[Dict]:
        """
        获取模型信息

        参数:
            model_id: 模型ID

        返回:
            模型信息字典，如果不存在则返回 None
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    return None

                return {
                    'model_id': model.model_id,
                    'model_name': model.model_name,
                    'model_version': model.model_version,
                    'task_type': model.task_type,
                    'model_type': model.model_type,
                    'framework': model.framework,
                    'file_path': model.file_path,
                    'file_hash': model.file_hash,
                    'file_size': model.file_size,
                    'input_features': model.input_features,
                    'output_schema': model.output_schema,
                    'model_params': model.model_params,
                    'status': model.status,
                    'is_production': model.is_production,
                    'ab_test_group': model.ab_test_group,
                    'created_by': model.created_by,
                    'created_at': model.created_at.isoformat() if model.created_at else None,
                    'updated_at': model.updated_at.isoformat() if model.updated_at else None,
                    'deployed_at': model.deployed_at.isoformat() if model.deployed_at else None,
                    'description': model.description,
                    'tags': model.tags,
                    'metadata_json': model.metadata_json
                }

        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_QUERY.value,
                user_id="system",
                ip_address="localhost",
                resource_type="model",
                resource_id=model_id,
                details={
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            _logger.debug("获取模型信息失败: %s, 错误: %s", model_id, str(e))
            raise

    @staticmethod
    def list_models(
            task_type: Optional[str] = None,
            status: Optional[str] = None,
            model_type: Optional[str] = None,
            framework: Optional[str] = None,
            is_production: Optional[bool] = None
    ) -> List[Dict]:
        """
        列出模型

        参数:
            task_type: 任务类型筛选
            status: 状态筛选
            model_type: 模型类型筛选
            framework: 框架筛选
            is_production: 是否生产模型筛选

        返回:
            模型信息列表
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with get_db() as session:
                query = session.query(ModelMetadata)

                if task_type:
                    query = query.filter_by(task_type=task_type)
                if status:
                    query = query.filter_by(status=status)
                if model_type:
                    query = query.filter_by(model_type=model_type)
                if framework:
                    query = query.filter_by(framework=framework)
                if is_production is not None:
                    query = query.filter_by(is_production=is_production)

                models = query.order_by(desc(ModelMetadata.created_at)).all()

                return [{
                    'model_id': m.model_id,
                    'model_name': m.model_name,
                    'model_version': m.model_version,
                    'task_type': m.task_type,
                    'model_type': m.model_type,
                    'framework': m.framework,
                    'status': m.status,
                    'is_production': m.is_production,
                    'ab_test_group': m.ab_test_group,
                    'created_by': m.created_by,
                    'created_at': m.created_at.isoformat() if m.created_at else None
                } for m in models]

        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_QUERY.value,
                user_id="system",
                ip_address="localhost",
                resource_type="model",
                details={
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            _logger.debug("列出模型失败: %s", str(e))
            raise

    @staticmethod
    def get_model_history(model_id: str) -> List[Dict]:
        """
        获取模型历史

        参数:
            model_id: 模型ID

        返回:
            历史记录列表
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with get_db() as session:
                history = session.query(ModelVersionHistory).filter_by(
                    model_id=model_id
                ).order_by(desc(ModelVersionHistory.operation_time)).all()

                return [{
                    'operation': h.operation,
                    'operator': h.operator,
                    'operation_time': h.operation_time.isoformat(),
                    'reason': h.reason,
                    'details': h.details
                } for h in history]

        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_QUERY.value,
                user_id="system",
                ip_address="localhost",
                resource_type="model",
                resource_id=model_id,
                details={
                    "error": str(e),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )
            _logger.debug("获取模型历史失败: %s, 错误: %s", model_id, str(e))
            raise

    def update_model_config(
            self,
            model_id: str,
            operator: str,
            scorecard_config: Optional[Dict] = None,
            fraud_config: Optional[Dict] = None,
            reason: str = None,
            ip_address: str = None
    ):
        """
        更新模型的评分卡配置或反欺诈配置

        参数:
            model_id: 模型ID
            operator: 操作人
            scorecard_config: 评分卡配置参数
            fraud_config: 反欺诈配置参数
            reason: 操作原因
            ip_address: IP地址
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                if scorecard_config and model.task_type == TaskType.SCORING.value:
                    self._validate_scorecard_config(scorecard_config)
                    _logger.debug("验证评分卡配置通过: %s", model_id)

                if fraud_config and model.task_type == TaskType.FRAUD_DETECTION.value:
                    self._validate_fraud_config(fraud_config)
                    _logger.debug("验证反欺诈配置通过: %s", model_id)

                if not model.model_params:
                    model.model_params = {}

                if scorecard_config:
                    model.model_params['scorecard'] = scorecard_config
                    _logger.debug("更新评分卡配置: %s", model_id)

                if fraud_config:
                    model.model_params['fraud'] = fraud_config
                    _logger.debug("更新反欺诈配置: %s", model_id)

                if not model.metadata_json:
                    model.metadata_json = {}

                if scorecard_config:
                    model.metadata_json['scorecard_config'] = scorecard_config
                if fraud_config:
                    model.metadata_json['fraud_config'] = fraud_config

                model.updated_at = datetime.now()

                model_name = model.model_name
                model_version = model.model_version

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model_version,
                    operation=AuditAction.MODEL_UPDATE.value,
                    operator=operator,
                    operator_ip=ip_address,
                    reason=reason,
                    metadata_snapshot=self._create_snapshot(model),
                    details={
                        'updated_params': {
                            'scorecard': scorecard_config,
                            'fraud': fraud_config
                        },
                        'request_id': request_id,
                        'trace_id': trace_id,
                        'span_id': span_id,
                        'parent_span_id': parent_span_id
                    }
                )
                session.add(history)
                session.commit()

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_audit(
                action=AuditAction.MODEL_UPDATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                resource_name=model_name,
                details={
                    "scorecard_updated": scorecard_config is not None,
                    "fraud_updated": fraud_config is not None,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            _logger.info("模型配置更新成功: %s v%s", model_name, model_version)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_UPDATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            _logger.error("模型配置更新失败: %s, 错误: %s", model_id, str(e), exc_info=True)
            raise

    def archive_model(self, model_id: str, operator: str, reason: str = None, ip_address: str = None):
        """
        归档模型（软删除）

        参数:
            model_id: 模型ID
            operator: 操作人
            reason: 操作原因
            ip_address: IP地址
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                before_status = model.status
                model.status = ModelStatus.ARCHIVED.value
                model.archived_at = datetime.now()

                model_name = model.model_name
                model_version = model.model_version

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model_version,
                    operation=AuditAction.MODEL_ARCHIVE.value,
                    operator=operator,
                    operator_ip=ip_address,
                    reason=reason,
                    metadata_snapshot=self._create_snapshot(model),
                    details={
                        'before_status': before_status,
                        'request_id': request_id,
                        'trace_id': trace_id,
                        'span_id': span_id,
                        'parent_span_id': parent_span_id
                    }
                )
                session.add(history)
                session.commit()

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_audit(
                action=AuditAction.MODEL_ARCHIVE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                resource_name=model_name,
                details={
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            _logger.info("模型归档成功: %s v%s", model_name, model_version)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_ARCHIVE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="model",
                resource_id=model_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            _logger.error("模型归档失败: %s, 错误: %s", model_id, str(e), exc_info=True)
            raise

    @staticmethod
    def delete_from_bentoml(model_id: str) -> bool:
        """
        从 BentoML Model Store 删除模型

        参数:
            model_id: 模型ID

        返回:
            是否删除成功
        """
        try:
            bentoml.models.delete(model_id)
            _logger.info("从 BentoML 删除模型成功: %s", model_id)
            return True
        except BentoMLException as e:
            _logger.warning("从 BentoML 删除模型失败: %s, 错误: %s", model_id, str(e))
            return False

    def _validate_task_specific_config(
            self,
            task_type: str,
            scorecard_config: Optional[Dict] = None,
            fraud_config: Optional[Dict] = None
    ):
        """验证任务特定的配置参数"""
        if task_type == TaskType.SCORING.value and scorecard_config:
            self._validate_scorecard_config(scorecard_config)
        if task_type == TaskType.FRAUD_DETECTION.value and fraud_config:
            self._validate_fraud_config(fraud_config)

    @staticmethod
    def _validate_scorecard_config(config: Dict):
        """验证评分卡配置"""
        if 'base_score' in config:
            try:
                base_score = int(config['base_score'])
                if base_score < 0:
                    raise ValueError("base_score 必须大于等于0")
            except (ValueError, TypeError):
                raise ModelValidationException("base_score 必须是有效的整数")

        if 'pdo' in config:
            try:
                pdo = float(config['pdo'])
                if pdo <= 0:
                    raise ValueError("pdo 必须大于0")
            except (ValueError, TypeError):
                raise ModelValidationException("pdo 必须是有效的正数")

        if 'min_score' in config and 'max_score' in config:
            try:
                min_score = int(config['min_score'])
                max_score = int(config['max_score'])
                if min_score >= max_score:
                    raise ValueError("min_score 必须小于 max_score")
            except (ValueError, TypeError):
                raise ModelValidationException("min_score 和 max_score 必须是有效的整数")

        if 'direction' in config:
            direction = config['direction']
            if direction not in ["lower_better", "higher_better"]:
                raise ModelValidationException(
                    "direction 必须是 'lower_better' 或 'higher_better'"
                )

    @staticmethod
    def _validate_fraud_config(config: Dict):
        """验证反欺诈配置"""
        if 'threshold' in config:
            threshold = config['threshold']
            if not isinstance(threshold, (int, float)) or not 0 <= threshold <= 1:
                raise ModelValidationException("threshold 必须是 0-1 之间的数字")

        if 'risk_levels' in config:
            risk_levels = config['risk_levels']
            if not isinstance(risk_levels, dict):
                raise ModelValidationException("risk_levels 必须是字典类型")

        if 'output_fields' in config:
            output_fields = config['output_fields']
            if not isinstance(output_fields, list):
                raise ModelValidationException("output_fields 必须是列表类型")

    @staticmethod
    def _merge_model_params(
            model_params: Optional[Dict],
            scorecard_config: Optional[Dict],
            fraud_config: Optional[Dict],
            task_type: str
    ) -> Dict:
        """合并模型参数"""
        merged = model_params.copy() if model_params else {}

        if task_type == TaskType.SCORING.value and scorecard_config:
            merged['scorecard'] = scorecard_config

        if task_type == TaskType.FRAUD_DETECTION.value and fraud_config:
            merged['fraud'] = fraud_config

        return merged

    @staticmethod
    def _create_snapshot(metadata) -> Dict:
        """创建元数据快照"""
        return {
            'model_id': metadata.model_id,
            'model_name': metadata.model_name,
            'model_version': metadata.model_version,
            'task_type': metadata.task_type,
            'model_type': metadata.model_type,
            'framework': metadata.framework,
            'created_by': metadata.created_by,
            'created_at': metadata.created_at.isoformat() if metadata.created_at else None
        }


# ==================== 工厂函数 ====================
_model_registry: Optional[ModelRegistry] = None
_registry_lock = threading.Lock()


def get_model_registry() -> ModelRegistry:
    """获取模型注册中心实例"""
    global _model_registry

    if _model_registry is None:
        with _registry_lock:
            if _model_registry is None:
                _model_registry = ModelRegistry()

    return _model_registry