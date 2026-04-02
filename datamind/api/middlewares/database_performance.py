# datamind/api/middlewares/database_performance.py

"""数据库性能监控中间件

提供 PostgreSQL 数据库性能监控功能，包括请求级别的数据库查询统计、pg_stat_statements 查询统计、
连接池状态监控、数据库大小和表统计、索引使用情况分析等。

功能特性：
  - 请求级别的数据库查询统计：记录每个请求的数据库查询次数和耗时
  - pg_stat_statements 查询统计：收集数据库级别的查询统计信息
  - 连接池状态监控：监控数据库连接池的使用情况
  - 数据库大小和表统计：收集数据库大小和表统计信息
  - 索引使用情况分析：分析索引使用情况，识别未使用的索引
  - 慢查询记录：自动记录执行时间超过阈值的慢查询
  - 后台统计收集：定时收集数据库性能指标
  - 链路追踪：完整的 span 追踪

中间件类型：
  PostgreSQLPerformanceMiddleware: PostgreSQL 性能监控中间件
     - 请求级别的查询统计
     - 慢查询检测和记录
     - pg_stat_statements 统计收集
     - 连接池状态监控
     - 数据库大小和表统计

性能指标：
  - db_queries: 请求中的数据库查询次数
  - db_time_ms: 请求中的数据库查询总耗时
  - avg_query_time_ms: 平均查询耗时
  - slow_queries: 慢查询数量
  - cache_hit_ratio: 缓存命中率
  - connection_usage_percent: 连接池使用率

慢查询阈值：
  - slow_query_threshold: 慢查询阈值（毫秒），默认 100ms
  - 超过阈值的查询会被记录到慢查询列表
  - 最多保留 1000 条慢查询记录

使用示例：
    # 添加中间件
    app.add_middleware(
        PostgreSQLPerformanceMiddleware,
        slow_query_threshold=100.0,
        enable_pg_stat=True,
        collect_interval=60
    )

    # 获取慢查询列表
    slow_queries = await middleware.get_slow_queries(limit=50)

    # 获取查询统计
    stats = await middleware.get_query_stats()
"""

import time
import asyncio
from contextvars import ContextVar
from typing import Dict, Any, Optional, Set, List

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from sqlalchemy import text, event

from datamind.core.logging import log_audit, context
from datamind.core.logging import get_logger
from datamind.core.domain.enums import AuditAction
from datamind.core.db.database import get_db, get_engine
from datamind.config.settings import PerformanceConfig
from datamind.config import get_settings

logger = get_logger(__name__)

# 上下文变量：存储当前请求的查询统计
_request_query_stats: ContextVar[Dict[str, Any]] = ContextVar("request_query_stats", default={})
_events_registered = False  # 确保事件只注册一次
_events_lock = asyncio.Lock()


