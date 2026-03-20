#!/bin/bash
# 文件位置: /home/zhongsheng/PycharmProjects/Datamind/scripts/deploy-ha.sh

# Datamind 高可用部署脚本
set -e

echo "========================================="
echo "Datamind 高可用部署"
echo "========================================="

# 检查 Docker 命令
if command -v docker &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    echo "错误: 未找到 docker 或 docker-compose 命令"
    exit 1
fi

echo "使用命令: $DOCKER_COMPOSE"

# 创建必要的目录
echo "创建目录结构..."
mkdir -p docker/postgres/primary/{init,wal}
mkdir -p docker/postgres/replica/init
mkdir -p docker/postgres/backup
mkdir -p docker/pgpool
mkdir -p docker/nginx/ssl
mkdir -p logs models_storage config

# 复制初始化脚本到 Docker 目录
if [ -f scripts/init-primary.sh ]; then
    cp scripts/init-primary.sh docker/postgres/primary/init/01-init-primary.sh
else
    echo "警告: scripts/init-primary.sh 不存在，跳过复制"
fi

if [ -f scripts/init-replica.sh ]; then
    cp scripts/init-replica.sh docker/postgres/replica/init/01-init-replica.sh
else
    echo "警告: scripts/init-replica.sh 不存在，跳过复制"
fi

# 设置脚本权限
chmod +x docker/postgres/primary/init/*.sh 2>/dev/null || true
chmod +x docker/postgres/replica/init/*.sh 2>/dev/null || true
chmod +x scripts/*.sh 2>/dev/null || true

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 停止旧服务
echo "停止旧服务..."
$DOCKER_COMPOSE down 2>/dev/null || true

# 启动主库
echo "启动 PostgreSQL 主库..."
$DOCKER_COMPOSE up -d postgres-primary

# 等待主库就绪
echo "等待主库就绪..."
sleep 15

# 启动备库
echo "启动 PostgreSQL 备库..."
$DOCKER_COMPOSE up -d postgres-replica

# 等待备库同步
echo "等待备库同步..."
sleep 20

# 启动应用服务
echo "启动应用服务..."
$DOCKER_COMPOSE up -d redis minio minio-create-buckets api scoring-service fraud-service

# 检查状态
echo ""
echo "========================================="
echo "服务状态检查"
echo "========================================="

echo "主库状态:"
docker exec datamind-postgres-primary pg_isready -U datamind 2>/dev/null || echo "主库未就绪"

echo "备库状态:"
docker exec datamind-postgres-replica pg_isready -U datamind 2>/dev/null || echo "备库未就绪"

echo "复制状态:"
docker exec datamind-postgres-primary psql -U datamind -d datamind -c "
SELECT
    application_name,
    state,
    sync_state,
    EXTRACT(EPOCH FROM replay_lag) as lag_seconds
FROM pg_stat_replication;
" 2>/dev/null || echo "复制状态检查失败"

echo ""
echo "========================================="
echo "部署完成！"
echo "========================================="
echo "服务访问地址:"
echo "  - PostgreSQL 主库: localhost:5432"
echo "  - PostgreSQL 备库: localhost:5433"
echo "  - API 服务: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo "  - MinIO 控制台: http://localhost:9001"
echo ""
echo "查看日志: $DOCKER_COMPOSE logs -f"
echo "停止服务: $DOCKER_COMPOSE down"
echo "========================================="