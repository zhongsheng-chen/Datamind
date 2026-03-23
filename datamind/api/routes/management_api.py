# Datamind/datamind/api/routes/management_api.py
from fastapi import APIRouter, HTTPException, Depends, Request, Query
from typing import Optional
from datetime import datetime, timedelta

from datamind.core.db.database import get_db
from datamind.core.db.models import ApiCallLog, AuditLog
from datamind.core.logging import log_manager, debug_print
from datamind.core.logging import context
from datamind.core.ml.inference import inference_engine
from datamind.core.ml.model_loader import model_loader
from datamind.core.experiment.ab_test import ab_test_manager
from datamind.api.dependencies import require_admin
from datamind.config import settings

router = APIRouter()


@router.get("/stats/inference")
async def get_inference_stats(
        request: Request,
        days: int = Query(7, ge=1, le=30),
        current_user: str = Depends(require_admin)
):
    """获取推理统计信息"""
    request_id = get_request_id()

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

            return {
                "days": days,
                "stats": result,
                "request_id": request_id
            }

    except Exception as e:
        log_manager.log_audit(
            action="GET_STATS_ERROR",
            user_id=current_user,
            ip_address=request.client.host if request.client else None,
            details={"error": str(e)},
            request_id=request_id
        )
        raise HTTPException(status_code=500, detail=f"获取统计信息失败: {str(e)}")


@router.get("/stats/engine")
async def get_engine_stats(
        request: Request,
        current_user: str = Depends(require_admin)
):
    """获取引擎统计信息"""
    return {
        "inference_engine": inference_engine.get_stats(),
        "model_loader": {
            "loaded_models": len(model_loader.get_loaded_models()),
            "models": model_loader.get_loaded_models()
        },
        "ab_test": ab_test_manager.get_stats(),
        "request_id": context.get_request_id()
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
    """获取审计日志"""
    request_id = context.get_request_id()

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
                "request_id": request_id
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取审计日志失败: {str(e)}")


@router.get("/health/detailed")
async def detailed_health_check(
        request: Request,
        current_user: str = Depends(require_admin)
):
    """详细健康检查（仅管理员）"""
    from datamind.core.db.database import db_manager

    db_health = db_manager.check_health()

    return {
        "status": "healthy" if db_health['status'] == 'healthy' else "degraded",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "database": db_health,
            "model_loader": {
                "status": "healthy",
                "loaded_models": len(model_loader.get_loaded_models())
            },
            "inference_engine": {
                "status": "healthy",
                "stats": inference_engine.get_stats()
            },
            "ab_test": {
                "status": "healthy" if settings.AB_TEST_ENABLED else "disabled",
                "stats": ab_test_manager.get_stats()
            }
        },
        "version": settings.VERSION,
        "environment": settings.ENV,
        "request_id": context.get_request_id()
    }


@router.post("/cache/clear")
async def clear_cache(
        request: Request,
        cache_type: str = Query(..., pattern="^(model|ab_test|all)$"),
        current_user: str = Depends(require_admin)
):
    """清除缓存"""
    request_id = context.get_request_id()

    try:
        if cache_type in ['model', 'all']:
            # 卸载所有模型
            for model_info in model_loader.get_loaded_models():
                model_loader.unload_model(
                    model_info['model_id'],
                    operator=current_user,
                    ip_address=request.client.host if request.client else None
                )

        if cache_type in ['ab_test', 'all']:
            # 清除AB测试缓存
            if ab_test_manager.redis_client:
                keys = ab_test_manager.redis_client.keys(f"{settings.AB_TEST_REDIS_KEY_PREFIX}*")
                if keys:
                    ab_test_manager.redis_client.delete(*keys)

        log_manager.log_audit(
            action="CACHE_CLEAR",
            user_id=current_user,
            ip_address=request.client.host if request.client else None,
            details={"cache_type": cache_type},
            request_id=request_id
        )

        return {
            "success": True,
            "message": f"缓存已清除: {cache_type}",
            "request_id": request_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"清除缓存失败: {str(e)}")


@router.get("/config")
async def get_config(
        request: Request,
        current_user: str = Depends(require_admin)
):
    """获取配置信息（仅管理员）"""
    # 返回非敏感配置
    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.VERSION,
            "env": settings.ENV,
            "debug": settings.DEBUG
        },
        "api": {
            "prefix": settings.API_PREFIX,
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
            "rate_limit": f"{settings.RATE_LIMIT_REQUESTS}/{settings.RATE_LIMIT_PERIOD}s"
        },
        "database": {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW
        },
        "logging": {
            "level": settings.LOG_LEVEL,
            "format": settings.LOG_FORMAT,
            "retention_days": settings.LOG_RETENTION_DAYS
        },
        "ab_test": {
            "enabled": settings.AB_TEST_ENABLED,
            "assignment_expiry": settings.AB_TEST_ASSIGNMENT_EXPIRY
        },
        "model": {
            "inference_timeout": settings.MODEL_INFERENCE_TIMEOUT,
            "cache_size": settings.MODEL_CACHE_SIZE,
            "max_file_size_mb": settings.MODEL_FILE_MAX_SIZE / 1024 / 1024
        },
        "request_id": context.get_request_id()
    }