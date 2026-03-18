# Datamind/datamind/core/experiment/ab_test.py

import json
import random
import redis
import hashlib
from time import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from enum import Enum

from datamind.core.db.database import get_db
from datamind.core.db.models import ABTestConfig, ABTestAssignment, ModelMetadata
from datamind.core.domain.enums import ABTestStatus, AuditAction
from datamind.core.logging import log_manager, get_request_id, debug_print
from datamind.core.ml.exceptions import ABTestException
from datamind.config import get_settings


class AssignmentStrategy(str, Enum):
    """分配策略枚举

    定义A/B测试的用户分配策略类型

    属性:
        RANDOM: 随机分配 - 每次请求随机分配
        CONSISTENT: 一致性分配 - 同一用户始终分配到同一组
        BUCKET: 分桶分配 - 基于用户ID的哈希值分桶
        ROUND_ROBIN: 轮询分配 - 按顺序循环分配
        WEIGHTED: 加权分配 - 基于权重的随机分配
    """
    RANDOM = "random"
    CONSISTENT = "consistent"
    BUCKET = "bucket"
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"

    @classmethod
    def get_all(cls) -> List[str]:
        """获取所有策略名称"""
        return [item.value for item in cls]

    @classmethod
    def is_valid(cls, strategy: str) -> bool:
        """检查策略是否有效"""
        return strategy in cls.get_all()

    @classmethod
    def get_default(cls) -> str:
        """获取默认策略"""
        return cls.RANDOM.value

    @classmethod
    def get_description(cls, strategy: str) -> str:
        """获取策略描述"""
        descriptions = {
            cls.RANDOM.value: "每次请求随机分配，适用于无状态测试",
            cls.CONSISTENT.value: "同一用户始终分配到同一组，保证用户体验一致性",
            cls.BUCKET.value: "基于用户ID的哈希值分桶，适合大规模分流",
            cls.ROUND_ROBIN.value: "按顺序循环分配，适合均匀流量分配",
            cls.WEIGHTED.value: "基于权重的随机分配，可精细控制各组流量比例",
        }
        return descriptions.get(strategy, "未知策略")


