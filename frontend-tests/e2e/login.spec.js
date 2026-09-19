import { expect, test } from "@playwright/test";

test("用户可以提交登录表单并看到接口错误", async ({ page }) => {
  await page.route("**/api/session", async (route) => {
    await route.fulfill({ status: 401, json: { error: "尚未登录" } });
  });
  await page.route("**/api/login", async (route) => {
    await route.fulfill({ status: 401, json: { error: "用户名或密码错误" } });
  });

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "登录控制台" })).toBeVisible();
  await page.locator("#username").fill("operator");
  await page.locator("#password").fill("wrong-password");
  await page.getByRole("button", { name: "登录" }).click();

  await expect(page.getByRole("alert")).toHaveText("用户名或密码错误");
  await expect(page.getByRole("button", { name: "登录" })).toBeEnabled();
});

test("只读用户看不到未授权的管理操作", async ({ page }) => {
  const user = {
    user_id: "usr_reader",
    username: "reader",
    display_name: "只读用户",
    email: "reader@example.com",
    status: "active",
    roles: ["viewer"],
    permissions: ["model.read", "request.read"],
    effective_permissions: ["model.read", "request.read"],
    environment: "development",
    capabilities: {
      manage_models: false,
      manage_deployments: false,
      manage_routings: false,
      manage_experiments: false,
      manage_identity: false,
      invoke_predictions: false,
      manage_runtime: false,
    },
  };
  const snapshot = {
    generated_at: "2026-09-20T00:00:00Z",
    access: { requests: true, models: true },
    counts: { models: 0 },
    sections: {},
    request_summary: null,
    request_trend: [],
    model_usage: [],
  };

  await page.route("**/api/session", (route) => route.fulfill({ json: user }));
  await page.route("**/api/overview?**", (route) =>
    route.fulfill({ json: snapshot }),
  );
  await page.route("**/api/sections/models?**", (route) =>
    route.fulfill({
      json: {
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
        has_previous: false,
        has_next: false,
      },
    }),
  );
  await page.route("**/api/events", (route) => route.abort());

  await page.goto("/");
  await expect(page.locator("#dashboard-view")).toBeVisible();
  await page.getByRole("button", { name: /模型/ }).click();
  await expect(page.locator("#create-button")).toBeHidden();

  await page.locator("#account-menu-button").click();
  await expect(page.locator("#account-management")).toBeHidden();
  await expect(page.locator("#change-password-button")).toBeVisible();
});
