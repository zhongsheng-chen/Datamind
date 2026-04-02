# datamind/core/experiment/ab_test.py

"""A/B测试管理模块

提供A/B测试的完整管理功能，支持多种分流策略和结果分析。

核心功能：
  - 测试创建与管理：创建、启动、停止A/B测试
  - 流量分配：支持多种分配策略（随机、一致性、分桶、轮询、加权）
  - 用户分组：根据策略将用户分配到不同的测试组
  - 结果记录：记录测试指标和用户行为
  - 结果分析：统计分析测试结果，判断获胜组
  - 缓存机制：使用Redis缓存用户分配结果，提升性能

分配策略：
  - RANDOM: 随机分配，每次请求独立随机
  - CONSISTENT: 一致性分配，同一用户始终分配到同一组
  - BUCKET: 分桶分配，基于用户ID哈希值分桶（1000个桶）
  - ROUND_ROBIN: 轮询分配，按顺序循环分配
  - WEIGHTED: 加权分配，基于权重的随机分配

特性：
  - 流量控制：支持按百分比控制进入测试的流量
  - 时间控制：支持设置测试的开始和结束时间
  - 多指标监控：支持自定义监控指标
  - 获胜判断：支持基于指标自动判断获胜组
  - Redis缓存：提升高并发场景下的分配性能
  - 完整审计：记录所有测试操作和用户分配
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
from datamind.core.domain.enums import ABTestStatus, AuditAction
from datamind.core.logging import log_audit, context, get_logger
from datamind.core.common.exceptions import ABTestException
from datamind.config import get_settings

logger = get_logger(__name__)


def _ensure_tzaware(dt: Optional[datetime]) -> Optional[datetime]:
    """确保 datetime 对象带时区"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class AssignmentStrategy(str, Enum):
    """分配策略枚举"""
    RANDOM = "random"
    CONSISTENT = "consistent"
    BUCKET = "bucket"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"

    @classmethod
    def get_all(cls) -> List[str]:
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, strategy: str) -> bool:
        return strategy in cls.get_all()

    @classmethod
    def get_default(cls) -> str:
        return cls.RANDOM.value

    @classmethod
    def get_description(cls, strategy: str) -> str:
        descriptions = {
            cls.RANDOM.value: "每次请求随机分配，适用于无状态测试",
            cls.CONSISTENT.value: "同一用户始终分配到同一组，保证用户体验一致性",
            cls.BUCKET.value: "基于用户ID的哈希值分桶，适合大规模分流",
            cls.ROUND_ROBIN.value: "按顺序循环分配，适合均匀流量分配",
            cls.WEIGHTED.value: "基于权重的随机分配，可精细控制各组流量比例",
        }
        return descriptions.get(strategy, "未知策略")


class TrafficSplitter:
    """流量分割器"""

    def __init__(self, strategy: str = None):
        self.strategy = strategy or AssignmentStrategy.get_default()
        self._stats = {
            'total_splits': 0,
            'strategy_usage': {}
        }

    @staticmethod
    def split_random(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        weights = [g.get('weight', 0) for g in groups]
        total = sum(weights)
        if abs(total - 100) > 0.01:
            weights = [w / total * 100 for w in weights]
        return random.choices(groups, weights=weights)[0]

    @staticmethod
    def split_consistent(groups: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16) % 100
        cumulative = 0
        for group in groups:
            cumulative += group.get('weight', 0)
            if hash_val < cumulative:
                return group
        return groups[-1]

    @staticmethod
    def split_bucket(groups: List[Dict[str, Any]], user_id: str, bucket_count: int = 1000) -> Dict[str, Any]:
        bucket = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16) % bucket_count
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
        weights = [g.get('weight', 0) for g in groups]
        return random.choices(groups, weights=weights)[0]

    @classmethod
    def split(cls, groups: List[Dict[str, Any]], strategy: str, user_id: str = None, **kwargs) -> Dict[str, Any]:
        if not groups:
            raise ValueError("测试组列表不能为空")
        strategy = strategy or AssignmentStrategy.get_default()

        if strategy == AssignmentStrategy.RANDOM:
            return cls.split_random(groups)
        elif strategy == AssignmentStrategy.CONSISTENT:
            if not user_id:
                raise ValueError("一致性分配需要提供 user_id")
            return cls.split_consistent(groups, user_id)
        elif strategy == AssignmentStrategy.BUCKET:
            if not user_id:
                raise ValueError("分桶分配需要提供 user_id")
            bucket_count = kwargs.get('bucket_count', 1000)
            return cls.split_bucket(groups, user_id, bucket_count)
        elif strategy == AssignmentStrategy.ROUND_ROBIN:
            counter = kwargs.get('counter')
            return cls.split_round_robin(groups, counter)
        elif strategy == AssignmentStrategy.WEIGHTED:
            return cls.split_weighted(groups)
        else:
            raise ValueError(f"不支持的分配策略: {strategy}")

    def split_with_stats(self, groups: List[Dict[str, Any]], user_id: str = None, **kwargs) -> Dict[str, Any]:
        result = self.split(groups, self.strategy, user_id, **kwargs)
        self._stats['total_splits'] += 1
        strategy_key = self.strategy
        if strategy_key not in self._stats['strategy_usage']:
            self._stats['strategy_usage'][strategy_key] = 0
        self._stats['strategy_usage'][strategy_key] += 1
        return result

    def get_stats(self) -> Dict[str, Any]:
        return self._stats.copy()

    def reset_stats(self):
        self._stats = {'total_splits': 0, 'strategy_usage': {}}


