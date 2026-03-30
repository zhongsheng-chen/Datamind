# datamind/core/ml/runtime/engine.py
"""推理引擎

统一入口，根据模型能力自动路由到对应的 Pipeline。

核心功能：
  - predict: 统一预测入口
  - _run_scorecard_pipeline: 运行评分卡 Pipeline
  - _run_inference_pipeline: 运行通用推理 Pipeline

特性：
  - 能力驱动：根据模型能力自动选择 Pipeline
  - 策略路由：支持主模型/陪跑模型分流
  - 统一响应：所有模型返回一致的响应格式
  - 链路追踪：完整的 span 追踪
  - 审计日志：记录所有推理操作

使用示例：
  >>> from datamind.core.ml.runtime.engine import InferenceEngine
  >>> from datamind.core.ml.runtime.request import PredictRequest
  >>>
  >>> engine = InferenceEngine()
  >>> request = PredictRequest(
  ...     model_id="MDL_001",
  ...     features={"age": 35, "income": 50000},
  ...     need_explain=True
  ... )
  >>> response = engine.predict(request)
  >>> print(response.score)
  685.42
"""

from typing import Dict, Any, Optional
import time
import logging

from datamind.core.ml.model.loader import get_model_loader
from datamind.core.ml.runtime.request import PredictRequest
from datamind.core.ml.runtime.response import PredictResponse
from datamind.core.ml.capability import (
    ModelCapability,
    has_capability,
    get_capability_descriptions
)
from datamind.core.ml.pipeline.scorecard_pipeline import ScorecardPipeline
from datamind.core.ml.pipeline.inference_pipeline import InferencePipeline
from datamind.core.ml.features.transformer import WOETransformer
from datamind.core.ml.postprocess.scorer import ScoreScorer
from datamind.core.ml.explain.scorecard import ScorecardExplainer
from datamind.core.ml.explain.reason_code import ReasonCodeEngine
from datamind.core.ml.strategy import StrategyRouter
from datamind.core.ml.scorecard.manager import get_scorecard_manager
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.domain.enums import AuditAction


