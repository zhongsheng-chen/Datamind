# 前端开发

管理控制台的前端源码位于 `datamind/console/static/`，使用项目根目录的 Vite 配置构建。开发环境准备请参阅[开发指南](index.md)，控制台的启动方式请参阅[本地部署](../deployment/local.md#启动服务)。

## 构建与持续构建

在项目根目录安装前端依赖并构建资源：

```bash
npm ci
npm run build:console
```

开发时，可使用持续构建，在源码变更后自动更新资源：

```bash
npm run watch:console
```

管理控制台读取构建后的资源，首次从源码启动前须完成构建。

## 静态检查与测试

运行静态检查和单元测试：

```bash
npm run lint:console
npm run test:frontend
```

单元测试位于 `frontend-tests/unit/`。开发时可使用 `npm run test:frontend:watch` 持续测试。

运行浏览器测试：

```bash
npm run test:e2e
```

首次运行前，请准备对应的浏览器：

- **Linux 和 macOS**：使用 `npx playwright install chromium` 安装 Chromium；如需同时安装 Linux 系统依赖，可使用 `npx playwright install --with-deps chromium`。
- **Windows**：安装 Microsoft Edge。

浏览器测试位于 `frontend-tests/e2e/`。Playwright 自动构建前端并启动预览服务，失败时保留 trace。测试使用模拟 API 响应，真实后端的完整流程需单独验证，具体请参阅[测试指南](testing.md)。

## 资源交付

Vite 构建生成的前端资源随 Wheel 包发布，具体流程请参阅[构建与 Release](release.md)。

- **构建目录**：前端源码位于 `datamind/console/static/`，构建后生成的文件保存至 `datamind/console/dist/`。
- **交付验证**：修改后完成构建、静态检查及相关测试；发布前使用构建后的 Wheel 或镜像启动管理控制台，确认页面与静态资源正常加载。
