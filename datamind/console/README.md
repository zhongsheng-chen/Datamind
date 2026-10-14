# Console 开发

产品操作、截图、账户与权限见 [ReadTheDocs Console 手册](https://datamind.readthedocs.io/en/latest/guides/console/)。前端构建、测试和资源交付见 [前端开发](../../docs/development/frontend.md)。

源码位于 static/，构建产物位于 dist/。在项目根目录使用推荐的 Node.js 24：

```bash
npm ci
npm run build:console
npm run watch:console
```

watch 持续构建前端；`datamind console run --reload` 重载 Python，不替代前端构建。不要直接编辑 dist 生成文件。运行后端 Console 测试前准备构建产物。

HTTP 后端与管理动作修改需同时检查认证、权限、审计及相应 tests/console 用例。正式发布资源随 Wheel/镜像交付，流程见 [构建与 Release](../../docs/development/release.md)。
