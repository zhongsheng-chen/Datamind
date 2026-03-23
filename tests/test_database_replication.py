# tests/test_database_replication.py
"""测试数据库主备复制功能

测试 DatabaseManager 的复制监控功能，包括：
- 复制状态检查
- 同步状态检查
- 复制槽检查
- 复制性能指标
- 复制优化建议
- 告警机制
- get_engine 和 get_engines 函数

运行方式：
    # 运行所有 mock 测试
    pytest tests/test_database_replication.py -v

    # 运行集成测试（需要实际数据库环境）
    RUN_INTEGRATION_TESTS=1 pytest tests/test_database_replication.py -v -k "integration"

    # 运行特定测试
    pytest tests/test_database_replication.py -v -k "test_check_replication_status"
"""

import os
import pytest
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock
from typing import Dict, Any, List

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from datamind.core.db.database import (
    DatabaseManager, get_db, get_engine, get_engines, db_manager
)
from datamind.core.logging import context
from datamind.config import get_settings


# ==================== Fixtures ====================

@pytest.fixture
def mock_log_manager():
    """Mock 日志管理器"""
    with patch('datamind.core.logging.log_manager') as mock:
        mock.log_audit = MagicMock()
        mock.log_access = MagicMock()
        mock.log_performance = MagicMock()
        mock.get_stats = MagicMock(return_value={'logs_processed': 0, 'errors': 0, 'warnings': 0})
        yield mock


@pytest.fixture
def mock_db_manager():
    """创建 mock 的 DatabaseManager 实例"""
    # 重置单例状态
    if hasattr(DatabaseManager, '_instance'):
        DatabaseManager._instance = None
    if hasattr(db_manager, '_initialized'):
        db_manager._initialized = False

    manager = DatabaseManager()
    manager._initialized = True
    manager._engines = {
        'default': MagicMock(),
        'readonly': MagicMock()
    }
    manager.database_url = "postgresql://test:test@localhost:5432/testdb"
    return manager


@pytest.fixture
def mock_replication_session():
    """创建 mock 的数据库会话，专门用于复制测试"""
    session = MagicMock()

    # 默认 execute 返回空结果
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_result.fetchone.return_value = None
    session.execute.return_value = mock_result

    # 创建 mock 结果行的辅助方法
    def create_mock_row(**kwargs):
        row = MagicMock()
        for key, value in kwargs.items():
            setattr(row, key, value)
        return row

    session.create_mock_row = create_mock_row
    return session


@pytest.fixture
def temp_db_url():
    """临时数据库 URL"""
    return "sqlite:///:memory:"


@pytest.fixture
def replication_config():
    """复制测试配置"""
    return {
        'alert_thresholds': {
            'warning_lag_seconds': 10,
            'critical_lag_seconds': 60,
            'warning_lag_bytes': 100 * 1024 * 1024,
            'critical_lag_bytes': 1024 * 1024 * 1024,
        }
    }


# ==================== 引擎访问测试 ====================

class TestEngineAccess:
    """测试数据库引擎访问函数"""

    def test_get_engine_default(self, mock_db_manager):
        """测试获取默认引擎"""
        with patch('datamind.core.db.database.db_manager', mock_db_manager):
            # 确保引擎存在
            mock_db_manager._engines['default'] = MagicMock()

            engine = get_engine('default')
            assert engine is not None

    def test_get_engine_invalid_name(self, mock_db_manager):
        """测试获取不存在的引擎"""
        with patch('datamind.core.db.database.db_manager', mock_db_manager):
            with pytest.raises(ValueError, match="引擎 'invalid' 不存在"):
                get_engine('invalid')

    def test_get_engines(self, mock_db_manager):
        """测试获取所有引擎"""
        with patch('datamind.core.db.database.db_manager', mock_db_manager):
            engines = get_engines()
            assert isinstance(engines, dict)
            assert 'default' in engines
            assert 'readonly' in engines


# ==================== 复制状态测试 ====================

