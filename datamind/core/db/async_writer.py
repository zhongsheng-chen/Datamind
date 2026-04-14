# datamind/core/db/async_writer.py

"""通用异步数据库写入器

提供非阻塞的数据库写入功能，支持任意 SQLAlchemy 模型的异步写入。

核心功能：
  - 异步写入：使用 asyncio.Queue 实现非阻塞写入
  - 批量处理：支持批量写入减少数据库连接开销
  - 泛型支持：支持任意 SQLAlchemy 模型
  - 优雅关闭：确保队列中的任务在服务关闭前完成
  - 降级保护：队列满时降级为同步写入
  - 统计信息：提供写入统计和队列状态

使用示例：
    from datamind.core.db.async_writer import AsyncDBWriter, get_async_writer
    from datamind.core.db.models import ApiCallLog, AuditLog

    writer = AsyncDBWriter()
    await writer.start()

    # 写入单条记录
    await writer.write(ApiCallLog, request_id="xxx", ...)

    # 批量写入
    await writer.write_batch([log1, log2, log3])

    # 更新记录
    await writer.update(Model, model_id, {"status": "active"})

    # 删除记录
    await writer.delete(Model, model_id)

    # 关闭
    await writer.stop()
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Type, TypeVar
from dataclasses import dataclass, field

from sqlalchemy import update as sa_update, delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from datamind.core.db.database import get_db
from datamind.core.domain.enums import DatabaseOperation
from datamind.core.logging import get_logger

_logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class WriteTask:
    """写入任务"""
    operation: DatabaseOperation
    model_class: type
    data: Dict[str, Any]
    created_at: float = field(default_factory=time.time)


class AsyncDBWriter:
    """异步数据库写入器"""

    def __init__(
        self,
        queue_size: int = 10000,
        batch_size: int = 100,
        batch_interval_ms: float = 100,
        enable_batch: bool = True
    ):
        """
        初始化异步写入器

        参数:
            queue_size: 队列最大容量
            batch_size: 批量写入大小
            batch_interval_ms: 批量写入间隔（毫秒）
            enable_batch: 是否启用批量写入
        """
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._batch_size = batch_size
        self._batch_interval = batch_interval_ms / 1000
        self._enable_batch = enable_batch
        self._task: Optional[asyncio.Task] = None
        self._running = False

        self._stats = {
            "total_tasks": 0,
            "processed_tasks": 0,
            "failed_tasks": 0,
            "dropped_tasks": 0,
            "batch_writes": 0
        }

    def is_running(self) -> bool:
        """检查写入器是否运行中"""
        return self._running

    async def start(self) -> None:
        """启动异步写入器"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._worker())
        _logger.debug("异步写入器已启动: queue_size=%d, batch_size=%d, batch_interval=%dms",
                    self._queue.maxsize, self._batch_size, self._batch_interval * 1000)

    async def stop(self, timeout: float = 10.0) -> None:
        """
        停止异步写入器

        参数:
            timeout: 等待队列清空的超时时间（秒）
        """
        if not self._running:
            return

        self._running = False

        # 等待队列清空
        start_time = time.time()
        queue_size = self._queue.qsize()
        while queue_size > 0 and (time.time() - start_time) < timeout:
            _logger.debug("等待队列清空: 剩余 %d 条日志", queue_size)
            await asyncio.sleep(0.5)
            queue_size = self._queue.qsize()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        _logger.info("异步写入器已停止: %s", self._stats)

    async def write(self, model_class: Type[T], **kwargs) -> bool:
        """
        异步写入单条记录

        参数:
            model_class: SQLAlchemy 模型类
            **kwargs: 模型字段值

        返回:
            True 表示已加入队列，False 表示队列满被丢弃
        """
        task = WriteTask(
            operation=DatabaseOperation.INSERT,
            model_class=model_class,
            data=kwargs
        )
        return await self._enqueue(task)

    async def write_batch(self, instances: List) -> bool:
        """
        异步批量写入

        参数:
            instances: 模型实例列表

        返回:
            True 表示已加入队列，False 表示队列满被丢弃
        """
        if not instances:
            return True

        task = WriteTask(
            operation=DatabaseOperation.BATCH_INSERT,
            model_class=instances[0].__class__,
            data={"instances": instances}
        )
        return await self._enqueue(task)

    async def update(
        self,
        model_class: Type[T],
        model_id: str,
        update_data: Dict[str, Any],
        id_field: str = "id"
    ) -> bool:
        """
        异步更新记录

        参数:
            model_class: SQLAlchemy 模型类
            model_id: 记录ID
            update_data: 要更新的字段
            id_field: ID字段名（默认 "id"）

        返回:
            True 表示已加入队列，False 表示队列满被丢弃
        """
        task = WriteTask(
            operation=DatabaseOperation.UPDATE,
            model_class=model_class,
            data={
                "model_id": model_id,
                "update_data": update_data,
                "id_field": id_field
            }
        )
        return await self._enqueue(task)

    async def delete(
        self,
        model_class: Type[T],
        model_id: str,
        id_field: str = "id"
    ) -> bool:
        """
        异步删除记录

        参数:
            model_class: SQLAlchemy 模型类
            model_id: 记录ID
            id_field: ID字段名（默认 "id"）

        返回:
            True 表示已加入队列，False 表示队列满被丢弃
        """
        task = WriteTask(
            operation=DatabaseOperation.DELETE,
            model_class=model_class,
            data={
                "model_id": model_id,
                "id_field": id_field
            }
        )
        return await self._enqueue(task)

    async def upsert(
        self,
        model_class: Type[T],
        insert_data: Dict[str, Any],
        update_data: Dict[str, Any],
        conflict_fields: List[str]
    ) -> bool:
        """
        异步插入或更新记录（PostgreSQL ON CONFLICT）

        参数:
            model_class: SQLAlchemy 模型类
            insert_data: 插入数据
            update_data: 冲突时更新的数据
            conflict_fields: 冲突检测字段

        返回:
            True 表示已加入队列，False 表示队列满被丢弃
        """
        task = WriteTask(
            operation=DatabaseOperation.UPSERT,
            model_class=model_class,
            data={
                "insert_data": insert_data,
                "update_data": update_data,
                "conflict_fields": conflict_fields
            }
        )
        return await self._enqueue(task)

    async def _enqueue(self, task: WriteTask) -> bool:
        """将任务加入队列"""
        self._stats["total_tasks"] += 1
        try:
            self._queue.put_nowait(task)
            return True
        except asyncio.QueueFull:
            self._stats["dropped_tasks"] += 1
            _logger.warning("队列已满，降级为同步写入: operation=%s", task.operation.value)
            # 降级：同步写入
            return self._write_sync(task)

    def _write_sync(self, task: WriteTask) -> bool:
        """同步写入（降级备用）"""
        try:
            with get_db() as session:
                if task.operation == DatabaseOperation.INSERT:
                    instance = task.model_class(**task.data)
                    session.add(instance)
                    session.commit()
                elif task.operation == DatabaseOperation.BATCH_INSERT:
                    session.add_all(task.data["instances"])
                    session.commit()
                elif task.operation == DatabaseOperation.UPDATE:
                    data = task.data
                    stmt = sa_update(task.model_class).where(
                        getattr(task.model_class, data["id_field"]) == data["model_id"]
                    ).values(**data["update_data"])
                    session.execute(stmt)
                    session.commit()
                elif task.operation == DatabaseOperation.DELETE:
                    data = task.data
                    stmt = sa_delete(task.model_class).where(
                        getattr(task.model_class, data["id_field"]) == data["model_id"]
                    )
                    session.execute(stmt)
                    session.commit()
                elif task.operation == DatabaseOperation.UPSERT:
                    data = task.data
                    stmt = pg_insert(task.model_class).values(**data["insert_data"])
                    stmt = stmt.on_conflict_do_update(
                        index_elements=data["conflict_fields"],
                        set_=data["update_data"]
                    )
                    session.execute(stmt)
                    session.commit()
                else:
                    _logger.warning("不支持的操作类型: %s", task.operation)
                    return False
            return True
        except Exception as e:
            _logger.error("同步写入失败: %s", e)
            self._stats["failed_tasks"] += 1
            return False

    async def _worker(self) -> None:
        """后台工作线程"""
        batch_tasks: List[WriteTask] = []
        last_batch_time = time.time()

        while self._running:
            try:
                # 尝试获取任务（带超时）
                try:
                    task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=self._batch_interval
                    )
                    batch_tasks.append(task)
                except asyncio.TimeoutError:
                    pass

                # 判断是否需要批量写入
                if batch_tasks and (
                    len(batch_tasks) >= self._batch_size or
                    (time.time() - last_batch_time) >= self._batch_interval
                ):
                    await self._flush_batch(batch_tasks)
                    self._stats["processed_tasks"] += len(batch_tasks)
                    self._stats["batch_writes"] += 1
                    batch_tasks = []
                    last_batch_time = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                _logger.error("工作线程异常: %s", e)
                await asyncio.sleep(1)

        # 处理剩余任务
        if batch_tasks:
            await self._flush_batch(batch_tasks)
            self._stats["processed_tasks"] += len(batch_tasks)

    async def _flush_batch(self, tasks: List[WriteTask]) -> None:
        """批量写入"""
        if not tasks:
            return

        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self._write_batch_sync,
                tasks
            )
        except Exception as e:
            self._stats["failed_tasks"] += len(tasks)
            _logger.error("批量写入失败: %s", e)

    @staticmethod
    def _write_batch_sync(tasks: List[WriteTask]) -> None:
        """同步批量写入（在工作线程中执行）- 静态方法"""
        try:
            with get_db() as session:
                for task in tasks:
                    if task.operation == DatabaseOperation.INSERT:
                        instance = task.model_class(**task.data)
                        session.add(instance)
                    elif task.operation == DatabaseOperation.BATCH_INSERT:
                        session.add_all(task.data["instances"])
                    elif task.operation == DatabaseOperation.UPDATE:
                        data = task.data
                        stmt = sa_update(task.model_class).where(
                            getattr(task.model_class, data["id_field"]) == data["model_id"]
                        ).values(**data["update_data"])
                        session.execute(stmt)
                    elif task.operation == DatabaseOperation.DELETE:
                        data = task.data
                        stmt = sa_delete(task.model_class).where(
                            getattr(task.model_class, data["id_field"]) == data["model_id"]
                        )
                        session.execute(stmt)
                    elif task.operation == DatabaseOperation.UPSERT:
                        data = task.data
                        stmt = pg_insert(task.model_class).values(**data["insert_data"])
                        stmt = stmt.on_conflict_do_update(
                            index_elements=data["conflict_fields"],
                            set_=data["update_data"]
                        )
                        session.execute(stmt)
                session.commit()
        except Exception as e:
            _logger.error("批量写入失败: %s", e)
            raise

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats: Dict[str, Any] = self._stats.copy()
        stats["queue_size"] = self._queue.qsize()
        stats["running"] = self._running
        stats["max_queue_size"] = self._queue.maxsize

        # 计算成功率
        if stats["total_tasks"] > 0:
            stats["success_rate"] = round(
                (stats["processed_tasks"] - stats["failed_tasks"]) / stats["total_tasks"] * 100, 2
            )
        else:
            stats["success_rate"] = 100.0

        return stats

    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats = {
            "total_tasks": 0,
            "processed_tasks": 0,
            "failed_tasks": 0,
            "dropped_tasks": 0,
            "batch_writes": 0
        }
        _logger.info("统计信息已重置")


# ==================== 静态函数（全局单例） ====================

_async_writer: Optional[AsyncDBWriter] = None


async def get_async_writer() -> AsyncDBWriter:
    """获取全局异步写入器实例（静态函数）"""
    global _async_writer
    if _async_writer is None:
        _async_writer = AsyncDBWriter()
        await _async_writer.start()
    return _async_writer


async def close_async_writer(timeout: float = 10.0) -> None:
    """关闭全局异步写入器（静态函数）"""
    global _async_writer
    if _async_writer:
        await _async_writer.stop(timeout)
        _async_writer = None


def is_async_writer_running() -> bool:
    """检查异步写入器是否运行中（静态函数）"""
    return _async_writer is not None and _async_writer.is_running()


def get_async_writer_stats() -> Optional[Dict[str, Any]]:
    """获取异步写入器统计信息（静态函数）"""
    if _async_writer:
        return _async_writer.get_stats()
    return None