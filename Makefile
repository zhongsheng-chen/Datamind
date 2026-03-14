# datamind/Makefile
.PHONY: help install dev install-dev clean test lint format migrate backup restore shell run docker-build docker-up docker-down

# 颜色定义
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m

help:
	@echo "$(GREEN)Datamind 项目管理$(NC)"
	@echo ""
	@echo "$(YELLOW)常用命令:$(NC)"
	@echo "  make install      - 安装生产依赖"
	@echo "  make dev          - 安装开发依赖"
	@echo "  make clean        - 清理缓存文件"
	@echo "  make test         - 运行测试"
	@echo "  make lint         - 代码检查"
	@echo "  make format       - 代码格式化"
	@echo "  make migrate      - 数据库迁移"
	@echo "  make backup       - 数据库备份"
	@echo "  make restore      - 数据库恢复"
	@echo "  make run          - 运行开发服务器"
	@echo "  make docker-build - 构建Docker镜像"
	@echo "  make docker-up    - 启动Docker容器"
	@echo "  make docker-down  - 停止Docker容器"

install:
	@echo "$(GREEN)安装生产依赖...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)依赖安装完成$(NC)"

dev: install
	@echo "$(GREEN)安装开发依赖...$(NC)"
	pip install -r requirements-dev.txt
	@echo "$(GREEN)开发环境准备完成$(NC)"

clean:
	@echo "$(YELLOW)清理缓存文件...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ htmlcov/ .coverage
	@echo "$(GREEN)清理完成$(NC)"

test:
	@echo "$(GREEN)运行测试...$(NC)"
	pytest tests/ -v --cov=core --cov=api --cov-report=term --cov-report=html
	@echo "$(GREEN)测试完成$(NC)"

lint:
	@echo "$(GREEN)代码检查...$(NC)"
	flake8 core/ api/ --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 core/ api/ --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
	mypy core/ api/ --ignore-missing-imports
	@echo "$(GREEN)代码检查完成$(NC)"

format:
	@echo "$(GREEN)代码格式化...$(NC)"
	black core/ api/ tests/
	isort core/ api/ tests/
	@echo "$(GREEN)格式化完成$(NC)"

migrate:
	@echo "$(GREEN)执行数据库迁移...$(NC)"
	alembic upgrade head
	@echo "$(GREEN)迁移完成$(NC)"

backup:
	@echo "$(GREEN)数据库备份...$(NC)"
	python scripts/backup_db.py backup
	@echo "$(GREEN)备份完成$(NC)"

restore:
	@echo "$(YELLOW)数据库恢复...$(NC)"
	@read -p "请输入备份文件名: " file; \
	python scripts/backup_db.py restore --file $$file
	@echo "$(GREEN)恢复完成$(NC)"

shell:
	@echo "$(GREEN)启动IPython shell...$(NC)"
	IPython -i -c "from core.db import *; from core.ml import *; from core.logging import *; from config import *"

run:
	@echo "$(GREEN)启动开发服务器...$(NC)"
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	@echo "$(GREEN)构建Docker镜像...$(NC)"
	docker-compose build

docker-up:
	@echo "$(GREEN)启动Docker容器...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)容器已启动$(NC)"

docker-down:
	@echo "$(YELLOW)停止Docker容器...$(NC)"
	docker-compose down
	@echo "$(GREEN)容器已停止$(NC)"

docker-logs:
	docker-compose logs -f

init-db:
	@echo "$(GREEN)初始化数据库...$(NC)"
	python scripts/init_db.py
	@echo "$(GREEN)数据库初始化完成$(NC)"

reset-db:
	@echo "$(RED)警告: 此操作将删除所有数据！$(NC)"
	@read -p "确定要继续吗？ (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(YELLOW)删除数据库...$(NC)"; \
		dropdb --if-exists datamind; \
		createdb datamind; \
		echo "$(GREEN)数据库已重置$(NC)"; \
		make init-db; \
	else \
		echo "$(GREEN)操作已取消$(NC)"; \
	fi

seed-data:
	@echo "$(GREEN)导入测试数据...$(NC)"
	python scripts/seed_data.py
	@echo "$(GREEN)测试数据导入完成$(NC)"

.PHONY: help install dev install-dev clean test lint format migrate backup restore shell run docker-build docker-up docker-down docker-logs init-db reset-db seed-data