class TrafficSplitter:
    """流量分割器

    负责根据不同的策略将用户流量分配到不同的测试组

    此类提供静态方法，也可实例化使用
    """

    def __init__(self, strategy: str = None):
        """
        初始化流量分割器

        参数:
            strategy: 分配策略，如果为None则使用默认策略
        """
        self.strategy = strategy or AssignmentStrategy.get_default()
        self._stats = {
            'total_splits': 0,
            'strategy_usage': {}
        }

    @staticmethod
    def split_random(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        随机分配 - 每次随机选择一个组

        参数:
            groups: 测试组列表，每个组包含 name, weight, model_id 等字段

        返回:
            选中的组
        """
        weights = [g.get('weight', 0) for g in groups]
        # 确保权重总和为100
        total = sum(weights)
        if abs(total - 100) > 0.01:
            # 归一化处理
            weights = [w / total * 100 for w in weights]

        return random.choices(groups, weights=weights)[0]

    @staticmethod
    def split_consistent(groups: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """
        一致性分配 - 同一用户始终分配到同一组

        参数:
            groups: 测试组列表
            user_id: 用户ID

        返回:
            选中的组
        """
        # 使用用户ID的MD5哈希值进行一致性分配
        hash_val = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16) % 100

        cumulative = 0
        for group in groups:
            cumulative += group.get('weight', 0)
            if hash_val < cumulative:
                return group
        return groups[-1]

    @staticmethod
    def split_bucket(groups: List[Dict[str, Any]], user_id: str, bucket_count: int = 1000) -> Dict[str, Any]:
        """
        分桶分配 - 基于用户ID的哈希值分桶

        参数:
            groups: 测试组列表
            user_id: 用户ID
            bucket_count: 总桶数

        返回:
            选中的组
        """
        # 计算用户所属的桶
        bucket = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16) % bucket_count

        # 将桶映射到组
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
        轮询分配 - 按顺序循环分配

        参数:
            groups: 测试组列表
            counter: 计数器，如果不提供则随机选择起始点

        返回:
            选中的组
        """
        if counter is None:
            counter = random.randint(0, len(groups) - 1)

        # 根据权重调整轮询
        weighted_groups = []
        for group in groups:
            weight = group.get('weight', 0)
            # 按权重复制组
            weighted_groups.extend([group] * int(weight))

        if weighted_groups:
            return weighted_groups[counter % len(weighted_groups)]
        return groups[0]

    @staticmethod
    def split_weighted(groups: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        加权分配 - 基于权重的随机分配（与random类似但更强调权重）

        参数:
            groups: 测试组列表

        返回:
            选中的组
        """
        weights = [g.get('weight', 0) for g in groups]
        return random.choices(groups, weights=weights)[0]

    @classmethod
    def split(cls, groups: List[Dict[str, Any]], strategy: str, user_id: str = None, **kwargs) -> Dict[str, Any]:
        """
        通用分配方法 - 根据策略自动选择分配方式

        参数:
            groups: 测试组列表
            strategy: 分配策略
            user_id: 用户ID（用于需要用户ID的策略）
            **kwargs: 其他参数

        返回:
            选中的组

        抛出:
            ValueError: 不支持的策略
        """
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
        """
        带统计的分配方法

        参数:
            groups: 测试组列表
            user_id: 用户ID
            **kwargs: 其他参数

        返回:
            选中的组
        """
        result = self.split(groups, self.strategy, user_id, **kwargs)

        # 更新统计
        self._stats['total_splits'] += 1
        strategy_key = self.strategy
        if strategy_key not in self._stats['strategy_usage']:
            self._stats['strategy_usage'][strategy_key] = 0
        self._stats['strategy_usage'][strategy_key] += 1

        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._stats.copy()

    def reset_stats(self):
        """重置统计信息"""
        self._stats = {
            'total_splits': 0,
            'strategy_usage': {}
        }


class ABTestManager:
    """A/B测试管理器"""

    def __init__(self):
        settings = get_settings()

        ab_test_config = settings.ab_test
        redis_config = settings.redis

        self.enabled = ab_test_config.enabled
        self.redis_key_prefix = ab_test_config.redis_key_prefix
        self.assignment_expiry = ab_test_config.assignment_expiry

        # Redis配置
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

        # 使用 TrafficSplitter
        self.splitter = TrafficSplitter()

        debug_print("ABTestManager", "初始化A/B测试管理器")

    def _init_redis(self):
        """初始化Redis连接"""
        try:
            if self.redis_url:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    password=self.redis_password,
                    max_connections=self.redis_max_connections,
                    socket_timeout=self.redis_socket_timeout,
                    decode_responses=True
                )
                debug_print("ABTestManager", "Redis连接成功")
        except Exception as e:
            debug_print("ABTestManager", f"Redis连接失败: {e}")
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
        """
        创建A/B测试

        参数:
            test_name: 测试名称
            task_type: 任务类型
            groups: 测试组配置 [{"name": "A", "weight": 50, "model_id": "xxx"}, ...]
            created_by: 创建人
            description: 描述
            traffic_allocation: 流量分配百分比
            assignment_strategy: 分配策略
            start_date: 开始时间
            end_date: 结束时间
            metrics: 监控指标
            winning_criteria: 获胜标准
            ip_address: IP地址

        返回:
            test_id: 测试ID
        """
        request_id = get_request_id()
        start_time = datetime.now()

        try:
            # 验证策略是否有效
            if not AssignmentStrategy.is_valid(assignment_strategy):
                raise ABTestException(f"无效的分配策略: {assignment_strategy}")

            # 验证组配置
            self._validate_groups(groups)

            # 生成测试ID
            test_id = f"ABT_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}"

            # 设置默认时间
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

            log_manager.log_audit(
                action=AuditAction.CREATE.value,
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
                    "duration_ms": round(duration, 2)
                },
                request_id=request_id
            )

            debug_print("ABTestManager", f"创建A/B测试成功: {test_id}")
            return test_id

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_manager.log_audit(
                action=AuditAction.CREATE.value,
                user_id=created_by,
                ip_address=ip_address,
                resource_type="ab_test",
                details={
                    "test_name": test_name,
                    "error": str(e),
                    "duration_ms": round(duration, 2)
                },
                reason=str(e),
                request_id=request_id
            )
            raise

    def _validate_groups(self, groups: List[Dict[str, Any]]):
        """验证测试组配置"""
        if not groups:
            raise ABTestException("测试组不能为空")

        total_weight = sum(g.get('weight', 0) for g in groups)
        if abs(total_weight - 100) > 0.01:
            raise ABTestException(f"组权重总和必须为100，当前: {total_weight}")

        # 验证模型ID是否存在
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
        """启动A/B测试"""
        request_id = get_request_id()
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

            log_manager.log_audit(
                action=AuditAction.ACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                resource_name=test.test_name,
                details={"duration_ms": round(duration, 2)},
                request_id=request_id
            )

            debug_print("ABTestManager", f"启动A/B测试成功: {test_id}")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds() * 1000
            log_manager.log_audit(
                action=AuditAction.ACTIVATE.value,
                user_id=operator,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={"error": str(e), "duration_ms": round(duration, 2)},
                reason=str(e),
                request_id=request_id
            )
            raise

    def get_assignment(
            self,
            test_id: str,
            user_id: str,
            ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        获取用户的分组分配

        参数:
            test_id: 测试ID
            user_id: 用户ID
            ip_address: IP地址

        返回:
            Dict: {
                'test_id': str,
                'user_id': str,
                'group_name': str,
                'model_id': str,
                'assigned_at': str
            }
        """
        request_id = get_request_id()
        start_time = time.time()

        try:
            # 检查缓存
            cache_key = f"{self.redis_key_prefix}{test_id}:{user_id}"
            if self.redis_client:
                cached = self.redis_client.get(cache_key)
                if cached:
                    self._stats['cache_hits'] += 1
                    debug_print("ABTestManager", f"缓存命中: {cache_key}")
                    return json.loads(cached)

            self._stats['cache_misses'] += 1

            with get_db() as session:
                # 获取测试配置
                test = session.query(ABTestConfig).filter_by(
                    test_id=test_id,
                    status=ABTestStatus.RUNNING.value
                ).first()

                if not test:
                    raise ABTestException(f"测试不存在或未运行: {test_id}")

                # 检查是否在有效期内
                now = datetime.now()
                if now < test.start_date or (test.end_date and now > test.end_date):
                    raise ABTestException("测试不在有效期内")

                # 检查流量分配
                if random.random() * 100 > test.traffic_allocation:
                    # 不在测试流量内，返回默认组
                    return {
                        'test_id': test_id,
                        'user_id': user_id,
                        'group_name': 'default',
                        'model_id': None,
                        'assigned_at': now.isoformat(),
                        'in_test': False
                    }

                # 检查是否已有分配
                existing = session.query(ABTestAssignment).filter_by(
                    test_id=test_id,
                    user_id=user_id
                ).first()

                if existing:
                    # 检查是否过期
                    if existing.expires_at and now > existing.expires_at:
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

                # 使用 TrafficSplitter 分配新组
                group = TrafficSplitter.split(
                    groups=test.groups,
                    strategy=test.assignment_strategy,
                    user_id=user_id
                )

                # 保存分配
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
                log_manager.log_audit(
                    action="AB_TEST_ASSIGN",
                    user_id=user_id,
                    ip_address=ip_address,
                    resource_type="ab_test",
                    resource_id=test_id,
                    details={
                        "group_name": group['name'],
                        "model_id": group['model_id'],
                        "strategy": test.assignment_strategy,
                        "duration_ms": round(duration, 2)
                    },
                    request_id=request_id
                )

                debug_print("ABTestManager", f"分配成功: {test_id} -> {group['name']}")
                return result

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            log_manager.log_audit(
                action="AB_TEST_ASSIGN",
                user_id=user_id,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={"error": str(e), "duration_ms": round(duration, 2)},
                reason=str(e),
                request_id=request_id
            )
            raise

    def _assign_group(self, groups: List[Dict], user_id: str, strategy: str) -> Dict:
        """分配测试组（保留原方法以保持兼容性）"""
        return TrafficSplitter.split(groups, strategy, user_id)

    def _cache_assignment(self, key: str, value: Dict, ttl: int = 3600):
        """缓存分配结果"""
        if self.redis_client:
            try:
                self.redis_client.setex(
                    key,
                    ttl,
                    json.dumps(value, default=str)
                )
            except Exception as e:
                debug_print("ABTestManager", f"缓存失败: {e}")

    def record_result(
            self,
            test_id: str,
            user_id: str,
            metrics: Dict[str, Any],
            ip_address: Optional[str] = None
    ):
        """记录测试结果"""
        request_id = get_request_id()

        try:
            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
                if not test:
                    raise ABTestException(f"测试不存在: {test_id}")

                # 更新测试结果
                if not test.results:
                    test.results = {}

                if user_id not in test.results:
                    test.results[user_id] = []

                test.results[user_id].append({
                    'timestamp': datetime.now().isoformat(),
                    'metrics': metrics
                })

                session.commit()

                log_manager.log_audit(
                    action="AB_TEST_RECORD",
                    user_id=user_id,
                    ip_address=ip_address,
                    resource_type="ab_test",
                    resource_id=test_id,
                    details={"metrics": metrics},
                    request_id=request_id
                )

        except Exception as e:
            log_manager.log_audit(
                action="AB_TEST_RECORD",
                user_id=user_id,
                ip_address=ip_address,
                resource_type="ab_test",
                resource_id=test_id,
                details={"error": str(e)},
                reason=str(e),
                request_id=request_id
            )
            raise

    def analyze_results(self, test_id: str) -> Dict[str, Any]:
        """分析测试结果"""
        try:
            with get_db() as session:
                test = session.query(ABTestConfig).filter_by(test_id=test_id).first()
                if not test:
                    raise ABTestException(f"测试不存在: {test_id}")

                if not test.results:
                    return {"status": "no_data"}

                # 按组分批结果
                group_results = {}
                for group in test.groups:
                    group_name = group['name']
                    group_results[group_name] = {
                        'count': 0,
                        'metrics': {}
                    }

                # 聚合结果
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

                # 计算统计
                for group_name, group in group_results.items():
                    for metric, values in group['metrics'].items():
                        if values:
                            group['metrics'][metric] = {
                                'avg': sum(values) / len(values),
                                'min': min(values),
                                'max': max(values),
                                'count': len(values)
                            }

                # 判断获胜组
                winning_group = self._determine_winner(group_results, test.winning_criteria)

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
            log_manager.log_audit(
                action="AB_TEST_ANALYZE",
                user_id="system",
                resource_type="ab_test",
                resource_id=test_id,
                details={"error": str(e)}
            )
            raise

    def _determine_winner(self, group_results: Dict, criteria: Optional[Dict]) -> Optional[str]:
        """判断获胜组"""
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
        """获取统计信息"""
        return self._stats.copy()


# 全局A/B测试管理器实例
ab_test_manager = ABTestManager()