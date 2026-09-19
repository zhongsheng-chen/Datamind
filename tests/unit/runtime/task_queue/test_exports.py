"""运行时任务队列包公共导出测试

验证运行时任务队列包公开 API 的完整性和可访问性。

核心功能：
  - test_task_queue_exports_expected_public_api:
    验证 __all__ 包含完整且准确的公共 API
  - test_all_declared_exports_are_available:
    验证声明的公共对象均可从包级访问
"""

import datamind.runtime.task_queue as task_queue


EXPECTED_EXPORTS = {
    "BatchCancelledError",
    "TaskDispatchError",
    "TaskPublisher",
}


def test_task_queue_exports_expected_public_api() -> None:
    """测试运行时任务队列包公开完整且准确的 API"""
    assert set(task_queue.__all__) == EXPECTED_EXPORTS
    assert len(task_queue.__all__) == len(EXPECTED_EXPORTS)


def test_all_declared_exports_are_available() -> None:
    """测试 __all__ 中声明的对象均可从包级访问"""
    for name in task_queue.__all__:
        assert hasattr(task_queue, name), name
