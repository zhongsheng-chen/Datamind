"""运行时任务队列异常

定义任务发布与批次执行过程使用的异常类型。

核心功能：
  - TaskDispatchError: 任务无法发布到执行队列
  - BatchCancelledError: 批次执行收到取消请求

使用示例：
  from datamind.runtime.task_queue.errors import (
      BatchCancelledError,
      TaskDispatchError,
  )
"""


class TaskDispatchError(RuntimeError):
    """任务无法发布到执行队列"""


class BatchCancelledError(RuntimeError):
    """批次执行收到协作式取消请求"""
