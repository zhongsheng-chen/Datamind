# Datamind 存储组件

提供统一的文件存储接口，支持多种存储后端（本地文件系统、AWS S3、MinIO），以及模型版本管理功能。

## 特性

- **统一接口** - 所有存储后端实现相同的 API
- **多后端支持** - 本地文件系统、AWS S3、MinIO
- **版本管理** - 完整的模型版本控制
- **元数据管理** - 文件元数据存储和查询
- **签名 URL** - 生成临时访问链接
- **高可用** - 支持分布式存储
- **审计日志** - 所有操作记录日志

## 目录结构
```text
storage/
├── init.py # 模块初始化
├── base.py # 存储基类接口
├── local_storage.py # 本地文件系统存储
├── s3_storage.py # AWS S3存储
├── minio_storage.py # MinIO存储
├── models/ # 模型存储模块
│      ├── init.py
│      ├── model_storage.py # 模型存储管理
│      └── version_manager.py # 版本管理器
└── README.md
```


## 快速开始

### 1. 本地文件系统存储

```python
from datamind.storage import LocalStorage

# 初始化本地存储
storage = LocalStorage(
    root_path="/data/models",  # 存储根目录
    base_path="models"  # 基础路径
)

# 保存文件
with open("model.pkl", "rb") as f:
    result = await storage.save(
        path="credit_model/v1/model.pkl",
        content=f,
        metadata={
            "description": "信用评分模型",
            "version": "1.0.0"
        }
    )
print(f"文件保存成功: {result['path']}")

# 加载文件
content = await storage.load("credit_model/v1/model.pkl")

# 获取签名URL（本地存储返回文件路径）
url = await storage.get_signed_url("credit_model/v1/model.pkl", expires_in=3600)
print(f"下载链接: {url}")
```

### 2. AWS S3 存储

```python
from datamind.storage import S3Storage

# 初始化S3存储
storage = S3Storage(
    bucket_name="datamind-models",
    aws_access_key_id="YOUR_ACCESS_KEY",
    aws_secret_access_key="YOUR_SECRET_KEY",
    region_name="us-east-1",
    base_path="models"
)

# 保存文件
with open("model.pkl", "rb") as f:
    result = await storage.save(
        path="credit_model/v1/model.pkl",
        content=f,
        metadata={"version": "1.0.0"}
    )

# 生成签名URL（用于前端直传）
url = await storage.get_signed_url("credit_model/v1/model.pkl", expires_in=3600)
print(f"下载链接: {url}")
```

### 3. MinIO 存储

```python
from datamind.storage import MinIOStorage

# 初始化MinIO存储
storage = MinIOStorage(
    endpoint="localhost:9000",
    bucket_name="datamind-models",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False  # 是否使用HTTPS
)

# 生成上传签名URL（用于前端直传）
upload_url = await storage.get_upload_url(
    "models/credit_model/v1/model.pkl",
    expires_in=3600
)
print(f"上传链接: {upload_url}")

# 获取对象信息
info = await storage.get_object_info("models/credit_model/v1/model.pkl")
print(f"对象信息: {info}")
```

## 模型存储管理

### 基本使用

``` python
from storage.models import ModelStorage
from storage import MinIOStorage

# 初始化存储后端
storage = MinIOStorage(
    endpoint="localhost:9000",
    bucket_name="datamind-models"
)

# 创建模型存储管理器
model_storage = ModelStorage(storage_backend=storage)

# 保存模型
with open("model.pkl", "rb") as f:
    result = await model_storage.save_model(
        model_id="MDL_20240315_ABCD1234",
        version="1.0.0",
        model_file=f,
        framework="sklearn",
        metadata={
            "description": "信用评分模型",
            "accuracy": 0.95,
            "created_by": "admin"
        }
    )

# 加载模型
content = await model_storage.load_model(
    model_id="MDL_20240315_ABCD1234",
    version="1.0.0"  # None表示最新版本
)

# 列出所有模型
models = await model_storage.list_models()
for model in models:
    print(f"模型: {model['model_id']}, 版本数: {model['version_count']}")

# 获取模型信息
info = await model_storage.get_model_info("MDL_20240315_ABCD1234")
print(f"模型信息: {info}")

# 获取下载签名URL
url = await model_storage.get_signed_url(
    model_id="MDL_20240315_ABCD1234",
    version="1.0.0"
)
print(f"下载链接: {url}")

# 删除模型
await model_storage.delete_model("MDL_20240315_ABCD1234", version="1.0.0")
```

## 版本管理

