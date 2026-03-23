# datamind/core/ml/model_registry.py

"""模型注册中心

负责模型的注册、版本管理、状态管理和配置管理。

核心功能：
  - register_model: 注册新模型，保存模型文件到存储路径
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
  - 文件管理：自动保存模型文件，支持多种格式
  - 完整审计：记录所有模型操作到版本历史表
  - 链路追踪：完整的 span 追踪
"""

import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, BinaryIO
import uuid

from datamind.core.db.database import get_db
from datamind.core.db.models import ModelMetadata, ModelVersionHistory
from datamind.core.logging import log_audit, context
from datamind.core.logging.debug import debug_print
from datamind.core.domain.enums import ModelStatus, AuditAction
from .exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelFileException
)


class ModelRegistry:
    """模型注册中心"""

    def __init__(self, settings=None):
        """
        初始化模型注册中心

        参数:
            settings: 配置对象
        """
        # 如果没有传入 settings，则从配置中获取
        if settings is None:
            from datamind.config import get_settings, BASE_DIR
            settings = get_settings()

        model_config = settings.model

        # 构建绝对路径
        models_path = model_config.models_path
        if os.path.isabs(models_path):
            self.storage_path = Path(models_path)
        else:
            # 使用 BASE_DIR 作为基础目录
            self.storage_path = BASE_DIR / models_path

        self.max_size = model_config.max_size
        self.allowed_extensions = model_config.allowed_extensions

        # 创建目录
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # 输出绝对路径用于调试
        debug_print("ModelRegistry", f"模型存储路径: {self.storage_path.absolute()}")

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
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            # 生成模型ID
            model_id = f"MDL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8].upper()}"

            debug_print("ModelRegistry", f"开始注册模型: {model_name} v{model_version} -> {model_id}")

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

            # 保存模型文件
            file_hash, file_size, file_path = self._save_model_file(
                model_file, model_id, model_version, framework
            )

            # 验证模型文件
            self._validate_model_file(file_path, framework, model_type)

            # 创建元数据
            with get_db() as session:
                # 检查是否已存在相同名称和版本的模型
                existing = session.query(ModelMetadata).filter_by(
                    model_name=model_name,
                    model_version=model_version
                ).first()

                if existing:
                    raise ModelAlreadyExistsException(
                        f"模型 {model_name} 版本 {model_version} 已存在"
                    )

                metadata = ModelMetadata(
                    model_id=model_id,
                    model_name=model_name,
                    model_version=model_version,
                    task_type=task_type,
                    model_type=model_type,
                    framework=framework,
                    file_path=str(file_path),
                    file_hash=file_hash,
                    file_size=file_size,
                    input_features=input_features,
                    output_schema=output_schema,
                    model_params=merged_model_params,
                    status=ModelStatus.INACTIVE.value,
                    created_by=created_by,
                    description=description,
                    tags=tags
                )

                session.add(metadata)
                session.flush()

                # 记录版本历史
                history_details = {
                    'input_features_count': len(input_features),
                    'output_schema_keys': list(output_schema.keys()),
                    'file_size': file_size,
                    'file_hash': file_hash[:8]
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
                    metadata_snapshot=self._create_snapshot(metadata),
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
                "file_size": file_size,
                "duration_ms": round(duration, 2),
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

            debug_print("ModelRegistry", f"模型注册成功: {model_id}")
            return model_id

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
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

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
                    details={'before_status': before_status}
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
                    "model_version": model.model_version,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
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
                    details={'before_status': before_status}
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
                    "model_version": model.model_version,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
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
                    'tags': model.tags
                }

        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_QUERY.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "model_id": model_id,
                    "error": str(e),
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
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )
            raise

    def promote_to_production(self, model_id: str, operator: str, reason: str = None, ip_address: str = None):
        """
        将模型提升为生产模型

        同一任务类型只能有一个生产模型，调用此方法会自动：
          - 将当前模型设为生产模型
          - 将同任务类型的其他模型设为非生产

        参数:
            model_id: 模型ID
            operator: 操作人
            reason: 提升原因
            ip_address: IP地址
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                # 获取当前模型
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
                    details={'before_production': before_prod}
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
                    "model_version": model.model_version,
                    "task_type": model.task_type,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
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
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
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
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )
            raise

    def get_model_params(self, model_id: str) -> Optional[Dict]:
        """
        获取模型的完整参数

        参数:
            model_id: 模型ID

        返回:
            模型参数字典，如果不存在则返回 None
        """
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    return None

                result = {
                    'model_params': model.model_params
                }

                if model.model_params and 'scorecard' in model.model_params:
                    result['scorecard'] = model.model_params['scorecard']

                if model.model_params and 'risk_config' in model.model_params:
                    result['risk_config'] = model.model_params['risk_config']

                return result

        except Exception as e:
            log_audit(
                action=AuditAction.MODEL_UPDATE.value,
                user_id="system",
                ip_address="localhost",
                details={
                    "model_id": model_id,
                    "error": str(e),
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
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                if scorecard_params and model.task_type == "scoring":
                    self._validate_scorecard_params(scorecard_params)
                if risk_config and model.task_type == "fraud_detection":
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
                        }
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
                    "model_version": model.model_version,
                    "scorecard_updated": scorecard_params is not None,
                    "risk_config_updated": risk_config is not None,
                    "reason": reason,
                    "duration_ms": round(duration, 2),
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
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    def _validate_task_specific_config(
            self,
            task_type: str,
            scorecard_params: Optional[Dict] = None,
            risk_config: Optional[Dict] = None
    ):
        """验证任务特定的配置参数"""
        if task_type == "scoring" and scorecard_params:
            self._validate_scorecard_params(scorecard_params)
        if task_type == "fraud_detection" and risk_config:
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

        levels = config['levels']
        if not isinstance(levels, dict):
            raise ModelValidationException("风险等级配置必须是字典类型")

        thresholds = []
        for level_name, threshold in levels.items():
            if not isinstance(threshold, dict):
                raise ModelValidationException(f"风险等级 '{level_name}' 的配置必须是字典")

            min_val = threshold.get('min', 0)
            max_val = threshold.get('max', 1)

            try:
                min_val = float(min_val)
                max_val = float(max_val)
            except (ValueError, TypeError):
                raise ModelValidationException(
                    f"风险等级 '{level_name}' 的阈值必须是有效的数字"
                )

            if min_val < 0 or max_val > 1 or min_val > max_val:
                raise ModelValidationException(
                    f"风险等级 '{level_name}' 的阈值范围无效"
                )

            thresholds.append((level_name, min_val, max_val))

        thresholds.sort(key=lambda x: x[1])
        for i in range(len(thresholds) - 1):
            current_max = thresholds[i][2]
            next_min = thresholds[i + 1][1]
            if current_max > next_min:
                raise ModelValidationException(
                    f"风险等级 '{thresholds[i][0]}' 和 '{thresholds[i + 1][0]}' 的范围重叠"
                )

    def _merge_model_params(
            self,
            model_params: Optional[Dict],
            scorecard_params: Optional[Dict],
            risk_config: Optional[Dict],
            task_type: str
    ) -> Dict:
        """合并模型参数"""
        merged = model_params.copy() if model_params else {}

        if task_type == "scoring" and scorecard_params:
            merged['scorecard'] = scorecard_params

        if task_type == "fraud_detection" and risk_config:
            merged['risk_config'] = risk_config

        return merged

    def _save_model_file(self, file_obj: BinaryIO, model_id: str, version: str, framework: str) -> tuple:
        """
        保存模型文件

        参数:
            file_obj: 文件对象
            model_id: 模型ID
            version: 版本号
            framework: 框架名称

        返回:
            (文件哈希, 文件大小, 文件路径)
        """
        try:
            model_dir = self.storage_path / model_id / 'versions'
            model_dir.mkdir(parents=True, exist_ok=True)

            ext_map = {
                'sklearn': '.pkl',
                'xgboost': '.json',
                'lightgbm': '.txt',
                'torch': '.pt',
                'tensorflow': '.h5',
                'onnx': '.onnx',
                'catboost': '.cbm'
            }
            ext = ext_map.get(framework, '.bin')

            file_path = model_dir / f"model_{version}{ext}"

            sha256 = hashlib.sha256()
            file_size = 0

            with open(file_path, 'wb') as f:
                while chunk := file_obj.read(8192):
                    f.write(chunk)
                    sha256.update(chunk)
                    file_size += len(chunk)

            file_hash = sha256.hexdigest()

            latest_link = self.storage_path / model_id / 'latest'
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(f"versions/model_{version}{ext}")

            debug_print("ModelRegistry", f"模型文件保存成功: {file_path.absolute()} ({file_size} bytes)")

            return file_hash, file_size, file_path

        except Exception as e:
            raise ModelFileException(f"保存模型文件失败: {str(e)}")

    def _validate_model_file(self, file_path: Path, framework: str, model_type: str):
        """
        验证模型文件

        参数:
            file_path: 文件路径
            framework: 框架名称
            model_type: 模型类型
        """
        try:
            if not file_path.exists():
                raise ModelValidationException(f"模型文件不存在: {file_path}")

            if file_path.stat().st_size == 0:
                raise ModelValidationException("模型文件为空")

            debug_print("ModelRegistry", f"模型文件验证通过: {file_path.absolute()}")

        except Exception as e:
            raise ModelValidationException(f"模型验证失败: {str(e)}")

    def _create_snapshot(self, metadata) -> Dict:
        """创建元数据快照"""
        return {
            'model_id': metadata.model_id,
            'model_name': metadata.model_name,
            'model_version': metadata.model_version,
            'task_type': metadata.task_type,
            'model_type': metadata.model_type,
            'framework': metadata.framework,
            'input_features': metadata.input_features,
            'output_schema': metadata.output_schema,
            'created_by': metadata.created_by,
            'created_at': metadata.created_at.isoformat() if metadata.created_at else None
        }


# 全局模型注册中心实例
model_registry = ModelRegistry()