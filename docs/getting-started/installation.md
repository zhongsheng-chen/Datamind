# 安装

建议使用 Python 3.12 和 PostgreSQL 17，其中 Python 支持 `>=3.12,<3.15`。

## 使用 pip 安装

按需要选择模型框架对应的 extra。

### scikit-learn

```bash
python -m pip install "pydatamind[sklearn]"
```

### XGBoost

```bash
python -m pip install "pydatamind[xgboost]"
```

### LightGBM

```bash
python -m pip install "pydatamind[lightgbm]"
```

### CatBoost

```bash
python -m pip install "pydatamind[catboost]"
```

### 全部框架

```bash
python -m pip install "pydatamind[full]"
```

## 验证安装

```bash
datamind --version
datamind --help
```

Python 中的导入名保持为：

```python
import datamind
```

## 基础设施

| 依赖 | 是否必需 | 用途 |
| --- | --- | --- |
| Python | 必需 | CLI 与应用运行 |
| PostgreSQL | 必需 | 保存平台数据 |
| Redis | 按功能使用 | 批量预测、影子预测的任务 Broker |
| MinIO | 按存储方式使用 | 对象存储；默认也可使用本地存储 |
| Node.js | 从源码构建 Console 时 | 推荐 Node.js 24；安装发行包无需本地构建前端 |

CI 当前基础设施镜像为 PostgreSQL 17.11、Redis 8.8.2、MinIO `RELEASE.2025-09-07T16-13-09Z`，这些版本是验证依据，并非最低兼容版本承诺。

## 从源码安装

```bash
git clone https://github.com/zhongsheng-chen/Datamind.git
cd Datamind
python -m pip install -e ".[sklearn]"
```

如需运行管理控制台，先构建前端资源：

```bash
npm ci
npm run build:console
```

完整配置项以仓库根目录的 [`.env.example`](https://github.com/zhongsheng-chen/Datamind/blob/main/.env.example) 为准。

完成安装后，继续阅读[配置与初始化](configuration.md)，再按[快速上手](quickstart.md)交付第一个模型服务。
