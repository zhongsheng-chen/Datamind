FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 3000

ENV DATAMIND_CONFIG_PATH=/app/config/config.yaml

# 健康检查 (每10秒检查一次 /ping)
HEALTHCHECK --interval=10s --timeout=3s \
  CMD curl -f http://localhost:3000/healthz || exit 1

# 启动 BentoML 服务
CMD ["bentoml", "serve", "src.service:Datamind", "--host", "0.0.0.0", "--port", "3000"]
