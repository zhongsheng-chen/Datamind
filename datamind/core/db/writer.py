# datamind/core/db/writer.py

"""同步数据库写入器

提供同步的数据库写入功能，作为异步写入器的降级备用方案。

核心功能：
  - 同步写入单条记录
  - 同步批量写入
  - 同步更新记录
  - 同步删除记录

使用场景：
  - 异步写入器未初始化时的降级
  - 测试环境
  - 需要立即写入的场景
"""

from typing import Dict, Any, Optional, List, Type, TypeVar
from sqlalchemy import update as sa_update, delete as sa_delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from datamind.core.db.database import get_db
from datamind.core.logging import get_logger

_logger = get_logger(__name__)

T = TypeVar('T')


class SyncDBWriter:
    """同步数据库写入器"""

    def __init__(self):
        self._stats = {
            "total_writes": 0,
            "success_writes": 0,
            "failed_writes": 0
        }

    def write(self, model_class: Type[T], **kwargs) -> Optional[T]:
        """
        同步写入单条记录

        参数:
            model_class: SQLAlchemy 模型类
            **kwargs: 模型字段值

        返回:
            创建的模型实例，失败时返回 None
        """
        try:
            with get_db() as session:
                instance = model_class(**kwargs)
                session.add(instance)
                session.commit()
                session.refresh(instance)

                self._stats["total_writes"] += 1
                self._stats["success_writes"] += 1

                _logger.debug("同步写入成功: %s", model_class.__name__)
                return instance

        except Exception as e:
            self._stats["total_writes"] += 1
            self._stats["failed_writes"] += 1
            _logger.error("同步写入失败: %s, error=%s", model_class.__name__, e)
            return None

    def write_batch(self, instances: List) -> int:
        """
        同步批量写入

        参数:
            instances: 模型实例列表

        返回:
            成功写入的数量
        """
        if not instances:
            return 0

        try:
            with get_db() as session:
                session.add_all(instances)
                session.commit()

                count = len(instances)
                self._stats["total_writes"] += count
                self._stats["success_writes"] += count

                _logger.debug("批量写入成功: %d 条记录", count)
                return count

        except Exception as e:
            self._stats["total_writes"] += len(instances)
            self._stats["failed_writes"] += len(instances)
            _logger.error("批量写入失败: %s", e)
            return 0

    def update(
        self,
        model_class: Type[T],
        model_id: str,
        update_data: Dict[str, Any],
        id_field: str = "id"
    ) -> bool:
        """
        同步更新记录

        参数:
            model_class: SQLAlchemy 模型类
            model_id: 记录ID
            update_data: 要更新的字段
            id_field: ID字段名（默认 "id"）

        返回:
            是否更新成功
        """
        try:
            with get_db() as session:
                stmt = sa_update(model_class).where(
                    getattr(model_class, id_field) == model_id
                ).values(**update_data)
                result = session.execute(stmt)
                session.commit()

                self._stats["total_writes"] += 1
                if result.rowcount > 0:
                    self._stats["success_writes"] += 1
                    return True
                else:
                    self._stats["failed_writes"] += 1
                    _logger.warning("更新记录不存在: %s, id=%s", model_class.__name__, model_id)
                    return False

        except Exception as e:
            self._stats["total_writes"] += 1
            self._stats["failed_writes"] += 1
            _logger.error("更新失败: %s, error=%s", model_class.__name__, e)
            return False

    def delete(
        self,
        model_class: Type[T],
        model_id: str,
        id_field: str = "id"
    ) -> bool:
        """
        同步删除记录

        参数:
            model_class: SQLAlchemy 模型类
            model_id: 记录ID
            id_field: ID字段名（默认 "id"）

        返回:
            是否删除成功
        """
        try:
            with get_db() as session:
                stmt = sa_delete(model_class).where(
                    getattr(model_class, id_field) == model_id
                )
                result = session.execute(stmt)
                session.commit()

                self._stats["total_writes"] += 1
                if result.rowcount > 0:
                    self._stats["success_writes"] += 1
                    _logger.debug("删除成功: %s, id=%s", model_class.__name__, model_id)
                    return True
                else:
                    self._stats["failed_writes"] += 1
                    _logger.warning("删除记录不存在: %s, id=%s", model_class.__name__, model_id)
                    return False

        except Exception as e:
            self._stats["total_writes"] += 1
            self._stats["failed_writes"] += 1
            _logger.error("删除失败: %s, id=%s, error=%s", model_class.__name__, model_id, e)
            return False

    def upsert(
        self,
        model_class: Type[T],
        insert_data: Dict[str, Any],
        update_data: Dict[str, Any],
        conflict_fields: List[str]
    ) -> bool:
        """
        同步插入或更新记录（PostgreSQL ON CONFLICT）

        参数:
            model_class: SQLAlchemy 模型类
            insert_data: 插入数据
            update_data: 冲突时更新的数据
            conflict_fields: 冲突检测字段

        返回:
            是否操作成功
        """
        try:
            with get_db() as session:
                stmt = pg_insert(model_class).values(**insert_data)
                stmt = stmt.on_conflict_do_update(
                    index_elements=conflict_fields,
                    set_=update_data
                )
                session.execute(stmt)
                session.commit()

                self._stats["total_writes"] += 1
                self._stats["success_writes"] += 1
                return True

        except Exception as e:
            self._stats["total_writes"] += 1
            self._stats["failed_writes"] += 1
            _logger.error("Upsert失败: %s, error=%s", model_class.__name__, e)
            return False

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        return self._stats.copy()

    def reset_stats(self) -> None:
        """重置统计信息"""
        self._stats = {
            "total_writes": 0,
            "success_writes": 0,
            "failed_writes": 0
        }


# ==================== 静态函数（全局单例） ====================

_sync_writer: Optional[SyncDBWriter] = None


def get_sync_writer() -> SyncDBWriter:
    """获取全局同步写入器实例（静态函数）"""
    global _sync_writer
    if _sync_writer is None:
        _sync_writer = SyncDBWriter()
    return _sync_writer


def close_sync_writer() -> None:
    """关闭全局同步写入器（静态函数）"""
    global _sync_writer
    _sync_writer = None