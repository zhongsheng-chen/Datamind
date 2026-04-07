#!/usr/bin/env python
# -*- coding: utf-8 -*-
# tests/demo_storage.py

"""存储组件使用示例

演示 Datamind 存储系统的所有核心功能：
  - 存储配置加载
  - 本地文件系统存储
  - 模型文件的保存和加载
  - 版本管理
  - 配置热重载
  - 统计信息查看
"""

import sys
import json
import time
import asyncio
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datamind.config import get_settings, reload_storage_config
from datamind.storage.local_storage import LocalStorage
from datamind.storage.models import ModelStorage, VersionManager
from datamind import PROJECT_ROOT


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def print_json(data, indent=2):
    """打印 JSON 格式数据"""
    print(json.dumps(data, indent=indent, ensure_ascii=False, default=str))


def init_storage():
    """初始化存储系统"""
    print_section("初始化存储系统")

    settings = get_settings()
    storage_config = settings.storage

    print(f"存储类型: {storage_config.storage_type.value}")
    print(f"启用缓存: {storage_config.enable_cache}")
    print(f"缓存大小: {storage_config.cache_size}")
    print(f"缓存过期时间: {storage_config.cache_ttl} 秒")
    print(f"启用压缩: {storage_config.enable_compression}")
    print(f"压缩库: {storage_config.compression_library.value if storage_config.enable_compression else '未启用'}")
    print(f"启用加密: {storage_config.enable_encryption}")
    print(f"最大文件大小: {storage_config.max_file_size // (1024 * 1024)} MB")
    print(f"允许的扩展名: {storage_config.allowed_extensions}")

    # 显示本地存储路径
    if storage_config.storage_type.value == "local":
        models_path = storage_config.local.models_path
        resolved_path = storage_config.local.get_resolved_models_path()
        print(f"模型存储路径: {models_path}")
        print(f"解析后路径: {resolved_path}")

    # 创建存储后端
    backend = LocalStorage(
        root_path=str(PROJECT_ROOT / storage_config.local.models_path),
        base_path="models"
    )

    return backend


async def demo_save_and_load(backend):
    """演示保存和加载模型"""
    print_section("保存和加载模型示例")

    model_storage = ModelStorage(backend)

    # 创建测试数据
    test_model = {
        "model_name": "test_model",
        "version": "1.0.0",
        "coefficients": [0.5, -0.3, 0.8, 1.2],
        "intercept": 0.1,
        "features": ["age", "income", "debt", "credit_score"],
        "created_at": time.time()
    }

    print("测试数据:")
    print_json(test_model)

    # 保存模型
    print("\n保存模型...")
    try:
        # 将模型数据转换为字节
        import pickle
        model_bytes = pickle.dumps(test_model)

        # 创建文件对象
        from io import BytesIO
        file_obj = BytesIO(model_bytes)

        result = await model_storage.save_model(
            model_id="test_model",
            version="1.0.0",
            model_file=file_obj,
            framework="sklearn",
            metadata={"description": "测试模型"}
        )
        print(f"保存成功: {result}")
    except Exception as e:
        print(f"保存失败: {e}")
        return

    # 加载模型
    print("\n加载模型...")
    try:
        content = await model_storage.load_model("test_model", version="1.0.0")
        loaded_model = pickle.loads(content)
        print("加载成功")
        print(f"加载的数据: {print_json(loaded_model)}")
    except Exception as e:
        print(f"加载失败: {e}")


async def demo_version_management(backend):
    """演示版本管理"""
    print_section("版本管理示例")

    version_manager = VersionManager(backend, model_id="test_model")

    # 添加版本
    print("添加版本...")
    try:
        # 创建版本文件
        import pickle
        from io import BytesIO

        for version in ["1.0.0", "1.1.0", "1.2.0"]:
            model_data = {
                "version": version,
                "coefficients": [0.5, -0.3, 0.8, float(version.replace('.', '')) / 100],
                "created_at": time.time()
            }
            model_bytes = pickle.dumps(model_data)
            file_obj = BytesIO(model_bytes)

            # 保存文件
            path = f"test_model/versions/model_{version}.pkl"
            await backend.save(path, file_obj, metadata={"version": version})

            # 添加版本记录
            await version_manager.add_version(
                version=version,
                file_path=path,
                metadata={"description": f"版本 {version}"}
            )
            print(f"  已添加版本: {version}")
    except Exception as e:
        print(f"添加版本失败: {e}")

    # 列出所有版本
    print("\n列出所有版本:")
    versions = await version_manager.list_versions(include_metadata=True)
    for v in versions:
        print(f"  - {v['version']} (生产: {v.get('is_production', False)})")

    # 设置生产版本
    print("\n设置生产版本为 1.2.0...")
    try:
        await version_manager.set_production_version("1.2.0")
        print("设置成功")
    except Exception as e:
        print(f"设置失败: {e}")

    # 获取生产版本
    print("\n获取生产版本:")
    prod_version = await version_manager.get_production_version()
    if prod_version:
        print(f"  生产版本: {prod_version['version']}")
    else:
        print("  未找到生产版本")

    # 获取版本统计
    print("\n版本统计:")
    stats = await version_manager.get_version_stats()
    print_json(stats)


