# datamind/serving/scoring_service.py

"""评分卡 BentoML 服务

提供评分卡模型的 BentoML 服务封装。

核心功能：
  - 单条评分预测：返回信用评分、违约概率和特征贡献
  - 健康检查：检查服务状态和模型加载情况
  - 模型管理：列出已加载模型、重新加载模型

特性：
  - A/B测试支持：集成 A/B 测试分流
  - 生产模型自动选择：未指定模型时使用生产模型
  - 完整审计：记录所有预测请求
  - 链路追踪：完整的 trace_id, span_id, parent_span_id
  - 多解释体系：统一接口支持 scorecard/shap/unsupported 三种解释类型
"""

import time
import json
import bentoml
import traceback
from typing import Dict, Any

from datamind.serving.base import BaseBentoService
from datamind.core.scoring.engine import ScoringEngine
from datamind.core.logging import log_audit, context, log_performance
from datamind.core.logging.manager import LogManager
from datamind.core.domain.enums import AuditAction
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.config import get_settings

settings = get_settings()


class ModelNotFoundException(Exception):
    """模型未找到异常"""
    pass


class ModelInferenceException(Exception):
    """模型推理异常"""
    pass


@bentoml.service(
    name="scoring_service",
    traffic={
        "timeout": settings.inference.timeout,
        "concurrency": 100
    },
    resources={
        "cpu": getattr(settings.inference, 'resources_cpu', "1"),
        "memory": getattr(settings.inference, 'resources_memory', "2Gi")
    },
    workers=1,
    threads=4,
)
class ScoringService:
    """评分卡服务

    提供评分卡模型的预测接口，支持单条评分和特征贡献分析。
    """

    def __init__(self):
        """
        初始化评分卡服务
        """
        # 调试模式从环境变量读取
        debug = getattr(settings, 'debug', False)
        self.base = BaseBentoService('scoring', 'scoring_service', debug=debug)
        self._debug_enabled = debug

        # 获取日志器
        self._log_manager = LogManager()
        self.logger = self._log_manager.app_logger

        self._info("评分卡服务初始化完成")

    def _debug(self, msg: str, *args) -> None:
        """调试输出"""
        if self._debug_enabled and self.logger:
            self.logger.debug(msg, *args)

    def _info(self, msg: str, *args) -> None:
        """信息输出"""
        if self.logger:
            self.logger.info(msg, *args)

    def _error(self, msg: str, *args) -> None:
        """错误输出"""
        if self.logger:
            self.logger.error(msg, *args)

    @staticmethod
    def _get_score_mapping(engine: ScoringEngine) -> Dict[str, Any]:
        """
        获取评分映射配置（用于审计）

        参数:
            engine: 评分引擎实例

        返回:
            评分映射配置字典
        """
        return {
            "type": "pdo",
            "pdo": engine.score_converter.pdo,
            "base_score": engine.score_converter.base_score,
            "base_odds": engine.score_converter.base_odds,
            "min_score": engine.score_converter.min_score,
            "max_score": engine.score_converter.max_score
        }

    @staticmethod
    def _make_explain(explain_result: Dict[str, Any], score: float) -> Dict[str, Any]:
        """
        构建特征贡献响应

        参数:
            explain_result: engine.explain() 返回的结果
            score: 预测的信用评分（用于验证）

        返回:
            统一格式的 explain 响应
        """
        explain_type = explain_result.get('explain_type', 'unknown')

        if explain_type == 'scorecard':
            total_score = explain_result.get('total_score', score)
            return {
                "type": "scorecard",
                "contribution_unit": "score",
                "details": {
                    "log_odds": explain_result.get("log_odds_contributions", {}),
                    "score": explain_result.get("score_contributions", {}),
                    "intercept_log_odds": explain_result.get("intercept_log_odds", 0),
                    "intercept_score": explain_result.get("intercept_score", 0),
                    "total_log_odds": explain_result.get("total_log_odds", 0),
                    "total_score": total_score,
                    "validation": {
                        "score_from_explain": total_score,
                        "score_match": abs(total_score - score) < 0.01
                    }
                }
            }

        elif explain_type == 'blackbox':
            shap_values = explain_result.get("shap_values", {})
            base_value = explain_result.get("base_value", 0)
            expected_value = explain_result.get("expected_value", 0)

            predicted_value = base_value + sum(shap_values.values())
            if 0 <= predicted_value <= 1:
                output_space = "probability"
            else:
                output_space = "log_odds"

            return {
                "type": "shap",
                "contribution_unit": output_space,
                "details": {
                    "shap_values": shap_values,
                    "base_value": base_value,
                    "expected_value": expected_value,
                    "prediction_output": predicted_value,
                    "output_space": output_space,
                    "validation": {
                        "shap_sum": sum(shap_values.values()),
                        "base_plus_sum": predicted_value,
                        "output_space": output_space
                    }
                }
            }

        else:
            return {
                "type": "unsupported",
                "reason": explain_result.get("reason", "model_not_supported"),
                "message": explain_result.get("message", "当前模型不支持特征贡献解释")
            }

    @bentoml.api
    async def predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        评分卡预测

        请求格式:
            {
                "application_id": "APP_001",
                "features": {"age": 35, "income": 50000, ...},
                "model_id": "MDL_001",
                "ab_test_id": "ABT_001",
                "return_details": false
            }

        响应格式:
            {
                "score": 685.42,
                "probability": 0.023,
                "model": {
                    "id": "MDL_001",
                    "version": "1.0.0",
                    "type": "logistic_regression",
                    "framework": "sklearn",
                    "score_mapping": {...}
                },
                "trace": {
                    "request_id": "req-xxx",
                    "trace_id": "trace-xxx",
                    "span_id": "span-xxx",
                    "parent_span_id": "",
                    "latency_ms": 12.5
                },
                "explain": {...}
            }
        """
        start_time = time.time()

        # 生成追踪 ID
        request_id = context.generate_request_id()
        trace_id = context.generate_trace_id()
        span_id = context.generate_span_id()

        context.set_request_id(request_id)
        context.set_trace_id(trace_id)
        context.set_span_id(span_id)
        parent_span_id = context.get_parent_span_id()

        # 获取请求参数
        application_id = request.get("application_id")
        features = request.get("features", {})
        model_id = request.get("model_id")
        ab_test_id = request.get("ab_test_id")
        return_details = request.get("return_details", False)

        # 验证必需参数
        if not application_id:
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "application_id 不能为空"}
            }
        if not features:
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "features 不能为空"}
            }

        # A/B 测试分流
        actual_model_id = model_id
        ab_test_info = None

        if ab_test_id and settings.ab_test.enabled:
            try:
                assignment = ab_test_manager.get_assignment(
                    test_id=ab_test_id,
                    user_id=application_id,
                    ip_address=None
                )
                if assignment.get('in_test') and assignment.get('model_id'):
                    actual_model_id = assignment['model_id']
                    ab_test_info = {
                        'test_id': assignment['test_id'],
                        'group_name': assignment['group_name']
                    }
            except Exception as e:
                self._debug("A/B测试错误: %s", e)

        # 如果没有指定模型，使用生产模型
        if not actual_model_id:
            prod_model_id, _, _ = self.base.get_production_model()
            if prod_model_id:
                actual_model_id = prod_model_id
            else:
                return {
                    "code": 1003,
                    "message": "模型未加载",
                    "data": {"error": "未指定 model_id 且没有生产模型"}
                }

        try:
            # 获取模型引擎
            _, engine, model_version = self.base.get_model(actual_model_id)
            if engine is None:
                return {
                    "code": 1003,
                    "message": "模型未加载",
                    "data": {"error": f"模型 {actual_model_id} 未加载"}
                }

            # 获取模型元数据
            model_meta = self.base.get_model_metadata(actual_model_id) or {}
            model_type = model_meta.get('model_type', 'unknown')
            framework = model_meta.get('framework', 'unknown')

            # 执行预测
            result = engine.score(features, return_proba=True)

            latency_ms = (time.time() - start_time) * 1000

            # 构建基础响应
            response_data = {
                "score": result.get('score'),
                "probability": result.get('proba'),
                "model": {
                    "id": actual_model_id,
                    "version": model_version,
                    "type": model_type,
                    "framework": framework,
                    "score_mapping": self._get_score_mapping(engine)
                },
                "trace": {
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id or "",
                    "latency_ms": round(latency_ms, 2)
                }
            }

            # 添加 A/B 测试信息
            if ab_test_info:
                response_data["experiment"] = {
                    "test_id": ab_test_info['test_id'],
                    "group_name": ab_test_info['group_name'],
                    "in_test": True
                }

            # 如果需要详细信息，获取特征贡献
            if return_details:
                try:
                    explain_result = engine.explain(features, return_score_scale=True)
                    response_data["explain"] = self._make_explain(
                        explain_result, result.get('score')
                    )
                except Exception as e:
                    self._debug("获取特征贡献失败: %s", e)
                    response_data["explain"] = {
                        "type": "unsupported",
                        "reason": "explain_failed",
                        "message": f"特征贡献解释失败: {str(e)}"
                    }

            # 构建最终响应
            response = {
                "code": 0,
                "message": "成功",
                "data": response_data
            }

            # 审计日志
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                ip_address=None,
                details={
                    "application_id": application_id,
                    "model_id": actual_model_id,
                    "model_version": model_version,
                    "total_score": result.get('score'),
                    "probability": result.get('proba'),
                    "latency_ms": round(latency_ms, 2),
                    "ab_test_id": ab_test_id,
                    "return_details": return_details,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            # 性能日志
            log_performance(
                operation=AuditAction.MODEL_INFERENCE.value,
                duration_ms=latency_ms,
                extra={
                    "model_id": actual_model_id,
                    "application_id": application_id,
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                }
            )

            return response

        except ModelNotFoundException as e:
            return {
                "code": 1003,
                "message": "模型未找到",
                "data": {"error": str(e)}
            }

        except ModelInferenceException as e:
            return {
                "code": 1005,
                "message": "模型预测失败",
                "data": {"error": str(e)}
            }

        except Exception as e:
            self._error("预测失败: %s", e)
            log_audit(
                action=AuditAction.MODEL_INFERENCE.value,
                user_id="bentoml",
                details={
                    "application_id": application_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                    "request_id": request_id,
                    "trace_id": trace_id,
                    "span_id": span_id
                },
                reason=str(e),
                request_id=request_id
            )
            return {
                "code": 1001,
                "message": "系统错误",
                "data": {"error": f"预测失败: {str(e)}"}
            }

    @bentoml.api
    async def health(self) -> Dict[str, Any]:
        """健康检查"""
        result = self.base.health_check()
        return {
            "code": 0,
            "message": "成功" if result.get("status") == "healthy" else "服务降级",
            "data": result
        }

    @bentoml.api
    async def models(self) -> Dict[str, Any]:
        """列出已加载的模型"""
        models = self.base.get_loaded_models()
        return {
            "code": 0,
            "message": "成功",
            "data": {
                "service": "scoring_service",
                "models": models,
                "total": len(models)
            }
        }

    @bentoml.api
    async def reload_model(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """重新加载模型"""
        model_id = request.get("model_id")
        if not model_id:
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "model_id 不能为空"}
            }
        result = self.base.reload_model(model_id)
        return {
            "code": 0 if result.get("success") else 1001,
            "message": "成功" if result.get("success") else "失败",
            "data": result
        }


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import asyncio
    import random

    from datamind.core.logging.bootstrap import install_bootstrap_logger, flush_bootstrap_logs

    install_bootstrap_logger()


    async def run_test():
        """测试评分卡服务"""
        service = ScoringService()
        service._debug_enabled = True

        service._debug("等待模型加载...")
        await asyncio.sleep(3)

        loaded_models = service.base.get_loaded_models()
        service._debug("已加载模型: %s", loaded_models)

        if not loaded_models:
            service._debug("没有已加载的模型，跳过测试")
            return

        def random_features():
            return {
                "age": random.randint(18, 65),
                "income": random.randint(30000, 150000),
                "debt_ratio": round(random.uniform(0, 0.8), 2),
                "credit_history": random.randint(300, 850),
                "employment_years": random.randint(0, 40),
                "loan_amount": random.randint(10000, 500000)
            }

        test_cases = [
            {
                "application_id": f"TEST_{context.generate_request_id()}",
                "features": random_features(),
                "return_details": True
            }
        ]

        print("\n" + "=" * 60)
        print("开始测试评分卡服务")
        print("=" * 60)

        for i, test_case in enumerate(test_cases):
            print(f"\n测试用例 {i + 1}:")
            print(f"  application_id: {test_case['application_id']}")
            print(f"  features: {json.dumps(test_case['features'], indent=4)}")
            print(f"  return_details: {test_case['return_details']}")

            try:
                response = await service.predict(test_case)
                print(f"\n响应:")
                print(json.dumps(response, ensure_ascii=False, indent=2))
            except Exception as e:
                print(f"\n错误: {e}")
                traceback.print_exc()

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)


    try:
        asyncio.run(run_test())
    finally:
        flush_bootstrap_logs()