# datamind/context/keys.py

"""上下文键定义

定义请求上下文中使用的标准字段名。

核心功能：
  - TRACE_ID: 链路追踪ID
  - REQUEST_ID: 请求ID
  - USER: 操作用户
  - IP: 客户端IP地址
  - ALL_KEYS: 所有键的集合（用于校验和调试）

使用示例：
  from datamind.context.keys import TRACE_ID, REQUEST_ID, ALL_KEYS

  context = {
      TRACE_ID: "trace-123",
      REQUEST_ID: "req-456",
  }

  # 校验
  missing = ALL_KEYS - set(context.keys())
"""

TRACE_ID = "trace_id"
REQUEST_ID = "request_id"
USER = "user"
IP = "ip"

ALL_KEYS = {
    TRACE_ID: None,
    REQUEST_ID: None,
    USER: None,
    IP: None,
}