# datamind/core/domain/permissions.py

"""权限检查模块

定义基于用户角色的权限检查函数，用于控制用户对不同功能的访问权限。

角色说明：
    - ADMIN (admin): 平台管理员，拥有所有权限，包括用户管理、系统配置、审计日志查看等
    - DEVELOPER (developer): 模型开发者，可以管理模型、部署、查看指标、管理自己的API密钥
    - ANALYST (analyst): 数据分析师，可以查看模型效果、分析结果、调用推理
    - API_USER (api_user): API用户，仅能通过API调用推理，不能访问Web界面

权限函数分类：
    模型管理权限：
        - can_manage_models(): 模型注册、更新、删除
        - can_deploy_models(): 模型部署、版本切换、回滚

    数据查看权限：
        - can_view_metrics(): 查看性能指标、模型效果
        - can_view_audit_logs(): 查看审计日志（管理员全量，开发者仅自己）
        - can_view_ab_test_results(): 查看A/B测试结果

    操作权限：
        - can_infer(): 调用推理API
        - can_create_ab_test(): 创建A/B测试
        - can_manage_api_keys(): 管理API密钥（管理员全量，开发者仅自己）

    系统管理权限：
        - can_manage_users(): 用户管理（创建、修改、删除用户）
        - can_access_admin_panel(): 访问管理后台
        - can_manage_system_config(): 系统配置管理

使用场景：
    1. API路由权限控制
        @router.post("/models")
        async def create_model(request: Request):
            user_role = UserRole(request.state.user.get('strategy'))
            if not can_manage_models(user_role):
                raise HTTPException(403, "无权限管理模型")

    2. 审计日志过滤
        logs = query.filter(...)
        if not can_view_audit_logs(user_role, current_user_id, target_user_id):
            logs = logs.filter(operator == current_user_id)

    3. 前端菜单显示
        if can_access_admin_panel(user_role):
            menu.append({"name": "系统管理"})

权限矩阵：
    ┌─────────────────────────┬─────────┬───────────┬─────────┬──────────┐
    │ 权限                     │ ADMIN   │ DEVELOPER │ ANALYST │ API_USER │
    ├─────────────────────────┼─────────┼───────────┼─────────┼──────────┤
    │ 模型管理                 │    ✓    │     ✓     │    ✗    │    ✗     │
    │ 模型部署                 │    ✓    │     ✓     │    ✗    │    ✗     │
    │ 查看性能指标             │    ✓    │     ✓     │    ✓    │    ✗     │
    │ 调用推理                 │    ✓    │     ✓     │    ✓    │    ✓     │
    │ 查看审计日志             │    ✓    │   仅自己  │    ✗    │    ✗     │
    │ 管理用户                 │    ✓    │     ✗     │    ✗    │    ✗     │
    │ 管理API密钥              │    ✓    │   仅自己  │    ✗    │    ✗     │
    │ 访问管理后台             │    ✓    │     ✗     │    ✗    │    ✗     │
    │ 管理系统配置             │    ✓    │     ✗     │    ✗    │    ✗     │
    │ 创建A/B测试              │    ✓    │     ✓     │    ✗    │    ✗     │
    │ 查看A/B测试结果          │    ✓    │     ✓     │    ✓    │    ✗     │
    └─────────────────────────┴─────────┴───────────┴─────────┴──────────┘

注意事项：
    - 所有权限检查函数都返回布尔值
    - 角色使用 UserRole 枚举类型，确保类型安全
    - 查看审计日志时，需要传递当前用户ID和目标用户ID进行判断
    - 管理API密钥时，开发者只能管理自己的密钥
"""

from typing import Optional, List
from datamind.core.domain.enums import UserRole


def can_manage_models(role: UserRole) -> bool:
    """检查是否可以管理模型

    管理模型包括：模型注册、更新元数据、删除模型等操作。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许管理模型，False 表示不允许

    示例:
        >>> can_manage_models(UserRole.ADMIN)
        True
        >>> can_manage_models(UserRole.API_USER)
        False
    """
    return role in [UserRole.ADMIN, UserRole.DEVELOPER]


def can_deploy_models(role: UserRole) -> bool:
    """检查是否可以部署模型

    部署模型包括：模型上线、版本切换、回滚、环境部署等操作。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许部署模型，False 表示不允许
    """
    return role in [UserRole.ADMIN, UserRole.DEVELOPER]


def can_view_metrics(role: UserRole) -> bool:
    """检查是否可以查看性能指标

    性能指标包括：模型推理延迟、准确率、召回率、CPU/内存使用率等。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许查看指标，False 表示不允许
    """
    return role in [UserRole.ADMIN, UserRole.DEVELOPER, UserRole.ANALYST]


def can_infer(role: UserRole) -> bool:
    """检查是否可以调用推理API

    推理API包括：评分预测、反欺诈检测等模型推理接口。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许调用推理，False 表示不允许
    """
    return role in [UserRole.ADMIN, UserRole.DEVELOPER, UserRole.ANALYST, UserRole.API_USER]


