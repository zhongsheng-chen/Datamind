# datamind/serving/base.py

"""BentoML 服务基类

提供模型加载、热更新、审计日志等基础功能。

核心功能：
  - 模型加载：从数据库加载模型元数据，创建评分引擎
  - WOE转换器创建：为评分卡模型自动创建WOE转换器
  - 热加载监控：检测模型版本变化，自动重新加载
  - 生产模型管理：自动加载生产环境配置的模型
  - 健康检查：检查数据库、模型加载状态
  - 完整审计：记录模型加载、卸载、版本更新等操作

特性：
  - 异步加载：不阻塞服务启动
  - 线程安全：使用锁保护共享资源
  - 热更新：检测模型版本变化自动重载
  - 链路追踪：完整的 trace_id, span_id, parent_span_id
  - 多环境支持：development/testing/staging/production
"""

import atexit
import time
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from datamind.core.scoring.adapters import get_adapter
from datamind.core.scoring.engine import ScoringEngine
from datamind.core.scoring.transform import WOETransformer
from datamind.core.scoring.binning import Bin
from datamind.core.db.database import get_db, db_manager
from datamind.core.db.models import ModelDeployment, ModelMetadata
from datamind.core.domain.enums import AuditAction, TaskType, ModelStatus, DeploymentEnvironment
from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.config import ScorecardConstants
from datamind.config import get_settings

settings = get_settings()

logger = get_logger(__name__)


