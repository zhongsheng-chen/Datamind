# datamind/core/experiment/ab_test.py
import hashlib
import json
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import redis

from time import time
from datamind.core.logging import log_manager, get_request_id, debug_print
from datamind.core.db.database import get_db
from datamind.core.db.models import ABTestConfig, ABTestAssignment, ModelMetadata
from datamind.core.db.enums import ABTestStatus, AuditAction
from datamind.core.ml.exceptions import ABTestException
from datamind.config import settings


class ABTestManager:
    """A/B测试管理器"""

    def __init__(self):
        self.redis_client = None
        self._init_redis()
        self._stats = {
            'total_assignments': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        debug_print("ABTestManager", "初始化A/B测试管理器")

    def _init_redis(self):
        """初始化Redis连接"""
        try:
            if settings.REDIS_URL:
                self.redis_client = redis.from_url(
                    settings.REDIS_URL,
                    password=settings.REDIS_PASSWORD,
                    max_connections=settings.REDIS_MAX_CONNECTIONS,
                    socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
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

        Args:
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

        Returns:
            test_id: 测试ID
        """
        request_id = get_request_id()
        start_time = datetime.now()

        try:
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

        Args:
            test_id: 测试ID
            user_id: 用户ID
            ip_address: IP地址

        Returns:
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
            cache_key = f"{settings.AB_TEST_REDIS_KEY_PREFIX}{test_id}:{user_id}"
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

                # 分配新组
                group = self._assign_group(test.groups, user_id, test.assignment_strategy)

                # 保存分配
                assignment = ABTestAssignment(
                    test_id=test_id,
                    user_id=user_id,
                    group_name=group['name'],
                    model_id=group['model_id'],
                    expires_at=now + timedelta(seconds=settings.AB_TEST_ASSIGNMENT_EXPIRY)
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
        """分配测试组"""
        if strategy == 'random':
            # 随机分配
            rand = random.random() * 100
            cumulative = 0
            for group in groups:
                cumulative += group.get('weight', 0)
                if rand < cumulative:
                    return group
            return groups[-1]

        elif strategy == 'consistent':
            # 一致性哈希
            hash_val = int(hashlib.md5(user_id.encode()).hexdigest()[:8], 16) % 100
            cumulative = 0
            for group in groups:
                cumulative += group.get('weight', 0)
                if hash_val < cumulative:
                    return group
            return groups[-1]

        else:
            raise ABTestException(f"不支持的分配策略: {strategy}")

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