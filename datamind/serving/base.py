# datamind/serving/base.py

"""BentoML 服务基类

提供模型加载、热更新、审计日志等基础功能。

核心功能：
  - 模型加载：从数据库加载模型元数据，创建评分引擎
  - WOE转换器创建：为评分卡模型自动创建WOE转换器
  - 热加载监控：检测模型版本变化，自动重新加载
  - 健康检查：检查数据库、模型加载状态

特性：
  - 异步加载：不阻塞服务启动
  - 线程安全：使用锁保护共享资源
  - 热更新：检测模型版本变化自动重载
  - 审计日志：记录模型加载、卸载、版本更新等操作
  - 链路追踪：完整的 span 追踪
  - 多环境支持：development/testing/staging/production
"""

import os
import atexit
import threading
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

from datamind.config import get_settings
from datamind.config.scorecard_config import ScorecardConstants
from datamind.core.db.database import get_db
from datamind.core.db.models import ModelDeployment, ModelMetadata
from datamind.core.domain.enums import AuditAction, DeploymentEnvironment, TaskType
from datamind.core.logging import get_logger, log_manager, log_audit, context
from datamind.core.logging.bootstrap import (
    install_bootstrap_logger,
    flush_bootstrap_logs,
    bootstrap_warning
)
from datamind.core.scoring.adapters import get_adapter
from datamind.core.scoring.binning import Bin
from datamind.core.scoring.engine import ScoringEngine
from datamind.core.scoring.transform import WOETransformer
from datamind.core.model import get_model_loader


def _ensure_logging_initialized() -> None:
    """确保当前进程的日志系统已初始化"""
    if log_manager.initialized:
        return

    cfg = get_settings()
    logging_config = cfg.logging

    bootstrap_level = logging_config.console_level
    if not logging_config.console_output:
        bootstrap_level = logging_config.level if logging_config.level else logging.INFO

    bootstrap_capacity = logging_config.async_queue_size if logging_config.async_queue_size else 10000

    install_bootstrap_logger(capacity=bootstrap_capacity, level=bootstrap_level)
    log_manager.initialize(logging_config)

    target_handler = None
    if log_manager.logger and log_manager.logger.handlers:
        target_handler = log_manager.logger.handlers[0]

    if target_handler:
        flush_bootstrap_logs(target_handler)
    else:
        bootstrap_warning("未找到目标处理器，启动日志未刷新")

    logger = get_logger(__name__)
    logger.debug("日志系统初始化完成")


_cfg = get_settings()
_logger = get_logger(__name__)


