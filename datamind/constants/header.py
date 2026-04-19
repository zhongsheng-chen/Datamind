# datamind/constants/header.py

"""HTTP头常量

定义API请求和响应中使用的自定义HTTP头名称，用于链路追踪和模型路由。

核心功能：
  - Header: HTTP头名称常量类

使用示例：
  from datamind.constants.header import Header

  # 设置请求头
  headers = {
      Header.trace_id: generate_trace_id(),
      Header.model_id: target_model_id,
  }

头部分类：
  链路追踪：
    - trace_id: 全链路追踪ID
    - request_id: 单次请求ID

  模型标识：
    - model_id: 目标模型ID
    - model_version: 目标模型版本

  AB测试：
    - ab_group: 分配的AB测试组别
    - ab_test_id: AB测试实验ID

  响应控制：
    - target_model: 实际使用的模型ID
    - target_version: 实际使用的模型版本
    - return_details: 是否返回详细信息
"""


class Header:
    """HTTP头名称常量"""

    # 链路追踪
    trace_id: str = "X-Trace-Id"
    request_id: str = "X-Request-Id"

    # 模型标识
    model_id: str = "X-Model-Id"
    model_version: str = "X-Model-Version"

    # AB测试
    ab_group: str = "X-AB-Group"
    ab_test_id: str = "X-AB-Test-Id"

    # 响应控制
    target_model: str = "X-Target-Model"
    target_version: str = "X-Target-Version"
    return_details: str = "X-Return-Details"