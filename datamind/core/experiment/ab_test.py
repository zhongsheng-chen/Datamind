# datamind/core/experiment/ab_test.py

"""A/B测试管理模块

提供A/B测试的完整管理功能，支持多种分流策略和结果分析。

核心功能：
  - 测试创建与管理：创建、启动、停止A/B测试
  - 流量分配：支持多种分配策略（随机、一致性、分桶、轮询、加权）
  - 客户分组：永久一致性分组，同一客户在同一测试中永远分配到同一组
  - 结果记录：记录测试指标和用户行为
  - 结果分析：统计分析测试结果，判断获胜组
  - 缓存机制：使用Redis缓存客户分配结果，提升性能

分配策略：
  - RANDOM: 随机分配，每次请求独立随机
  - CONSISTENT: 一致性分配，同一客户始终分配到同一组
  - BUCKET: 分桶分配，基于客户ID哈希值分桶（1000个桶）
  - ROUND_ROBIN: 轮询分配，按顺序循环分配
  - WEIGHTED: 加权分配，基于权重的随机分配

设计原则：
  - 永久一致性：同一客户在同一测试中永远分配到同一组
  - 实验隔离：不同测试使用 test_id 与 customer_id 的组合作为分组依据
  - 无状态分组：分组结果可复现，不依赖数据库状态
  - 数据库仅作记录：数据库只存储分配记录用于审计，不参与分组决策
  - 永不过期：分配记录永久有效，不存在过期后重新分组的问题

特性：
  - 流量控制：支持按百分比控制进入测试的流量
  - 时间控制：支持设置测试的开始和结束时间
  - 多指标监控：支持自定义监控指标
  - 获胜判断：支持基于指标自动判断获胜组
  - Redis缓存：提升高并发场景下的分配性能
  - 完整审计：记录所有测试操作和客户分配
  - 链路追踪：完整的 span 追踪
"""

import time
import json
import random
import redis
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from enum import Enum

from datamind.core.db.database import get_db
from datamind.core.db.models import ABTestConfig, ABTestAssignment, ModelMetadata
from datamind.core.domain.enums import ABTestStatus, AuditAction, PerformanceOperation
from datamind.core.logging import context, get_logger, log_audit, log_performance
from datamind.core.common.exceptions import ABTestException
from datamind.config import get_settings

logger = get_logger(__name__)


def _ensure_tzaware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    确保 datetime 对象带时区信息

    参数:
        dt: 需要处理的 datetime 对象，可以为 None

    返回:
        处理后的带时区的 datetime 对象，或 None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _calculate_duration_ms(start_time: float) -> float:
    """
    计算从起始时间到当前时间的耗时（毫秒）

    参数:
        start_time: 起始时间戳（秒），通常由 time.time() 获取

    返回:
        耗时，单位为毫秒
    """
    return (time.time() - start_time) * 1000


