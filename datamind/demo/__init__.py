# Datamind/datamind/demo/__init__.py
"""示例模型训练模块

提供示例模型训练和演示功能，用于测试模型部署和服务。
"""

from datamind.demo.train_sample_model import train_sample_model, generate_sample_data

__all__ = ['train_sample_model', 'generate_sample_data']