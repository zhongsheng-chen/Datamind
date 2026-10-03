"""Generate CLI/config references from current definitions; --check detects drift."""

from __future__ import annotations

import argparse
import ast
import importlib
import inspect
import json
import re
import textwrap
from enum import Enum
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[1]
SOURCE_URL = "https://github.com/zhongsheng-chen/Datamind/blob/main/"
GROUPS = {
    "system": (
        "初始化与认证",
        "../getting-started/configuration.md",
        "init/login/logout/whoami/db",
    ),
    "model": ("模型管理", "../models/index.md", "model"),
    "deployment": ("部署管理", "../deployment/full.md", "deployment"),
    "routing": ("路由管理", "../routing/rules.md", "route"),
    "experiment": ("实验管理", "../experiments/index.md", "experiment"),
    "variant": ("实验分组", "../experiments/assignment.md", "experiment variant"),
    "outcome": ("业务结果回流", "../experiments/outcomes.md", "outcome"),
    "identity": ("用户与角色", "../guides/access-control.md", "user/role"),
    "processes": (
        "服务管理",
        "../deployment/processes.md",
        "service/console/runtime",
    ),
}


def cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def value_text(value: Any) -> str:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()  # Only class defaults, never live settings.
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, Path):
        value = str(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def walk(command: Any, path: tuple[str, ...] = ()):
    if hasattr(command, "commands"):
        for name, child in command.commands.items():
            yield from walk(child, (*path, name))
    else:
        yield path, command


def cli_group(path: tuple[str, ...]) -> str:
    if path[:2] == ("experiment", "variant"):
        return "variant"
    return {
        "route": "routing",
        "user": "identity",
        "role": "identity",
        "service": "processes",
        "console": "processes",
        "runtime": "processes",
    }.get(path[0], path[0] if path[0] in GROUPS else "system")


def cli_pages() -> dict[Path, str]:
    from datamind.cli.main import app

    entries = list(walk(typer.main.get_command(app)))
    pages = {}
    index = [
        "# 命令索引",
        "",
        "按命令组查阅参数、默认值与权限。完整操作流程见各组对应指南，生命周期见[状态与权限](../reference/states-permissions.md)。",
        "",
        "```bash",
        "datamind --help",
        "datamind --version",
        "datamind <命令组> <命令> --help",
        "```",
        "",
        "`--help` 可离线查看。认证启用时，资源命令读取本地 CLI 登录凭据；服务启动和数据库迁移属于进程管理，不代替 HTTP 登录。",
        "",
        "多数资源命令提供 `--format text/json`，默认值以各参数表为准。JSON 输出保留资源 ID、状态和业务字段；列表输出通常是 JSON 数组，分页参数控制本次返回范围，不保证返回总数或分页对象。日志可能独立写入 stderr/日志文件，自动化客户端应检查退出码并解析完整 JSON 值。失败时命令退出非零，不能仅根据控制台出现资源 ID 判断成功。",
        "",
        "| 命令组 | 命令数量 |",
        "| --- | --- |",
    ]
    for group, (title, guide, _) in GROUPS.items():
        commands = [(p, c) for p, c in entries if cli_group(p) == group]
        index.append(f"| [{title}]({group}.md) | {len(commands)} |")
        lines = [
            f"# {title}",
            "",
            f"相关说明见[对应文档]({guide})，状态限制见[状态与权限](../reference/states-permissions.md)。",
            "",
            "`<参数名>` 为位置参数，`null` 表示未指定。所有命令支持 `--help`，标记“可重复”的选项可多次传入。",
            "",
        ]
        for path, command in commands:
            callback = inspect.unwrap(command.callback)
            source_path = Path(inspect.getsourcefile(callback)).relative_to(ROOT)
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
            permissions = sorted(
                {
                    kw.value.value
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call)
                    for kw in node.keywords
                    if kw.arg == "required_permission"
                    and isinstance(kw.value, ast.Constant)
                }
            )
            name = "datamind " + " ".join(path)
            lines += [
                f"## {name}",
                "",
                (command.help or "").strip().rstrip(".。") + "。",
                "",
                f"权限：{', '.join(f'`{p}`' for p in permissions) if permissions else '无需资源权限'}",
                "",
                f"[源码]({SOURCE_URL}{source_path.as_posix()})",
                "",
            ]
            positional = [p for p in command.params if p.param_type_name == "argument"]
            usage = (
                name
                + "".join(
                    f" <{p.name}>" if p.required else f" [<{p.name}>]"
                    for p in positional
                )
                + " [OPTIONS]"
            )
            lines += [
                "```text",
                usage,
                "```",
                "",
                "| 参数 | 类型 | 必需 | 默认值 | 说明 |",
                "| --- | --- | --- | --- | --- |",
            ]
            if not command.params:
                lines = lines[:-2]
                lines += ["无额外参数。", ""]
            for p in command.params:
                opts = "/".join([*p.opts, *getattr(p, "secondary_opts", [])])
                if p.param_type_name == "argument":
                    opts = "<" + p.name + ">"
                kind = {
                    "text": "字符串",
                    "integer": "整数",
                    "float": "数值",
                    "boolean": "布尔",
                    "path": "路径",
                    "integer range": "整数范围",
                }.get(getattr(p.type, "name", "text"), getattr(p.type, "name", "text"))
                choices = getattr(p.type, "choices", None)
                if choices:
                    kind = "/".join(
                        str(x.value if isinstance(x, Enum) else x) for x in choices
                    )
                if getattr(p, "multiple", False):
                    kind += "（可重复）"
                default = "—" if p.required else value_text(p.default)
                lines.append(
                    f"| `{cell(opts)}` | {cell(kind)} | {'是' if p.required else '否'} | `{cell(default)}` | {cell(getattr(p, 'help', '') or '')} |"
                )
            errors = []
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and node.exc.args
                ):
                    arg = node.exc.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value not in errors:
                            errors.append(arg.value)
            if errors:
                lines += ["", "输入校验：", ""] + ["- " + cell(e) for e in errors]
            # Collect explicitly constructed result objects, not request/config dictionaries.
            keys = set()
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Assign)
                    and any(
                        isinstance(t, ast.Name) and t.id == "result"
                        for t in node.targets
                    )
                    and isinstance(node.value, ast.Dict)
                ):
                    keys.update(
                        k.value
                        for k in node.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)
                    )
            if keys:
                lines += [
                    "",
                    "输出对象字段：" + "、".join(f"`{k}`" for k in sorted(keys)) + "。",
                ]
            lines += [""]
        pages[ROOT / "docs/cli" / f"{group}.md"] = "\n".join(lines).rstrip() + "\n"
    index += [
        "",
        "## JSON 输出约定",
        "",
        "以下展示模型注册响应的关键字段（省略存储等字段）；资源 ID 是后续命令的输入，业务版本与制品修订分别保留：",
        "",
        "```json",
        '{"name":"scorecard-demo","model_id":"<model_id>","version":"1.0.0","version_id":"<version_id>","artifact_id":"<artifact_id>","artifact_revision":1,"action":"created"}',
        "```",
        "",
        "注册 `action` 为 `created`、`revised` 或 `unchanged`。模型 `list` 的 JSON 为数组，`show` 为对象；部署创建/查询保留 `deployment_id`、版本、环境、`rollout_type`、`role` 与 `status`；路由保留 `routing_id`、`deployment_id`、比例及启用状态；实验与分组保留各自 ID、状态和配置；业务结果输出包含原始决策归属。字段随资源命令而异，不能把某个示例当作所有命令的统一响应。",
        "",
        "init、login、logout、whoami 和进程启动命令没有 --format 参数。用户创建与密码重置会交互读取密码，--format json 不会取消交互。自动化应先查看该命令是否具备无交互参数。",
        "",
        f"当前共 {len(entries)} 个叶子命令。新增或修改命令后运行 `python -m scripts.generate_docs_reference` 更新，使用 `--check` 检查文档与定义是否一致。",
        "",
    ]
    pages[ROOT / "docs/cli/index.md"] = "\n".join(index)
    return pages


