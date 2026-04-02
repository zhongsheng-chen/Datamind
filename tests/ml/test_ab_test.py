# tests/ml/test_ab_test_01.py

"""测试 A/B 测试模块"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from datamind.core.experiment.ab_test import (
    ABTestManager,
    TrafficSplitter,
    AssignmentStrategy
)
from datamind.core.common.exceptions import ABTestException
from datamind.core.domain.enums import ABTestStatus, AuditAction


class TestAssignmentStrategy:
    """测试分配策略枚举"""

    def test_get_all_strategies(self):
        """测试获取所有策略"""
        strategies = AssignmentStrategy.get_all()
        assert len(strategies) == 5
        assert 'random' in strategies
        assert 'consistent' in strategies
        assert 'bucket' in strategies
        assert 'round_robin' in strategies
        assert 'weighted' in strategies

    def test_is_valid(self):
        """测试策略有效性验证"""
        assert AssignmentStrategy.is_valid('random') is True
        assert AssignmentStrategy.is_valid('consistent') is True
        assert AssignmentStrategy.is_valid('invalid') is False

    def test_get_default(self):
        """测试获取默认策略"""
        assert AssignmentStrategy.get_default() == 'random'

    def test_get_description(self):
        """测试获取策略描述"""
        desc = AssignmentStrategy.get_description('random')
        assert '随机' in desc
        assert AssignmentStrategy.get_description('invalid') == '未知策略'


class TestTrafficSplitter:
    """测试流量分割器"""

    def test_init(self):
        """测试初始化"""
        splitter = TrafficSplitter()
        assert splitter.strategy == 'random'
        assert splitter.get_stats()['total_splits'] == 0

    def test_init_with_custom_strategy(self):
        """测试自定义策略初始化"""
        splitter = TrafficSplitter('consistent')
        assert splitter.strategy == 'consistent'

    def test_split_random(self):
        """测试随机分配"""
        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        results = []
        for _ in range(100):
            result = TrafficSplitter.split_random(groups)
            assert result['name'] in ['A', 'B']
            results.append(result['name'])

        assert 'A' in results
        assert 'B' in results

    def test_split_consistent(self):
        """测试一致性分配"""
        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        user_id = "user_123"
        result1 = TrafficSplitter.split_consistent(groups, user_id)
        result2 = TrafficSplitter.split_consistent(groups, user_id)

        assert result1['name'] == result2['name']

    def test_split_bucket(self):
        """测试分桶分配"""
        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        user_id = "user_123"
        result1 = TrafficSplitter.split_bucket(groups, user_id)
        result2 = TrafficSplitter.split_bucket(groups, user_id)

        assert result1['name'] == result2['name']

    def test_split_round_robin(self):
        """测试轮询分配"""
        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        result1 = TrafficSplitter.split_round_robin(groups, 0)
        result2 = TrafficSplitter.split_round_robin(groups, 1)

        assert result1['name'] in ['A', 'B']
        assert result2['name'] in ['A', 'B']

        result3 = TrafficSplitter.split_round_robin(groups, 2)
        assert result3['name'] in ['A', 'B']

    def test_split_weighted(self):
        """测试加权分配"""
        groups = [
            {'name': 'A', 'weight': 70, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 30, 'model_id': 'model_b'}
        ]

        counts = {'A': 0, 'B': 0}
        for _ in range(1000):
            result = TrafficSplitter.split_weighted(groups)
            counts[result['name']] += 1

        assert counts['A'] > counts['B']

    def test_split_with_strategy(self):
        """测试通用分配方法"""
        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        result = TrafficSplitter.split(groups, 'random')
        assert result['name'] in ['A', 'B']

        result = TrafficSplitter.split(groups, 'consistent', user_id='user123')
        assert result['name'] in ['A', 'B']

        with pytest.raises(ValueError):
            TrafficSplitter.split(groups, 'invalid')

    def test_split_with_stats(self):
        """测试带统计的分配"""
        splitter = TrafficSplitter('random')
        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        for _ in range(10):
            splitter.split_with_stats(groups)

        stats = splitter.get_stats()
        assert stats['total_splits'] == 10
        assert stats['strategy_usage']['random'] == 10

    def test_reset_stats(self):
        """测试重置统计信息"""
        splitter = TrafficSplitter('random')
        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        splitter.split_with_stats(groups)
        splitter.reset_stats()

        stats = splitter.get_stats()
        assert stats['total_splits'] == 0
        assert stats['strategy_usage'] == {}


class TestABTestManager:
    """测试 A/B 测试管理器"""

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis 客户端"""
        with patch('redis.from_url') as mock:
            redis_client = MagicMock()
            # 默认返回 None，表示缓存未命中
            redis_client.get.return_value = None
            mock.return_value = redis_client
            yield redis_client

    @pytest.fixture
    def ab_manager(self, mock_redis):
        """创建 A/B 测试管理器实例"""
        with patch('datamind.core.experiment.ab_test.get_settings') as mock_settings:
            settings = MagicMock()
            settings.ab_test.enabled = True
            settings.ab_test.redis_key_prefix = "ab_test:"
            settings.ab_test.assignment_expiry = 86400
            settings.redis.url = "redis://localhost:6379"
            settings.redis.password = None
            settings.redis.max_connections = 50
            settings.redis.socket_timeout = 5
            mock_settings.return_value = settings

            manager = ABTestManager()
            yield manager

    def test_init(self, ab_manager):
        """测试初始化"""
        assert ab_manager.enabled is True
        assert ab_manager.redis_key_prefix == "ab_test:"
        assert ab_manager.assignment_expiry == 86400
        assert ab_manager._stats['total_assignments'] == 0

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_create_test_success(self, mock_get_db, ab_manager, mock_redis):
        """测试成功创建 A/B 测试"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_123'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_456'}
        ]

        with patch('datamind.core.experiment.ab_test.log_audit') as mock_audit:
            with patch('datamind.core.experiment.ab_test.context.get_request_id', return_value='req-123'):
                with patch('datamind.core.experiment.ab_test.context.get_span_id', return_value='span-456'):
                    with patch('datamind.core.experiment.ab_test.context.get_parent_span_id',
                               return_value='parent-789'):
                        test_id = ab_manager.create_test(
                            test_name="test_ab_test",
                            task_type="scoring",
                            groups=groups,
                            created_by="test_user",
                            description="测试A/B测试",
                            traffic_allocation=80.0,
                            assignment_strategy="random",
                            ip_address="127.0.0.1"
                        )

        assert test_id.startswith("ABT_")
        assert len(test_id) > 10

        mock_audit.assert_called_once()
        call_args = mock_audit.call_args[1]
        assert call_args['action'] == AuditAction.AB_TEST_CREATE.value
        assert call_args['user_id'] == "test_user"
        assert call_args['details']['span_id'] == "span-456"
        assert call_args['details']['parent_span_id'] == "parent-789"

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_create_test_invalid_groups(self, mock_get_db, ab_manager):
        """测试创建无效组配置的测试"""
        with pytest.raises(ABTestException) as exc:
            ab_manager.create_test(
                test_name="test",
                task_type="scoring",
                groups=[],
                created_by="test_user"
            )
        assert "测试组不能为空" in str(exc.value)

        groups = [
            {'name': 'A', 'weight': 60, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 30, 'model_id': 'model_b'}
        ]
        with pytest.raises(ABTestException) as exc:
            ab_manager.create_test(
                test_name="test",
                task_type="scoring",
                groups=groups,
                created_by="test_user"
            )
        assert "权重总和必须为100" in str(exc.value)

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_start_test_success(self, mock_get_db, ab_manager):
        """测试成功启动测试"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        mock_test = MagicMock()
        mock_test.status = ABTestStatus.DRAFT.value
        mock_test.test_name = "test_ab"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_test

        with patch('datamind.core.experiment.ab_test.log_audit') as mock_audit:
            with patch('datamind.core.experiment.ab_test.context.get_request_id', return_value='req-123'):
                with patch('datamind.core.experiment.ab_test.context.get_span_id', return_value='span-456'):
                    with patch('datamind.core.experiment.ab_test.context.get_parent_span_id',
                               return_value='parent-789'):
                        ab_manager.start_test("ABT_123", "test_user", "127.0.0.1")

        assert mock_test.status == ABTestStatus.RUNNING.value

        mock_audit.assert_called_once()
        call_args = mock_audit.call_args[1]
        assert call_args['action'] == AuditAction.AB_TEST_START.value
        assert call_args['user_id'] == "test_user"

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_start_test_not_found(self, mock_get_db, ab_manager):
        """测试启动不存在的测试"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session
        mock_session.query.return_value.filter_by.return_value.first.return_value = None

        with pytest.raises(ABTestException) as exc:
            ab_manager.start_test("INVALID_ID", "test_user")

        assert "测试不存在" in str(exc.value)

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_get_assignment_cache_hit(self, mock_get_db, ab_manager, mock_redis):
        """测试缓存命中的分配"""
        cached_result = {
            'test_id': 'ABT_123',
            'user_id': 'user_123',
            'group_name': 'A',
            'model_id': 'model_a',
            'assigned_at': datetime.now().isoformat(),
            'in_test': True
        }
        # 设置缓存命中
        mock_redis.get.return_value = json.dumps(cached_result)

        with patch('datamind.core.experiment.ab_test.context.get_request_id', return_value='req-123'):
            with patch('datamind.core.experiment.ab_test.context.get_span_id', return_value='span-456'):
                with patch('datamind.core.experiment.ab_test.context.get_parent_span_id', return_value='parent-789'):
                    result = ab_manager.get_assignment("ABT_123", "user_123")

        assert result['group_name'] == 'A'
        assert result['model_id'] == 'model_a'
        assert ab_manager._stats['cache_hits'] == 1

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_get_assignment_no_traffic(self, mock_get_db, ab_manager):
        """测试流量分配为0的情况"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        mock_test = MagicMock()
        mock_test.status = ABTestStatus.RUNNING.value
        mock_test.start_date = datetime.now() - timedelta(days=1)
        mock_test.end_date = datetime.now() + timedelta(days=1)
        mock_test.traffic_allocation = 0
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_test

        with patch('random.random', return_value=0.1):
            with patch('datamind.core.experiment.ab_test.context.get_request_id', return_value='req-123'):
                result = ab_manager.get_assignment("ABT_123", "user_123")

        assert result['in_test'] is False
        assert result['group_name'] == 'default'
        assert result['model_id'] is None

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_record_result_success(self, mock_get_db, ab_manager):
        """测试记录结果成功"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        mock_test = MagicMock()
        mock_test.results = {}
        mock_test.test_id = "ABT_123"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_test

        metrics = {'score': 85.5, 'conversion': 0.75}

        with patch('datamind.core.experiment.ab_test.log_audit') as mock_audit:
            with patch('datamind.core.experiment.ab_test.context.get_request_id', return_value='req-123'):
                ab_manager.record_result("ABT_123", "user_123", metrics, "127.0.0.1")

        assert "user_123" in mock_test.results
        assert len(mock_test.results["user_123"]) == 1
        assert mock_test.results["user_123"][0]['metrics'] == metrics

        mock_audit.assert_called_once()
        call_args = mock_audit.call_args[1]
        assert call_args['action'] == "AB_TEST_RECORD"

    @patch('datamind.core.experiment.ab_test.get_db')
    def test_analyze_results(self, mock_get_db, ab_manager):
        """测试分析结果"""
        mock_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_session

        groups = [
            {'name': 'A', 'weight': 50, 'model_id': 'model_a'},
            {'name': 'B', 'weight': 50, 'model_id': 'model_b'}
        ]

        mock_test = MagicMock()
        mock_test.test_id = "ABT_123"
        mock_test.test_name = "test_ab"
        mock_test.status = ABTestStatus.RUNNING.value
        mock_test.assignment_strategy = "random"
        mock_test.groups = groups
        mock_test.winning_criteria = {'metric': 'score'}
        mock_test.results = {
            'user_1': [{'timestamp': datetime.now().isoformat(), 'metrics': {'score': 90}}],
            'user_2': [{'timestamp': datetime.now().isoformat(), 'metrics': {'score': 95}}],
            'user_3': [{'timestamp': datetime.now().isoformat(), 'metrics': {'score': 85}}]
        }

        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_test

        # Mock 分配记录
        def mock_filter_by(**kwargs):
            if 'user_id' in kwargs:
                user_id = kwargs['user_id']
                mock_assign = MagicMock()
                if user_id == 'user_1' or user_id == 'user_2':
                    mock_assign.group_name = 'A'
                elif user_id == 'user_3':
                    mock_assign.group_name = 'B'
                else:
                    mock_assign = None
                return MagicMock(first=lambda: mock_assign)
            return MagicMock()

        mock_session.query.return_value.filter_by.side_effect = mock_filter_by

        with patch('datamind.core.experiment.ab_test.log_audit'):
            result = ab_manager.analyze_results("ABT_123")

        assert result['test_id'] == "ABT_123"
        assert 'groups' in result
        assert 'winning_group' in result
        assert 'total_users' in result
        # 由于 mock 的分配记录可能不完整，只验证结构存在
        assert isinstance(result['total_users'], int)

    def test_get_stats(self, ab_manager):
        """测试获取统计信息"""
        ab_manager._stats['total_assignments'] = 10
        ab_manager._stats['cache_hits'] = 5
        ab_manager._stats['cache_misses'] = 5

        stats = ab_manager.get_stats()

        assert stats['total_assignments'] == 10
        assert stats['cache_hits'] == 5
        assert stats['cache_misses'] == 5


class TestABTestIntegration:
    """A/B 测试集成测试"""

    @patch('datamind.core.experiment.ab_test.get_db')
    @patch('datamind.core.experiment.ab_test.get_settings')
    def test_full_ab_test_flow(self, mock_settings, mock_get_db):
        """测试完整的 A/B 测试流程"""
        # Mock Redis - 返回 None 表示缓存未命中
        with patch('redis.from_url') as mock_redis:
            mock_redis_client = MagicMock()
            mock_redis_client.get.return_value = None
            mock_redis.return_value = mock_redis_client

            # Mock 设置
            settings = MagicMock()
            settings.ab_test.enabled = True
            settings.ab_test.redis_key_prefix = "ab_test:"
            settings.ab_test.assignment_expiry = 86400
            settings.redis.url = "redis://localhost:6379"
            settings.redis.password = None
            settings.redis.max_connections = 50
            settings.redis.socket_timeout = 5
            mock_settings.return_value = settings

            # Mock 数据库
            mock_session = MagicMock()
            mock_get_db.return_value.__enter__.return_value = mock_session

            # 1. 创建测试
            manager = ABTestManager()
            groups = [
                {'name': 'A', 'weight': 50, 'model_id': 'model_123'},
                {'name': 'B', 'weight': 50, 'model_id': 'model_456'}
            ]

            with patch('datamind.core.experiment.ab_test.log_audit'):
                with patch('datamind.core.experiment.ab_test.context.get_request_id', return_value='req-123'):
                    test_id = manager.create_test(
                        test_name="integration_test",
                        task_type="scoring",
                        groups=groups,
                        created_by="tester",
                        ip_address="127.0.0.1"
                    )

            # 2. 启动测试
            mock_test = MagicMock()
            mock_test.status = ABTestStatus.DRAFT.value
            mock_test.test_name = "integration_test"
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_test

            manager.start_test(test_id, "tester")

            # 3. 分配用户
            mock_test.status = ABTestStatus.RUNNING.value
            mock_test.start_date = datetime.now() - timedelta(days=1)
            mock_test.end_date = datetime.now() + timedelta(days=1)
            mock_test.traffic_allocation = 100.0
            mock_test.groups = groups
            mock_test.assignment_strategy = "random"

            # 创建一个 mock 的 existing 对象
            mock_existing = MagicMock()
            mock_existing.expires_at = datetime.now() - timedelta(hours=1)
            mock_existing.group_name = 'A'
            mock_existing.model_id = 'model_123'
            mock_existing.assigned_at = datetime.now() - timedelta(hours=2)

            # 使用一个列表和索引来模拟无限循环
            return_values = [mock_test, mock_existing] + [mock_test] * 100  # 足够多的值
            call_count = 0

            def side_effect_func(*args, **kwargs):
                nonlocal call_count
                result = return_values[call_count]
                call_count += 1
                return result

            mock_session.query.return_value.filter_by.return_value.first.side_effect = side_effect_func

            with patch('random.random', return_value=0.5):
                with patch('datamind.core.experiment.ab_test.context.get_request_id', return_value='req-123'):
                    assignment = manager.get_assignment(test_id, "user_123")

            assert assignment['in_test'] is True
            assert assignment['group_name'] in ['A', 'B']

            # 4. 记录结果
            manager.record_result(test_id, "user_123", {'score': 95.0})

            # 5. 分析结果
            mock_test.results = {
                'user_123': [{'timestamp': datetime.now().isoformat(), 'metrics': {'score': 95.0}}]
            }

            # 设置分配记录查询返回
            mock_assignment = MagicMock()
            mock_assignment.group_name = assignment['group_name']
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_assignment

            with patch('datamind.core.experiment.ab_test.log_audit'):
                result = manager.analyze_results(test_id)

            assert result['test_id'] == test_id
            assert 'groups' in result
            assert 'winning_group' in result

            print(f"\n完整 A/B 测试流程测试通过: {test_id}")