class ABTestManager:
    """A/B测试管理器"""

    def __init__(self):
        settings = get_settings()
        ab_test_config = settings.ab_test
        redis_config = settings.redis

        self.enabled = ab_test_config.enabled
        self.redis_key_prefix = ab_test_config.redis_key_prefix
        self.assignment_expiry = ab_test_config.assignment_expiry

        self.redis_url = redis_config.url
        self.redis_password = redis_config.password
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
        try:
            if self.redis_url:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    password=self.redis_password,
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
            assignment_strategy: str = 'random',
            start_date: Optional[datetime] = None,
            end_date: Optional[datetime] = None,
            metrics: Optional[List[str]] = None,
            winning_criteria: Optional[Dict] = None,
            ip_address: Optional[str] = None
    ) -> str:
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

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

            duration = (datetime.now() - start_time).total_seconds() * 1000

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

            logger.info("A/B测试创建成功: test_id=%s, 名称=%s, 任务类型=%s, 创建人=%s",
                       test_id, test_name, task_type, created_by)
            return test_id

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.AB_TEST_CREATE.value,
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
            logger.error("A/B测试创建失败: 名称=%s, 错误=%s", test_name, e)
            raise

    def _validate_groups(self, groups: List[Dict[str, Any]]):
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

    def start_test(self, test_id: str, operator: str, ip_address: Optional[str] = None):
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = datetime.now()

        try:
            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
                if not test:
                    raise ABTestException(f"测试不存在: {test_id}")

                if test.status != ABTestStatus.DRAFT.value:
                    raise ABTestException(f"测试状态错误，无法启动: {test.status}")

                test.status = ABTestStatus.RUNNING.value
                session.commit()

            duration = (datetime.now() - start_time).total_seconds() * 1000

            log_audit(
                action=AuditAction.AB_TEST_START.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                resource_name=test.test_name,
                details={
                    "duration_ms": round(duration, 2),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                request_id=request_id
            )

            logger.info("A/B测试启动成功: test_id=%s, 名称=%s, 操作人=%s",
                       test_id, test.test_name, operator)

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_audit(
                action=AuditAction.AB_TEST_START.value,
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
            logger.error("A/B测试启动失败: test_id=%s, 错误=%s", test_id, e)
            raise

    def get_assignment(
            self,
            test_id: str,
            user_id: str,
            ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()
        start_time = time.time()

        try:
            cache_key = f"{self.redis_key_prefix}{test_id}:{user_id}"
            if self.redis_client:
                cached = self.redis_client.get(cache_key)
                if cached:
                    self._stats['cache_hits'] += 1
                    logger.debug("A/B测试分配缓存命中: %s", cache_key)
                    return json.loads(cached)

            self._stats['cache_misses'] += 1

            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(
                    test_id=test_id,
                    status=ABTestStatus.RUNNING.value
                ).first()

                if not test:
                    raise ABTestException(f"测试不存在或未运行: {test_id}")

                # 获取当前时间（带时区）
                now = datetime.now(timezone.utc)

                # 确保 start_date 和 end_date 带时区
                start_date = _ensure_tzaware(test.start_date)
                end_date = _ensure_tzaware(test.end_date)

                if now < start_date or (end_date and now > end_date):
                    raise ABTestException("测试不在有效期内")

                if random.random() * 100 > test.traffic_allocation:
                    return {
                        'test_id': test_id,
                        'user_id': user_id,
                        'group_name': 'default',
                        'model_id': None,
                        'assigned_at': now.isoformat(),
                        'in_test': False
                    }

                existing = session.query(ABTestAssignment).filter_by(
                    test_id=test_id,
                    user_id=user_id
                ).first()

                if existing:
                    expires_at = _ensure_tzaware(existing.expires_at)
                    if expires_at and now > expires_at:
                        session.delete(existing)
                        session.commit()
                    else:
                        result = {
                            'test_id': test_id,
                            'user_id': user_id,
                            'group_name': existing.group_name,
                            'model_id': existing.model_id,
                            'assigned_at': existing.assigned_at.isoformat(),
                            'in_test': True
                        }
                        self._cache_assignment(cache_key, result)
                        return result

                group = TrafficSplitter.split(
                    groups=test.groups,
                    strategy=test.assignment_strategy,
                    user_id=user_id
                )

                assignment = ABTestAssignment(
                    test_id=test_id,
                    user_id=user_id,
                    group_name=group['name'],
                    model_id=group['model_id'],
                    expires_at=now + timedelta(seconds=self.assignment_expiry)
                )
                session.add(assignment)
                session.commit()

                result = {
                    'test_id': test_id,
                    'user_id': user_id,
                    'group_name': group['name'],
                    'model_id': group['model_id'],
                    'assigned_at': now.isoformat(),
                    'in_test': True
                }

                self._cache_assignment(cache_key, result)
                self._stats['total_assignments'] += 1

                duration = (time.time() - start_time) * 1000
                log_audit(
                    action=AuditAction.AB_TEST_ASSIGNMENT.value,
                    user_id=user_id,
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

                logger.debug("A/B测试分配成功: test_id=%s, user_id=%s, group=%s, model_id=%s",
                            test_id, user_id, group['name'], group['model_id'])
                return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            log_audit(
                action=AuditAction.AB_TEST_ERROR.value,
                user_id=user_id,
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
            logger.error("A/B测试分配失败: test_id=%s, user_id=%s, 错误=%s", test_id, user_id, e)
            raise

    def _assign_group(self, groups: List[Dict], user_id: str, strategy: str) -> Dict:
        return TrafficSplitter.split(groups, strategy, user_id)

    def _cache_assignment(self, key: str, value: Dict, ttl: int = 3600):
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception as e:
                logger.debug("A/B测试分配缓存失败: %s, 错误=%s", key, e)

    def record_result(
            self,
            test_id: str,
            user_id: str,
            metrics: Dict[str, Any],
            ip_address: Optional[str] = None
    ):
        request_id = context.get_request_id()
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

        try:
            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
                if not test:
                    raise ABTestException(f"测试不存在: {test_id}")

                if not test.results:
                    test.results = {}

                if user_id not in test.results:
                    test.results[user_id] = []

                test.results[user_id].append({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'metrics': metrics
                })

                session.commit()

                log_audit(
                    action=AuditAction.AB_TEST_RECORD.value,
                    user_id=user_id,
                    ip_address=ip_address,
                    resource_type="ab_test",
                    resource_id=test_id,
                    details={
                        "metrics": metrics,
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    },
                    request_id=request_id
                )

                logger.debug("A/B测试结果记录成功: test_id=%s, user_id=%s", test_id, user_id)

        except Exception as e:
            log_audit(
                action=AuditAction.AB_TEST_ERROR.value,
                user_id=user_id,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                },
                reason=str(e),
                request_id=request_id
            )
            logger.error("A/B测试结果记录失败: test_id=%s, user_id=%s, 错误=%s", test_id, user_id, e)
            raise

    def analyze_results(self, test_id: str) -> Dict[str, Any]:
        span_id = context.get_span_id()
        parent_span_id = context.get_parent_span_id()

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

                for user_id, records in test.results.items():
                    assignment = session.query(ABTestAssignment).filter_by(
                        test_id=test_id,
                        user_id=user_id
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

                result = {
                    'test_id': test_id,
                    'test_name': test.test_name,
                    'status': test.status,
                    'strategy': test.assignment_strategy,
                    'groups': group_results,
                    'winning_group': winning_group,
                    'total_users': len(test.results)
                }

                log_audit(
                    action=AuditAction.AB_TEST_COMPLETE.value,
                    user_id="system",
                    resource_type="ab_test",
                    resource_id=test_id,
                    details={
                        "winning_group": winning_group,
                        "total_users": len(test.results),
                        "span_id": span_id,
                        "parent_span_id": parent_span_id
                    }
                )

                logger.info("A/B测试结果分析完成: test_id=%s, 名称=%s, 总用户数=%d, 获胜组=%s",
                           test_id, test.test_name, len(test.results), winning_group)

                return result

        except Exception as e:
            log_audit(
                action=AuditAction.AB_TEST_COMPLETE.value,
                user_id="system",
                resource_type="ab_test",
                resource_id=test_id,
                details={
                    "error": str(e),
                    "span_id": span_id,
                    "parent_span_id": parent_span_id
                }
            )
            logger.error("A/B测试结果分析失败: test_id=%s, 错误=%s", test_id, e)
            raise

    def _determine_winner(self, group_results: Dict, criteria: Optional[Dict]) -> Optional[str]:
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
        return self._stats.copy()


# 全局A/B测试管理器实例
ab_test_manager = ABTestManager()