def schema_type(prop: dict, schema: dict) -> str:
    if "$ref" in prop:
        target = prop["$ref"].rsplit("/", 1)[-1]
        definition = schema.get("$defs", {}).get(target, {})
        if "enum" not in definition:
            return target
        prop = definition
    if "enum" in prop:
        return "/".join(str(item) for item in prop["enum"])
    if "anyOf" in prop:
        return " | ".join(schema_type(item, schema) for item in prop["anyOf"])
    if "const" in prop:
        return str(prop["const"])
    kind = prop.get("type", "any")
    if kind == "array":
        return "array[" + schema_type(prop.get("items", {}), schema) + "]"
    return kind + (f" ({prop['format']})" if "format" in prop else "")


def api_pages() -> dict[Path, str]:
    from datamind.runtime.server import schemas

    lines = [
        "# 请求字段",
        "",
        "HTTP 封装、响应与错误见 [预测 API](runtime-api.md)。请求仅接受下表声明的字段，字符串会去除首尾空白。",
        "",
    ]
    for name, cls in vars(schemas).items():
        if (
            not inspect.isclass(cls)
            or cls.__module__ != schemas.__name__
            or not issubclass(cls, BaseModel)
            or name == "RuntimeRequest"
        ):
            continue
        schema = cls.model_json_schema()
        lines += [
            f"## {name}",
            "",
            "| 字段 | 类型 | 必需 | 默认值 | 约束 |",
            "| --- | --- | --- | --- | --- |",
        ]
        for field, info in cls.model_fields.items():
            prop = schema["properties"][field]
            constraints = []
            for variant in [prop, *prop.get("anyOf", [])]:
                constraints.extend(
                    f"{key}={value}"
                    for key, value in variant.items()
                    if key
                    in {
                        "minLength",
                        "maxLength",
                        "minItems",
                        "maxItems",
                        "minProperties",
                        "minimum",
                        "maximum",
                    }
                )
            default = (
                "—"
                if info.is_required()
                else value_text(info.get_default(call_default_factory=False))
            )
            lines.append(
                f"| `{field}` | `{cell(schema_type(prop, schema))}` | {'是' if info.is_required() else '否'} | `{cell(default)}` | {cell(', '.join(constraints))} |"
            )
        lines += [""]
    return {ROOT / "docs/reference/runtime-schemas.md": "\n".join(lines)}