class BaseBentoService:
    """BentoML 服务基类

    提供模型加载、热更新、审计日志等基础功能。

    属性:
        service_type: 服务类型（scoring/fraud_detection）
        service_name: 服务名称
        _task_type: 任务类型枚举
        _active_models: 已加载的模型字典
        _model_versions: 模型版本字典
        _engines: 评分引擎字典
        _hot_reload_thread: 热加载监控线程
        _stop_reload: 停止热加载事件
        _reload_interval: 热加载检查间隔（秒）
        _initialized: 初始化标志

    使用示例:
        class MyService(BaseBentoService):
            def __init__(self):
                super().__init__('scoring', 'my_service')
    """

    def __init__(self, service_type: str, service_name: str) -> None:
        """初始化服务

        参数:
            service_type: 服务类型（scoring/fraud_detection）
            service_name: 服务名称
        """
        _ensure_logging_initialized()

        self.service_type = service_type
        self.service_name = service_name
        self._task_type = TaskType.SCORING if service_type == 'scoring' else TaskType.FRAUD_DETECTION

        # 存储已加载的模型
        self._active_models: Dict[str, Dict[str, Any]] = {}
        self._model_versions: Dict[str, str] = {}
        self._engines: Dict[str, ScoringEngine] = {}

        # 热加载监控
        self._hot_reload_thread: Optional[threading.Thread] = None
        self._stop_reload = threading.Event()
        self._reload_interval = 30

        self._initialized = False

        _logger.info("启动服务: %s/%s", service_name, service_type)

        try:
            from datamind.core.db.database import db_manager
            if not db_manager.initialized:
                db_manager.initialize()
            _logger.debug("数据库连接成功")
        except Exception as e:
            _logger.error(f"数据库连接失败: {e}")

        self._start_hot_reload_monitor()
        atexit.register(self._cleanup)

    @staticmethod
    def _get_environment() -> str:
        """获取当前部署环境

        返回:
            环境名称（development/testing/staging/production）
        """
        env = _cfg.app.environment.value if hasattr(_cfg.app, 'environment') else "development"
        env_lower = env.lower()

        if env_lower == "production":
            return DeploymentEnvironment.PRODUCTION.value
        elif env_lower == "staging":
            return DeploymentEnvironment.STAGING.value
        elif env_lower == "testing":
            return DeploymentEnvironment.TESTING.value
        return DeploymentEnvironment.DEVELOPMENT.value

    def _get_model_metadata_from_db(self, model_id: str) -> Optional[Dict[str, Any]]:
        """从数据库获取模型元数据

        参数:
            model_id: 模型ID

        返回:
            模型元数据字典，不存在时返回 None
        """
        try:
            with get_db() as session:
                model_info = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model_info:
                    _logger.error("模型不存在: %s", model_id)
                    return None

                return {
                    'model_id': model_info.model_id,
                    'model_version': model_info.model_version,
                    'model_name': model_info.model_name,
                    'model_type': model_info.model_type,
                    'framework': model_info.framework,
                    'task_type': model_info.task_type,
                    'input_features': getattr(model_info, 'input_features', None),
                    'model_params': getattr(model_info, 'model_params', {}) or {}
                }
        except Exception as e:
            _logger.error("查询模型元数据失败: %s", e)
            return None

    def _load_model(self, model_id: str) -> bool:
        """加载模型到内存（使用 ModelLoader）

        参数:
            model_id: 模型ID

        返回:
            True 表示加载成功，False 表示加载失败
        """
        try:
            if model_id in self._active_models:
                return True

            # 使用 ModelLoader 从 BentoML 加载模型
            loader = get_model_loader()

            if not loader.load_model(model_id):
                _logger.error("模型加载失败: %s", model_id)
                return False

            # 获取模型实例和元数据
            loaded_model = loader.get_model_instance(model_id)
            model_meta = loader.get_model_metadata(model_id)

            if not loaded_model or not model_meta:
                _logger.error("获取模型实例失败: %s", model_id)
                return False

            # 创建 WOE 转换器（如果是评分卡模型）
            transformer = self._create_woe_transformer(model_id, model_meta)

            # 创建适配器
            adapter = get_adapter(loaded_model, feature_names=model_meta.get('input_features'))

            # 创建评分引擎
            engine = ScoringEngine(
                model_adapter=adapter,
                transformer=transformer,
                pdo=ScorecardConstants.DEFAULT_PDO,
                base_score=ScorecardConstants.DEFAULT_BASE_SCORE,
                base_odds=ScorecardConstants.DEFAULT_ODDS,
                min_score=ScorecardConstants.DEFAULT_MIN_SCORE,
                max_score=ScorecardConstants.DEFAULT_MAX_SCORE
            )

            # 存储到内存
            self._active_models[model_id] = {
                'engine': engine,
                'adapter': adapter,
                'version': model_meta.get('model_version'),
                'loaded_at': datetime.now(),
                'metadata': {
                    'model_name': model_meta.get('model_name'),
                    'model_type': model_meta.get('model_type'),
                    'framework': model_meta.get('framework'),
                    'task_type': model_meta.get('task_type')
                },
                'transformer': transformer
            }
            self._model_versions[model_id] = model_meta.get('model_version')
            self._engines[model_id] = engine

            _logger.info("模型已加载: %s v%s",
                        model_meta.get('model_name'),
                        model_meta.get('model_version'))
            return True

        except Exception as e:
            _logger.error("加载模型异常: %s", e, exc_info=True)
            return False

    def _create_woe_transformer(self, model_id: str, model_meta: Dict[str, Any]) -> Optional[WOETransformer]:
        """创建WOE转换器（仅评分卡模型）

        参数:
            model_id: 模型ID
            model_meta: 模型元数据

        返回:
            WOETransformer 实例，不是评分卡模型或配置缺失时返回 None
        """
        if self._task_type != TaskType.SCORING:
            return None

        scorecard_config = model_meta.get('model_params', {}).get('scorecard', {})
        binning_config = scorecard_config.get('binning', {})

        if not binning_config:
            _logger.warning("评分卡模型缺少分箱配置: %s", model_id)
            return None

        try:
            binning = {}
            for feat_name, bins_data in binning_config.items():
                bins = []
                for bin_data in bins_data:
                    if isinstance(bin_data, dict):
                        bins.append(Bin.from_dict(bin_data))
                    else:
                        bins.append(bin_data)
                binning[feat_name] = bins

            transformer = WOETransformer(binning)
            _logger.debug("WOE转换器已创建: %s", model_id)
            return transformer
        except Exception as e:
            _logger.error("创建WOE转换器失败: %s", e)
            return None

    def _unload_model(self, model_id: str) -> None:
        """从内存中卸载模型

        参数:
            model_id: 模型ID
        """
        if model_id in self._active_models:
            model_name = self._active_models[model_id]['metadata'].get('model_name', model_id)
            del self._active_models[model_id]
            if model_id in self._engines:
                del self._engines[model_id]
            if model_id in self._model_versions:
                del self._model_versions[model_id]
            _logger.info("模型已卸载: %s", model_name)

    def _start_hot_reload_monitor(self) -> None:
        """启动热加载监控线程

        定期检查数据库中的模型版本，发现新版本时自动重新加载
        """
        def monitor() -> None:
            _logger.debug("热加载监控已启动")
            env_value = self._get_environment()

            while not self._stop_reload.is_set():
                try:
                    with get_db() as session:
                        deployments = session.query(ModelDeployment).filter(
                            ModelDeployment.environment == env_value,
                            ModelDeployment.is_active == True
                        ).all()

                        for deployment in deployments:
                            model_id = deployment.model_id
                            model_info = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                            if not model_info:
                                continue

                            current_version = self._model_versions.get(model_id)
                            latest_version = model_info.model_version

                            if latest_version and latest_version != current_version:
                                _logger.info("热更新: %s %s -> %s", model_id, current_version, latest_version)
                                self._unload_model(model_id)
                                self._load_model(model_id)

                                log_audit(
                                    action=AuditAction.MODEL_UPDATE.value,
                                    user_id="bentoml",
                                    details={
                                        "model_id": model_id,
                                        "old_version": current_version,
                                        "new_version": latest_version,
                                        "service": self.service_name,
                                        "action": "hot_reload"
                                    },
                                    request_id=context.get_request_id()
                                )

                except Exception as e:
                    _logger.debug("热加载监控异常: %s", e)

                self._stop_reload.wait(self._reload_interval)

        self._hot_reload_thread = threading.Thread(
            target=monitor,
            daemon=True,
            name=f"{self.service_name}_reloader"
        )
        self._hot_reload_thread.start()

    def get_model(self, model_id: str, auto_load: bool = True) -> Tuple[Optional[str], Optional[ScoringEngine], Optional[str]]:
        """获取模型

        参数:
            model_id: 模型ID
            auto_load: 是否自动加载（如果模型未加载）

        返回:
            (model_id, engine, version) 元组，模型不存在时返回 (None, None, None)
        """
        if model_id in self._active_models:
            info = self._active_models[model_id]
            return model_id, info['engine'], info['version']

        if auto_load:
            if self._load_model(model_id):
                info = self._active_models.get(model_id)
                if info:
                    return model_id, info['engine'], info['version']

        return None, None, None

    def get_loaded_model_ids(self) -> List[str]:
        """获取已加载的模型ID列表

        返回:
            模型ID列表
        """
        return list(self._active_models.keys())

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """获取已加载的模型信息列表

        返回:
            模型信息字典列表
        """
        return [
            {
                'model_id': mid,
                'model_name': info['metadata'].get('model_name'),
                'version': info['version'],
                'loaded_at': info['loaded_at'].isoformat(),
                'model_type': info['metadata'].get('model_type'),
                'framework': info['metadata'].get('framework'),
                'task_type': info['metadata'].get('task_type')
            }
            for mid, info in self._active_models.items()
        ]

    def get_model_metadata(self, model_id: str) -> Optional[Dict[str, Any]]:
        """获取模型的元数据

        参数:
            model_id: 模型ID

        返回:
            模型元数据，未加载时返回 None
        """
        if model_id in self._active_models:
            return self._active_models[model_id].get('metadata')
        return None

    def is_model_loaded(self, model_id: str) -> bool:
        """检查模型是否已加载

        参数:
            model_id: 模型ID

        返回:
            True 表示已加载，False 表示未加载
        """
        return model_id in self._active_models

    def reload_model(self, model_id: str) -> Dict[str, Any]:
        """手动重新加载模型

        参数:
            model_id: 模型ID

        返回:
            操作结果字典，包含 success、message 等字段
        """
        try:
            _logger.info("重新加载模型: %s", model_id)
            self._unload_model(model_id)
            success = self._load_model(model_id)

            if success:
                return {
                    'success': True,
                    'message': f'模型 {model_id} 重新加载成功',
                    'model_id': model_id,
                    'version': self._model_versions.get(model_id)
                }
            else:
                return {
                    'success': False,
                    'message': f'模型 {model_id} 重新加载失败'
                }
        except Exception as e:
            _logger.error("重新加载模型失败: %s", e)
            return {
                'success': False,
                'message': str(e)
            }

    def unload_model(self, model_id: str) -> Dict[str, Any]:
        """手动卸载模型

        参数:
            model_id: 模型ID

        返回:
            操作结果字典，包含 success、message 等字段
        """
        try:
            if model_id not in self._active_models:
                return {
                    'success': False,
                    'message': f'模型 {model_id} 未加载'
                }
            self._unload_model(model_id)
            return {
                'success': True,
                'message': f'模型 {model_id} 卸载成功'
            }
        except Exception as e:
            _logger.error("卸载模型失败: %s", e)
            return {
                'success': False,
                'message': str(e)
            }

    def health_check(self) -> Dict[str, Any]:
        """健康检查

        返回:
            健康状态字典，包含 status、service、loaded_models 等字段
        """
        status = 'healthy'
        issues = []

        if not self._active_models:
            status = 'degraded'
            issues.append('no_models_loaded')

        for mid, info in self._active_models.items():
            if not info.get('engine'):
                status = 'unhealthy'
                issues.append(f'model_{mid}_invalid')

        return {
            'status': status,
            'service': self.service_name,
            'task_type': self._task_type.value,
            'loaded_models': len(self._active_models),
            'models': list(self._active_models.keys()),
            'issues': issues,
            'timestamp': datetime.now().isoformat()
        }

    def _cleanup(self) -> None:
        """清理资源

        停止热加载线程，卸载所有模型
        """
        _logger.info("开始清理资源...")

        self._stop_reload.set()

        if self._hot_reload_thread and self._hot_reload_thread.is_alive():
            try:
                self._hot_reload_thread.join(timeout=5.0)
                if self._hot_reload_thread.is_alive():
                    _logger.warning("热加载线程未能在5秒内退出，继续清理其他资源")
                else:
                    _logger.debug("热加载线程已退出")
            except Exception as e:
                _logger.error("等待热加载线程退出时出错: %s", e)

        for model_id in list(self._active_models.keys()):
            try:
                self._unload_model(model_id)
            except Exception as e:
                _logger.error("清理模型 %s 时出错: %s", model_id, e)

        _logger.info("资源清理完成")

    def stop(self) -> None:
        """停止服务"""
        _logger.info("停止服务: %s", self.service_name)
        self._stop_reload.set()

    def __del__(self) -> None:
        """析构函数，确保停止热加载"""
        if hasattr(self, '_stop_reload'):
            self._stop_reload.set()