# core/model_registry.py
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import uuid
import joblib
import yaml

from sqlalchemy.orm import Session
from .models import ModelMetadata, ModelVersionHistory, AuditLog
from .database import get_db_session
from .log_manager import log_manager
from .exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelFileException
)
from ..config.settings import settings


class ModelRegistry:
    """模型注册中心 - 管理模型的生命周期"""

    def __init__(self):
        self.storage_path = Path(settings.MODELS_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def register_model(
        self,
        model_name: str,
        model_version: str,
        model_type: str,
        framework: str,
        model_file_path: Path,
        input_features: List[str],
        output_schema: Dict[str, str],
        created_by: str,
        description: Optional[str] = None,
        model_file=None  # 支持直接上传文件对象
    ) -> str:
        """
        注册新模型

        Args:
            model_name: 模型名称
            model_version: 模型版本
            model_type: 模型类型
            framework: 模型框架
            model_file_path: 模型文件路径
            input_features: 输入特征列表
            output_schema: 输出格式定义
            created_by: 创建人
            description: 描述
            model_file: 模型文件对象（可选）

        Returns:
            model_id: 生成的模型ID
        """
        try:
            # 生成模型ID
            model_id = f"MDL_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8].upper()}"

            # 计算文件哈希和大小
            if model_file:
                # 保存上传的文件
                file_hash, file_size = self._save_uploaded_file(
                    model_file,
                    model_id,
                    model_version,
                    framework
                )
                file_path = self._get_model_path(model_id, model_version, framework)
            else:
                # 复制本地文件
                file_hash, file_size, file_path = self._copy_model_file(
                    model_file_path,
                    model_id,
                    model_version,
                    framework
                )

            # 验证模型文件
            self._validate_model_file(file_path, framework, model_type)

            # 创建元数据
            metadata = ModelMetadata(
                model_id=model_id,
                model_name=model_name,
                model_version=model_version,
                model_type=model_type,
                framework=framework,
                file_path=str(file_path),
                file_hash=file_hash,
                file_size=file_size,
                input_features=input_features,
                output_schema=output_schema,
                status='inactive',
                created_by=created_by,
                description=description
            )

            # 保存到数据库
            with get_db_session() as session:
                # 检查是否已存在相同名称和版本的模型
                existing = session.query(ModelMetadata).filter_by(
                    model_name=model_name,
                    model_version=model_version
                ).first()

                if existing:
                    raise ModelAlreadyExistsException(
                        f"Model {model_name} version {model_version} already exists"
                    )

                session.add(metadata)
                session.flush()

                # 记录历史
                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model_version,
                    operation='REGISTER',
                    operator=created_by,
                    metadata_snapshot=self._create_snapshot(metadata)
                )
                session.add(history)

                # 记录审计日志
                audit = AuditLog(
                    audit_id=f"AUD_{uuid.uuid4().hex[:12].upper()}",
                    event_type='MODEL_OPERATION',
                    operator=created_by,
                    resource_type='model',
                    resource_id=model_id,
                    action='REGISTER',
                    after_state={'model_id': model_id, 'model_name': model_name},
                    result='SUCCESS'
                )
                session.add(audit)

                session.commit()

            # 记录业务日志
            log_manager.log_audit(
                action='MODEL_REGISTER',
                user_id=created_by,
                model_id=model_id,
                model_name=model_name,
                model_version=model_version
            )

            return model_id

        except Exception as e:
            log_manager.log_audit(
                action='MODEL_REGISTER_FAILED',
                user_id=created_by,
                model_name=model_name,
                model_version=model_version,
                error=str(e)
            )
            raise

    def _save_uploaded_file(self, file_obj, model_id: str, version: str, framework: str) -> Tuple[str, int]:
        """保存上传的文件"""
        model_dir = self.storage_path / model_id / 'versions'
        model_dir.mkdir(parents=True, exist_ok=True)

        # 根据框架确定文件扩展名
        ext_map = {
            'sklearn': 'pkl',
            'xgboost': 'json' if settings.XGBOOST_USE_JSON else 'model',
            'lightgbm': 'txt',
            'torch': 'pt',
            'tensorflow': 'h5',
            'onnx': 'onnx',
            'catboost': 'cbm'
        }
        ext = ext_map.get(framework, 'bin')

        file_path = model_dir / f"model_{version}.{ext}"

        # 保存文件
        with open(file_path, 'wb') as f:
            if hasattr(file_obj, 'read'):
                f.write(file_obj.read())
            else:
                f.write(file_obj)

        # 计算哈希和大小
        file_hash = self._calculate_file_hash(file_path)
        file_size = file_path.stat().st_size

        # 创建符号链接 latest
        latest_link = self.storage_path / model_id / 'latest'
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(f"versions/model_{version}.{ext}")

        return file_hash, file_size

    def _copy_model_file(self, source_path: Path, model_id: str, version: str, framework: str) -> Tuple[str, int, Path]:
        """复制模型文件"""
        if not source_path.exists():
            raise ModelFileException(f"Model file not found: {source_path}")

        model_dir = self.storage_path / model_id / 'versions'
        model_dir.mkdir(parents=True, exist_ok=True)

        # 根据源文件扩展名确定目标文件名
        ext = source_path.suffix
        if not ext:
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

        dest_path = model_dir / f"model_{version}{ext}"

        # 复制文件
        shutil.copy2(source_path, dest_path)

        # 计算哈希和大小
        file_hash = self._calculate_file_hash(dest_path)
        file_size = dest_path.stat().st_size

        # 创建符号链接 latest
        latest_link = self.storage_path / model_id / 'latest'
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        latest_link.symlink_to(f"versions/model_{version}{ext}")

        return file_hash, file_size, dest_path

    def _validate_model_file(self, file_path: Path, framework: str, model_type: str):
        """验证模型文件"""
        try:
            if framework == 'sklearn':
                model = joblib.load(file_path)
                # 验证模型类型
                expected_types = {
                    'decision_tree': 'DecisionTree',
                    'random_forest': 'RandomForest',
                    'xgboost': 'XGB',
                    'lightgbm': 'LGBM',
                    'logistic_regression': 'LogisticRegression'
                }
                model_class = model.__class__.__name__
                if expected_types.get(model_type) not in model_class:
                    raise ModelValidationException(
                        f"Model type mismatch: expected {model_type}, got {model_class}"
                    )

            elif framework == 'xgboost':
                import xgboost as xgb
                if file_path.suffix == '.json':
                    model = xgb.Booster()
                    model.load_model(str(file_path))
                else:
                    model = xgb.Booster()
                    model.load_model(str(file_path))

            # 其他框架的验证...

        except Exception as e:
            raise ModelValidationException(f"Model validation failed: {str(e)}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        """计算文件SHA256哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _create_snapshot(self, metadata) -> Dict:
        """创建元数据快照"""
        return {
            'model_id': metadata.model_id,
            'model_name': metadata.model_name,
            'model_version': metadata.model_version,
            'model_type': metadata.model_type,
            'framework': metadata.framework,
            'input_features': metadata.input_features,
            'output_schema': metadata.output_schema,
            'created_by': metadata.created_by,
            'created_at': metadata.created_at.isoformat() if metadata.created_at else None
        }

    def _get_model_path(self, model_id: str, version: str, framework: str) -> Path:
        """获取模型文件路径"""
        ext_map = {
            'sklearn': 'pkl',
            'xgboost': 'json',
            'lightgbm': 'txt',
            'torch': 'pt',
            'tensorflow': 'h5',
            'onnx': 'onnx',
            'catboost': 'cbm'
        }
        ext = ext_map.get(framework, 'bin')
        return self.storage_path / model_id / 'versions' / f"model_{version}.{ext}"

    def activate_model(self, model_id: str, operator: str):
        """激活模型"""
        with get_db_session() as session:
            model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
            if not model:
                raise ModelNotFoundException(f"Model not found: {model_id}")

            model.status = 'active'
            model.updated_at = datetime.now()

            history = ModelVersionHistory(
                model_id=model_id,
                model_version=model.model_version,
                operation='ACTIVATE',
                operator=operator
            )
            session.add(history)
            session.commit()

        log_manager.log_audit(
            action='MODEL_ACTIVATE',
            user_id=operator,
            model_id=model_id
        )

    def deactivate_model(self, model_id: str, operator: str):
        """停用模型"""
        with get_db_session() as session:
            model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
            if not model:
                raise ModelNotFoundException(f"Model not found: {model_id}")

            model.status = 'inactive'
            model.updated_at = datetime.now()

            history = ModelVersionHistory(
                model_id=model_id,
                model_version=model.model_version,
                operation='DEACTIVATE',
                operator=operator
            )
            session.add(history)
            session.commit()

        log_manager.log_audit(
            action='MODEL_DEACTIVATE',
            user_id=operator,
            model_id=model_id
        )

    def set_production_model(self, model_id: str, operator: str):
        """设置为生产模型"""
        with get_db_session() as session:
            # 先将所有模型设为非生产
            session.query(ModelMetadata).filter_by(is_production=True).update(
                {'is_production': False}
            )

            # 设置当前模型为生产
            model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
            if not model:
                raise ModelNotFoundException(f"Model not found: {model_id}")

            model.is_production = True
            model.deployed_at = datetime.now()

            history = ModelVersionHistory(
                model_id=model_id,
                model_version=model.model_version,
                operation='SET_PRODUCTION',
                operator=operator
            )
            session.add(history)
            session.commit()

        log_manager.log_audit(
            action='MODEL_SET_PRODUCTION',
            user_id=operator,
            model_id=model_id
        )

    def get_model_info(self, model_id: str) -> Optional[Dict]:
        """获取模型信息"""
        with get_db_session() as session:
            model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
            if model:
                return {
                    'model_id': model.model_id,
                    'model_name': model.model_name,
                    'model_version': model.model_version,
                    'model_type': model.model_type,
                    'framework': model.framework,
                    'status': model.status,
                    'is_production': model.is_production,
                    'created_by': model.created_by,
                    'created_at': model.created_at.isoformat() if model.created_at else None,
                    'description': model.description
                }
            return None

    def list_models(
        self,
        status: Optional[str] = None,
        model_type: Optional[str] = None,
        framework: Optional[str] = None
    ) -> List[Dict]:
        """列出模型"""
        with get_db_session() as session:
            query = session.query(ModelMetadata)

            if status:
                query = query.filter_by(status=status)
            if model_type:
                query = query.filter_by(model_type=model_type)
            if framework:
                query = query.filter_by(framework=framework)

            models = query.order_by(ModelMetadata.created_at.desc()).all()

            return [{
                'model_id': m.model_id,
                'model_name': m.model_name,
                'model_version': m.model_version,
                'model_type': m.model_type,
                'framework': m.framework,
                'status': m.status,
                'is_production': m.is_production,
                'created_by': m.created_by,
                'created_at': m.created_at.isoformat() if m.created_at else None
            } for m in models]

    def get_model_history(self, model_id: str) -> List[Dict]:
        """获取模型历史"""
        with get_db_session() as session:
            history = session.query(ModelVersionHistory).filter_by(
                model_id=model_id
            ).order_by(ModelVersionHistory.operation_time.desc()).all()

            return [{
                'operation': h.operation,
                'operator': h.operator,
                'operation_time': h.operation_time.isoformat(),
                'reason': h.reason,
                'metadata_snapshot': h.metadata_snapshot
            } for h in history]


# 全局模型注册中心实例
model_registry = ModelRegistry()