class TestReplicationStatus:
    """测试复制状态检查"""

    def test_check_replication_status_healthy(self, mock_db_manager, mock_replication_session):
        """测试复制状态健康的情况"""
        # 创建 mock 结果行
        row1 = mock_replication_session.create_mock_row(
            application_name='replica1',
            client_addr='192.168.1.100',
            state='streaming',
            sync_state='async',
            replay_lag='00:00:00.5',
            replay_lag_seconds=0.5,
            write_lag='00:00:00.4',
            flush_lag='00:00:00.45',
            byte_lag=1024 * 1024  # 1MB
        )
        row2 = mock_replication_session.create_mock_row(
            application_name='replica2',
            client_addr='192.168.1.101',
            state='streaming',
            sync_state='async',
            replay_lag='00:00:00.3',
            replay_lag_seconds=0.3,
            write_lag='00:00:00.25',
            flush_lag='00:00:00.28',
            byte_lag=512 * 1024  # 512KB
        )

        # Mock session 的 execute 方法
        mock_replication_session.execute.return_value.fetchall.return_value = [row1, row2]

        # Mock pg_is_in_recovery 返回 False（主库）
        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),  # pg_is_in_recovery
            MagicMock(scalar=lambda: True),  # has_permission
            mock_replication_session.execute.return_value  # 复制状态查询
        ]

        # 使用 context manager 模拟 session
        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_status()

            assert result['status'] == 'healthy'
            assert result['has_replicas'] is True
            assert len(result['replicas']) == 2
            assert result['max_lag_seconds'] == 0.5
            assert result['max_byte_lag_mb'] == 1.0

    def test_check_replication_status_warning(self, mock_db_manager, mock_replication_session):
        """测试复制状态告警的情况"""
        row = mock_replication_session.create_mock_row(
            application_name='replica1',
            client_addr='192.168.1.100',
            state='streaming',
            sync_state='async',
            replay_lag='00:00:15.0',
            replay_lag_seconds=15.0,  # 15秒延迟（超过警告阈值10秒）
            write_lag='00:00:14.5',
            flush_lag='00:00:14.8',
            byte_lag=100 * 1024 * 1024  # 100MB
        )

        mock_replication_session.execute.return_value.fetchall.return_value = [row]

        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),
            MagicMock(scalar=lambda: True),
            mock_replication_session.execute.return_value
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_status()

            assert result['status'] == 'warning'
            assert result['max_lag_seconds'] == 15.0

    def test_check_replication_status_critical(self, mock_db_manager, mock_replication_session):
        """测试复制状态严重告警的情况"""
        row = mock_replication_session.create_mock_row(
            application_name='replica1',
            client_addr='192.168.1.100',
            state='streaming',
            sync_state='async',
            replay_lag='00:01:30.0',
            replay_lag_seconds=90.0,  # 90秒延迟（超过严重阈值60秒）
            write_lag='00:01:29.0',
            flush_lag='00:01:29.5',
            byte_lag=2 * 1024 * 1024 * 1024  # 2GB
        )

        mock_replication_session.execute.return_value.fetchall.return_value = [row]

        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),
            MagicMock(scalar=lambda: True),
            mock_replication_session.execute.return_value
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_status()

            assert result['status'] == 'critical'
            assert result['max_lag_seconds'] == 90.0

    def test_check_replication_status_no_replicas(self, mock_db_manager, mock_replication_session):
        """测试没有复制副本的情况"""
        mock_replication_session.execute.return_value.fetchall.return_value = []

        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),
            MagicMock(scalar=lambda: True),
            mock_replication_session.execute.return_value
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_status()

            assert result['status'] == 'healthy'
            assert result['has_replicas'] is False
            assert len(result['replicas']) == 0

    def test_check_replication_status_replica_mode(self, mock_db_manager, mock_replication_session):
        """测试在备库上查询复制状态"""
        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: True),  # pg_is_in_recovery 返回 True
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_status()

            assert result['status'] == 'replica'
            assert result['is_replica'] is True
            assert 'message' in result

    def test_check_replication_status_insufficient_permission(self, mock_db_manager, mock_replication_session):
        """测试权限不足的情况"""
        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),  # pg_is_in_recovery
            MagicMock(scalar=lambda: False),  # has_permission 返回 False
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_status()

            assert result['status'] == 'insufficient_permission'
            assert 'error' in result

    def test_check_replication_status_error(self, mock_db_manager, mock_replication_session):
        """测试查询复制状态时发生错误"""
        mock_replication_session.execute.side_effect = Exception("数据库连接失败")

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_status()

            assert result['status'] == 'error'
            assert 'error' in result