def can_view_audit_logs(role: UserRole, current_user_id: Optional[str] = None,
                        log_user_id: Optional[str] = None) -> bool:
    """检查是否可以查看审计日志

    审计日志记录所有用户的操作行为，包括谁、什么时间、做了什么操作。

    权限规则：
        - 管理员(ADMIN): 可以查看所有用户的审计日志
        - 开发者(DEVELOPER): 只能查看自己的审计日志
        - 分析师(ANALYST): 不能查看审计日志
        - API用户(API_USER): 不能查看审计日志

    参数:
        strategy: 当前用户角色
        current_user_id: 当前操作用户ID（用于开发者权限判断）
        log_user_id: 审计日志中的用户ID（要查看谁的日志）

    返回:
        True 表示允许查看，False 表示不允许

    示例:
        # 管理员查看所有日志
        >>> can_view_audit_logs(UserRole.ADMIN)
        True

        # 开发者查看自己的日志
        >>> can_view_audit_logs(UserRole.DEVELOPER, "user_001", "user_001")
        True

        # 开发者查看他人的日志
        >>> can_view_audit_logs(UserRole.DEVELOPER, "user_001", "user_002")
        False

        # 分析师不能查看审计日志
        >>> can_view_audit_logs(UserRole.ANALYST)
        False
    """
    # 管理员可以查看所有审计日志
    if role == UserRole.ADMIN:
        return True

    # 开发者只能查看自己的操作日志
    if role == UserRole.DEVELOPER:
        # 如果没有指定日志用户ID，说明是查询自己的日志列表
        if log_user_id is None:
            return True
        # 检查日志是否属于当前用户
        return current_user_id == log_user_id

    # 分析师和API用户不能查看审计日志
    return False


def can_manage_users(role: UserRole) -> bool:
    """检查是否可以管理用户

    用户管理包括：创建用户、修改用户信息、重置密码、禁用/启用用户、删除用户。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许管理用户，False 表示不允许
    """
    return role == UserRole.ADMIN


def can_manage_api_keys(role: UserRole, current_user_id: Optional[str] = None,
                        target_user_id: Optional[str] = None) -> bool:
    """检查是否可以管理API密钥

    API密钥管理包括：创建密钥、吊销密钥、设置过期时间、配置IP白名单等。

    权限规则：
        - 管理员(ADMIN): 可以管理所有用户的API密钥
        - 开发者(DEVELOPER): 只能管理自己的API密钥
        - 分析师(ANALYST): 不能管理API密钥
        - API用户(API_USER): 不能管理API密钥

    参数:
        strategy: 当前用户角色
        current_user_id: 当前用户ID（用于开发者权限判断）
        target_user_id: 目标用户ID（要管理哪个用户的密钥）

    返回:
        True 表示允许管理，False 表示不允许

    示例:
        # 管理员管理所有用户的密钥
        >>> can_manage_api_keys(UserRole.ADMIN)
        True

        # 开发者管理自己的密钥
        >>> can_manage_api_keys(UserRole.DEVELOPER, "user_001")
        True

        # 开发者管理他人的密钥
        >>> can_manage_api_keys(UserRole.DEVELOPER, "user_001", "user_002")
        False
    """
    # 管理员可以管理所有用户的API密钥
    if role == UserRole.ADMIN:
        return True

    # 开发者只能管理自己的API密钥
    if role == UserRole.DEVELOPER:
        # 如果没有指定目标用户，说明是管理自己的密钥
        if target_user_id is None:
            return True
        return current_user_id == target_user_id

    return False


def can_access_admin_panel(role: UserRole) -> bool:
    """检查是否可以访问管理后台

    管理后台包括：系统配置、用户管理、全局设置等功能。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许访问管理后台，False 表示不允许
    """
    return role == UserRole.ADMIN


def can_manage_system_config(role: UserRole) -> bool:
    """检查是否可以管理系统配置

    系统配置包括：全局参数设置、功能开关、限流阈值、告警配置等。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许管理系统配置，False 表示不允许
    """
    return role == UserRole.ADMIN


def can_create_ab_test(role: UserRole) -> bool:
    """检查是否可以创建A/B测试

    A/B测试创建包括：定义测试组、配置流量分配、设置评估指标等。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许创建A/B测试，False 表示不允许
    """
    return role in [UserRole.ADMIN, UserRole.DEVELOPER]


def can_view_ab_test_results(role: UserRole) -> bool:
    """检查是否可以查看A/B测试结果

    A/B测试结果包括：各组表现对比、置信区间、胜出组判断等。

    参数:
        strategy: 用户角色

    返回:
        True 表示允许查看测试结果，False 表示不允许
    """
    return role in [UserRole.ADMIN, UserRole.DEVELOPER, UserRole.ANALYST]


def get_permissions_for_role(role: UserRole) -> List[str]:
    """获取角色对应的权限列表

    返回该角色拥有的所有权限名称，可用于前端菜单控制或API权限校验。

    参数:
        strategy: 用户角色

    返回:
        权限名称列表

    示例:
        >>> get_permissions_for_role(UserRole.DEVELOPER)
        ['manage_models', 'deploy_models', 'view_metrics', 'infer',
         'view_audit_logs', 'manage_api_keys', 'create_ab_test', 'view_ab_test_results']
    """
    permissions_map = {
        UserRole.ADMIN: [
            "manage_models", "deploy_models", "view_metrics", "infer",
            "view_audit_logs", "manage_users", "manage_api_keys",
            "access_admin_panel", "manage_system_config", "create_ab_test",
            "view_ab_test_results"
        ],
        UserRole.DEVELOPER: [
            "manage_models", "deploy_models", "view_metrics", "infer",
            "view_audit_logs", "manage_api_keys", "create_ab_test",
            "view_ab_test_results"
        ],
        UserRole.ANALYST: [
            "view_metrics", "infer", "view_ab_test_results"
        ],
        UserRole.API_USER: [
            "infer"
        ],
    }

    return permissions_map.get(role, [])


def has_permission(role: UserRole, permission: str) -> bool:
    """检查角色是否有指定权限

    快速检查某个具体权限是否被授予该角色。

    参数:
        strategy: 用户角色
        permission: 权限名称（如 "manage_models"）

    返回:
        True 表示有该权限，False 表示没有

    示例:
        >>> has_permission(UserRole.DEVELOPER, "manage_models")
        True
        >>> has_permission(UserRole.API_USER, "manage_models")
        False
    """
    return permission in get_permissions_for_role(role)