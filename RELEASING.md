# 发布入口

版本、构建身份、Python 包、框架镜像与 CI 发布顺序统一维护在 [ReadTheDocs 构建与 Release](https://datamind.readthedocs.io/en/latest/development/release/)，本地源文件为 [docs/development/release.md](docs/development/release.md)。

发布实现位于 scripts/release.py、build_support/ 与 .github/workflows/release.yml。修改发布行为时同步正式文档，并验证最终 Wheel 和镜像；不要在这里维护另一套发布流程。
