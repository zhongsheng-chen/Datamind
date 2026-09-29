"""运行时任务队列.

提供发布 Celery 任务及处理任务队列异常的公开接口。

核心功能：
  - TaskPublisher: 发布和撤销运行时异步任务
  - TaskDispatchError: 任务发布或撤销失败
  - BatchCancelledError: 批次执行收到取消请求

使用示例：
  from datamind.runtime.task_queue import TaskPublisher

  publisher = TaskPublisher()
  publisher.submit_shadow(
      execution_id="exe_0123456789abcdef",
      task_id="tsk_0123456789abcdef",
  )
"""

from datamind.runtime.task_queue.errors import (
    BatchCancelledError,
    TaskDispatchError,
)
from datamind.runtime.task_queue.publisher import TaskPublisher


__all__ = [
    "BatchCancelledError",
    "TaskDispatchError",
    "TaskPublisher",
]
