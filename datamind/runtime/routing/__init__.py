"""运行时路由组件

负责请求规则匹配、流量分配校验和目标部署选择。

核心功能：
  - RuleMatcher: 匹配请求与路由规则
  - RuntimeRouter: 选择请求使用的部署
  - RouteResult: 描述路由选择结果
  - RoutingPlan: 描述主路由和影子路由
  - validate_traffic_allocation: 校验路由流量占比

使用示例：
  from datamind.runtime.routing import RuntimeRouter

  router = RuntimeRouter()
  plan = await router.resolve(
      model_id="mdl_0123456789abcdef",
      environment="production",
      subject_key="customer_10001",
      payload={
          "age": 35,
          "annual_income": 120000,
          "debt_to_income_ratio": 0.32,
          "credit_utilization_ratio": 0.45,
          "delinquency_count": 0,
      },
  )

  print(plan.primary.deployment_id)
"""

from datamind.runtime.routing.matcher import RuleMatcher
from datamind.runtime.routing.policy import validate_traffic_allocation
from datamind.runtime.routing.router import (
    RouteResult,
    RoutingPlan,
    RuntimeRouter,
)

__all__ = [
    "RuleMatcher",
    "RuntimeRouter",
    "RouteResult",
    "RoutingPlan",
    "validate_traffic_allocation",
]