CONFIG_TITLES = {
    "AuditConfig": "审计",
    "AuthConfig": "认证",
    "LocalAuthConfig": "本地认证",
    "ClassificationConfig": "分类预测",
    "ScoringConfig": "评分预测",
    "ConsoleConfig": "管理控制台",
    "DatabaseConfig": "数据库",
    "InitializationConfig": "初始化",
    "LoggingConfig": "日志",
    "RuntimeConfig": "运行协调与影子预测",
    "ServiceConfig": "预测服务",
    "StorageConfig": "制品存储",
    "LocalStorageConfig": "本地存储",
    "MinIOStorageConfig": "MinIO 存储",
    "TaskQueueConfig": "任务队列",
    "TaskWorkerConfig": "任务 Worker",
}


def documented_attributes(docstring: str | None) -> dict[str, str]:
    """Read attribute and multiline environment-variable doc entries."""
    lines = (docstring or "").splitlines()
    descriptions = {}
    for index, line in enumerate(lines):
        match = re.match(r"\s*-\s*([a-zA-Z_][a-zA-Z_0-9]*):\s*(.*)$", line)
        if not match:
            continue
        key, description = match.groups()
        if not description and index + 1 < len(lines):
            continuation = lines[index + 1]
            if continuation.startswith(" ") and not continuation.lstrip().startswith(
                "-"
            ):
                description = continuation.strip()
        if description:
            descriptions[key] = re.sub(r"[，,]\s*默认.*$", "", description)
    return descriptions


def config_description(cls: type[BaseSettings], field: str, info: Any) -> str:
    """Require a description from source; never silently document an empty cell."""
    module = inspect.getmodule(cls)
    class_docs = documented_attributes(cls.__doc__)
    module_docs = documented_attributes(module.__doc__ if module else None)
    env_name = cls.model_config["env_prefix"] + field.upper()
    description = (
        info.description
        or class_docs.get(field)
        or module_docs.get(field)
        or module_docs.get(env_name)
    )
    if not description:
        raise ValueError(f"Missing configuration description: {cls.__name__}.{field}")
    # Units supplement existing source documentation without changing config fields.
    units = {
        ("LoggingConfig", "max_bytes"): "单位：字节。",
        ("LocalAuthConfig", "lock_minutes"): "单位：分钟。",
        ("LocalAuthConfig", "break_glass_access_token_expires_minutes"): "单位：分钟。",
        ("AuthConfig", "access_token_expires_minutes"): "单位：分钟。",
        ("AuthConfig", "refresh_token_expires_days"): "单位：天。",
    }
    note = units.get((cls.__name__, field), "")
    return description.rstrip("。") + "。" + note


