# Datamind/docker/Dockerfile
FROM node:24-bookworm-slim AS console-build

WORKDIR /build
COPY package.json package-lock.json vite.config.mjs ./
RUN npm ci --no-audit --no-fund
COPY datamind/console/static/ ./datamind/console/static/
RUN npm run build:console

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    # alembic \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .
COPY --from=console-build /build/datamind/console/dist/ ./datamind/console/dist/

# 创建必要目录
RUN mkdir -p /app/logs /app/models_storage

# 暴露端口
EXPOSE 8000 9090

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
