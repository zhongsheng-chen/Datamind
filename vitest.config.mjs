import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["frontend-tests/unit/**/*.test.js"],
    restoreMocks: true,
  },
});
