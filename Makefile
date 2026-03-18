# Datamind/Makefile
.PHONY: help install dev clean test lint format migrate backup restore \
        run docker-build docker-up docker-down docker-logs init-db \
        reset-db seed-data shell bench health logs

# 颜色定义
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
BLUE := \033[0;34m
NC := \033[0m

# 项目变量
PROJECT_NAME := datamind
PYTHON := python3
PIP := pip3
DOCKER_COMPOSE := docker-compose
ALEMBIC := alembic

# 默认目标
.DEFAULT_GOAL := help

help:
	@echo "$(BLUE)╔══════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║         Datamind 项目管理工具                            ║$(NC)"
	@echo "$(BLUE)╚══════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)环境配置:$(NC)"
	@echo "  make install      - 安装生产依赖"
	@echo "  make dev          - 安装开发依赖"
	@echo "  make clean        - 清理缓存文件"
	@echo ""
	@echo "$(GREEN)数据库操作:$(NC)"
	@echo "  make init-db      - 初始化数据库"
	@echo "  make migrate      - 执行数据库迁移"
	@echo "  make migrate-create - 创建新的迁移脚本"
	@echo "  make migrate-down - 回滚一个版本"
	@echo "  make reset-db     - 重置数据库（危险操作）"
	@echo "  make backup       - 备份数据库"
	@echo "  make restore      - 恢复数据库"
	@echo ""
	@echo "$(GREEN)代码质量:$(NC)"
	@echo "  make lint         - 代码检查"
	@echo "  make format       - 代码格式化"
	@echo "  make test         - 运行测试"
	@echo "  make test-cov     - 运行测试并生成覆盖率报告"
	@echo ""
	@echo "$(GREEN)运行服务:$(NC)"
	@echo "  make run          - 运行开发服务器"
	@echo "  make run-api      - 运行 API 服务"
	@echo "  make run-scoring  - 运行评分卡服务"
	@echo "  make run-fraud    - 运行反欺诈服务"
	@echo "  make run-all      - 运行所有服务"
	@echo ""
	@echo "$(GREEN)Docker 操作:$(NC)"
	@echo "  make docker-build - 构建 Docker 镜像"
	@echo "  make docker-up    - 启动 Docker 容器"
	@echo "  make docker-down  - 停止 Docker 容器"
	@echo "  make docker-logs  - 查看容器日志"
	@echo "  make docker-clean - 清理 Docker 资源"
	@echo ""
	@echo "$(GREEN)监控与调试:$(NC)"
	@echo "  make health       - 健康检查"
	@echo "  make logs         - 查看日志"
	@echo "  make shell        - 启动 IPython shell"
	@echo "  make bench        - 运行性能测试"
	@echo "  make stats        - 查看系统统计信息"
	@echo ""

# ==================== 环境配置 ====================

install:
	@echo "$(GREEN)安装生产依赖...$(NC)"
	$(PIP) install -r requirements.txt
	@echo "$(GREEN)✅ 依赖安装完成$(NC)"

dev: install
	@echo "$(GREEN)安装开发依赖...$(NC)"
	$(PIP) install -r requirements-dev.txt
	@echo "$(GREEN)✅ 开发环境准备完成$(NC)"

clean:
	@echo "$(YELLOW)清理缓存文件...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage
	@echo "$(GREEN)✅ 清理完成$(NC)"

# ==================== 数据库操作 ====================

init-db:
	@echo "$(GREEN)初始化数据库...$(NC)"
	$(PYTHON) scripts/init_db.py
	@echo "$(GREEN)✅ 数据库初始化完成$(NC)"

migrate:
	@echo "$(GREEN)执行数据库迁移...$(NC)"
	$(ALEMBIC) upgrade head
	@echo "$(GREEN)✅ 迁移完成$(NC)"

migrate-create:
	@read -p "请输入迁移描述: " desc; \
	$(ALEMBIC) revision --autogenerate -m "$$desc"
	@echo "$(GREEN)✅ 迁移脚本创建完成$(NC)"

migrate-down:
	@echo "$(YELLOW)回滚一个版本...$(NC)"
	$(ALEMBIC) downgrade -1
	@echo "$(GREEN)✅ 回滚完成$(NC)"

reset-db:
	@echo "$(RED)⚠️  警告: 此操作将删除所有数据！$(NC)"
	@read -p "确定要继续吗？ (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(YELLOW)删除数据库...$(NC)"; \
		dropdb --if-exists datamind 2>/dev/null || true; \
		createdb datamind 2>/dev/null || true; \
		echo "$(GREEN)数据库已重置$(NC)"; \
		$(MAKE) init-db; \
		$(MAKE) migrate; \
	else \
		echo "$(GREEN)操作已取消$(NC)"; \
	fi

backup:
	@echo "$(GREEN)数据库备份...$(NC)"
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	FILENAME="backups/datamind_$$TIMESTAMP.sql"; \
	pg_dump datamind > $$FILENAME; \
	echo "$(GREEN)✅ 备份完成: $$FILENAME$(NC)"

restore:
	@echo "$(YELLOW)数据库恢复...$(NC)"
	@ls -la backups/
	@read -p "请输入备份文件名: " file; \
	if [ -f "backups/$$file" ]; then \
		dropdb --if-exists datamind; \
		createdb datamind; \
		psql datamind < backups/$$file; \
		echo "$(GREEN)✅ 恢复完成$(NC)"; \
	else \
		echo "$(RED)❌ 文件不存在: backups/$$file$(NC)"; \
	fi

# ==================== 代码质量 ====================

lint:
	@echo "$(GREEN)代码检查...$(NC)"
	flake8 api/ core/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 api/ core/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	mypy api/ core/ --ignore-missing-imports
	@echo "$(GREEN)✅ 代码检查完成$(NC)"

format:
	@echo "$(GREEN)代码格式化...$(NC)"
	black api/ core/ tests/
	isort api/ core/ tests/
	@echo "$(GREEN)✅ 格式化完成$(NC)"

test:
	@echo "$(GREEN)运行测试...$(NC)"
	pytest tests/ -v
	@echo "$(GREEN)✅ 测试完成$(NC)"

test-cov:
	@echo "$(GREEN)运行测试并生成覆盖率报告...$(NC)"
	pytest tests/ -v --cov=api --cov=core --cov-report=term --cov-report=html
	@echo "$(GREEN)✅ 测试完成，覆盖率报告: htmlcov/index.html$(NC)"

# ==================== 运行服务 ====================

run:
	@echo "$(GREEN)启动开发服务器...$(NC)"
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-api:
	@echo "$(GREEN)启动 API 服务 (端口 8000)...$(NC)"
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-scoring:
	@echo "$(GREEN)启动评分卡服务 (端口 3001)...$(NC)"
	cd serving && bentoml serve scoring_service:service --reload --port 3001

run-fraud:
	@echo "$(GREEN)启动反欺诈服务 (端口 3002)...$(NC)"
	cd serving && bentoml serve fraud_service:service --reload --port 3002

run-all:
	@echo "$(GREEN)启动所有服务...$(NC)"
	@$(MAKE) -j 3 run-api run-scoring run-fraud

run-prod:
	@echo "$(GREEN)启动生产服务...$(NC)"
	gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000

# ==================== Docker 操作 ====================

docker-build:
	@echo "$(GREEN)构建 Docker 镜像...$(NC)"
	$(DOCKER_COMPOSE) build

docker-build-api:
	@echo "$(GREEN)构建 API 镜像...$(NC)"
	docker build -f docker/Dockerfile -t datamind-api .

docker-build-serving:
	@echo "$(GREEN)构建模型服务镜像...$(NC)"
	docker build -f serving/docker/Dockerfile -t datamind-serving ./serving

docker-up:
	@echo "$(GREEN)启动 Docker 容器...$(NC)"
	$(DOCKER_COMPOSE) up -d
	@echo "$(GREEN)✅ 容器已启动$(NC)"
	@$(MAKE) docker-ps

docker-down:
	@echo "$(YELLOW)停止 Docker 容器...$(NC)"
	$(DOCKER_COMPOSE) down
	@echo "$(GREEN)✅ 容器已停止$(NC)"

docker-restart:
	@echo "$(YELLOW)重启 Docker 容器...$(NC)"
	$(DOCKER_COMPOSE) restart
	@echo "$(GREEN)✅ 容器已重启$(NC)"

docker-logs:
	$(DOCKER_COMPOSE) logs -f

docker-logs-api:
	$(DOCKER_COMPOSE) logs -f api

docker-logs-scoring:
	$(DOCKER_COMPOSE) logs -f scoring-service

docker-logs-fraud:
	$(DOCKER_COMPOSE) logs -f fraud-service

docker-ps:
	$(DOCKER_COMPOSE) ps

docker-clean:
	@echo "$(YELLOW)清理 Docker 资源...$(NC)"
	docker system prune -f
	@echo "$(GREEN)✅ 清理完成$(NC)"

docker-clean-all:
	@echo "$(RED)⚠️  警告: 这将删除所有未使用的 Docker 资源！$(NC)"
	@read -p "确定要继续吗？ (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker system prune -a -f --volumes; \
		echo "$(GREEN)✅ 清理完成$(NC)"; \
	else \
		echo "$(GREEN)操作已取消$(NC)"; \
	fi

# ==================== 监控与调试 ====================

health:
	@echo "$(GREEN)健康检查...$(NC)"
	@echo "API 服务: $$(curl -s http://localhost:8000/health | jq -r '.status // "unknown"')"
	@echo "评分卡服务: $$(curl -s http://localhost:3001/health | jq -r '.status // "unknown"')"
	@echo "反欺诈服务: $$(curl -s http://localhost:3002/health | jq -r '.status // "unknown"')"

health-detailed:
	@echo "$(GREEN)详细健康检查...$(NC)"
	curl -s http://localhost:8000/health | jq '.'
	@echo ""
	curl -s http://localhost:3001/health | jq '.'
	@echo ""
	curl -s http://localhost:3002/health | jq '.'

logs:
	@echo "$(GREEN)查看日志...$(NC)"
	@echo "1) 所有日志"
	@echo "2) 访问日志"
	@echo "3) 错误日志"
	@echo "4) 审计日志"
	@echo "5) 性能日志"
	@read -p "请选择 (1-5): " choice; \
	case $$choice in \
		1) tail -f logs/datamind.log ;; \
		2) tail -f logs/access.log ;; \
		3) tail -f logs/datamind.error.log ;; \
		4) tail -f logs/audit.log ;; \
		5) tail -f logs/performance.log ;; \
		*) echo "无效选择" ;; \
	esac

