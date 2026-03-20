#!/bin/bash
# 文件位置: /home/zhongsheng/PycharmProjects/Datamind/scripts/test-ha.sh

# 测试主备切换和读写分离
echo "========================================="
echo "测试 PostgreSQL 高可用"
echo "========================================="

# 检查复制状态
echo ""
echo "1. 检查复制状态..."
docker exec datamind-postgres-primary psql -U datamind -d datamind -c "
SELECT
    application_name,
    state,
    sync_state,
    replay_lag
FROM pg_stat_replication;
"

# 测试写操作（主库）
echo ""
echo "2. 测试写操作..."
docker exec datamind-postgres-primary psql -U datamind -d datamind -c "
CREATE TABLE IF NOT EXISTS test_ha (
    id SERIAL PRIMARY KEY,
    test_time TIMESTAMP DEFAULT NOW(),
    test_data TEXT
);
INSERT INTO test_ha (test_data) VALUES ('test write operation');
SELECT COUNT(*) as test_count FROM test_ha;
"

# 测试读操作（备库）
echo ""
echo "3. 测试读操作（备库）..."
sleep 2  # 等待复制
docker exec datamind-postgres-replica psql -U readonly -d datamind -c "
SELECT COUNT(*) as test_count FROM test_ha;
"

# 检查复制延迟
echo ""
echo "4. 检查复制延迟..."
docker exec datamind-postgres-primary psql -U datamind -d datamind -c "
SELECT
    application_name,
    EXTRACT(EPOCH FROM replay_lag) as lag_seconds,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) as lag_bytes
FROM pg_stat_replication;
"

# 测试复制槽状态
echo ""
echo "5. 检查复制槽状态..."
docker exec datamind-postgres-primary psql -U datamind -d datamind -c "
SELECT
    slot_name,
    slot_type,
    active,
    pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) as retained_bytes
FROM pg_replication_slots;
"

echo ""
echo "========================================="
echo "测试完成！"
echo "========================================="