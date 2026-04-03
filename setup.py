# Datamind/setup.py

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="datamind",
    version="0.1.0",
    author="Zhongsheng Chen",
    description="Datamind 模型部署平台",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/datamind",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        # BentoML 核心
        "bentoml>=1.0.0",
        # Web 框架
        "fastapi>=0.100.0",
        "uvicorn[standard]>=0.23.0",
        # 数据库
        "sqlalchemy<2.0.0",
        "psycopg2-binary>=2.9.0",
        "alembic>=1.12.0",
        # Redis
        "redis>=5.0.0",
        # 配置管理
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
        "python-dotenv>=1.0.0",
        # 模型框架
        "scikit-learn>=1.3.0",
        "xgboost>=2.0.0",
        "lightgbm>=4.0.0",
        "catboost>=1.2.0",
        "torch>=2.0.0",
        "tensorflow>=2.13.0",
        "onnxruntime>=1.15.0",
        # 数据处理
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "joblib>=1.3.0",
        # 工具
        "click>=8.0.0",
        "requests>=2.25.0",
        "pyyaml>=5.4.0",
        "python-multipart>=0.0.6",
        "watchdog>=3.0.0",
        "tenacity>=8.2.0",
        "semver>=3.0.0",
        # 云存储
        "boto3>=1.28.0",
        "minio>=7.2.0",
        # 监控
        "psutil>=5.9.0",
        # JWT
        "pyjwt>=2.8.0",
        # SHAP（可选）
        "shap>=0.42.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ],
        "prod": [
            "gunicorn>=21.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "datamind=cli.main:main",
        ],
    },
    include_package_data=True,
)