shell:
	@echo "$(GREEN)启动 IPython shell...$(NC)"
	IPython -i -c "from core.db import *; from core.ml import *; from core.logging import *; from config import *; from api import *"

bench:
	@echo "$(GREEN)运行性能测试...$(NC)"
	@read -p "请输入模型ID: " model_id; \
	python scripts/benchmark.py $$model_id --requests 100 --concurrency 10

stats:
	@echo "$(GREEN)系统统计信息...$(NC)"
	@echo "CPU使用: $$(top -bn1 | grep 'Cpu(s)' | awk '{print $$2}')%"
	@echo "内存使用: $$(free -h | grep Mem | awk '{print $$3 "/" $$2}')"
	@echo "磁盘使用: $$(df -h . | awk 'NR==2 {print $$5}')"
	@echo ""
	@echo "$(YELLOW)模型统计:$(NC)"
	@python -c "from core.ml import model_loader; print(f'已加载模型: {len(model_loader.get_loaded_models())}')"
	@python -c "from core.ml import inference_engine; print(f'总推理次数: {inference_engine.get_stats()[\"total_inferences\"]}')"

# ==================== 实用工具 ====================

seed-data:
	@echo "$(GREEN)导入测试数据...$(NC)"
	$(PYTHON) scripts/seed_data.py
	@echo "$(GREEN)✅ 测试数据导入完成$(NC)"

requirements:
	@echo "$(GREEN)生成 requirements.txt...$(NC)"
	pip freeze > requirements.txt
	@echo "$(GREEN)✅ 生成完成$(NC)"

check-env:
	@echo "$(GREEN)检查环境变量...$(NC)"
	@python -c "from config import settings; print(f'环境: {settings.ENV}'); print(f'调试模式: {settings.DEBUG}'); print(f'数据库: {settings.DATABASE_URL.split(\"@\")[-1]}')"

git-status:
	git status

git-push:
	git push origin HEAD

# ==================== 帮助 ====================

usage: help

# 防止与文件重名
.PHONY: help install dev clean test lint format migrate backup restore \
        run docker-build docker-up docker-down docker-logs init-db \
        reset-db seed-data shell bench health logs check-env \
        run-api run-scoring run-fraud run-all run-prod \
        docker-build-api docker-build-serving docker-restart docker-ps \
        docker-clean docker-clean-all health-detailed migrate-create \
        migrate-down test-cov requirements git-status git-push \
        docker-logs-api docker-logs-scoring docker-logs-fraud stats