async def demo_list_and_delete(backend):
    """演示列出和删除模型"""
    print_section("列出和删除模型示例")

    model_storage = ModelStorage(backend)

    # 列出所有模型
    print("列出所有模型:")
    try:
        models = await model_storage.list_models()
        if models:
            for model in models:
                print(f"  模型: {model['model_id']}")
                print(f"    版本数: {model['version_count']}")
                if model.get('latest'):
                    print(f"    最新版本: {model['latest']['path']}")
        else:
            print("  (无模型)")
    except Exception as e:
        print(f"列出模型失败: {e}")

    # 获取模型信息
    print("\n获取模型信息:")
    try:
        info = await model_storage.get_model_info("test_model")
        print(f"  模型ID: {info['model_id']}")
        print(f"  版本数: {info['version_count']}")
    except Exception as e:
        print(f"获取信息失败: {e}")

    # 删除模型
    print("\n删除模型...")
    try:
        result = await model_storage.delete_model("test_model", version="1.0.0")
        print(f"  删除版本 1.0.0: {result}")
    except Exception as e:
        print(f"删除失败: {e}")


async def demo_error_handling(backend):
    """演示错误处理"""
    print_section("错误处理示例")

    model_storage = ModelStorage(backend)

    # 尝试加载不存在的模型
    print("尝试加载不存在的模型:")
    try:
        await model_storage.load_model("not_exist_model", version="1.0.0")
        print("  加载成功（不应该）")
    except FileNotFoundError as e:
        print(f"  正确拒绝: {e}")

    # 尝试加载不存在的版本
    print("\n尝试加载不存在的版本:")
    try:
        await model_storage.load_model("test_model", version="99.99.99")
        print("  加载成功（不应该）")
    except FileNotFoundError as e:
        print(f"  正确拒绝: {e}")


async def demo_cleanup(backend):
    """演示清理功能"""
    print_section("清理示例")

    model_storage = ModelStorage(backend)

    # 删除所有测试模型
    print("清理测试模型...")
    try:
        await model_storage.delete_model("test_model", version=None)
        print("  已删除 test_model 所有版本")
    except Exception as e:
        print(f"  删除失败: {e}")

    # 列出清理后的文件
    print("\n清理后剩余模型:")
    try:
        models = await model_storage.list_models()
        if models:
            for model in models:
                print(f"  - {model['model_id']}")
        else:
            print("  (无模型)")
    except Exception as e:
        print(f"列出失败: {e}")


def demo_reload_config():
    """演示配置热重载"""
    print_section("配置热重载示例")

    settings = get_settings()
    original_type = settings.storage.storage_type.value
    print(f"原始存储类型: {original_type}")

    print("\n执行热重载...")
    reload_storage_config()

    new_settings = get_settings()
    new_type = new_settings.storage.storage_type.value
    print(f"重载后存储类型: {new_type}")


def demo_config_summary():
    """演示配置摘要"""
    print_section("配置摘要")

    settings = get_settings()
    summary = settings.storage.to_summary_dict()
    print_json(summary)


async def main_async():
    """异步主函数"""
    print("\n" + "=" * 60)
    print("Datamind 存储组件演示程序")
    print("=" * 60)
    print(f"Python 版本: {sys.version}")
    print(f"操作系统: {sys.platform}")
    print(f"项目根目录: {PROJECT_ROOT}")

    # 初始化存储
    backend = init_storage()

    # 运行演示
    await demo_save_and_load(backend)
    await demo_version_management(backend)
    await demo_list_and_delete(backend)
    await demo_error_handling(backend)
    demo_config_summary()
    demo_reload_config()
    await demo_cleanup(backend)

    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


def main():
    """主函数"""
    asyncio.run(main_async())


if __name__ == "__main__":
    main()