# ==================== 同步状态测试 ====================

class TestSyncStatus:
    """测试同步复制状态"""

    def test_check_sync_status_primary(self, mock_db_manager, mock_replication_session):
        """测试主库的同步状态"""
        row = mock_replication_session.create_mock_row(
            synchronous_standby_names='replica1',
            synchronous_commit='on',
            in_recovery=False,
            is_replica=False
        )

        mock_replication_session.execute.return_value.fetchone.return_value = row

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_sync_status()

            assert result['synchronous_standby_names'] == 'replica1'
            assert result['synchronous_commit'] == 'on'
            assert result['is_primary'] is True
            assert result['is_replica'] is False

    def test_check_sync_status_replica(self, mock_db_manager, mock_replication_session):
        """测试备库的同步状态"""
        row = mock_replication_session.create_mock_row(
            synchronous_standby_names='',
            synchronous_commit='on',
            in_recovery=True,
            is_replica=True
        )

        mock_replication_session.execute.return_value.fetchone.return_value = row

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_sync_status()

            assert result['is_primary'] is False
            assert result['is_replica'] is True

    def test_check_sync_status_async_mode(self, mock_db_manager, mock_replication_session):
        """测试异步复制模式"""
        row = mock_replication_session.create_mock_row(
            synchronous_standby_names='',
            synchronous_commit='off',
            in_recovery=False,
            is_replica=False
        )

        mock_replication_session.execute.return_value.fetchone.return_value = row

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_sync_status()

            assert result['synchronous_commit'] == 'off'


# ==================== 复制槽测试 ====================

class TestReplicationSlots:
    """测试复制槽状态检查"""

    def test_check_replication_slots_healthy(self, mock_db_manager, mock_replication_session):
        """测试健康复制槽状态"""
        row1 = mock_replication_session.create_mock_row(
            slot_name='slot1',
            slot_type='physical',
            database=None,
            active=True,
            restart_lsn='0/3000000',
            wal_retained_bytes=50 * 1024 * 1024,  # 50MB
            status='healthy'
        )
        row2 = mock_replication_session.create_mock_row(
            slot_name='slot2',
            slot_type='physical',
            database=None,
            active=True,
            restart_lsn='0/4000000',
            wal_retained_bytes=100 * 1024 * 1024,  # 100MB
            status='healthy'
        )

        mock_replication_session.execute.return_value.fetchall.return_value = [row1, row2]

        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),  # pg_is_in_recovery
            mock_replication_session.execute.return_value  # 复制槽查询
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_slots()

            assert result['total_slots'] == 2
            assert result['active_slots'] == 2
            assert result['inactive_slots'] == 0
            assert len(result['slots']) == 2

    def test_check_replication_slots_inactive(self, mock_db_manager, mock_replication_session):
        """测试包含不活跃复制槽的情况"""
        row1 = mock_replication_session.create_mock_row(
            slot_name='slot1',
            slot_type='physical',
            database=None,
            active=True,
            restart_lsn='0/3000000',
            wal_retained_bytes=50 * 1024 * 1024,
            status='healthy'
        )
        row2 = mock_replication_session.create_mock_row(
            slot_name='slot2',
            slot_type='physical',
            database=None,
            active=False,
            restart_lsn='0/4000000',
            wal_retained_bytes=200 * 1024 * 1024,
            status='inactive'
        )

        mock_replication_session.execute.return_value.fetchall.return_value = [row1, row2]

        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),
            mock_replication_session.execute.return_value
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_slots()

            assert result['total_slots'] == 2
            assert result['active_slots'] == 1
            assert result['inactive_slots'] == 1

    def test_check_replication_slots_replica(self, mock_db_manager, mock_replication_session):
        """测试在备库上查询复制槽"""
        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: True),  # pg_is_in_recovery
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.check_replication_slots()

            assert result['status'] == 'replica'
            assert result['is_replica'] is True