def config_pages() -> dict[Path, str]:
    lines = [
        "# 配置参考",
        "",
        "按功能查阅环境变量、用途、默认值与校验规则。首次配置见[配置与初始化](../getting-started/configuration.md)。",
        "",
        "配置优先级从高到低为：显式构造参数、环境变量、工作目录 `.env`、默认值。CLI、Runtime、Console 与任务 Worker 使用相同的部署配置，修改后重启相关进程。嵌套配置使用独立前缀，例如 `DATAMIND_STORAGE_MINIO_`。",
        "",
        '列表使用 JSON，例如 `DATAMIND_AUTH_LOCAL_ALLOWED_NETWORKS=["127.0.0.0/8"]`。相对路径以进程工作目录为起点。数据库 URL 必须填写，选择 MinIO 时填写访问密钥，启用认证时填写签名密钥。',
        "",
    ]
    count = 0
    for path in sorted((ROOT / "datamind/config").glob("*.py")):
        if path.stem in {"__init__", "settings", "providers"}:
            continue
        module = importlib.import_module("datamind.config." + path.stem)
        for name, cls in vars(module).items():
            if (
                not inspect.isclass(cls)
                or cls.__module__ != module.__name__
                or not issubclass(cls, BaseSettings)
            ):
                continue
            schema = cls.model_json_schema()
            props = schema["properties"]
            lines += [
                f"## {CONFIG_TITLES.get(name, name)}",
                "",
                f"前缀：`{cls.model_config['env_prefix']}`。[源码]({SOURCE_URL}datamind/config/{path.name})",
                "",
                "| 环境变量 | 类型 | 默认值 | 说明 |",
                "| --- | --- | --- | --- |",
            ]
            for field, info in cls.model_fields.items():
                if inspect.isclass(info.annotation) and issubclass(
                    info.annotation, BaseSettings
                ):
                    continue
                prop = props[field]
                annotation = schema_type(prop, schema)
                default = (
                    "必需"
                    if info.is_required()
                    else value_text(info.get_default(call_default_factory=False))
                )
                lines.append(
                    f"| `{cls.model_config['env_prefix']}{field.upper()}` | `{cell(annotation)}` | `{cell(default)}` | {cell(config_description(cls, field, info))} |"
                )
                count += 1
            class_tree = ast.parse(textwrap.dedent(inspect.getsource(cls)))
            validators = []
            for node in ast.walk(class_tree):
                if (
                    isinstance(node, ast.Raise)
                    and isinstance(node.exc, ast.Call)
                    and node.exc.args
                ):
                    a = node.exc.args[0]
                    msg = (
                        a.value
                        if isinstance(a, ast.Constant)
                        else "".join(
                            x.value for x in a.values if isinstance(x, ast.Constant)
                        )
                        if isinstance(a, ast.JoinedStr)
                        else ""
                    )
                    if msg and msg not in validators:
                        validators.append(msg.split("当前值")[0].rstrip("，:： "))
            if validators:
                lines += ["", "校验规则：", ""] + ["- " + cell(v) for v in validators]
            lines += [""]
    lines += [
        "## 运行时依赖",
        "",
        "数据库连接必须指向 PostgreSQL（异步驱动 URL 使用 `postgresql+asyncpg://`）。选择 local 存储时所有加载进程必须能访问同一制品目录；选择 MinIO 时 endpoint 不带协议，TLS 由 `secure` 控制。",
        "",
        "Task Queue 的 batch/shadow 队列必须不同。Runtime 和任务 Worker 使用相同 Broker URL 和队列名称，`visibility_timeout_seconds` 应覆盖任务运行时长。批量切片大小与 Celery 进程并发是两个不同设置。",
        "",
        "日志的时区影响 CLI 时间显示和日志格式；数据库持久化时刻按时区感知时间处理。审计 `failure_mode=open` 允许业务在审计失败时继续，`closed` 会阻止受审计操作；此设置不同于关闭审计。",
        "",
        f"共 {count} 个环境变量。初始化步骤见[配置与初始化](../getting-started/configuration.md)，部署约束见[生产部署](../deployment/production.md)。",
        "",
    ]
    return {ROOT / "docs/reference/configuration.md": "\n".join(lines)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    pages = {**cli_pages(), **config_pages(), **api_pages()}
    changed = []
    for path, text in pages.items():
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            changed.append(path.relative_to(ROOT).as_posix())
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
    if args.check and changed:
        raise SystemExit("Reference drift: " + ", ".join(changed))
    print(f"{len(pages)} reference pages " + ("checked" if args.check else "generated"))


if __name__ == "__main__":
    main()
