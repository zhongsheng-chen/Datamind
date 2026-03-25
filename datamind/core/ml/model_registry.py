# datamind/core/ml/model_registry.py

"""模型注册中心

负责模型的注册、版本管理、状态管理和配置管理。

核心功能：
  - register_model: 注册新模型，保存模型文件到 BentoML Model Store
  - activate_model: 激活模型（设置为 active 状态）
  - deactivate_model: 停用模型（设置为 inactive 状态）
  - promote_to_production: 提升模型为生产模型
  - get_model_info: 获取模型详细信息
  - list_models: 列出模型（支持多维度筛选）
  - get_model_history: 获取模型操作历史
  - update_model_params: 更新模型参数（评分卡/风险配置）

特性：
  - 版本管理：支持模型版本控制和历史追溯
  - 生产环境管理：同一任务类型只能有一个生产模型
  - 配置验证：自动验证评分卡参数和风险配置
  - BentoML 集成：模型存储在 BentoML Model Store
  - 完整审计：记录所有模型操作到版本历史表
  - 链路追踪：完整的 span 追踪
"""

import os
import tempfile
import shutil
import hashlib
import uuid
import pickle
from pathlib import Path
from typing import Dict, Optional, List, BinaryIO, Any
from datetime import datetime

import bentoml
from bentoml.exceptions import BentoMLException

from datamind.core.db.database import get_db
from datamind.core.db.models import ModelMetadata, ModelVersionHistory
from datamind.core.domain.enums import ModelStatus, AuditAction, TaskType, ModelType, Framework
from datamind.core.domain.validation import validate_or_raise
from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.core.ml.exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelFileException,
    UnsupportedFrameworkException
)
from datamind.core.ml.frameworks import (
    get_bentoml_backend,
    get_framework_signatures,
    is_framework_supported,
    get_supported_frameworks
)