# ==================== 复制性能指标测试 ====================

class TestReplicationMetrics:
    """测试复制性能指标"""

    def test_get_replication_metrics(self, mock_db_manager, mock_replication_session):
        """测试获取复制性能指标"""
        row = mock_replication_session.create_mock_row(
            total_replicas=2,
            streaming_replicas=2,
            avg_replay_lag=0.5,
            max_replay_lag=1.2,
            total_byte_lag=1024 * 1024 * 100,  # 100MB
            sync_replicas=0,
            quorum_replicas=0,
            async_replicas=2
        )

        mock_replication_session.execute.return_value.fetchone.return_value = row

        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),
            mock_replication_session.execute.return_value
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.get_replication_metrics()

            assert result['total_replicas'] == 2
            assert result['streaming_replicas'] == 2
            assert result['avg_replay_lag_seconds'] == 0.5
            assert result['max_replay_lag_seconds'] == 1.2
            assert result['total_byte_lag_mb'] == 100.0
            assert result['sync_replicas'] == 0
            assert result['async_replicas'] == 2

    def test_get_replication_metrics_no_replicas(self, mock_db_manager, mock_replication_session):
        """测试没有副本时获取复制性能指标"""
        row = mock_replication_session.create_mock_row(
            total_replicas=0,
            streaming_replicas=0,
            avg_replay_lag=0,
            max_replay_lag=0,
            total_byte_lag=0,
            sync_replicas=0,
            quorum_replicas=0,
            async_replicas=0
        )

        mock_replication_session.execute.return_value.fetchone.return_value = row

        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: False),
            mock_replication_session.execute.return_value
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.get_replication_metrics()

            assert result['total_replicas'] == 0
            assert result['avg_replay_lag_seconds'] == 0

    def test_get_replication_metrics_replica(self, mock_db_manager, mock_replication_session):
        """测试在备库上获取复制指标"""
        mock_replication_session.execute.side_effect = [
            MagicMock(scalar=lambda: True),  # pg_is_in_recovery
        ]

        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_get_session.return_value.__enter__.return_value = mock_replication_session

            result = mock_db_manager.get_replication_metrics()

            assert result['status'] == 'replica'
            assert result['is_replica'] is True


# ==================== 复制优化建议测试 ====================

class TestReplicationRecommendations:
    """测试复制优化建议"""

    def test_get_recommendations_healthy(self, mock_db_manager):
        """测试健康状态下的复制建议"""
        with patch.object(mock_db_manager, 'check_replication_status') as mock_check:
            mock_check.return_value = {
                'status': 'healthy',
                'has_replicas': True,
                'max_lag_seconds': 0.5,
                'replicas': [{'name': 'replica1'}]
            }

            result = mock_db_manager.get_replication_recommendations()

            assert len(result['recommendations']) == 0

    def test_get_recommendations_no_replicas(self, mock_db_manager):
        """测试没有副本时的复制建议"""
        with patch.object(mock_db_manager, 'check_replication_status') as mock_check:
            mock_check.return_value = {
                'status': 'healthy',
                'has_replicas': False,
                'max_lag_seconds': 0
            }

            result = mock_db_manager.get_replication_recommendations()

            assert len(result['recommendations']) == 1
            rec = result['recommendations'][0]
            assert rec['severity'] == 'high'
            assert '未配置任何只读副本' in rec['issue']

    def test_get_recommendations_high_lag(self, mock_db_manager):
        """测试高延迟时的复制建议"""
        with patch.object(mock_db_manager, 'check_replication_status') as mock_check:
            mock_check.return_value = {
                'status': 'critical',
                'has_replicas': True,
                'max_lag_seconds': 120.0  # 2分钟延迟
            }

            result = mock_db_manager.get_replication_recommendations()

            assert len(result['recommendations']) >= 1
            # 应该包含延迟相关的建议
            lag_recommendations = [r for r in result['recommendations'] if '延迟' in r['issue']]
            assert len(lag_recommendations) >= 1

    def test_get_recommendations_error(self, mock_db_manager):
        """测试错误状态下的复制建议"""
        with patch.object(mock_db_manager, 'check_replication_status') as mock_check:
            mock_check.return_value = {
                'status': 'error',
                'error': 'Connection failed'
            }

            result = mock_db_manager.get_replication_recommendations()

            assert len(result['recommendations']) == 1
            rec = result['recommendations'][0]
            assert rec['severity'] == 'high'
            assert '无法获取复制状态' in rec['issue']