class BaseBentoService:
    """
    BentoML 服务基类

    提供模型加载、热更新、审计日志等基础功能。

    属性:
        service_type: 服务类型 (scoring/fraud_detection)
        service_name: 服务名称
        _active_models: 已加载的模型缓存
        _model_versions: 模型版本映射
        _engines: 评分引擎缓存
        _hot_reload_thread: 热加载监控线程
        _stop_reload: 停止热加载事件
        _reload_interval: 热加载检查间隔（秒）
    """

    # 类级别锁，确保数据库只初始化一次
    _db_lock = threading.RLock()
    _db_initialized = False

    def __init__(self, service_type: str, service_name: str, debug: bool = False):
        """
        初始化服务

        参数:
            service_type: 服务类型 (scoring/fraud_detection)
            service_name: 服务名称
            debug: 是否启用调试日志（保留参数以兼容，但不再使用）
        """
        self.service_type = service_type
        self.service_name = service_name
        self._task_type = TaskType.SCORING if service_type == 'scoring' else TaskType.FRAUD_DETECTION

        # 模型缓存
        self._active_models: Dict[str, Dict[str, Any]] = {}
        self._model_versions: Dict[str, str] = {}

        # 引擎缓存
        self._engines: Dict[str, ScoringEngine] = {}

        # 热加载线程控制
        self._hot_reload_thread: Optional[threading.Thread] = None
        self._stop_reload = threading.Event()
        self._reload_interval = 30

        # 初始化状态
        self._initialized = False

        # 初始化数据库连接
        self._init_database()

        # 加载生产模型（异步，不阻塞启动）
        self._load_production_model_async()

        # 启动热加载监控
        self._start_hot_reload_monitor()

        # 注册退出清理
        atexit.register(self._cleanup)

        logger.info("初始化完成: service=%s, task_type=%s", service_name, self._task_type.value)

    def _cleanup(self):
        """清理资源（由 atexit 调用）"""
        logger.info("开始清理资源...")

        self._stop_reload.set()

        if self._hot_reload_thread and self._hot_reload_thread.is_alive():
            try:
                self._hot_reload_thread.join(timeout=2)
                if self._hot_reload_thread.is_alive():
                    logger.warning("热加载线程未能在2秒内退出")
                else:
                    logger.debug("热加载线程已退出")
            except Exception as e:
                logger.error("等待热加载线程退出时出错: %s", e)

        for model_id in list(self._active_models.keys()):
            try:
                self._unload_model(model_id)
            except Exception as e:
                logger.error("清理模型 %s 时出错: %s", model_id, e)

        logger.info("资源清理完成")

    # ==================== 环境配置 ====================

    @staticmethod
    def _get_environment() -> str:
        """获取环境值"""
        env = settings.app.env
        if env == "production":
            return DeploymentEnvironment.PRODUCTION.value
        elif env == "staging":
            return DeploymentEnvironment.STAGING.value
        elif env == "testing":
            return DeploymentEnvironment.TESTING.value
        return DeploymentEnvironment.DEVELOPMENT.value

    # ==================== 数据库初始化 ====================

    def _init_database(self):
        """初始化数据库连接（线程安全）"""
        with self._db_lock:
            if not self._db_initialized:
                try:
                    logger.debug("初始化数据库连接...")
                    db_manager.initialize()
                    self._db_initialized = True
                    logger.info("数据库连接初始化成功")
                except Exception as e:
                    logger.error("数据库连接初始化失败: %s", e)

    # ==================== 模型加载/卸载 ====================

    def _load_production_model_async(self):
        """异步加载生产模型（不阻塞服务启动）"""

        def load():
            time.sleep(2)
            try:
                self._load_production_model()
            except Exception as e:
                logger.error("加载生产模型失败: %s", e)

        thread = threading.Thread(target=load, daemon=True, name=f"{self.service_name}_loader")
        thread.start()

    def _load_production_model(self):
        """加载生产环境模型"""
        if not self._db_initialized:
            logger.debug("数据库未就绪，跳过生产模型加载")
            return

        try:
            env_value = self._get_environment()
            logger.debug("环境: %s", env_value)

            with get_db() as session:
                deployment = session.query(ModelDeployment).filter(
                    ModelDeployment.environment == env_value,
                    ModelDeployment.is_active == True
                ).first()

                if deployment:
                    model_id = deployment.model_id
                    logger.debug("找到部署配置: %s", model_id)

                    model_info = session.query(ModelMetadata).filter_by(model_id=model_id).first()

                    if model_info and model_info.status == ModelStatus.ACTIVE.value:
                        self._load_model(model_id)
                        self._initialized = True
                        logger.info("加载生产模型成功: %s", model_id)
                    else:
                        logger.warning("生产模型未激活: %s", model_id)
                else:
                    logger.debug("未找到生产模型部署配置")

        except Exception as e:
            logger.error("加载生产模型失败: %s", e)

    def _load_model(self, model_id: str) -> bool:
        """
        加载指定模型

        核心功能：
          - 从数据库获取模型元数据
          - 加载模型文件（joblib/pickle）
          - 为评分卡模型创建WOE转换器
          - 创建模型适配器和评分引擎
          - 缓存模型实例

        参数:
            model_id: 模型ID

        返回:
            是否加载成功
        """
        try:
            if model_id in self._active_models:
                logger.debug("模型已加载: %s", model_id)
                return True

            with get_db() as session:
                model_info = session.query(ModelMetadata).filter_by(model_id=model_id).first()
                if not model_info:
                    logger.error("模型不存在: %s", model_id)
                    return False

                if model_info.task_type != self._task_type.value:
                    logger.warning("模型类型不匹配: %s != %s",
                                   model_info.task_type, self._task_type.value)
                    return False

                # 加载模型文件
                import joblib
                import os

                model_path = model_info.file_path
                if not os.path.exists(model_path):
                    logger.error("模型文件不存在: %s", model_path)
                    return False

                logger.debug("加载模型文件: %s", model_path)
                model = joblib.load(model_path)

                # 获取特征名
                feature_names = model_info.input_features if hasattr(model_info, 'input_features') else None

                # ========== 创建WOE转换器==========
                transformer = None
                if self._task_type == TaskType.SCORING:
                    # 从模型参数中获取评分卡配置
                    scorecard_params = model_info.model_params.get('scorecard', {}) if model_info.model_params else {}

                    # 检查是否有分箱配置
                    binning_config = scorecard_params.get('binning', {})

                    if binning_config:
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
                            logger.info("已为模型 %s 创建WOE转换器", model_id)
                        except Exception as e:
                            logger.error("创建WOE转换器失败: %s", e)
                            transformer = None
                    else:
                        logger.warning("评分卡模型 %s 缺少分箱配置，特征分将使用原始值（可能不准确）", model_id)

                # 创建适配器
                adapter = get_adapter(model, feature_names=feature_names)

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

                self._active_models[model_id] = {
                    'engine': engine,
                    'adapter': adapter,
                    'version': model_info.model_version,
                    'loaded_at': datetime.now(),
                    'metadata': {
                        'model_name': model_info.model_name,
                        'model_type': model_info.model_type,
                        'framework': model_info.framework,
                        'task_type': model_info.task_type
                    },
                    'transformer': transformer
                }
                self._model_versions[model_id] = model_info.model_version
                self._engines[model_id] = engine

                logger.info("模型加载成功: %s (version=%s)", model_id, model_info.model_version)
                return True

        except Exception as e:
            logger.error("加载模型异常: %s, %s", model_id, e)
            return False

    def _unload_model(self, model_id: str):
        """卸载模型"""
        if model_id in self._active_models:
            del self._active_models[model_id]
            if model_id in self._engines:
                del self._engines[model_id]
            if model_id in self._model_versions:
                del self._model_versions[model_id]
            logger.debug("模型卸载成功: %s", model_id)

    # ==================== 热加载监控 ====================

    def _start_hot_reload_monitor(self):
        """启动热加载监控线程"""

        def monitor():
            logger.debug("热加载监控线程启动")
            env_value = self._get_environment()

            while not self._stop_reload.is_set():
                try:
                    if not self._db_initialized:
                        self._stop_reload.wait(self._reload_interval)
                        continue

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
                                logger.info("检测到模型版本更新: %s %s -> %s",
                                            model_id, current_version, latest_version)
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
                    logger.error("热加载监控异常: %s", e)

                self._stop_reload.wait(self._reload_interval)

        self._hot_reload_thread = threading.Thread(
            target=monitor,
            daemon=True,
            name=f"{self.service_name}_reloader"
        )
        self._hot_reload_thread.start()

    # ==================== 公开接口 - 模型获取 ====================

    def get_production_model(self) -> Tuple[Optional[str], Optional[ScoringEngine], Optional[str]]:
        """
        获取生产模型

        返回:
            (model_id, engine, model_version) 元组，未找到返回 (None, None, None)
        """
        if not self._active_models:
            self._load_production_model()
            if not self._active_models:
                return None, None, None

        for mid, info in self._active_models.items():
            return mid, info['engine'], info['version']

        return None, None, None

    def get_model(self, model_id: str, auto_load: bool = True) -> Tuple[
        Optional[str], Optional[ScoringEngine], Optional[str]]:
        """
        根据模型ID获取模型

        参数:
            model_id: 模型ID
            auto_load: 如果模型未加载，是否自动加载

        返回:
            (model_id, engine, model_version) 元组，未找到返回 (None, None, None)
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
        """获取所有已加载的模型ID列表"""
        return list(self._active_models.keys())

    def get_loaded_models(self) -> List[Dict[str, Any]]:
        """获取已加载的模型列表"""
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
        """
        获取模型元数据

        参数:
            model_id: 模型ID

        返回:
            模型元数据字典，如果模型未加载则返回 None
        """
        if model_id in self._active_models:
            return self._active_models[model_id].get('metadata')
        return None

    # ==================== 模型操作 ====================

    def reload_model(self, model_id: str) -> Dict[str, Any]:
        """手动重新加载模型"""
        try:
            logger.info("手动重新加载模型: %s", model_id)
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
            logger.error("重新加载模型失败: %s", e)
            return {
                'success': False,
                'message': str(e)
            }

    def unload_model(self, model_id: str) -> Dict[str, Any]:
        """卸载模型"""
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
            logger.error("卸载模型失败: %s", e)
            return {
                'success': False,
                'message': str(e)
            }

    # ==================== 健康检查 ====================

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        status = 'healthy'
        issues = []

        if not self._db_initialized:
            status = 'degraded'
            issues.append('database_not_initialized')

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

    def stop(self):
        """停止服务"""
        logger.info("停止服务")
        self._stop_reload.set()

    def __del__(self):
        if hasattr(self, '_stop_reload'):
            self._stop_reload.set()