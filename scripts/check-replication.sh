#!/bin/bash
# 文件位置: /home/zhongsheng/PycharmProjects/Datamind/scripts/check-replication.sh

# 复制状态检查脚本
echo "========================================="
echo "PostgreSQL 复制状态检查"
echo "时间: $(date)"
echo "========================================="

# 检查主库状态
echo ""
echo "主库状态:"
docker exec datamind-postgres-primary pg_isready -U datamind

# 检查备库状态
echo ""
echo "备库状态:"
docker exec datamind-postgres-replica pg_isready -U datamind

# 检查复制状态
echo ""
echo "复制状态:"
docker exec datamind-postgres-primary psql -U datamind -d datamind -c "
SELECT
    application_name,
    client_addr,
    state,
    sync_state,
    replay_lag,
    EXTRACT(EPOCH FROM replay_lag) as lag_seconds,
    pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) as lag_bytes
FROM pg_stat_replication;
"

# 检查复制槽
echo ""
echo "复制槽状态:"
docker exec datamind-postgres-primary psql -U datamind -d datamind -c "
SELECT
    slot_name,
    slot_type,
    active,
    pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) as retained_bytes
FROM pg_replication_slots;
"

# 检查备库接收状态
echo ""
echo "备库接收状态:"
docker exec datamind-postgres-replica psql -U datamind -d datamind -c "
SELECT
    pg_is_in_recovery() as is_replica,
    pg_last_wal_receive_lsn() as receive_lsn,
    pg_last_wal_replay_lsn() as replay_lsn,
    pg_last_xact_replay_timestamp() as last_replay_time;
"