class PostgreSQLPerformanceMiddleware(BaseHTTPMiddleware):
    """
    PostgreSQL 性能监控中间件

    监控 PostgreSQL 数据库性能，包括：
      - 请求级别的数据库查询统计
      - 使用 pg_stat_statements 获取查询统计
      - 监控连接池状态
      - 记录慢查询
      - 查询性能分析

    属性:
        slow_query_threshold: 慢查询阈值（毫秒）
        enable_pg_stat: 是否启用 pg_stat_statements 统计
        collect_interval: 收集统计信息的间隔（秒）
        enable_request_tracking: 是否启用请求级别的查询追踪
    """

    def __init__(
            self,
            app: ASGIApp,
            config: Optional[PerformanceConfig] = None,
            slow_query_threshold: Optional[float] = None,
            enable_pg_stat: bool = True,
            collect_interval: Optional[int] = None,
            enable_request_tracking: bool = True
    ):
        """
        初始化 PostgreSQL 性能监控中间件

        参数:
            app: ASGI 应用
            config: 性能监控配置对象
            slow_query_threshold: 慢查询阈值（毫秒），默认 100ms
            enable_pg_stat: 是否启用 pg_stat_statements 统计
            collect_interval: 收集统计信息的间隔（秒），默认 60秒
            enable_request_tracking: 是否启用请求级别的查询追踪
        """
        super().__init__(app)

        # 加载配置
        settings = get_settings()
        self.config = config or settings.performance

        # 参数优先级：直接参数 > 配置对象 > 默认值
        self.slow_query_threshold = slow_query_threshold if slow_query_threshold is not None else self.config.slow_query_threshold
        self.enable_pg_stat = enable_pg_stat
        self.collect_interval = collect_interval or self.config.pg_stat_interval
        self.enable_request_tracking = enable_request_tracking

        # 存储查询统计
        self.query_stats: Dict[str, Dict[str, Any]] = {}
        self._stats_lock = asyncio.Lock()

        # 存储慢查询记录
        self.slow_queries: List[Dict[str, Any]] = []
        self._slow_queries_lock = asyncio.Lock()
        self._max_slow_queries = 1000  # 最多保留1000条慢查询记录

        # 启动后台统计收集任务
        self._background_tasks: Set[asyncio.Task] = set()
        if enable_pg_stat:
            self._start_stats_collector()

        # 注册 SQLAlchemy 事件监听（只注册一次）
        if enable_request_tracking:
            self._register_sqlalchemy_events()

        logger.info("PostgreSQL性能监控中间件初始化完成: 慢查询阈值=%.2fms, 收集间隔=%ds, pg_stat=%s",
                   self.slow_query_threshold, self.collect_interval, "启用" if enable_pg_stat else "禁用")

    def _register_sqlalchemy_events(self):
        """注册 SQLAlchemy 事件监听，用于追踪查询"""
        global _events_registered

        async def register():
            global _events_registered
            async with _events_lock:
                if _events_registered:
                    return

                try:
                    # 获取数据库引擎
                    engine = get_engine('default')

                    @event.listens_for(engine, "before_cursor_execute")
                    def before_cursor_execute(conn, cursor, statement, params, context, executemany):
                        """查询执行前记录开始时间"""
                        context._query_start_time = time.time()
                        # 记录查询语句到上下文中
                        if hasattr(context, '_queries'):
                            context._queries.append({
                                "statement": statement,
                                "params": params,
                                "start_time": context._query_start_time
                            })
                        else:
                            context._queries = [{
                                "statement": statement,
                                "params": params,
                                "start_time": context._query_start_time
                            }]

                    @event.listens_for(engine, "after_cursor_execute")
                    def after_cursor_execute(conn, cursor, statement, params, context, executemany):
                        """查询执行后记录耗时"""
                        if hasattr(context, '_query_start_time'):
                            elapsed = (time.time() - context._query_start_time) * 1000

                            # 获取当前请求的统计信息
                            request_stats = _request_query_stats.get()
                            if request_stats:
                                request_stats["count"] += 1
                                request_stats["total_time"] += elapsed
                                request_stats["queries"].append({
                                    "statement": statement[:500],
                                    "duration_ms": round(elapsed, 2),
                                    "params": str(params)[:200] if params else None
                                })

                            # 记录慢查询
                            if elapsed > self.slow_query_threshold:
                                # 获取当前请求ID
                                req_id = context.get_request_id() if hasattr(context, 'get_request_id') else None
                                asyncio.create_task(
                                    self._record_slow_query(statement, elapsed, req_id)
                                )

                            # 调试输出
                            logger.debug("查询耗时: %.2fms - %s", elapsed, statement[:100])

                            # 清理开始时间
                            delattr(context, '_query_start_time')

                    _events_registered = True
                    logger.info("SQLAlchemy 数据库查询事件监听已注册")

                except Exception as e:
                    logger.warning("注册 SQLAlchemy 事件失败: %s", e)

        # 在事件循环中执行注册
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(register())
            else:
                loop.run_until_complete(register())
        except RuntimeError:
            # 没有运行的事件循环，直接同步执行
            asyncio.run(register())

    async def dispatch(self, request: Request, call_next):
        """处理请求 - 实现请求级别的数据库查询监控"""
        # 初始化当前请求的查询统计
        request_stats = {
            "count": 0,
            "total_time": 0.0,
            "queries": []
        }

        # 设置上下文变量
        token = _request_query_stats.set(request_stats)

        try:
            # 处理请求
            response = await call_next(request)

            # 记录请求级别的数据库统计到审计日志
            if request_stats["count"] > 0:
                user_id = "anonymous"
                username = "anonymous"
                if hasattr(request.state, 'user') and request.state.user:
                    user_id = request.state.user.get('id', 'unknown')
                    username = request.state.user.get('username', 'unknown')

                client_ip = self._get_client_ip(request)
                request_id = context.get_request_id()
                trace_id = context.get_trace_id()
                span_id = context.get_span_id()
                parent_span_id = context.get_parent_span_id()

                log_audit(
                    action=AuditAction.DB_QUERY_STATS.value,
                    user_id=user_id,
                    ip_address=client_ip,
                    details={
                        "method": request.method,
                        "path": request.url.path,
                        "username": username,
                        "db_queries": request_stats["count"],
                        "db_time_ms": round(request_stats["total_time"], 2),
                        "avg_query_time_ms": round(request_stats["total_time"] / request_stats["count"], 2) if request_stats["count"] > 0 else 0,
                        "slow_queries": len([q for q in request_stats["queries"] if q["duration_ms"] > self.slow_query_threshold]),
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                # 如果有慢查询，记录详细信息
                slow_queries = [q for q in request_stats["queries"] if q["duration_ms"] > self.slow_query_threshold]
                if slow_queries:
                    logger.warning("请求包含慢查询: 路径=%s, 慢查询数=%d, 最大耗时=%.2fms",
                                  request.url.path, len(slow_queries), max(q["duration_ms"] for q in slow_queries))
                    for sq in slow_queries[:5]:  # 最多记录5条慢查询
                        log_audit(
                            action=AuditAction.SLOW_QUERY.value,
                            user_id=user_id,
                            ip_address=client_ip,
                            details={
                                "path": request.url.path,
                                "query": sq["statement"],
                                "duration_ms": sq["duration_ms"],
                                "trace_id": trace_id,
                                "span_id": span_id,
                                "parent_span_id": parent_span_id
                            },
                            request_id=request_id
                        )

            return response

        finally:
            # 清理上下文变量
            _request_query_stats.reset(token)

    def _get_client_ip(self, request: Request) -> Optional[str]:
        """获取客户端真实IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()

        return request.client.host if request.client else None

    async def _record_slow_query(self, query_text: str, duration_ms: float, request_id: Optional[str] = None):
        """记录慢查询到列表"""
        async with self._slow_queries_lock:
            self.slow_queries.insert(0, {
                "query": query_text[:500],
                "duration_ms": round(duration_ms, 2),
                "timestamp": time.time(),
                "request_id": request_id
            })

            # 限制慢查询记录数量
            if len(self.slow_queries) > self._max_slow_queries:
                self.slow_queries = self.slow_queries[:self._max_slow_queries]

        logger.debug("慢查询: %.2fms - %s", duration_ms, query_text[:200])

    async def collect_pg_stat_statements(self, db) -> Dict[str, Any]:
        """
        从 pg_stat_statements 收集查询统计信息

        需要先启用 pg_stat_statements 扩展：
        CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
        """
        if not self.enable_pg_stat:
            return {}

        try:
            # 查询 pg_stat_statements
            query = text("""
                SELECT 
                    queryid,
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    stddev_exec_time,
                    rows,
                    shared_blks_hit,
                    shared_blks_read
                FROM pg_stat_statements
                WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
                ORDER BY total_exec_time DESC
                LIMIT 20
            """)

            result = await db.execute(query)
            rows = result.fetchall()

            stats = []
            for row in rows:
                stats.append({
                    "queryid": row[0],
                    "query": row[1][:200],
                    "calls": row[2],
                    "total_exec_time_ms": round(row[3], 2),
                    "mean_exec_time_ms": round(row[4], 2),
                    "stddev_exec_time_ms": round(row[5], 2),
                    "rows": row[6],
                    "cache_hit_ratio": round(row[7] / (row[7] + row[8]) * 100, 2) if (row[7] + row[8]) > 0 else 0
                })

            return {
                "top_queries": stats,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.debug("收集 pg_stat_statements 失败: %s", e)
            return {"error": str(e)}

    async def collect_connection_pool_stats(self, db) -> Dict[str, Any]:
        """收集连接池统计信息"""
        try:
            query = text("""
                SELECT
                    count(*)                                              as total_connections,
                    count(*) FILTER (WHERE state = 'active')              as active_connections,
                    count(*) FILTER (WHERE state = 'idle')                as idle_connections,
                    count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_transaction
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)

            result = await db.execute(query)
            row = result.fetchone()

            max_conn_query = text("SHOW max_connections")
            max_conn_result = await db.execute(max_conn_query)
            max_connections = int(max_conn_result.scalar())

            return {
                "total_connections": row[0],
                "active_connections": row[1],
                "idle_connections": row[2],
                "idle_in_transaction": row[3],
                "max_connections": max_connections,
                "usage_percent": round(row[0] / max_connections * 100, 2) if max_connections > 0 else 0,
                "available_connections": max_connections - row[0]
            }

        except Exception as e:
            logger.debug("收集连接池统计失败: %s", e)
            return {"error": str(e)}

    async def collect_database_stats(self, db) -> Dict[str, Any]:
        """收集数据库整体统计信息"""
        try:
            # 查询数据库大小
            size_query = text("""
                SELECT pg_database_size(current_database()) / 1024 / 1024 as size_mb
            """)
            size_result = await db.execute(size_query)
            db_size_mb = size_result.scalar()

            # 查询表统计
            table_stats_query = text("""
                SELECT
                    schemaname,
                    tablename,
                    n_live_tup as row_count,
                    n_dead_tup as dead_rows,
                    last_vacuum,
                    last_autovacuum,
                    last_analyze,
                    last_autoanalyze,
                    n_tup_ins,
                    n_tup_upd,
                    n_tup_del
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
                LIMIT 10
            """)

            table_result = await db.execute(table_stats_query)
            tables = []
            for row in table_result.fetchall():
                tables.append({
                    "schema": row[0],
                    "table": row[1],
                    "row_count": row[2],
                    "dead_rows": row[3],
                    "dead_row_ratio": round(row[3] / row[2] * 100, 2) if row[2] > 0 else 0,
                    "last_vacuum": row[4].isoformat() if row[4] else None,
                    "last_autovacuum": row[5].isoformat() if row[5] else None,
                    "last_analyze": row[6].isoformat() if row[6] else None,
                    "last_autoanalyze": row[7].isoformat() if row[7] else None,
                    "inserts": row[8],
                    "updates": row[9],
                    "deletes": row[10]
                })

            # 查询索引统计（最少使用的索引）
            index_stats_query = text("""
                SELECT 
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE idx_scan > 0
                ORDER BY idx_scan ASC
                LIMIT 10
            """)

            index_result = await db.execute(index_stats_query)
            indexes = []
            for row in index_result.fetchall():
                indexes.append({
                    "schema": row[0],
                    "table": row[1],
                    "index": row[2],
                    "scans": row[3],
                    "tuples_read": row[4],
                    "tuples_fetched": row[5]
                })

            return {
                "database_size_mb": round(db_size_mb, 2),
                "top_tables": tables,
                "least_used_indexes": indexes,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.debug("收集数据库统计失败: %s", e)
            return {"error": str(e)}

    async def reset_pg_stat_statements(self, db) -> Dict[str, Any]:
        """重置 pg_stat_statements 统计"""
        try:
            await db.execute(text("SELECT pg_stat_statements_reset()"))
            await db.commit()
            return {"success": True, "message": "统计已重置"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _start_stats_collector(self):
        """启动后台统计收集任务"""
        async def collect_stats():
            logger.info("数据库统计收集器已启动，收集间隔=%d秒", self.collect_interval)
            while True:
                try:
                    await asyncio.sleep(self.collect_interval)

                    try:
                        async for db in get_db():
                            try:
                                # 收集 pg_stat_statements
                                pg_stats = await self.collect_pg_stat_statements(db)
                                if pg_stats and "top_queries" in pg_stats:
                                    async with self._stats_lock:
                                        for query in pg_stats["top_queries"]:
                                            query_id = str(query["queryid"])
                                            self.query_stats[query_id] = {
                                                "query": query["query"],
                                                "calls": query["calls"],
                                                "total_time": query["total_exec_time_ms"],
                                                "mean_time": query["mean_exec_time_ms"],
                                                "stddev_time": query["stddev_exec_time_ms"],
                                                "rows": query["rows"],
                                                "cache_hit_ratio": query["cache_hit_ratio"],
                                                "last_updated": time.time()
                                            }

                                # 收集连接池统计
                                conn_stats = await self.collect_connection_pool_stats(db)

                                # 收集数据库统计
                                db_stats = await self.collect_database_stats(db)

                                # 记录审计日志
                                if pg_stats or conn_stats or db_stats:
                                    log_audit(
                                        action=AuditAction.MONITORING_COLLECT.value,
                                        user_id="system",
                                        ip_address=None,
                                        details={
                                            "timestamp": time.time(),
                                            "pg_stats_available": bool(pg_stats and "top_queries" in pg_stats),
                                            "connection_stats_available": bool(conn_stats and "error" not in conn_stats),
                                            "database_stats_available": bool(db_stats and "error" not in db_stats)
                                        }
                                    )
                                    if pg_stats and "top_queries" in pg_stats:
                                        logger.debug("数据库统计收集完成: 查询统计数=%d", len(pg_stats["top_queries"]))

                            except Exception as e:
                                logger.debug("收集统计失败: %s", e)
                            finally:
                                await db.close()
                                break
                    except Exception as e:
                        logger.debug("获取数据库会话失败: %s", e)

                except asyncio.CancelledError:
                    logger.info("数据库统计收集器已停止")
                    break
                except Exception as e:
                    logger.warning("统计收集器异常: %s", e)

        task = asyncio.create_task(collect_stats())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def get_query_stats(self) -> Dict[str, Any]:
        """获取查询统计信息"""
        async with self._stats_lock:
            stats = {}
            for query_id, data in self.query_stats.items():
                stats[query_id] = {
                    "query": data.get("query", "Unknown"),
                    "calls": data.get("calls", 0),
                    "total_time_ms": round(data.get("total_time", 0), 2),
                    "mean_time_ms": round(data.get("mean_time", 0), 2),
                    "stddev_time_ms": round(data.get("stddev_time", 0), 2),
                    "rows": data.get("rows", 0),
                    "cache_hit_ratio": data.get("cache_hit_ratio", 0),
                    "last_updated": data.get("last_updated")
                }
            return stats

    async def get_slow_queries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的慢查询记录"""
        async with self._slow_queries_lock:
            return self.slow_queries[:limit]

    async def shutdown(self):
        """关闭中间件，清理后台任务"""
        logger.info("正在关闭数据库性能监控中间件...")
        for task in self._background_tasks:
            task.cancel()
        if self._background_tasks:
            await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        logger.info("数据库性能监控中间件已关闭")


def setup_database_performance_middleware(
    app: ASGIApp,
    config: Optional[PerformanceConfig] = None,
    **kwargs
) -> None:
    """
    设置数据库性能监控中间件的便捷函数

    参数:
        app: ASGI 应用
        config: 性能监控配置对象
        **kwargs: 其他参数，会传递给 PostgreSQLPerformanceMiddleware
    """
    app.add_middleware(PostgreSQLPerformanceMiddleware, config=config, **kwargs)
    logger.info("数据库性能监控中间件已添加")