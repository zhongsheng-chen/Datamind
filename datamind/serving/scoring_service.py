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
  - 多解释体系：统一接口支持 scorecard/shap/unsupported 三种解释类型
  - 特征贡献转换：使用 ContributionConverter 确保评分贡献转换一致性
  - 完整审计：记录所有预测请求
  - 链路追踪：完整的 trace_id, span_id, parent_span_id
"""

import time
import json
import bentoml
import traceback
from typing import Dict, Any, Optional

from datamind.serving.base import BaseBentoService
from datamind.core.scoring.engine import ScoringEngine
from datamind.core.scoring.contrib import ContributionConverter
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.config import get_settings

settings = get_settings()

logger = get_logger(__name__)


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
    """评分卡服务"""

    def __init__(self):
        """初始化评分卡服务"""
        self.base = BaseBentoService('scoring', 'scoring_service', debug=False)

        logger.info("评分卡服务初始化完成")

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
    def _make_explain(
        explain_result: Dict[str, Any],
        score: float,
        engine: ScoringEngine
    ) -> Dict[str, Any]:
        """
        构建特征贡献响应

        使用 ContributionConverter 将 logit 空间的贡献转换为评分空间，
        确保与 Score 模块的转换逻辑完全一致。

        参数:
            explain_result: engine.explain() 返回的结果
            score: 预测的信用评分（用于验证）
            engine: 评分引擎实例（用于获取评分参数）

        返回:
            统一格式的 explain 响应
        """
        explain_type = explain_result.get('explain_type', 'unknown')

        if explain_type == 'scorecard':
            # 创建贡献转换器
            converter = ContributionConverter(engine.score_converter)

            # 获取评分参数
            factor = converter.get_factor()
            offset = converter.get_offset()

            # 获取 logit 空间的贡献
            log_odds_contrib = explain_result.get("log_odds_contributions", {})
            intercept_log_odds = explain_result.get("intercept_log_odds", 0.0)
            total_log_odds = explain_result.get("total_log_odds", 0.0)

            # 使用转换器将 logit 贡献转换为评分贡献
            score_contrib = converter.logit_to_score(log_odds_contrib)

            # 截距评分贡献：intercept_score = -factor × intercept_log_odds
            intercept_score = -factor * intercept_log_odds

            # 总评分：使用 Score.from_logit 方法，公式为 offset - factor × logit
            total_score = engine.score_converter.from_logit(total_log_odds)

            # 获取评分参数信息
            score_params = {
                "factor": factor,
                "offset": offset,
                "pdo": engine.score_converter.pdo,
                "base_score": engine.score_converter.base_score,
                "base_odds": engine.score_converter.base_odds
            }

            # 如果 engine.explain() 已经返回了 score_contributions，可以用于验证
            original_score_contrib = explain_result.get("score_contributions", {})
            has_original = bool(original_score_contrib)

            return {
                "type": "scorecard",
                "contribution_unit": "score",
                "score_params": score_params,
                "details": {
                    "log_odds": log_odds_contrib,
                    "score": score_contrib,
                    "intercept_log_odds": intercept_log_odds,
                    "intercept_score": intercept_score,
                    "total_log_odds": total_log_odds,
                    "total_score": total_score,
                    "validation": {
                        "score_from_explain": total_score,
                        "score_match": abs(total_score - score) < 0.01,
                        "converter_used": True,
                        "has_original_score_contrib": has_original
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
    async def predict(self, request: dict) -> dict:
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
                "code": 0,
                "message": "成功",
                "data": {
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
            logger.debug("请求参数缺失: application_id 为空")
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "application_id 不能为空"}
            }
        if not features:
            logger.debug("请求参数缺失: features 为空")
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
                logger.debug("A/B测试分配结果: %s", assignment)

                if assignment.get('in_test') and assignment.get('model_id'):
                    actual_model_id = assignment['model_id']
                    ab_test_info = {
                        'test_id': assignment['test_id'],
                        'group_name': assignment['group_name']
                    }
                    logger.info("A/B测试分流: 申请ID=%s, 测试ID=%s, 分组=%s, 模型ID=%s",
                               application_id, ab_test_id, assignment['group_name'], actual_model_id)
                else:
                    logger.debug("用户不在测试中或没有模型ID: %s", assignment)
            except Exception as e:
                logger.warning("A/B测试分配失败: 测试ID=%s, 申请ID=%s, 错误=%s",
                              ab_test_id, application_id, e)
        else:
            logger.debug("未启用A/B测试: ab_test_id=%s, enabled=%s", ab_test_id, settings.ab_test.enabled)

        # 如果没有指定模型，使用生产模型
        if not actual_model_id:
            prod_model_id, _, _ = self.base.get_production_model()
            if prod_model_id:
                actual_model_id = prod_model_id
                logger.info("使用生产模型: 申请ID=%s, 模型ID=%s", application_id, actual_model_id)
            else:
                logger.warning("未指定模型ID且没有生产模型: 申请ID=%s", application_id)
                return {
                    "code": 1003,
                    "message": "模型未加载",
                    "data": {"error": "未指定 model_id 且没有生产模型"}
                }

        try:
            # 获取模型引擎
            _, engine, model_version = self.base.get_model(actual_model_id)
            if engine is None:
                logger.warning("模型未加载: 申请ID=%s, 模型ID=%s", application_id, actual_model_id)
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

            logger.info("评分预测完成: 申请ID=%s, 模型ID=%s, 版本=%s, 评分=%.2f, 概率=%.6f, 耗时=%.2fms",
                       application_id, actual_model_id, model_version,
                       result.get('score'), result.get('proba'), latency_ms)

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
                        explain_result,
                        result.get('score'),
                        engine
                    )
                    logger.debug("特征贡献解释完成: 申请ID=%s, 解释类型=%s",
                                application_id, explain_result.get('explain_type', 'unknown'))
                except Exception as e:
                    logger.warning("获取特征贡献失败: 申请ID=%s, 错误=%s", application_id, e)
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
            logger.warning("模型未找到: 申请ID=%s, 模型ID=%s, 错误=%s",
                          application_id, actual_model_id, e)
            return {
                "code": 1003,
                "message": "模型未找到",
                "data": {"error": str(e)}
            }

        except ModelInferenceException as e:
            logger.error("模型预测失败: 申请ID=%s, 模型ID=%s, 错误=%s",
                        application_id, actual_model_id, e)
            return {
                "code": 1005,
                "message": "模型预测失败",
                "data": {"error": str(e)}
            }

        except Exception as e:
            logger.error("预测异常: 申请ID=%s, 模型ID=%s, 错误=%s",
                        application_id, actual_model_id, e, exc_info=True)
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
    async def health(self) -> dict:
        """健康检查"""
        result = self.base.health_check()
        status = result.get("status")
        if status == "healthy":
            logger.debug("健康检查: 状态=健康")
        else:
            logger.warning("健康检查: 状态=%s, 问题=%s", status, result.get("issues", []))
        return {
            "code": 0,
            "message": "成功" if status == "healthy" else "服务降级",
            "data": result
        }

    @bentoml.api
    async def models(self) -> dict:
        """列出已加载的模型"""
        models = self.base.get_loaded_models()
        logger.info("列出已加载模型: 服务=%s, 模型数量=%d", "scoring_service", len(models))
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
    async def reload_model(self, request: dict) -> dict:
        """重新加载模型"""
        model_id = request.get("model_id")
        if not model_id:
            logger.debug("重新加载模型请求缺少model_id参数")
            return {
                "code": 1006,
                "message": "参数错误",
                "data": {"error": "model_id 不能为空"}
            }
        logger.info("手动重新加载模型: 模型ID=%s", model_id)
        result = self.base.reload_model(model_id)
        if result.get("success"):
            logger.info("模型重新加载成功: 模型ID=%s, 版本=%s", model_id, result.get("version"))
        else:
            logger.error("模型重新加载失败: 模型ID=%s, 错误=%s", model_id, result.get("message"))
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

        logger.info("等待模型加载...")
        await asyncio.sleep(3)

        loaded_models = service.base.get_loaded_models()
        logger.info("已加载模型: %s", loaded_models)

        if not loaded_models:
            logger.warning("没有已加载的模型，跳过测试")
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