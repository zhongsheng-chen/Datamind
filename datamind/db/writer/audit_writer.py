# datamind/db/writer/audit_writer.py

"""异步审计日志写入器

提供异步批量写入审计日志的能力，避免阻塞主业务流程。

核心功能：
  - write: 写入审计日志（非阻塞）
  - flush: 强制刷新缓冲区

使用示例：
  from datamind.db.writer.audit_writer import AuditWriter

  writer = AuditWriter(batch_size=20)
  writer.write({
      "action": "model_deploy",
      "operator": "admin",
      "model_id": "mdl_001",
  })
"""

import queue
import threading

from datamind.db.models.audit import Audit
from datamind.db.core.session import get_session


class AuditWriter:
    """异步审计日志写入器"""

    def __init__(self, batch_size: int = 20):
        """初始化写入器

        参数：
            batch_size: 批量写入大小
        """
        self.queue = queue.Queue()
        self.batch_size = batch_size
        self._start_worker()

    def write(self, record: dict) -> None:
        """写入审计日志

        参数：
            record: 审计记录字典
        """
        self.queue.put(record)

    def _start_worker(self) -> None:
        """启动后台工作线程"""
        def run():
            buffer = []
            while True:
                item = self.queue.get()
                buffer.append(item)

                if len(buffer) >= self.batch_size:
                    self._flush(buffer)
                    buffer = []

        threading.Thread(target=run, daemon=True).start()

    def _flush(self, records: list) -> None:
        """批量写入数据库

        参数：
            records: 审计记录列表
        """
        session = get_session()
        session.bulk_insert_mappings(Audit, records)
        session.commit()
        session.close()