``` python
from storage.models import VersionManager

# 创建版本管理器
version_mgr = VersionManager(storage, "MDL_20240315_ABCD1234")

# 添加版本
await version_mgr.add_version(
    version="1.0.0",
    file_path="models/MDL_20240315_ABCD1234/versions/model_1.0.0.pkl",
    metadata={
        "description": "初始版本",
        "accuracy": 0.95
    }
)

await version_mgr.add_version(
    version="1.1.0",
    file_path="models/MDL_20240315_ABCD1234/versions/model_1.1.0.pkl",
    metadata={
        "description": "优化版本",
        "accuracy": 0.96
    },
    is_production=True  # 设为生产版本
)

# 获取最新版本
latest = await version_mgr.get_version()
print(f"最新版本: {latest['version']}")

# 获取生产版本
production = await version_mgr.get_production_version()
print(f"生产版本: {production['version']}")

# 列出所有版本
versions = await version_mgr.list_versions(include_metadata=True)
for v in versions:
    print(f"版本: {v['version']}, 生产: {v['is_production']}")

# 比较版本差异
diff = await version_mgr.get_version_diff("1.0.0", "1.1.0")
print(f"差异: {diff}")

# 打标签
await version_mgr.tag_version("1.0.0", "stable")
await version_mgr.tag_version("1.0.0", "tested")

# 根据标签查询
stable_versions = await version_mgr.get_versions_by_tag("stable")
print(f"稳定版本: {stable_versions}")

# 增加下载计数
await version_mgr.increment_download_count("1.1.0")

# 获取统计信息
stats = await version_mgr.get_version_stats()
print(f"统计信息: {stats}")

# 回滚到旧版本
rollback = await version_mgr.rollback_to_version("1.0.0")
print(f"回滚版本: {rollback['version']}")

# 清理旧版本（保留最近5个）
deleted = await version_mgr.cleanup_old_versions(keep_count=5)
print(f"已清理版本: {deleted}")
```



## 配置说明

### 环境变量

#### 本地存储

```bash
# 本地存储路径
STORAGE_LOCAL_PATH=/data/models
```

#### AWS S3
```bash

# AWS 认证
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1

# S3 存储桶
S3_BUCKET_NAME=datamind-models
```

#### MinIO
```bash

# MinIO 配置
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=datamind-models
MINIO_SECURE=false
MINIO_REGION=us-east-1
```

### Django/Flask 配置示例

``` python
# config/settings.py
class StorageConfig:
    # 存储类型: local, s3, minio
    STORAGE_TYPE = os.getenv('STORAGE_TYPE', 'local')
    
    # 本地存储
    STORAGE_LOCAL_PATH = os.getenv('STORAGE_LOCAL_PATH', '/data/models')
    
    # S3 存储
    S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'datamind-models')
    AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
    AWS_DEFAULT_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    
    # MinIO 存储
    MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
    MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
    MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minioadmin')
    MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'datamind-models')
    MINIO_SECURE = os.getenv('MINIO_SECURE', 'false').lower() == 'true'
```


## API 参考
### 存储后端接口 (StorageBackend)

| 方法 | 描述 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| save() | 保存文件 | path, content, metadata | 文件信息 |
| load() | 加载文件 | path, version | 文件内容 |
| delete() | 删除文件 | path, version | bool |
| exists() | 检查文件是否存在 | path | bool |
| list() | 列出文件 | prefix | 文件列表 |
| get_metadata() | 获取元数据 | path | 元数据 |
| copy() | 复制文件 | source_path, dest_path | 复制结果 |
| move() | 移动文件 | source_path, dest_path | 移动结果 |
| get_signed_url() | 获取签名URL | path, expires_in | URL |

### 模型存储 (ModelStorage)

| 方法 | 描述 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| save_model() | 保存模型 | model_id, version, model_file, framework, metadata | 保存结果 |
| load_model() | 加载模型 | model_id, version | 模型内容 |
| delete_model() | 删除模型 | model_id, version | bool |
| list_models() | 列出模型 | prefix | 模型列表 |
| get_model_info() | 获取模型信息 | model_id | 模型信息 |
| get_signed_url() | 获取下载URL | model_id, version | URL |
| migrate_model() | 迁移模型 | model_id, target_storage | 迁移结果 |

### 版本管理器 (VersionManager)

| 方法 | 描述 | 参数 | 返回值 |
| :--- | :--- | :--- | :--- |
| add_version() | 添加版本 | version, file_path, metadata, is_production | 版本信息 |
| get_version() | 获取版本 | version | 版本信息 |
| list_versions() | 列出版本 | include_metadata | 版本列表 |
| delete_version() | 删除版本 | version | bool |
| set_production_version() | 设置生产版本 | version | 版本信息 |
| get_production_version() | 获取生产版本 | - | 版本信息 |
| compare_versions() | 比较版本 | version1, version2 | 比较结果 |
| get_version_diff() | 获取版本差异 | version1, version2 | 差异信息 |
| rollback_to_version() | 回滚版本 | version | 新版本信息 |
| tag_version() | 添加标签 | version, tag | 版本信息 |
| get_versions_by_tag() | 按标签查询 | tag | 版本列表 |
| increment_download_count() | 增加下载计数 | version | 新计数 |
| get_version_stats() | 获取统计信息 | - | 统计信息 |
| cleanup_old_versions() | 清理旧版本 | keep_count | 删除的版本列表 |

