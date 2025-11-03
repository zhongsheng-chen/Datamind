FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir bentoml lightgbm xgboost catboost scikit-learn numpy pyyaml

EXPOSE 3000

ENV DATAMIND_CONFIG_PATH=/app/config/config.yaml

## 启动 BentoML 服务（开发模式）
CMD ["bentoml", "serve", "src/service.py:svc", "--port", "3000", "--reload"]

## 启动 BentoML 服务（生产模式）
# CMD ["bentoml", "serve-gunicorn", "src/service.py:svc", "--bind", "0.0.0.0:3000", "--workers", "4"]