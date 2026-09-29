# 安装

Datamind 支持 Python 3.12、3.13 和 3.14。

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

Datamind 使用 PostgreSQL 保存平台数据。批量任务、影子预测和模型对象存储等能力还会根据部署方式使用 Redis、MinIO 等外部基础设施。

完整配置项以仓库根目录的 [`.env.example`](https://github.com/zhongsheng-chen/Datamind/blob/main/.env.example) 为准。

完成安装后，继续阅读 [快速上手](quickstart.md)。
