# Datamind/datamind/core/ml/model_registry.py
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, BinaryIO
import uuid

from datamind.core.db.database import get_db
from datamind.core.db.models import ModelMetadata, ModelVersionHistory
from datamind.core.logging import log_manager, get_request_id, debug_print
from datamind.core.domain.enums import ModelStatus, AuditAction
from datamind.config import get_settings
from .exceptions import (
    ModelNotFoundException,
    ModelAlreadyExistsException,
    ModelValidationException,
    ModelFileException
)


class ModelRegistry:
    """模型注册中心 - 管理模型的生命周期，带完整审计"""

    def __init__(self):
        settings = get_settings()
        model_config = settings.model
        self.storage_path = Path(model_config.models_path)
        self.max_size = model_config.max_size
        self.allowed_extensions = model_config.allowed_extensions

        self.storage_path.mkdir(parents=True, exist_ok=True)

        debug_print("ModelRegistry", f"模型存储路径: {self.storage_path}")

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
            # 新增参数：评分卡配置
            scorecard_params: Optional[Dict] = None,
            # 新增参数：风险配置
            risk_config: Optional[Dict] = None
    ) -> str:
        """
        注册新模型

        Args:
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
            scorecard_params: 评分卡配置参数（仅对评分卡模型有效）
                {
                    "base_score": 600,      # 基准分
                    "pdo": 50,               # 每翻倍赔率对应的分数变化
                    "min_score": 320,        # 最低分
                    "max_score": 960,        # 最高分
                    "direction": "lower_better"  # 评分方向
                }
            risk_config: 风险配置参数（仅对反欺诈模型有效）
                {
                    "levels": {
                        "low": {"max": 0.3},
                        "medium": {"min": 0.3, "max": 0.6},
                        "high": {"min": 0.6, "max": 0.8},
                        "very_high": {"min": 0.8}
                    }
                }

        Returns:
            model_id: 生成的模型ID
        """
        request_id = get_request_id()
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

                # 添加配置信息到历史记录
                if scorecard_params:
                    history_details['scorecard_params'] = scorecard_params
                if risk_config:
                    history_details['risk_config'] = risk_config

                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model_version,
                    operation=AuditAction.CREATE.value,
                    operator=created_by,
                    operator_ip=ip_address,
                    metadata_snapshot=self._create_snapshot(metadata),
                    details=history_details
                )
                session.add(history)
                session.commit()

            duration = (datetime.now() - start_time).total_seconds() * 1000

            # 记录审计日志
            audit_details = {
                "model_id": model_id,
                "model_name": model_name,
                "model_version": model_version,
                "task_type": task_type,
                "model_type": model_type,
                "framework": framework,
                "file_size": file_size,
                "duration_ms": round(duration, 2)
            }

            # 添加配置信息到审计日志
            if scorecard_params:
                audit_details["scorecard_params"] = scorecard_params
            if risk_config:
                audit_details["risk_config"] = risk_config

            log_manager.log_audit(
                action="MODEL_REGISTER",
                user_id=created_by,
                ip_address=ip_address,
                details=audit_details,
                request_id=request_id
            )

            debug_print("ModelRegistry", f"模型注册成功: {model_id}")
            return model_id

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_manager.log_audit(
                action="MODEL_REGISTER",
                user_id=created_by,
                ip_address=ip_address,
                details={
                    "model_name": model_name,
                    "model_version": model_version,
                    "error": str(e),
                    "duration_ms": round(duration, 2)
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
        """
        验证任务特定的配置参数
        """
        # 评分卡模型配置验证
        if task_type == "scoring" and scorecard_params:
            self._validate_scorecard_params(scorecard_params)

        # 反欺诈模型配置验证
        if task_type == "fraud_detection" and risk_config:
            self._validate_risk_config(risk_config)

    def _validate_scorecard_params(self, params: Dict):
        """
        验证评分卡参数

        Args:
            params: {
                "base_score": 600,
                "pdo": 50,
                "min_score": 320,
                "max_score": 960,
                "direction": "lower_better"
            }
        """
        # 验证基准分
        if 'base_score' in params:
            try:
                base_score = int(params['base_score'])
                if base_score < 0:
                    raise ValueError("base_score 必须大于等于0")
            except (ValueError, TypeError):
                raise ModelValidationException("base_score 必须是有效的整数")

        # 验证PDO
        if 'pdo' in params:
            try:
                pdo = float(params['pdo'])
                if pdo <= 0:
                    raise ValueError("pdo 必须大于0")
            except (ValueError, TypeError):
                raise ModelValidationException("pdo 必须是有效的正数")

        # 验证分数范围
        if 'min_score' in params and 'max_score' in params:
            try:
                min_score = int(params['min_score'])
                max_score = int(params['max_score'])
                if min_score >= max_score:
                    raise ValueError("min_score 必须小于 max_score")
            except (ValueError, TypeError):
                raise ModelValidationException("min_score 和 max_score 必须是有效的整数")

        # 验证方向
        if 'direction' in params:
            direction = params['direction']
            if direction not in ["lower_better", "higher_better"]:
                raise ModelValidationException(
                    "direction 必须是 'lower_better' 或 'higher_better'"
                )

    def _validate_risk_config(self, config: Dict):
        """
        验证风险配置

        Args:
            config: {
                "levels": {
                    "low": {"max": 0.3},
                    "medium": {"min": 0.3, "max": 0.6},
                    "high": {"min": 0.6, "max": 0.8},
                    "very_high": {"min": 0.8}
                }
            }
        """
        if 'levels' not in config:
            raise ModelValidationException("风险配置必须包含 'levels' 字段")

        levels = config['levels']
        if not isinstance(levels, dict):
            raise ModelValidationException("风险等级配置必须是字典类型")

        # 验证每个等级的范围
        thresholds = []
        for level_name, threshold in levels.items():
            if not isinstance(threshold, dict):
                raise ModelValidationException(f"风险等级 '{level_name}' 的配置必须是字典")

            # 验证阈值范围
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

        # 验证等级范围是否重叠
        thresholds.sort(key=lambda x: x[1])  # 按最小值排序
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
        """
        合并模型参数

        将评分卡配置和风险配置合并到 model_params 中
        """
        merged = model_params.copy() if model_params else {}

        if task_type == "scoring" and scorecard_params:
            merged['scorecard'] = scorecard_params

        if task_type == "fraud_detection" and risk_config:
            merged['risk_config'] = risk_config

        return merged

    def _save_model_file(self, file_obj: BinaryIO, model_id: str, version: str, framework: str) -> tuple:
        """保存模型文件"""
        try:
            model_dir = self.storage_path / model_id / 'versions'
            model_dir.mkdir(parents=True, exist_ok=True)

            # 根据框架确定文件扩展名
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

            # 保存文件并计算哈希
            sha256 = hashlib.sha256()
            file_size = 0

            with open(file_path, 'wb') as f:
                while chunk := file_obj.read(8192):
                    f.write(chunk)
                    sha256.update(chunk)
                    file_size += len(chunk)

            file_hash = sha256.hexdigest()

            # 创建符号链接 latest
            latest_link = self.storage_path / model_id / 'latest'
            if latest_link.exists() or latest_link.is_symlink():
                latest_link.unlink()
            latest_link.symlink_to(f"versions/model_{version}{ext}")

            debug_print("ModelRegistry", f"模型文件保存成功: {file_path} ({file_size} bytes)")

            return file_hash, file_size, file_path

        except Exception as e:
            raise ModelFileException(f"保存模型文件失败: {str(e)}")

    def _validate_model_file(self, file_path: Path, framework: str, model_type: str):
        """验证模型文件"""
        try:
            if not file_path.exists():
                raise ModelValidationException(f"模型文件不存在: {file_path}")

            if file_path.stat().st_size == 0:
                raise ModelValidationException("模型文件为空")

            debug_print("ModelRegistry", f"模型文件验证通过: {file_path}")

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

    def get_model_params(self, model_id: str) -> Optional[Dict]:
        """
        获取模型的完整参数，包括评分卡配置和风险配置

        Args:
            model_id: 模型ID

        Returns:
            {
                "model_params": {...},           # 原始模型参数
                "scorecard": {...},                # 评分卡配置（如果有）
                "risk_config": {...}                # 风险配置（如果有）
            }
        """
        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    return None

                result = {
                    'model_params': model.model_params
                }

                # 提取评分卡配置
                if model.model_params and 'scorecard' in model.model_params:
                    result['scorecard'] = model.model_params['scorecard']

                # 提取风险配置
                if model.model_params and 'risk_config' in model.model_params:
                    result['risk_config'] = model.model_params['risk_config']

                return result

        except Exception as e:
            log_manager.log_audit(
                action="MODEL_GET_PARAMS",
                user_id="system",
                ip_address="localhost",
                details={"model_id": model_id, "error": str(e)}
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

        Args:
            model_id: 模型ID
            operator: 操作人
            scorecard_params: 新的评分卡配置
            risk_config: 新的风险配置
            reason: 更新原因
            ip_address: IP地址
        """
        request_id = get_request_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model:
                    raise ModelNotFoundException(f"模型未找到: {model_id}")

                # 验证新配置
                if scorecard_params and model.task_type == "scoring":
                    self._validate_scorecard_params(scorecard_params)
                if risk_config and model.task_type == "fraud_detection":
                    self._validate_risk_config(risk_config)

                # 更新配置
                if not model.model_params:
                    model.model_params = {}

                if scorecard_params:
                    model.model_params['scorecard'] = scorecard_params

                if risk_config:
                    model.model_params['risk_config'] = risk_config

                model.updated_at = datetime.now()

                # 记录历史
                history = ModelVersionHistory(
                    model_id=model_id,
                    model_version=model.model_version,
                    operation=AuditAction.UPDATE.value,
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
            log_manager.log_audit(
                action="MODEL_UPDATE_PARAMS",
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "model_name": model.model_name,
                    "model_version": model.model_version,
                    "scorecard_updated": scorecard_params is not None,
                    "risk_config_updated": risk_config is not None,
                    "reason": reason,
                    "duration_ms": round(duration, 2)
                },
                request_id=request_id
            )

            debug_print("ModelRegistry", f"模型参数更新成功: {model_id}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_manager.log_audit(
                action="MODEL_UPDATE_PARAMS",
                user_id=operator,
                ip_address=ip_address,
                details={
                    "model_id": model_id,
                    "error": str(e),
                    "duration_ms": round(duration, 2)
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    # ... 其他现有方法保持不变（activate_model, deactivate_model, get_model_info, list_models, set_production_model）


# 全局模型注册中心实例
model_registry = ModelRegistry()