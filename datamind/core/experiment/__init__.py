# Datamind/datamind/core/experiment/__init__.py

"""实验模块

提供A/B测试和实验管理功能，用于模型效果对比和业务决策。

核心功能：
  - A/B测试管理：创建、启动、停止A/B测试
  - 流量分配：支持多种分流策略（随机、一致性、分桶、轮询、加权）
  - 用户分组：根据策略将用户分配到不同的实验组
  - 结果分析：统计分析测试指标，自动判断获胜组
  - 缓存优化：Redis缓存分配结果，提升高并发性能

使用场景：
  - 模型效果对比：对比不同模型在相同流量下的表现
  - 策略优化：测试不同业务策略的效果
  - 版本发布：灰度发布和渐进式上线
  - 用户体验测试：对比不同UI/交互方案的效果

模块组成：
  - ABTestManager: A/B测试管理器，提供完整的测试生命周期管理
  - TrafficSplitter: 流量分割器，负责用户分配策略的实现
  - AssignmentStrategy: 分配策略枚举，定义支持的分配策略类型
"""

from datamind.core.experiment.ab_test import (
    ABTestManager,
    AssignmentStrategy,
    TrafficSplitter,
)

__all__ = [
    'ABTestManager',
    'AssignmentStrategy',
    'TrafficSplitter',
]