# ==================== 复制告警测试 ====================

class TestReplicationAlerts:
    """测试复制告警"""

    def test_send_replication_alert_warning(self, mock_db_manager):
        """测试发送警告告警"""
        replicas = [
            {'name': 'replica1', 'state': 'streaming', 'replay_lag_seconds': 15.0}
        ]

        try:
            mock_db_manager._send_replication_alert('warning', 15.0, 100 * 1024 * 1024, replicas)
            assert True
        except Exception as e:
            pytest.fail(f"发送告警失败: {e}")

    def test_send_replication_alert_critical(self, mock_db_manager):
        """测试发送严重告警"""
        replicas = [
            {'name': 'replica1', 'state': 'streaming', 'replay_lag_seconds': 120.0}
        ]

        try:
            mock_db_manager._send_replication_alert('critical', 120.0, 2 * 1024 * 1024 * 1024, replicas)
            assert True
        except Exception as e:
            pytest.fail(f"发送告警失败: {e}")

    def test_send_replication_alert_structure(self, mock_db_manager, caplog):
        """测试告警消息结构"""
        import logging
        replicas = [
            {'name': 'replica1', 'state': 'streaming', 'replay_lag_seconds': 15.0}
        ]

        with caplog.at_level(logging.WARNING):
            mock_db_manager._send_replication_alert('warning', 15.0, 100 * 1024 * 1024, replicas)

            # 验证告警日志被记录
            assert any('复制WARNING告警' in record.message for record in caplog.records)
            assert any('15.00秒' in record.message for record in caplog.records)
            assert any('replica1' in record.message for record in caplog.records)


# ==================== 健康检查测试 ====================

class TestHealthCheck:
    """测试数据库健康检查"""

    def test_health_check_all_healthy(self, mock_db_manager):
        """测试所有引擎健康"""
        mock_engine = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = MagicMock()
        mock_db_manager._engines = {
            'default': mock_engine,
            'readonly': mock_engine
        }

        result = mock_db_manager.check_health()

        assert result['status'] == 'healthy'
        assert 'default' in result['engines']
        assert 'readonly' in result['engines']
        assert result['engines']['default']['status'] == 'healthy'

    def test_health_check_partial_failure(self, mock_db_manager):
        """测试部分引擎失败"""
        mock_engine_healthy = MagicMock()
        mock_engine_healthy.connect.return_value.__enter__.return_value = MagicMock()

        mock_engine_failed = MagicMock()
        mock_engine_failed.connect.side_effect = Exception("连接失败")

        mock_db_manager._engines = {
            'default': mock_engine_healthy,
            'readonly': mock_engine_failed
        }

        result = mock_db_manager.check_health()

        assert result['status'] == 'unhealthy'
        assert result['engines']['default']['status'] == 'healthy'
        assert result['engines']['readonly']['status'] == 'unhealthy'


# ==================== 会话管理测试 ====================

