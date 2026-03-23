# datamind/api/routes/v1/management_api.py

"""管理 API 路由

提供系统管理相关的 RESTful API 接口，包括统计信息、审计日志、健康检查、缓存管理等。

功能特性：
  - 推理统计：按天统计推理请求量、平均耗时、P95耗时
  - 引擎统计：推理引擎、模型加载器、A/B测试的状态统计
  - 审计日志：查询系统审计日志，支持多维度筛选
  - 详细健康检查：检查数据库、模型加载器、推理引擎状态
  - 缓存管理：清除模型缓存、A/B测试缓存
  - 配置查看：查看系统配置信息（敏感信息已过滤）

API 端点：
  - GET /api/v1/management/stats/inference - 获取推理统计信息
  - GET /api/v1/management/stats/engine - 获取引擎统计信息
  - GET /api/v1/management/audit/logs - 获取审计日志
  - GET /api/v1/management/health/detailed - 详细健康检查
  - POST /api/v1/management/cache/clear - 清除缓存
  - GET /api/v1/management/config - 获取配置信息

权限要求：
  - 所有端点都需要管理员权限（require_admin）

审计日志：
  - 所有管理操作都记录审计日志
  - 包含完整的链路追踪信息
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy import func

from datamind.core.db.database import get_db
from datamind.core.db.models import ApiCallLog, AuditLog
from datamind.core.logging import log_audit, log_performance, context
from datamind.core.logging.debug import debug_print
from datamind.core.ml.inference import inference_engine
from datamind.core.ml.model_loader import model_loader
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.core.domain.enums import AuditAction
from datamind.api.dependencies import require_admin
from datamind.config import get_settings

router = APIRouter()
settings = get_settings()


@router.get("/stats/inference")
async def get_inference_stats(
        request: Request,
        days: int = Query(7, ge=1, le=30),
        current_user: str = Depends(require_admin)
):
    """获取推理统计信息

    参数:
        days: 统计天数（1-30天）

    返回:
        按天统计的推理请求数据
    """
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    try:
        start_date = datetime.now() - timedelta(days=days)

        with get_db() as session:
            # 按天统计
            stats = session.query(
                ApiCallLog.task_type,
                ApiCallLog.partition_date,
                func.count().label('total'),
                func.avg(ApiCallLog.processing_time_ms).label('avg_time'),
                func.percentile_cont(0.95).within_group(
                    ApiCallLog.processing_time_ms
                ).label('p95_time')
            ).filter(
                ApiCallLog.created_at >= start_date
            ).group_by(
                ApiCallLog.task_type,
                ApiCallLog.partition_date
            ).all()

            result = []
            for stat in stats:
                result.append({
                    'task_type': stat.task_type,
                    'date': stat.partition_date.isoformat(),
                    'total_requests': stat.total,
                    'avg_processing_time_ms': round(stat.avg_time, 2) if stat.avg_time else 0,
                    'p95_processing_time_ms': round(stat.p95_time, 2) if stat.p95_time else 0
                })

            # 记录审计日志
            log_audit(
                action=AuditAction.MODEL_QUERY.value,
                user_id=current_user,
                ip_address=client_ip,
                details={
                    "days": days,
                    "result_count": len(result),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            return {
                "days": days,
                "stats": result,
                "request_id": request_id,
                "trace_id": trace_id
            }

    except Exception as e:
        log_audit(
            action=AuditAction.MODEL_QUERY.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "error": str(e),
                "days": days,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            reason=str(e),
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/stats/engine")
async def get_engine_stats(
        request: Request,
        current_user: str = Depends(require_admin)
):
    """获取引擎统计信息

    返回推理引擎、模型加载器、A/B测试的统计信息。
    """
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    # 记录审计日志
    log_audit(
        action=AuditAction.MODEL_QUERY.value,
        user_id=current_user,
        ip_address=client_ip,
        details={
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        },
        request_id=request_id
    )

    return {
        "inference_engine": inference_engine.get_stats(),
        "model_loader": {
            "loaded_models": len(model_loader.get_loaded_models()),
            "models": model_loader.get_loaded_models()
        },
        "ab_test": ab_test_manager.get_stats(),
        "request_id": request_id,
        "trace_id": trace_id
    }


@router.get("/audit/logs")
async def get_audit_logs(
        request: Request,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        current_user: str = Depends(require_admin)
):
    """获取审计日志

    参数:
        start_date: 开始日期（ISO格式）
        end_date: 结束日期（ISO格式）
        user_id: 操作用户ID
        action: 操作类型
        resource_type: 资源类型
        limit: 返回数量限制（1-1000）
        offset: 偏移量

    返回:
        审计日志列表
    """
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    try:
        with get_db() as session:
            query = session.query(AuditLog)

            if start_date:
                query = query.filter(AuditLog.created_at >= datetime.fromisoformat(start_date))
            if end_date:
                query = query.filter(AuditLog.created_at <= datetime.fromisoformat(end_date))
            if user_id:
                query = query.filter(AuditLog.operator == user_id)
            if action:
                query = query.filter(AuditLog.action == action)
            if resource_type:
                query = query.filter(AuditLog.resource_type == resource_type)

            total = query.count()
            logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

            # 记录审计日志（查询审计日志本身也需要审计）
            log_audit(
                action=AuditAction.AUDIT_LOG_QUERY.value,
                user_id=current_user,
                ip_address=client_ip,
                details={
                    "start_date": start_date,
                    "end_date": end_date,
                    "user_id": user_id,
                    "action_filter": action,
                    "resource_type": resource_type,
                    "limit": limit,
                    "offset": offset,
                    "result_count": len(logs),
                    "total": total,
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "logs": [
                    {
                        "audit_id": log.audit_id,
                        "action": log.action,
                        "operator": log.operator,
                        "resource_type": log.resource_type,
                        "resource_id": log.resource_id,
                        "details": log.details,
                        "result": log.result,
                        "created_at": log.created_at.isoformat()
                    }
                    for log in logs
                ],
                "request_id": request_id,
                "trace_id": trace_id
            }

    except Exception as e:
        log_audit(
            action=AuditAction.AUDIT_LOG_QUERY.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "error": str(e),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            reason=str(e),
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取审计日志失败: {str(e)}")


@router.get("/health/detailed")
async def detailed_health_check(
        request: Request,
        current_user: str = Depends(require_admin)
):
    """详细健康检查（仅管理员）

    检查数据库、模型加载器、推理引擎、A/B测试的状态。
    """
    from datamind.core.db.database import db_manager

    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    db_health = db_manager.check_health()

    # 记录审计日志
    log_audit(
        action=AuditAction.MONITORING_COLLECT.value,
        user_id=current_user,
        ip_address=client_ip,
        details={
            "db_status": db_health['status'],
            "loaded_models": len(model_loader.get_loaded_models()),
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        },
        request_id=request_id
    )

    return {
        "status": "healthy" if db_health['status'] == 'healthy' else "degraded",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": db_health,
            "model_loader": {
                "status": "healthy",
                "loaded_models": len(model_loader.get_loaded_models()),
                "health_check": model_loader.health_check()
            },
            "inference_engine": {
                "status": "healthy",
                "stats": inference_engine.get_stats(),
                "cache_stats": inference_engine.get_cache_stats()
            },
            "ab_test": {
                "status": "healthy" if settings.ab_test.enabled else "disabled",
                "stats": ab_test_manager.get_stats()
            }
        },
        "version": settings.app.version,
        "environment": settings.app.env,
        "request_id": request_id,
        "trace_id": trace_id
    }


@router.post("/cache/clear")
async def clear_cache(
        request: Request,
        cache_type: str = Query(..., pattern="^(model|ab_test|all)$"),
        current_user: str = Depends(require_admin)
):
    """清除缓存

    参数:
        cache_type: 缓存类型（model/ab_test/all）

    返回:
        清除结果
    """
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    try:
        cleared_items = []

        if cache_type in ['model', 'all']:
            # 卸载所有模型
            loaded_models = model_loader.get_loaded_models()
            for model_info in loaded_models:
                model_loader.unload_model(
                    model_info['model_id'],
                    operator=current_user,
                    ip_address=client_ip
                )
            cleared_items.append(f"model_cache ({len(loaded_models)} models)")

        if cache_type in ['ab_test', 'all']:
            # 清除AB测试缓存
            if ab_test_manager.redis_client:
                keys = ab_test_manager.redis_client.keys(f"{settings.ab_test.redis_key_prefix}*")
                if keys:
                    ab_test_manager.redis_client.delete(*keys)
                    cleared_items.append(f"ab_test_cache ({len(keys)} keys)")

        # 记录审计日志
        log_audit(
            action=AuditAction.CONFIG_UPDATE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "cache_type": cache_type,
                "cleared_items": cleared_items,
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            request_id=request_id
        )

        return {
            "success": True,
            "message": f"缓存已清除: {cache_type}",
            "cleared_items": cleared_items,
            "request_id": request_id,
            "trace_id": trace_id
        }

    except Exception as e:
        log_audit(
            action=AuditAction.CONFIG_UPDATE.value,
            user_id=current_user,
            ip_address=client_ip,
            details={
                "cache_type": cache_type,
                "error": str(e),
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_span_id
            },
            reason=str(e),
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


@router.get("/config")
async def get_config(
        request: Request,
        current_user: str = Depends(require_admin)
):
    """获取配置信息（仅管理员）

    返回系统配置信息，敏感信息已过滤。
    """
    request_id = context.get_request_id()
    trace_id = context.get_trace_id()
    span_id = context.get_span_id()
    parent_span_id = context.get_parent_span_id()
    client_ip = request.client.host if request.client else None

    # 记录审计日志
    log_audit(
        action=AuditAction.MODEL_QUERY.value,
        user_id=current_user,
        ip_address=client_ip,
        details={
            "trace_id": trace_id,
            "span_id": span_id,
            "parent_span_id": parent_span_id
        },
        request_id=request_id
    )

    return {
        "app": {
            "name": settings.app.app_name,
            "version": settings.app.version,
            "env": settings.app.env,
            "debug": settings.app.debug
        },
        "api": {
            "prefix": settings.api.prefix,
            "rate_limit_enabled": settings.security.rate_limit_enabled,
            "rate_limit": f"{settings.security.rate_limit_requests}/{settings.security.rate_limit_period}s"
        },
        "database": {
            "pool_size": settings.database.pool_size,
            "max_overflow": settings.database.max_overflow
        },
        "logging": {
            "level": settings.logging.level.name,
            "format": settings.logging.format.value,
            "retention_days": settings.logging.retention_days
        },
        "ab_test": {
            "enabled": settings.ab_test.enabled,
            "assignment_expiry": settings.ab_test.assignment_expiry
        },
        "model": {
            "inference_timeout": settings.inference.timeout,
            "cache_size": settings.inference.cache_size,
            "max_file_size_mb": settings.model.max_size / 1024 / 1024
        },
        "request_id": request_id,
        "trace_id": trace_id
    }