class InferenceEngine:
    """统一推理引擎

    所有模型预测的唯一入口。根据模型能力和策略路由自动选择执行路径。
    """

    def __init__(self):
        """初始化推理引擎"""
        self._loader = get_model_loader()
        self._scorecard_manager = get_scorecard_manager()
        self._strategy_router = StrategyRouter()
        self._inference_pipeline = InferencePipeline()
        self._logger = logging.getLogger(__name__)

    def predict(self, request: PredictRequest) -> PredictResponse:
        """
        统一预测入口

        参数:
            request: 预测请求，包含 model_id、features、need_explain 等

        返回:
            PredictResponse 实例

        异常:
            ValueError: 模型不存在或无可用模型
            RuntimeError: 预测过程中发生错误
        """
        request_id = context.get_request_id()
        trace_id = context.get_trace_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        try:
            # ========== 1. 策略路由 ==========
            # 确定使用主模型还是陪跑模型
            route = self._strategy_router.route(
                task_type=request.task_type,
                environment=request.environment,
                user_id=request.user_id,
                challenger_weight=request.challenger_weight
            )
            model_id = route["model_id"]
            model_role = route["type"]  # champion / challenger

            # ========== 2. 加载模型 ==========
            model, metadata = self._loader.get_model_with_metadata(model_id)

            if model is None:
                raise ValueError(f"模型不存在或未加载: {model_id}")

            # ========== 3. 获取模型能力 ==========
            caps = model.get_capabilities()

            # ========== 4. 根据能力选择 Pipeline ==========
            if has_capability(caps, ModelCapability.SCORECARD):
                # 评分卡模型：走评分卡 Pipeline
                result = self._run_scorecard_pipeline(
                    model=model,
                    metadata=metadata,
                    request=request,
                    is_challenger=(model_role == "challenger")
                )
            else:
                # 其他模型：走通用推理 Pipeline
                result = self._inference_pipeline.run(
                    model=model,
                    metadata=metadata,
                    features=request.features
                )

            # ========== 5. 构建响应 ==========
            processing_time_ms = (time.time() - start_time) * 1000

            response = PredictResponse(
                score=result.get("score"),
                probability=result["proba"],
                feature_scores=result.get("feature_scores"),
                reason_codes=result.get("reason_codes"),
                capabilities=get_capability_descriptions(caps),
                model_id=model_id,
                model_type=metadata.get("model_type"),
                model_role=model_role,
                task_type=request.task_type,
                environment=request.environment,
                processing_time_ms=round(processing_time_ms, 2),
                supports_feature_scores=has_capability(caps, ModelCapability.FEATURE_SCORES),
                request_id=request_id,
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id
            )

            # ========== 6. 审计日志 ==========
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=request.user_id or "system",
                ip_address=request.ip_address,
                details={
                    "model_id": model_id,
                    "model_version": metadata.get("model_version"),
                    "model_role": model_role,
                    "task_type": request.task_type,
                    "environment": request.environment,
                    "score": response.score,
                    "probability": response.probability,
                    "processing_time_ms": response.processing_time_ms,
                    "need_explain": request.need_explain,
                    "need_reason": request.need_reason,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            # 性能日志（慢查询）
            if processing_time_ms > 100:
                log_performance(
                    operation=AuditAction.MODEL_INFERENCE.value,
                    duration_ms=processing_time_ms,
                    extra={
                        "model_id": model_id,
                        "model_role": model_role,
                        "is_slow": True,
                        "request_id": request_id,
                        "trace_id": trace_id
                    }
                )

            return response

        except Exception as e:
            processing_time_ms = (time.time() - start_time) * 1000
            self._logger.error(f"推理失败: {e}", exc_info=True)

            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id=request.user_id or "system",
                ip_address=request.ip_address,
                details={
                    "model_id": request.model_id,
                    "error": str(e),
                    "processing_time_ms": round(processing_time_ms, 2),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                },
                reason=str(e),
                request_id=request_id
            )

            raise RuntimeError(f"推理失败: {e}")

    def _run_scorecard_pipeline(
        self,
        model,
        metadata: Dict[str, Any],
        request: PredictRequest,
        is_challenger: bool = False
    ) -> Dict[str, Any]:
        """
        运行评分卡 Pipeline

        参数:
            model: LR 模型
            metadata: 模型元数据
            request: 预测请求
            is_challenger: 是否为陪跑模型

        返回:
            预测结果字典
        """
        model_id = metadata.get("model_id")

        # 加载评分卡配置
        config = self._scorecard_manager.get_active_config(model_id)

        if config is None:
            raise ValueError(f"未找到评分卡配置: {model_id}")

        # 构建 Pipeline 组件
        transformer = WOETransformer(config.feature_bins)
        scorer = ScoreScorer(
            base_score=config.base_score,
            base_odds=config.odds,
            pdo=config.pdo
        )
        explainer = ScorecardExplainer()

        # 可选：拒绝原因引擎
        reason_engine = None
        if request.need_reason:
            reason_config = self._load_reason_config(model_id)
            if reason_config:
                reason_engine = ReasonCodeEngine(reason_config)

        # 创建并运行 Pipeline
        pipeline = ScorecardPipeline(
            transformer=transformer,
            scorer=scorer,
            explainer=explainer,
            reason_engine=reason_engine
        )

        return pipeline.run(
            model=model,
            metadata=metadata,
            features=request.features,
            is_challenger=is_challenger,
            need_explain=request.need_explain,
            need_reason=request.need_reason
        )

    def _load_reason_config(self, model_id: str) -> Dict:
        """
        加载拒绝原因配置

        参数:
            model_id: 模型ID

        返回:
            拒绝原因配置字典
        """
        # TODO: 从数据库或配置中心加载
        # 示例返回空配置
        return {}

    def get_model_capabilities(self, model_id: str) -> Dict[str, Any]:
        """
        获取模型能力信息

        参数:
            model_id: 模型ID

        返回:
            能力信息字典
        """
        model, metadata = self._loader.get_model_with_metadata(model_id)
        caps = model.get_capabilities()

        return {
            "model_id": model_id,
            "model_type": metadata.get("model_type"),
            "capabilities": [cap.name for cap in get_capability_descriptions(caps)],
            "supports_feature_scores": has_capability(caps, ModelCapability.FEATURE_SCORES),
            "supports_shap": has_capability(caps, ModelCapability.SHAP),
            "supports_reason_codes": has_capability(caps, ModelCapability.REASON_CODE)
        }


# ============================================================================
# 工厂函数
# ============================================================================

_engine: Optional[InferenceEngine] = None
_engine_lock = threading.Lock()


def get_inference_engine() -> InferenceEngine:
    """获取推理引擎全局实例

    返回:
        InferenceEngine 单例实例
    """
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = InferenceEngine()
    return _engine


__all__ = [
    'InferenceEngine',
    'get_inference_engine',
]