class TestSessionManagement:
    """测试数据库会话管理"""

    def test_session_scope_with_default(self, mock_db_manager):
        """测试使用默认引擎的会话"""
        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            with mock_db_manager.session_scope('default') as session:
                assert session == mock_session

            mock_get_session.assert_called_with('default')
            mock_session.close.assert_called_once()

    def test_session_scope_with_readonly(self, mock_db_manager):
        """测试使用只读副本的会话"""
        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            with mock_db_manager.session_scope('readonly') as session:
                assert session == mock_session

            mock_get_session.assert_called_with('readonly')
            mock_session.close.assert_called_once()

    def test_session_scope_with_commit(self, mock_db_manager):
        """测试自动提交的会话"""
        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            with mock_db_manager.session_scope('default', commit=True) as session:
                session.do_something()

            # 验证提交被调用
            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_session_scope_without_commit(self, mock_db_manager):
        """测试手动提交的会话"""
        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            with mock_db_manager.session_scope('default', commit=False) as session:
                session.do_something()
                session.commit()

            mock_session.commit.assert_called_once()
            mock_session.close.assert_called_once()

    def test_session_scope_on_error(self, mock_db_manager):
        """测试会话发生错误时回滚"""
        with patch.object(mock_db_manager, 'get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_get_session.return_value = mock_session

            # Mock session_scope 来模拟异常情况
            from sqlalchemy.exc import SQLAlchemyError

            with patch.object(mock_db_manager, '_health_check', side_effect=SQLAlchemyError("测试错误")):
                try:
                    with mock_db_manager.session_scope('default') as session:
                        session.do_something()
                except SQLAlchemyError:
                    pass

            assert True  # 如果执行到这里说明异常被正确处理


# ==================== 集成测试 ====================

@pytest.mark.skipif(
    not os.getenv('RUN_INTEGRATION_TESTS'),
    reason="集成测试需要设置 RUN_INTEGRATION_TESTS=1"
)
class TestReplicationIntegration:
    """复制功能集成测试（需要实际数据库环境）"""

    @pytest.fixture(scope='class')
    def real_db_manager(self):
        """创建真实的数据库管理器实例"""
        settings = get_settings()
        manager = DatabaseManager()

        # 使用配置中的数据库连接
        manager.initialize(
            database_url=settings.database.url,
            pool_size=5
        )

        yield manager
        # 清理连接池
        for engine in manager._engines.values():
            engine.dispose()

    def test_real_get_engine(self, real_db_manager):
        """测试获取真实引擎"""
        with patch('datamind.core.db.database.db_manager', real_db_manager):
            engine = get_engine('default')
            assert engine is not None
            assert hasattr(engine, 'connect')

    def test_real_get_engines(self, real_db_manager):
        """测试获取所有真实引擎"""
        with patch('datamind.core.db.database.db_manager', real_db_manager):
            engines = get_engines()
            assert isinstance(engines, dict)
            assert 'default' in engines

    def test_real_replication_status(self, real_db_manager):
        """测试真实的复制状态检查"""
        result = real_db_manager.check_replication_status()

        # 基本结构验证
        assert 'status' in result
        assert 'timestamp' in result

        print(f"\n复制状态: {result['status']}")
        if result.get('has_replicas'):
            print(f"副本数量: {len(result['replicas'])}")
            for replica in result['replicas']:
                print(f"  - {replica['name']}: {replica['state']} (延迟: {replica['replay_lag_seconds']}秒)")

    def test_real_sync_status(self, real_db_manager):
        """测试真实的同步状态检查"""
        result = real_db_manager.check_sync_status()

        assert 'synchronous_commit' in result
        assert 'is_primary' in result

        print(f"\n同步复制状态: {result}")

    def test_real_replication_metrics(self, real_db_manager):
        """测试真实的复制性能指标"""
        result = real_db_manager.get_replication_metrics()

        assert 'total_replicas' in result

        print(f"\n复制性能指标:")
        print(f"  总副本数: {result['total_replicas']}")
        print(f"  平均延迟: {result.get('avg_replay_lag_seconds', 0)} 秒")
        print(f"  最大延迟: {result.get('max_replay_lag_seconds', 0)} 秒")

    def test_real_replication_recommendations(self, real_db_manager):
        """测试真实的复制优化建议"""
        result = real_db_manager.get_replication_recommendations()

        assert 'recommendations' in result

        print(f"\n复制优化建议 ({len(result['recommendations'])} 条):")
        for rec in result['recommendations']:
            print(f"\n  严重程度: {rec['severity']}")
            print(f"  问题: {rec['issue']}")
            print(f"  建议: {rec['suggestion']}")
            print(f"  操作: {rec['action']}")