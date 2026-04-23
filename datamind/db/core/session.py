# datamind/db/core/session.py

"""数据库会话管理

提供会话工厂和会话获取函数。

核心功能：
  - SessionManager: 会话管理器类
  - get_session_manager: 获取全局会话管理器单例
  - get_session: 获取数据库会话
  - session_scope: 会话上下文管理器

使用示例：
  from datamind.db.core.session import get_session, session_scope

  # 获取会话
  session = get_session()

  # 使用上下文管理器
  with session_scope() as session:
      session.query(Model).all()
"""

from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, Session
from datamind.db.core.engine import get_engine


class SessionManager:
    """会话管理器

    负责会话工厂的创建和会话的获取。
    """

    def __init__(self, config=None):
        """初始化会话管理器

        参数：
            config: 数据库配置对象
        """
        engine = get_engine(config)
        self._factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def get_session(self) -> Session:
        """获取数据库会话

        返回：
            数据库会话实例
        """
        return self._factory()

    @staticmethod
    def close_session(session: Session) -> None:
        """关闭数据库会话

        参数：
            session: 数据库会话实例
        """
        session.close()

    @contextmanager
    def session_scope(self):
        """会话上下文管理器

        自动处理提交和回滚。

        使用示例：
            with session_scope() as session:
                session.add(model)
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# 全局单例
_default_manager = None


def get_session_manager(config=None):
    """获取全局会话管理器单例

    参数：
        config: 数据库配置对象

    返回：
        SessionManager 实例
    """
    global _default_manager
    if _default_manager is None:
        _default_manager = SessionManager(config)
    return _default_manager


def get_session(config=None):
    """获取数据库会话（便捷函数）

    参数：
        config: 数据库配置对象

    返回：
        数据库会话实例
    """
    return get_session_manager(config).get_session()


@contextmanager
def session_scope(config=None):
    """会话上下文管理器（便捷函数）

    参数：
        config: 数据库配置对象

    使用示例：
        with session_scope() as session:
            session.query(Model).all()
    """
    with get_session_manager(config).session_scope() as session:
        yield session