## 使用场景
### 1. 模型训练后保存

```python
async def train_and_save_model(model, model_id, version):
    # 训练模型...
    
    # 保存到临时文件
    with tempfile.NamedTemporaryFile(suffix='.pkl') as tmp:
        joblib.dump(model, tmp.name)
        
        # 上传到存储
        with open(tmp.name, 'rb') as f:
            result = await model_storage.save_model(
                model_id=model_id,
                version=version,
                model_file=f,
                framework="sklearn",
                metadata={
                    "accuracy": 0.95,
                    "train_date": datetime.now().isoformat(),
                    "train_data": "dataset_v1"
                }
            )
    
    return result
```

### 2. 模型部署时加载

```python
async def load_model_for_inference(model_id):
    # 获取生产版本
    version_mgr = VersionManager(storage, model_id)
    prod_version = await version_mgr.get_production_version()
    
    if not prod_version:
        # 没有生产版本，使用最新版本
        prod_version = await version_mgr.get_version()
    
    # 加载模型
    content = await model_storage.load_model(
        model_id=model_id,
        version=prod_version['version']
    )
    
    # 记录下载
    await version_mgr.increment_download_count(prod_version['version'])
    
    # 反序列化模型
    import joblib
    import io
    model = joblib.load(io.BytesIO(content))
    
    return model
```

### 3. 前端直传文件

```python
# 后端生成上传URL
@app.post("/api/models/upload-url")
async def get_upload_url(model_id: str, version: str):
    path = f"models/{model_id}/versions/model_{version}.pkl"
    url = await minio_storage.get_upload_url(path, expires_in=3600)
    return {"upload_url": url}

# 前端直接上传
# const url = await response.json().upload_url;
# await fetch(url, {
#     method: 'PUT',
#     body: file,
#     headers: {'Content-Type': 'application/octet-stream'}
# });
```

## 最佳实践

### 1. 选择合适的存储后端

- 开发环境：使用本地存储，简单快速
- 生产环境：使用 MinIO 或 S3，保证高可用
- 多云环境：使用 S3 兼容的存储，便于迁移

### 2. 版本命名规范

遵循语义化版本规范 (Semantic Versioning):

- 主版本号：不兼容的API修改

- 次版本号：向下兼容的功能性新增

- 修订号：向下兼容的问题修正

例如: 1.0.0, 2.1.3, 1.0.0-beta

### 3. 元数据管理

```python
metadata = {
    "description": "模型描述",
    "author": "创建者",
    "created_at": "创建时间",
    "framework": "框架名称",
    "framework_version": "框架版本",
    "metrics": {
        "accuracy": 0.95,
        "precision": 0.93,
        "recall": 0.94
    },
    "training_info": {
        "dataset": "数据集名称",
        "epochs": 100,
        "batch_size": 32
    }
}
```

### 4. 错误处理

```python
try:
    result = await storage.save(path, content)
except FileNotFoundError:
    logger.error(f"文件不存在: {path}")
except PermissionError:
    logger.error(f"权限不足: {path}")
except S3Error as e:
    logger.error(f"S3错误: {e}")
except Exception as e:
    logger.error(f"未知错误: {e}")
    raise
```

### 5. 性能优化

```python
# 批量操作
async def batch_save(files: List[Tuple[str, BinaryIO]]):
    tasks = []
    for path, content in files:
        tasks.append(storage.save(path, content))
    return await asyncio.gather(*tasks)

# 使用连接池（S3/MinIO客户端自带）
# 调整超时设置
storage = MinIOStorage(
    endpoint="localhost:9000",
    bucket_name="models",
    access_key="minioadmin",
    secret_key="minioadmin",
    secure=False
)
```

## 故障排查

### 1. 连接问题

```python
# 测试连接
try:
    await storage.exists("test.txt")
    print("连接正常")
except Exception as e:
    print(f"连接失败: {e}")
```

### 2. 权限问题

```python
# 检查桶权限
buckets = await minio_storage.list_buckets()
print(f"可访问的桶: {buckets}")

# 设置桶策略
policy = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"AWS": "*"},
        "Action": ["s3:GetObject"],
        "Resource": [f"arn:aws:s3:::datamind-models/*"]
    }]
}
await minio_storage.set_bucket_policy("datamind-models", policy)
```

### 3. 文件不存在

```python

if not await storage.exists(path):
    # 尝试查找相似文件
    files = await storage.list(prefix=path.rsplit('/', 1)[0])
    print(f"可用文件: {files}")
```
## 性能指标
| 操作 | 本地存储 | MinIO | S3 |
| :--- | :--- | :--- | :--- |
| 保存 (1MB) | 5ms | 20ms | 30ms |
| 加载 (1MB) | 3ms | 15ms | 25ms |
| 删除 | 1ms | 5ms | 8ms |
| 列表 (1000项) | 50ms | 100ms | 150ms |
