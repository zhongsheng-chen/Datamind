/// <reference types="node" />

const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./frontend-tests/e2e",
  use: {
    baseURL: "http://127.0.0.1:4173",
    browserName: "chromium",
    channel: process.platform === "win32" ? "msedge" : undefined,
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run build:console && npx vite preview --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173",
    reuseExistingServer: true,
  },
});
