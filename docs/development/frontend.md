# 前端开发

Console 前端源码位于 `datamind/console/static/`，通过项目根目录的 Vite 配置构建。

## 构建与持续构建

```bash
npm ci
npm run build:console
npm run watch:console
```

`watch:console` 在源码变更时持续构建。生产打包依赖构建产物，源码运行 Console 前也需要准备前端资源。

## 静态检查与测试

```bash
npm run lint:console
npm run test:frontend
npm run test:e2e
```

前端单元测试位于 `frontend-tests/unit/`，浏览器测试位于 `frontend-tests/e2e/`。Linux/macOS 安装 Chromium 后运行浏览器测试：

```bash
npx playwright install chromium
npm run test:e2e
```

Linux 缺少浏览器系统库时可使用 Playwright 的 `install --with-deps chromium` 安装。Windows 配置使用 msedge，需要本机 Edge。playwright.config.js 自动构建 Console 并启动 Vite preview（127.0.0.1:4173），可以复用已有 preview 服务，失败时保留 trace。

这里验证前端行为，测试中的 API fixture 不等于真实后端完整验证。实际产品链路还需后端 E2E 或真实 Console 环境。

## 资源交付

Vite 入口为 datamind/console/static，构建输出 datamind/console/dist，并生成 .vite/manifest.json。Wheel 打包 dist/index.html、assets 和 manifest，源码目录不是发布资源的替代。修改页面后检查开发构建、Vitest、ESLint 与相关浏览器用例。正式发行前用 Wheel/镜像运行 Console 核对资源加载。

Console 产品操作见[Console 使用](../guides/console.md)。
