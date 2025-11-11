FROM python:3.10-slim

LABEL maintainer="dataminddev"

RUN useradd -m -s /bin/bash datamind

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN chown -R datamind:datamind /app

USER datamind

COPY --chown=datamind:datamind wait-for-it.sh entrypoint.sh /app/
RUN chmod +x /app/wait-for-it.sh /app/entrypoint.sh


RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 环境变量
ENV DATAMIND_CONFIG_PATH=/app/config/config.yaml

EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=10s --timeout=3s \
  CMD curl -f http://localhost:3000/healthz || exit 1

# 启动服务
CMD ["/app/entrypoint.sh"]
