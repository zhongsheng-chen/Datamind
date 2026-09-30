# CLI 开发

正式命令手册位于 [ReadTheDocs CLI Reference](https://datamind.readthedocs.io/en/latest/cli/)，本地源文件为 [docs/cli](../../docs/cli/index.md)。任务流程见 [使用指南](https://datamind.readthedocs.io/en/latest/guides/models/)。

命令入口在 main.py，各命令组分目录维护。参数解析、身份上下文和输出放在 CLI，共享业务约束放在 Service。开发步骤见 [数据库与扩展](../../docs/development/extensions.md)。

在项目根目录安装 `.[test]`，修改后运行相关 `tests/cli/` 用例。新增或变更命令时执行：

```bash
python -m scripts.generate_docs_reference
python -m scripts.generate_docs_reference --check
```

生成器读取当前 Typer 定义，不需要启动数据库或服务。不要在此重复维护参数表和产品操作手册。