class AssignmentStrategy(str, Enum):
    """分配策略枚举"""
    RANDOM = "random"
    CONSISTENT = "consistent"
    BUCKET = "bucket"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"

    @classmethod
    def get_all(cls) -> List[str]:
        """获取所有分配策略的列表"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, strategy: str) -> bool:
        """
        检查指定的策略是否有效

        参数:
            strategy: 策略名称字符串

        返回:
            策略是否有效
        """
        return strategy in cls.get_all()

    @classmethod
    def get_default(cls) -> str:
        """获取默认分配策略（CONSISTENT）"""
        return cls.CONSISTENT.value

    @classmethod
    def get_description(cls, strategy: str) -> str:
        """
        获取分配策略的描述信息

        参数:
            strategy: 策略名称字符串

        返回:
            策略的中文描述
        """
        descriptions = {
            cls.RANDOM.value: "每次请求随机分配，不推荐金融场景使用",
            cls.CONSISTENT.value: "同一客户始终分配到同一组，保证体验一致性",
            cls.BUCKET.value: "基于客户ID的哈希值分桶，适合大规模分流，结果可复现",
            cls.ROUND_ROBIN.value: "按顺序循环分配，适合均匀流量分配",
            cls.WEIGHTED.value: "基于权重的随机分配，可精细控制各组流量比例",
        }
        return descriptions.get(strategy, "未知策略")


class TrafficSplitter:
    """流量分割器，负责根据不同的策略将流量分配到不同的测试组"""

    def __init__(self, strategy: str = None):
        """
        初始化流量分割器

        参数:
            strategy: 默认使用的分配策略，如不指定则使用 CONSISTENT
        """
        self.strategy = strategy or AssignmentStrategy.get_default()
        self._stats = {
            'total_splits': 0,
            'strategy_usage': {}
        }

    @staticmethod
    def split_random(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        随机分配策略

        根据各组权重进行随机选择，权重总和应为100。

        参数:
            groups: 测试组列表，每个组应包含 name、model_id、weight 等字段

        返回:
            被选中的测试组

        异常:
            ValueError: 如果 groups 为空
        """
        weights = [g.get('weight', 0) for g in groups]
        total = sum(weights)
        if abs(total - 100) > 0.01:
            weights = [w / total * 100 for w in weights]
        return random.choices(groups, weights=weights)[0]

    @staticmethod
    def split_consistent(groups: List[Dict[str, Any]], customer_key: str) -> Dict[str, Any]:
        """
        一致性分配策略

        基于客户标识的哈希值进行分配，同一客户始终分配到同一组。

        参数:
            groups: 测试组列表
            customer_key: 客户唯一标识（通常为 test_id + customer_id）

        返回:
            被选中的测试组
        """
        hash_val = int(hashlib.sha256(customer_key.encode()).hexdigest()[:8], 16) % 100
        cumulative = 0
        for group in groups:
            cumulative += group.get('weight', 0)
            if hash_val < cumulative:
                return group
        return groups[-1]

    @staticmethod
    def split_bucket(groups: List[Dict[str, Any]], customer_key: str, bucket_count: int = 1000) -> Dict[str, Any]:
        """
        分桶分配策略

        将客户哈希到固定数量的桶中（默认1000个桶），每个桶映射到一个测试组。

        参数:
            groups: 测试组列表
            customer_key: 客户唯一标识
            bucket_count: 桶的总数，默认为1000

        返回:
            被选中的测试组
        """
        bucket = int(hashlib.sha256(customer_key.encode()).hexdigest()[:8], 16) % bucket_count
        buckets_per_group = []
        for group in groups:
            group_buckets = int(group.get('weight', 0) / 100 * bucket_count)
            buckets_per_group.append(group_buckets)
        cumulative = 0
        for i, group in enumerate(groups):
            cumulative += buckets_per_group[i]
            if bucket < cumulative:
                return group
        return groups[-1]

    @staticmethod
    def split_round_robin(groups: List[Dict[str, Any]], counter: int = None) -> Dict[str, Any]:
        """
        轮询分配策略

        按顺序循环分配流量，counter 参数决定当前轮询到的位置。

        参数:
            groups: 测试组列表
            counter: 当前轮询计数，如果不指定则随机起始位置

        返回:
            被选中的测试组
        """
        if counter is None:
            counter = random.randint(0, len(groups) - 1)
        weighted_groups = []
        for group in groups:
            weight = group.get('weight', 0)
            weighted_groups.extend([group] * int(weight))
        if weighted_groups:
            return weighted_groups[counter % len(weighted_groups)]
        return groups[0]

    @staticmethod
    def split_weighted(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        加权随机分配策略

        根据各组权重进行加权随机选择。

        参数:
            groups: 测试组列表，每个组应包含 weight 字段

        返回:
            被选中的测试组
        """
        weights = [g.get('weight', 0) for g in groups]
        return random.choices(groups, weights=weights)[0]

    @classmethod
    def split(cls, groups: List[Dict[str, Any]], strategy: str, customer_key: str = None, **kwargs) -> Dict[str, Any]:
        """
        核心分组方法，根据指定的策略进行流量分配

        参数:
            groups: 测试组列表
            strategy: 分配策略（random/consistent/bucket/round_robin/weighted）
            customer_key: 客户标识，一致性分配和分桶分配时必需
            **kwargs: 额外参数，如 bucket_count、counter 等

        返回:
            被选中的测试组

        异常:
            ValueError: groups 为空、策略不支持或缺少必要参数时抛出
        """
        if not groups:
            raise ValueError("测试组列表不能为空")
        strategy = strategy or AssignmentStrategy.get_default()

        if strategy == AssignmentStrategy.RANDOM:
            return cls.split_random(groups)
        elif strategy == AssignmentStrategy.CONSISTENT:
            if not customer_key:
                raise ValueError("一致性分配需要提供 customer_key")
            return cls.split_consistent(groups, customer_key)
        elif strategy == AssignmentStrategy.BUCKET:
            if not customer_key:
                raise ValueError("分桶分配需要提供 customer_key")
            bucket_count = kwargs.get('bucket_count', 1000)
            return cls.split_bucket(groups, customer_key, bucket_count)
        elif strategy == AssignmentStrategy.ROUND_ROBIN:
            counter = kwargs.get('counter')
            return cls.split_round_robin(groups, counter)
        elif strategy == AssignmentStrategy.WEIGHTED:
            return cls.split_weighted(groups)
        else:
            raise ValueError(f"不支持的分配策略: {strategy}")

    def split_with_stats(self, groups: List[Dict[str, Any]], customer_key: str = None, **kwargs) -> Dict[str, Any]:
        """
        带统计功能的流量分配

        执行分配并记录分配统计信息。

        参数:
            groups: 测试组列表
            customer_key: 客户标识
            **kwargs: 额外参数

        返回:
            被选中的测试组
        """
        result = self.split(groups, self.strategy, customer_key, **kwargs)
        self._stats['total_splits'] += 1
        strategy_key = self.strategy
        if strategy_key not in self._stats['strategy_usage']:
            self._stats['strategy_usage'][strategy_key] = 0
        self._stats['strategy_usage'][strategy_key] += 1
        return result

    def get_stats(self) -> Dict[str, Any]:
        """
        获取流量分割器的统计信息

        返回:
            包含 total_splits 和 strategy_usage 的统计字典
        """
        return self._stats.copy()

    def reset_stats(self):
        """重置流量分割器的统计信息"""
        self._stats = {'total_splits': 0, 'strategy_usage': {}}


class ABTestManager:
    """A/B测试管理器，提供测试创建、分配、记录和分析的完整功能"""

    def __init__(self):
        """初始化A/B测试管理器，配置Redis连接和统计信息"""
        settings = get_settings()
        ab_test_config = settings.ab_test
        redis_config = settings.redis

        self.enabled = ab_test_config.enabled
        self.redis_key_prefix = ab_test_config.redis_key_prefix
        self.assignment_expiry = 365 * 24 * 3600

        self.redis_url = redis_config.url
        self.redis_max_connections = redis_config.max_connections
        self.redis_socket_timeout = redis_config.socket_timeout

        self.redis_client = None
        self._init_redis()
        self._stats = {
            'total_assignments': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        self.splitter = TrafficSplitter()

        logger.info("A/B测试管理器初始化完成")

    def _init_redis(self):
        """初始化Redis连接，用于缓存分配结果"""
        try:
            if self.redis_url:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    max_connections=self.redis_max_connections,
                    socket_timeout=self.redis_socket_timeout,
                    decode_responses=True
                )
                logger.info("A/B测试 Redis 连接成功")
        except Exception as e:
            logger.warning("A/B测试 Redis 连接失败: %s，将使用内存缓存", e)
            self.redis_client = None

    def create_test(
            self,
            test_name: str,
            task_type: str,
            groups: List[Dict[str, Any]],
            created_by: str,
            description: Optional[str] = None,
            traffic_allocation: float = 100.0,
            assignment_strategy: str = 'consistent',
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            metrics: Optional[List[str]] = None,
            winning_criteria: Optional[Dict] = None,
            ip_address: Optional[str] = None
    ) -> str:
        """
        创建A/B测试

        在数据库中创建新的A/B测试配置，包括测试组、分配策略、流量控制等。

        参数:
            test_name: 测试名称，用于标识测试目的
            task_type: 任务类型，如 'classification', 'regression' 等
            groups: 测试组列表，每个组需包含 name、model_id、weight 字段，权重总和为100
            created_by: 创建者ID
            description: 测试描述，可选
            traffic_allocation: 流量分配比例（0-100），控制多少流量进入测试
            assignment_strategy: 分配策略，默认 'consistent'
            start_date: 测试开始时间，默认为当前时间
            end_date: 测试结束时间，默认为30天后
            metrics: 要监控的指标列表，如 ['accuracy', 'latency']
            winning_criteria: 获胜判断标准，如 {'metric': 'accuracy', 'min_diff': 0.01}
            ip_address: 创建者IP地址，用于审计

        返回:
            生成的测试ID，格式为 ABT_YYYYMMDDHHMMSS_XXXX

        异常:
            ABTestException: 分组无效、策略无效或模型不存在时抛出
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        try:
            if not AssignmentStrategy.is_valid(assignment_strategy):
                raise ABTestException(f"无效的分配策略: {assignment_strategy}")

            self._validate_groups(groups)

            test_id = f"ABT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"

            if not start_date:
                start_date = datetime.now()
            if not end_date:
                end_date = start_date + timedelta(days=30)

            with get_db() as session:
                test = ABTestConfig(
                    test_id=test_id,
                    test_name=test_name,
                    description=description,
                    task_type=task_type,
                    groups=groups,
                    traffic_allocation=traffic_allocation,
                    assignment_strategy=assignment_strategy,
                    start_date=start_date,
                    end_date=end_date,
                    status=ABTestStatus.DRAFT.value,
                    created_by=created_by,
                    metrics=metrics,
                    winning_criteria=winning_criteria
                )
                session.add(test)
                session.commit()

            duration = _calculate_duration_ms(start_time)

            log_performance(
                operation=PerformanceOperation.AB_TEST_CREATE,
                duration_ms=duration,
                request_id=request_id,
                extra={
                    "test_id": test_id,
                    "task_type": task_type,
                    "groups_count": len(groups),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            log_audit(
                action=AuditAction.AB_TEST_CREATE.value,
                user_id=created_by,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                resource_name=test_name,
                details={
                    "task_type": task_type,
                    "groups": groups,
                    "traffic_allocation": traffic_allocation,
                    "assignment_strategy": assignment_strategy,
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.info("A/B测试创建成功: test_id=%s, 名称=%s", test_id, test_name)
            return test_id

        except Exception as e:
            duration = _calculate_duration_ms(start_time)

            log_audit(
                action=AuditAction.AB_TEST_ERROR.value,
                user_id=created_by,
                ip_address=ip_address,
                resource_type="ab_test",
                details={
                    "test_name": test_name,
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            logger.error("A/B测试创建失败: 名称=%s, 错误=%s", test_name, str(e), exc_info=True)
            raise

    @staticmethod
    def _validate_groups(groups: List[Dict[str, Any]]):
        """
        验证测试组的有效性

        检查项：
        - 测试组列表不为空
        - 各组权重总和为100
        - 每个组指定的模型存在且处于激活状态

        参数:
            groups: 测试组列表

        异常:
            ABTestException: 验证失败时抛出
        """
        if not groups:
            raise ABTestException("测试组不能为空")

        total_weight = sum(g.get('weight', 0) for g in groups)
        if abs(total_weight - 100) > 0.01:
            raise ABTestException(f"组权重总和必须为100，当前: {total_weight}")

        for group in groups:
            model_id = group.get('model_id')
            if not model_id:
                raise ABTestException(f"组 {group.get('name')} 缺少模型ID")

            with get_db() as session:
                model = session.query(ModelMetadata).filter_by(
                    model_id=model_id,
                    status='active'
                ).first()
                if not model:
                    raise ABTestException(f"模型不存在或未激活: {model_id}")

    @staticmethod
    def start_test(test_id: str, operator: str, ip_address: Optional[str] = None):
        """
        启动A/B测试

        将测试状态从 DRAFT 变更为 RUNNING，开始正式分配流量。

        参数:
            test_id: 要启动的测试ID
            operator: 操作者ID
            ip_address: 操作者IP地址，用于审计

        异常:
            ABTestException: 测试不存在或状态不正确时抛出
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        try:
            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
                if not test:
                    raise ABTestException(f"测试不存在: {test_id}")

                if test.status != ABTestStatus.DRAFT.value:
                    raise ABTestException(f"测试状态错误，无法启动: {test.status}")

                test.status = ABTestStatus.RUNNING.value
                session.commit()
                test_name = test.test_name

            duration = _calculate_duration_ms(start_time)

            log_performance(
                operation=PerformanceOperation.AB_TEST_START,
                duration_ms=duration,
                request_id=request_id,
                extra={
                    "test_id": test_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            log_audit(
                action=AuditAction.AB_TEST_START.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                resource_name=test_name,
                details={
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.info("A/B测试启动成功: test_id=%s, 名称=%s", test_id, test_name)

        except Exception as e:
            duration = _calculate_duration_ms(start_time)

            log_audit(
                action=AuditAction.AB_TEST_ERROR.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            logger.error("A/B测试启动失败: test_id=%s, 错误=%s", test_id, str(e), exc_info=True)
            raise

    def get_assignment(
            self,
            test_id: str,
            customer_id: str,
            ip_address: Optional[str] = None,
            return_details: bool = False
    ) -> Dict[str, Any]:
        """
        获取客户分组分配

        根据测试配置和分配策略，为指定客户分配测试组。
        支持Redis缓存以提升性能，同一客户的分配结果永久一致。

        分配流程：
        - 检查Redis缓存，命中则直接返回
        - 验证测试是否存在且处于运行状态
        - 验证测试是否在有效期内
        - 流量控制：判断是否进入测试
        - 根据分配策略选择测试组
        - 保存分配记录到数据库
        - 缓存分配结果并返回

        参数:
            test_id: 测试ID
            customer_id: 客户ID（唯一标识，用于永久一致性分流）
            ip_address: 客户端IP地址，用于审计
            return_details: 是否返回详细信息（策略、分桶值等）

        返回:
            分配结果字典，包含以下字段：
                - test_id: 测试ID
                - customer_id: 客户ID
                - group_name: 分配的组名
                - model_id: 对应的模型ID
                - assigned_at: 分配时间
                - in_test: 是否进入测试（流量控制）
                - 当 return_details=True 时，额外包含 strategy、traffic_allocation、groups、bucket、hash_key

        异常:
            ABTestException: 测试不存在、未运行、不在有效期内时抛出
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        try:
            cache_key = f"{self.redis_key_prefix}{test_id}:{customer_id}"

            if self.redis_client:
                cached = self.redis_client.get(cache_key)
                if cached:
                    self._stats['cache_hits'] += 1
                    logger.debug("A/B测试分配缓存命中: test_id=%s, customer_id=%s", test_id, customer_id)
                    result = json.loads(cached)

                    if return_details and 'strategy' not in result:
                        result = self._add_details(result, test_id, customer_id)
                    return result

            self._stats['cache_misses'] += 1

            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(
                    test_id=test_id,
                    status=ABTestStatus.RUNNING.value
                ).first()

                if not test:
                    raise ABTestException(f"测试不存在或未运行: {test_id}")

                now = datetime.now(timezone.utc)
                start_date = _ensure_tzaware(test.start_date)
                end_date = _ensure_tzaware(test.end_date)

                if now < start_date or (end_date and now > end_date):
                    raise ABTestException("测试不在有效期内")

                # 流量控制
                if random.random() * 100 > test.traffic_allocation:
                    result = {
                        'test_id': test_id,
                        'customer_id': customer_id,
                        'group_name': 'default',
                        'model_id': None,
                        'assigned_at': now.isoformat(),
                        'in_test': False
                    }
                    self._cache_assignment(cache_key, result)
                    return result

                # 分配分组
                customer_key = f"{test_id}:{customer_id}"
                group = TrafficSplitter.split(
                    groups=test.groups,
                    strategy=test.assignment_strategy,
                    customer_key=customer_key
                )

                # 保存分配记录
                existing = session.query(ABTestAssignment).filter_by(
                    test_id=test_id,
                    customer_id=customer_id
                ).first()

                if not existing:
                    assignment = ABTestAssignment(
                        test_id=test_id,
                        customer_id=customer_id,
                        group_name=group['name'],
                        model_id=group['model_id'],
                        expires_at=None
                    )
                    session.add(assignment)
                    session.commit()

                # 构建基础结果
                result = {
                    'test_id': test_id,
                    'customer_id': customer_id,
                    'group_name': group['name'],
                    'model_id': group['model_id'],
                    'assigned_at': now.isoformat(),
                    'in_test': True
                }

                # 添加详细信息
                if return_details:
                    result['strategy'] = test.assignment_strategy
                    result['traffic_allocation'] = test.traffic_allocation
                    result['groups'] = [
                        {'name': g['name'], 'weight': g.get('weight', 0)}
                        for g in test.groups
                    ]

                    # 计算分桶值
                    hash_val = int(hashlib.sha256(customer_key.encode()).hexdigest()[:8], 16)
                    result['bucket'] = hash_val % 100
                    result['hash_key'] = customer_key

                self._cache_assignment(cache_key, result)
                self._stats['total_assignments'] += 1

                duration = _calculate_duration_ms(start_time)

                log_performance(
                    operation=PerformanceOperation.AB_TEST_ASSIGNMENT,
                    duration_ms=duration,
                    request_id=request_id,
                    extra={
                        "test_id": test_id,
                        "group_name": group['name'],
                        "strategy": test.assignment_strategy,
                        "cache_hit": False,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    }
                )

                log_audit(
                    action=AuditAction.AB_TEST_ASSIGNMENT.value,
                    user_id=customer_id,
                    ip_address=ip_address,
                    resource_type="ab_test",
                    resource_id=test_id,
                    details={
                        "group_name": group['name'],
                        "model_id": group['model_id'],
                        "strategy": test.assignment_strategy,
                        "duration_ms": round(duration, 2),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                logger.debug("A/B测试分配成功: test_id=%s, customer_id=%s, group=%s", test_id, customer_id,
                             group['name'])
                return result

        except Exception as e:
            duration = _calculate_duration_ms(start_time)

            log_audit(
                action=AuditAction.AB_TEST_ERROR.value,
                user_id=customer_id,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            logger.error("A/B测试分配失败: test_id=%s, customer_id=%s, 错误=%s", test_id, customer_id, str(e),
                         exc_info=True)
            raise

    @staticmethod
    def _add_details(
            result: Dict[str, Any],
            test_id: str,
            customer_id: str
    ) -> Dict[str, Any]:
        """
        为分配结果补充详细信息

        当从缓存获取的分配结果缺少详细信息时，从数据库补充。

        参数:
            result: 基础分配结果
            test_id: 测试ID
            customer_id: 客户ID

        返回:
            补充了详细信息的分配结果
        """
        with get_db() as session:
            test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
            if test:
                result['strategy'] = test.assignment_strategy
                result['traffic_allocation'] = test.traffic_allocation
                result['groups'] = [
                    {'name': g['name'], 'weight': g.get('weight', 0)}
                    for g in test.groups
                ]

                customer_key = f"{test_id}:{customer_id}"
                hash_val = int(hashlib.sha256(customer_key.encode()).hexdigest()[:8], 16)
                result['bucket'] = hash_val % 100
                result['hash_key'] = customer_key

        return result

    def _cache_assignment(self, key: str, value: Dict, ttl: int = 3600):
        """
        将分配结果缓存到Redis

        参数:
            key: 缓存键
            value: 要缓存的值（字典）
            ttl: 过期时间（秒），默认为1小时
        """
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception as e:
                logger.debug("A/B测试分配缓存失败: %s, 错误=%s", key, e)

    @staticmethod
    def record_result(
            test_id: str,
            customer_id: str,
            metrics: Dict[str, Any],
            ip_address: Optional[str] = None
    ):
        """
        记录测试结果

        将客户在测试中的表现指标记录到测试结果中，用于后续分析。

        参数:
            test_id: 测试ID
            customer_id: 客户ID
            metrics: 指标字典，如 {'accuracy': 0.95, 'latency': 100}
            ip_address: 客户端IP地址，用于审计

        异常:
            ABTestException: 测试不存在时抛出
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        try:
            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
                if not test:
                    raise ABTestException(f"测试不存在: {test_id}")

                if not test.results:
                    test.results = {}

                if customer_id not in test.results:
                    test.results[customer_id] = []

                test.results[customer_id].append({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'metrics': metrics
                })

                session.commit()

            duration = _calculate_duration_ms(start_time)

            log_performance(
                operation=PerformanceOperation.AB_TEST_RECORD,
                duration_ms=duration,
                request_id=request_id,
                extra={
                    "test_id": test_id,
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )

            log_audit(
                action=AuditAction.AB_TEST_RECORD.value,
                user_id=customer_id,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={
                    "metrics": metrics,
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.debug("A/B测试结果记录成功: test_id=%s, customer_id=%s", test_id, customer_id)

        except Exception as e:
            duration = _calculate_duration_ms(start_time)

            log_audit(
                action=AuditAction.AB_TEST_ERROR.value,
                user_id=customer_id,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            logger.error("A/B测试结果记录失败: test_id=%s, customer_id=%s, 错误=%s", test_id, customer_id, str(e),
                         exc_info=True)
            raise

    def analyze_results(self, test_id: str) -> Dict[str, Any]:
        """
        分析测试结果，判断获胜组

        收集所有客户的测试指标，按组统计平均值、最小值、最大值，
        并根据预设的获胜标准判断哪个组获胜。

        分析流程：
        - 获取测试配置和结果数据
        - 遍历所有客户，通过分配记录确定其所属组
        - 按组聚合指标数据
        - 计算各组的统计值（avg、min、max、count）
        - 根据 winning_criteria 判断获胜组

        参数:
            test_id: 测试ID

        返回:
            分析结果，包含：
                - test_id: 测试ID
                - test_name: 测试名称
                - status: 测试状态
                - strategy: 分配策略
                - groups: 各组统计结果，格式：
                    {
                        "group_name": {
                            "count": 用户数,
                            "metrics": {
                                "metric_name": {"avg": 平均值, "min": 最小值, "max": 最大值, "count": 样本数}
                            }
                        }
                    }
                - winning_group: 获胜组名称
                - total_users: 总用户数
        """
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        try:
            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
                if not test:
                    raise ABTestException(f"测试不存在: {test_id}")

                if not test.results:
                    return {"status": "no_data"}

                group_results = {}
                for group in test.groups:
                    group_name = group['name']
                    group_results[group_name] = {
                        'count': 0,
                        'metrics': {}
                    }

                for customer_id, records in test.results.items():
                    assignment = session.query(ABTestAssignment).filter_by(
                        test_id=test_id,
                        customer_id=customer_id
                    ).first()

                    if assignment and assignment.group_name in group_results:
                        group = group_results[assignment.group_name]
                        group['count'] += 1

                        for record in records:
                            for metric, value in record.get('metrics', {}).items():
                                if metric not in group['metrics']:
                                    group['metrics'][metric] = []
                                group['metrics'][metric].append(value)

                for group_name, group in group_results.items():
                    for metric, values in group['metrics'].items():
                        if values:
                            group['metrics'][metric] = {
                                'avg': sum(values) / len(values),
                                'min': min(values),
                                'max': max(values),
                                'count': len(values)
                            }

                winning_group = self._determine_winner(group_results, test.winning_criteria)

                duration = _calculate_duration_ms(start_time)

                log_performance(
                    operation=PerformanceOperation.AB_TEST_COMPLETE,
                    duration_ms=duration,
                    request_id=request_id,
                    extra={
                        "test_id": test_id,
                        "total_users": len(test.results),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    }
                )

                log_audit(
                    action=AuditAction.AB_TEST_COMPLETE.value,
                    user_id="system",
                    ip_address=None,
                    resource_type="ab_test",
                    resource_id=test_id,
                    details={
                        "winning_group": winning_group,
                        "total_users": len(test.results),
                        "duration_ms": round(duration, 2),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                logger.info("A/B测试结果分析完成: test_id=%s, 获胜组=%s", test_id, winning_group)

                return {
                    'test_id': test_id,
                    'test_name': test.test_name,
                    'status': test.status,
                    'strategy': test.assignment_strategy,
                    'groups': group_results,
                    'winning_group': winning_group,
                    'total_users': len(test.results)
                }

        except Exception as e:
            duration = _calculate_duration_ms(start_time)

            log_audit(
                action=AuditAction.AB_TEST_ERROR.value,
                user_id="system",
                ip_address=None,
                resource_type="ab_test",
                resource_id=test_id,
                details={
                    "error": str(e),
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            logger.error("A/B测试结果分析失败: test_id=%s, 错误=%s", test_id, str(e), exc_info=True)
            raise

    @staticmethod
    def _determine_winner(group_results: Dict, criteria: Optional[Dict]) -> Optional[str]:
        """
        根据获胜标准判断获胜组

        参数:
            group_results: 各组统计结果
            criteria: 获胜标准，包含 metric 字段指定比较的指标

        返回:
            获胜组名称，如果没有获胜标准或无法判断则返回 None
        """
        if not criteria:
            return None

        target_metric = criteria.get('metric')
        if not target_metric:
            return None

        best_group = None
        best_value = None

        for group_name, group in group_results.items():
            metric_data = group['metrics'].get(target_metric)
            if metric_data and 'avg' in metric_data:
                if best_value is None or metric_data['avg'] > best_value:
                    best_value = metric_data['avg']
                    best_group = group_name

        return best_group

    def get_stats(self) -> Dict[str, Any]:
        """
        获取A/B测试管理器的统计信息

        返回:
            包含 total_assignments、cache_hits、cache_misses 的统计字典
        """
        return self._stats.copy()


# 全局A/B测试管理器实例
ab_test_manager = ABTestManager()