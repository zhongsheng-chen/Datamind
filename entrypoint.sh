#!/bin/bash
set -e

# ==== 颜色定义 ====
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ==== 环境变量 ====
DATAMIND_VERSION=${DATAMIND_VERSION:-1.0.0}
DATAMIND_ENV=${DATAMIND_ENV:-production}

# 通知 Python logger 采用 entrypoint 模式，不重复打印时间
export DATAMIND_LOG_FORMAT=entrypoint

# ==== 日志函数 ====
log() {
    echo -e "[DATAMIND] [$(date '+%Y-%m-%d %H:%M:%S')] $1"
}
log_success() {
    echo -e "[DATAMIND] [$(date '+%Y-%m-%d %H:%M:%S')] ${GREEN}$1${NC}"
}
log_warn() {
    echo -e "[DATAMIND] [$(date '+%Y-%m-%d %H:%M:%S')] ${YELLOW}$1${NC}"
}
log_error() {
    echo -e "[DATAMIND] [$(date '+%Y-%m-%d %H:%M:%S')] ${RED}$1${NC}"
}

# ==== 启动信息 ====
log "================================================================================"
log "==== START: Datamind Service ===="
log "================================================================================"

# ==== Logo ====
echo "[DATAMIND]  ____        _                  _           _ "
echo "[DATAMIND] |  _ \\  __ _| |_ __ _ _ __ ___ (_)_ __   __| |"
echo "[DATAMIND] | | | |/ _\` | __/ _\` | '_ \` _ \\| | '_ \\ / _\` |"
echo "[DATAMIND] | |_| | (_| | || (_| | | | | | | | | | (_| |"
echo "[DATAMIND] |____/ \\__,_|\\__\\__,_|_| |_| |_|_|_| |_|\\__,_|"
echo "[DATAMIND]"

log "Powered by zhongsheng.chen@bankgy.com.cn"
log "Version: ${DATAMIND_VERSION} | Environment: ${DATAMIND_ENV}"
log "Starting Datamind service initialization..."

# ==== 抑制 TensorFlow / SQLALCHEMY 警告 ====
export TF_CPP_MIN_LOG_LEVEL=2
export SQLALCHEMY_SILENCE_UBER_WARNING=1
export SQLALCHEMY_WARN_20=1

# ==== 等待数据库启动 ====
/app/wait-for-it.sh $POSTGRES_HOST:5432 --timeout=60 --strict >/dev/null && log_success "Postgres is up"
/app/wait-for-it.sh $ORACLE_HOST:1521 --timeout=60 --strict >/dev/null && log_success "Oracle is up"

# ==== 注册模型 ====
log "==== START: Registering models ===="
start_time=$(date +%s)

if ! PYTHONPATH=. python -u src/register_model.py --all 2>&1 | while IFS= read -r line; do
    echo "[DATAMIND] [$(date '+%Y-%m-%d %H:%M:%S')] $line"
done; then
    log_error "ERROR: Model registration failed"
    exit 1
fi

end_time=$(date +%s)
elapsed=$((end_time - start_time))
log_success "==== DONE: Models registered successfully (耗时 ${elapsed}s) ===="

# ==== 启动服务 ====
bentoml serve src.service:Datamind --host 0.0.0.0 --port 3000 &
BENTO_PID=$!
log_success "Datamind service is running at http://0.0.0.0:3000"

# ==== 服务心跳日志（每 10 秒打印一次） ====
while kill -0 $BENTO_PID 2>/dev/null; do
    log_success "Datamind service is alive"
    sleep 10
done

wait $BENTO_PID
