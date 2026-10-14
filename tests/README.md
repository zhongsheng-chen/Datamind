# 测试目录

分层、基础设施参数、隔离、CI 和 Smoke 操作统一维护在 [ReadTheDocs 测试指南](https://datamind.readthedocs.io/en/latest/development/testing/)，本地源文件为 [docs/development/testing.md](../docs/development/testing.md)。

unit/ 验证局部逻辑，services/ 验证共享业务约束，cli/ 和 console/ 验证入口。integration/、e2e/、smoke/ 分别覆盖真实组件、完整后端链路和交付物；前端测试位于项目根目录 frontend-tests/。

新增测试优先选择能够验证实际行为的最低层级。真实基础设施使用专用数据库、Redis DB 和桶，沿用 conftest 的隔离与清理机制。缺少参数导致 skipped 时不能报告为集成验证通过。

在项目根目录安装 `.[test]` 后可运行具体用例：

```bash
python -m pytest -ra tests/cli
```

框架用例安装对应 extra，打包验证安装 `.[release]`。完整运行条件见正式指南，不在本文件重复维护连接模板和发布命令。
