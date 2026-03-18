# Datamind/datamind/serving/docker/Dockerfile
# 多阶段构建
FROM python:3.11-slim as builder

WORKDIR /build

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    curl \
    wget \
    git \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
COPY bentofile.yaml .

# 安装Python依赖
RUN pip install --user --no-cache-dir -r requirements.txt
RUN pip install --user --no-cache-dir bentoml

# 最终镜像
FROM python:3.11-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    postgresql-client \
    redis-tools \
    libgomp1 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 从builder复制Python包
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 创建应用用户
RUN groupadd -r datamind && useradd -r -g datamind datamind

# 复制应用代码
COPY --chown=datamind:datamind . .

# 创建必要的目录
RUN mkdir -p /app/logs /app/models_storage && \
    chown -R datamind:datamind /app/logs /app/models_storage

# 设置权限
RUN chmod +x /app/serving/docker/entrypoint.sh

# 切换到应用用户
USER datamind

# 暴露端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# 设置工作目录
WORKDIR /app/serving

# 启动命令
ENTRYPOINT ["/app/serving/docker/entrypoint.sh"]