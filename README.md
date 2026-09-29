<h1 align="center">Datamind</h1>

<p align="center">
  <strong>开放式模型服务管理平台</strong>
</p>

<p align="center">
  将模型交付为可管理、可部署、可调用、可审计的生产服务。
</p>

<p align="center">
  <a href="https://github.com/zhongsheng-chen/Datamind/actions/workflows/test.yml">
    <img alt="Tests" src="https://github.com/zhongsheng-chen/Datamind/actions/workflows/test.yml/badge.svg?branch=main">
  </a>
  <a href="https://datamind.readthedocs.io/">
    <img alt="Documentation" src="https://readthedocs.org/projects/datamind/badge/?version=latest">
  </a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12%20%7C%203.13%20%7C%203.14-blue">
  <a href="https://github.com/zhongsheng-chen/Datamind/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/badge/License-Apache%202.0-green.svg">
  </a>
</p>

<p align="center">
  <a href="https://datamind.readthedocs.io/"><strong>文档</strong></a> ·
  <a href="#quick-start"><strong>快速开始</strong></a> ·
  <a href="#capabilities"><strong>核心能力</strong></a> ·
  <a href="#model-support"><strong>模型支持</strong></a> ·
  <a href="https://github.com/zhongsheng-chen/Datamind/tree/main/examples"><strong>示例</strong></a>
</p>

---

## Datamind 是什么

Datamind 是一个开放式模型服务管理平台，专注于模型训练完成后的交付与运行。它连接模型开发与生产运行，让开发成果能够直接转化为生产服务。平台支持多框架、多任务和多算法，将复杂的交付、运行与治理沉淀为稳定的平台能力。

<a id="capabilities"></a>

## 核心能力

- **多框架、多任务、多算法**：支持不同模型技术栈，保持一致的交付与运行方式。
- **渐进式模型发布**：支持全量、金丝雀和影子发布，让模型上线与切换更加可控。
- **在线与批量推理**：支持实时预测和批量预测，满足不同生产运行场景。
- **在线实验与评估**：支持 A/B 实验、稳定分桶和流量分配，用于真实流量下的模型效果评估。
- **全生命周期治理**：提供权限控制、操作审计和运行状态管理，让模型服务可追踪、可管理。

<a id="quick-start"></a>

## 快速开始

安装 scikit-learn 与评分卡支持：

```bash
python -m pip install "pydatamind[sklearn]"
```

安装全部模型框架：

```bash
python -m pip install "pydatamind[full]"
```

确认 CLI：

```bash
datamind --version
datamind --help
```

完成数据库与运行环境配置后，启动 Runtime Service 和管理控制台：

```bash
datamind service run
datamind console run
```

默认端口：

```text
Runtime API   http://127.0.0.1:8700
Console       http://127.0.0.1:8701
```

更多安装、配置与部署说明见 [Datamind Documentation](https://datamind.readthedocs.io/)。

<a id="model-support"></a>

## 模型支持

| Extra | Framework | Model Type |
| --- | --- | --- |
| `sklearn` | scikit-learn | `logistic_regression`、`decision_tree`、`random_forest` |
| `xgboost` | XGBoost | `xgboost` |
| `lightgbm` | LightGBM | `lightgbm` |
| `catboost` | CatBoost | `catboost` |
| `full` | 全部框架 | 全部模型类型 |

当前支持两类任务：

- **classification** — 返回分类结果与概率。
- **scoring** — 返回信用评分、违约概率、特征分和截距分。

评分任务当前使用 scikit-learn 体系的逻辑回归评分卡；其他模型类型用于分类任务。

## Docker 镜像

Datamind 的 Docker 镜像发布于 Docker Hub：

```text
docker.io/zhongshengchen/datamind:latest
```

Docker 镜像、Docker Compose 及相关配置见 [Docker 部署文档](https://datamind.readthedocs.io/en/latest/deployment/docker/)。

## 文档

[**Datamind Documentation →**](https://datamind.readthedocs.io/)

安装 · 快速上手 · 架构 · Docker 部署

## 开发

安装开发环境：

```bash
python -m pip install -e ".[test,full,release]"
npm ci
```

常用入口：

```bash
make test
make test-framework
make frontend-test
make build
```

## License

Datamind 使用 [Apache License 2.0](LICENSE)。