class ModelRegistry:
    """模型注册中心"""

    def __init__(self, settings=None):
        """
        初始化模型注册中心

        参数:
            settings: 配置对象
        """
        from datamind.config import get_settings, BASE_DIR

        if settings is None:
            settings = get_settings()

        model_config = settings.model

        # 构建绝对路径（本地缓存路径）
        models_path = model_config.models_path
        if os.path.isabs(models_path):
            self.cache_path = Path(models_path)
        else:
            self.cache_path = BASE_DIR / models_path
        self.cache_path.mkdir(parents=True, exist_ok=True)

        debug_print("ModelRegistry", f"模型存储路径: {self.cache_path.absolute()}")

    def register_model(
            self,
            model_name: str,
            model_version: str,
            task_type: str,
            model_type: str,
            framework: str,
            input_features: List[str],
            output_schema: Dict[str, str],
            created_by: str,
            model_file: BinaryIO,
            description: Optional[str] = None,
            model_params: Optional[Dict] = None,
            tags: Optional[Dict] = None,
            ip_address: Optional[str] = None,
            scorecard_params: Optional[Dict] = None,
            risk_config: Optional[Dict] = None
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
            scorecard_params: 评分卡配置参数
            risk_config: 风险配置参数

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
                scorecard_params=scorecard_params,
                risk_config=risk_config
            )

            # 合并配置到 model_params
            merged_model_params = self._merge_model_params(
                model_params=model_params,
                scorecard_params=scorecard_params,
                risk_config=risk_config,
                task_type=task_type
            )

            # 检查模型是否已存在
            with get_db() as session:
                existing = session.query(ModelMetadata).filter_by(
                    model_name=model_name,
                    model_version=model_version
                ).first()
                if existing:
                    raise ModelAlreadyExistsException(
                        f"模型 {model_name} 版本 {model_version} 已存在"
                    )

            # 保存模型文件到临时文件
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                shutil.copyfileobj(model_file, tmp_file)
                tmp_path = Path(tmp_file.name)

            try:
                # 获取文件信息
                file_size = tmp_path.stat().st_size
                file_hash = self._calculate_file_hash(tmp_path)

                # 准备元数据
                metadata = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "model_version": model_version,
                    "task_type": task_type,
                    "model_type": model_type,
                    "framework": framework,
                    "input_features": input_features,
                    "output_schema": output_schema,
                    "model_params": merged_model_params,
                    "scorecard_params": scorecard_params,
                    "risk_config": risk_config,
                    "description": description,
                    "tags": tags or {},
                    "created_by": created_by,
                    "created_at": datetime.now().isoformat()
                }

                # 保存到 BentoML Model Store
                bento_model = self._save_to_bentoml(
                    name=model_id,
                    model_path=tmp_path,
                    framework=framework,
                    metadata=metadata,
                    labels={
                        "model_id": model_id,
                        "model_name": model_name,
                        "model_version": model_version,
                        "task_type": task_type,
                        "model_type": model_type,
                        "framework": framework,
                        "created_by": created_by
                    }
                )

                # 保存到本地缓存（用于调试）
                cached_path = self.cache_path / model_id / 'versions' / f"model_{model_version}"
                cached_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(tmp_path, cached_path)

                # 创建最新版本软链接
                latest_link = self.cache_path / model_id / 'latest'
                if latest_link.exists() or latest_link.is_symlink():
                    latest_link.unlink()
                latest_link.symlink_to(f"versions/model_{model_version}")

                # 创建元数据
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
                        metadata_json={
                            "bentoml_tag": str(bento_model.tag),
                            "bentoml_version": bento_model.version
                        }
                    )
                    session.add(metadata_record)
                    session.flush()

                    # 记录版本历史
                    history_details = {
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

                    if scorecard_params:
                        history_details['scorecard_params'] = scorecard_params
                    if risk_config:
                        history_details['risk_config'] = risk_config

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

                audit_details = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "model_version": model_version,
                    "task_type": task_type,
                    "model_type": model_type,
                    "framework": framework,
                    "bentoml_tag": str(bento_model.tag),
                    "file_size": file_size,
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }

                if scorecard_params:
                    audit_details["scorecard_params"] = scorecard_params
                if risk_config:
                    audit_details["risk_config"] = risk_config

                log_audit(
                    action=AuditAction.MODEL_CREATE.value,
                    user_id=created_by,
                    ip_address=ip_address,
                    details=audit_details,
                    request_id=request_id
                )

                debug_print("ModelRegistry", f"模型注册成功: {model_id} -> {bento_model.tag}")
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
                details={
                    "model_name": model_name,
                    "model_version": model_version,
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    def _save_to_bentoml(
            self,
            name: str,
            model_path: Path,
            framework: str,
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
        bentoml_backend = get_bentoml_backend(framework)
        signatures = get_framework_signatures(framework)

        try:
            # 根据框架加载模型
            if framework.lower() == 'sklearn':
                import joblib
                model = joblib.load(model_path)
                return bentoml_backend.save_model(
                    name=name,
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework.lower() == 'xgboost':
                import xgboost as xgb
                model = xgb.Booster()
                model.load_model(str(model_path))
                return bentoml_backend.save_model(
                    name=name,
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework.lower() == 'lightgbm':
                import lightgbm as lgb
                model = lgb.Booster(model_file=str(model_path))
                return bentoml_backend.save_model(
                    name=name,
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework.lower() == 'catboost':
                from catboost import CatBoost
                model = CatBoost()
                model.load_model(str(model_path))
                return bentoml_backend.save_model(
                    name=name,
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework.lower() in ['torch', 'pytorch']:
                import torch
                model = torch.load(model_path, map_location='cpu')
                return bentoml_backend.save_model(
                    name=name,
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework.lower() == 'tensorflow':
                import tensorflow as tf
                model = tf.keras.models.load_model(model_path)
                return bentoml_backend.save_model(
                    name=name,
                    model=model,
                    signatures=signatures,
                    labels=labels,
                    metadata=metadata
                )

            elif framework.lower() == 'onnx':
                import onnxruntime as ort
                model = ort.InferenceSession(str(model_path))
                return bentoml_backend.save_model(
                    name=name,
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
                    name=name,
                    model=model,
                    labels=labels,
                    metadata=metadata
                )

        except Exception as e:
            raise ModelFileException(f"保存到 BentoML 失败: {str(e)}")

    def _calculate_file_hash(self, file_path: Path) -> str:
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

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model.model_version,
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
            log_audit(
                action=AuditAction.MODEL_ACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "model_name": model.model_name,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("ModelRegistry", f"模型激活成功: {model_id}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_ACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
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

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model.model_version,
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
                details={
                    "model_id": model_id,
                    "model_name": model.model_name,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("ModelRegistry", f"模型停用成功: {model_id}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_DEACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    def promote_to_production(self, model_id: str, operator: str, reason: str = None, ip_address: str = None):
        """
        将模型提升为生产模型

        同一任务类型只能有一个生产模型

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

                # 将同任务类型的其他模型设为非生产
                session.query(ModelMetadata).filter_by(
                    task_type=model.task_type,
                    is_production=True
                ).update({'is_production': False})

                # 设置当前模型为生产
                before_prod = model.is_production
                model.is_production = True
                model.deployed_at = datetime.now()

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model.model_version,
                    operation=AuditAction.MODEL_PROMOTE.value,
                    operator=operator,
                    operator_ip=ip_address,
                    reason=reason,
                    metadata_snapshot=self._create_snapshot(model),
                    details={
                        'before_production': before_prod,
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
                details={
                    "model_id": model_id,
                    "model_name": model.model_name,
                    "task_type": model.task_type,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("ModelRegistry", f"生产模型设置成功: {model_id}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_PROMOTE.value,
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    def get_model_info(self, model_id: str) -> Optional[Dict]:
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
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )
            raise

    def list_models(
            self,
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

                models = query.order_by(ModelMetadata.created_at.desc()).all()

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
                details={
                    "error": str(e),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )
            raise

    def get_model_history(self, model_id: str) -> List[Dict]:
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
                ).order_by(ModelVersionHistory.operation_time.desc()).all()

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
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )
            raise

    def update_model_params(
            self,
            model_id: str,
            operator: str,
            scorecard_params: Optional[Dict] = None,
            risk_config: Optional[Dict] = None,
            reason: str = None,
            ip_address: str = None
    ):
        """
        更新模型的评分卡配置或风险配置

        参数:
            model_id: 模型ID
            operator: 操作人
            scorecard_params: 评分卡配置参数
            risk_config: 风险配置参数
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

                if scorecard_params and model.task_type == TaskType.SCORING.value:
                    self._validate_scorecard_params(scorecard_params)
                if risk_config and model.task_type == TaskType.FRAUD_DETECTION.value:
                    self._validate_risk_config(risk_config)

                if not model.model_params:
                    model.model_params = {}

                if scorecard_params:
                    model.model_params['scorecard'] = scorecard_params

                if risk_config:
                    model.model_params['risk_config'] = risk_config

                model.updated_at = datetime.now()

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model.model_version,
                    operation=AuditAction.MODEL_UPDATE.value,
                    operator=operator,
                    operator_ip=ip_address,
                    reason=reason,
                    metadata_snapshot=self._create_snapshot(model),
                    details={
                        'updated_params': {
                            'scorecard': scorecard_params,
                            'risk_config': risk_config
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
                details={
                    "model_id": model_id,
                    "model_name": model.model_name,
                    "scorecard_updated": scorecard_params is not None,
                    "risk_config_updated": risk_config is not None,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("ModelRegistry", f"模型参数更新成功: {model_id}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.MODEL_UPDATE.value,
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
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

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                before_status = model.status
                model.status = ModelStatus.ARCHIVED.value
                model.archived_at = datetime.now()

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model.model_version,
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

            log_audit(
                action=AuditAction.MODEL_ARCHIVE.value,
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "reason": reason,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            debug_print("ModelRegistry", f"模型归档成功: {model_id}")

        except Exception as e:
            raise

    def delete_from_bentoml(self, model_id: str) -> bool:
        """
        从 BentoML Model Store 删除模型

        参数:
            model_id: 模型ID

        返回:
            是否删除成功
        """
        try:
            bentoml.models.delete(model_id)
            debug_print("ModelRegistry", f"从 BentoML 删除模型成功: {model_id}")
            return True
        except BentoMLException as e:
            debug_print("ModelRegistry", f"从 BentoML 删除模型失败: {e}")
            return False

    def _validate_task_specific_config(
            self,
            task_type: str,
            scorecard_params: Optional[Dict] = None,
            risk_config: Optional[Dict] = None
    ):
        """验证任务特定的配置参数"""
        if task_type == TaskType.SCORING.value and scorecard_params:
            self._validate_scorecard_params(scorecard_params)
        if task_type == TaskType.FRAUD_DETECTION.value and risk_config:
            self._validate_risk_config(risk_config)

    def _validate_scorecard_params(self, params: Dict):
        """验证评分卡参数"""
        if 'base_score' in params:
            try:
                base_score = int(params['base_score'])
                if base_score < 0:
                    raise ValueError("base_score 必须大于等于0")
            except (ValueError, TypeError):
                raise ModelValidationException("base_score 必须是有效的整数")

        if 'pdo' in params:
            try:
                pdo = float(params['pdo'])
                if pdo <= 0:
                    raise ValueError("pdo 必须大于0")
            except (ValueError, TypeError):
                raise ModelValidationException("pdo 必须是有效的正数")

        if 'min_score' in params and 'max_score' in params:
            try:
                min_score = int(params['min_score'])
                max_score = int(params['max_score'])
                if min_score >= max_score:
                    raise ValueError("min_score 必须小于 max_score")
            except (ValueError, TypeError):
                raise ModelValidationException("min_score 和 max_score 必须是有效的整数")

        if 'direction' in params:
            direction = params['direction']
            if direction not in ["lower_better", "higher_better"]:
                raise ModelValidationException(
                    "direction 必须是 'lower_better' 或 'higher_better'"
                )

    def _validate_risk_config(self, config: Dict):
        """验证风险配置"""
        if 'levels' not in config:
            raise ModelValidationException("风险配置必须包含 'levels' 字段")

    def _merge_model_params(
            self,
            model_params: Optional[Dict],
            scorecard_params: Optional[Dict],
            risk_config: Optional[Dict],
            task_type: str
    ) -> Dict:
        """合并模型参数"""
        merged = model_params.copy() if model_params else {}

        if task_type == TaskType.SCORING.value and scorecard_params:
            merged['scorecard'] = scorecard_params

        if task_type == TaskType.FRAUD_DETECTION.value and risk_config:
            merged['risk_config'] = risk_config

        return merged

    def _create_snapshot(self, metadata) -> Dict:
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


# 全局模型注册中心实例
model_registry = ModelRegistry()