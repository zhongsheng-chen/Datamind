FROM python:3.10-slim

LABEL maintainer="dataminddev"

# === 创建非 root 用户 ===
RUN useradd -m -s /bin/bash datamind

WORKDIR /app
COPY . /app

# === 安装依赖（临时） ===
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ libpq-dev curl libgomp1 && \
    # 升级 pip 并安装依赖
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    # 删除编译工具，清理缓存
    apt-get remove -y build-essential gcc g++ && \
    apt-get autoremove -y && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /root/.cache

# === 权限设置 ===
RUN chown -R datamind:datamind /app
USER datamind

COPY --chown=datamind:datamind wait-for-it.sh entrypoint.sh /app/
RUN chmod +x /app/wait-for-it.sh /app/entrypoint.sh

# === 环境变量 ===
ENV DATAMIND_CONFIG_PATH=/app/config/config.yaml

EXPOSE 3000

# === 健康检查 ===
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:3000/healthz || exit 1

# === 启动服务 ===
CMD ["/app/entrypoint.sh"]
