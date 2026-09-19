import { describe, expect, it } from "vitest";

import {
  formatDuration,
  formatModelType,
  formatNavigationCount,
  formatOptionalDuration,
  formatPercentage,
  formatScore,
  formatTaskType,
  statusTone,
} from "../../datamind/console/static/assets/format.js";

describe("console formatters", () => {
  it("formats model and task domain values", () => {
    expect(formatModelType("logistic_regression")).toBe("逻辑回归");
    expect(formatTaskType("classification")).toBe("分类");
    expect(formatModelType("custom")).toBe("custom");
    expect(formatTaskType(null)).toBe("—");
  });

  it("formats numeric values without leaking invalid numbers", () => {
    expect(formatNavigationCount(999)).toBe("999");
    expect(formatNavigationCount(1200)).toBe("1.2k");
    expect(formatDuration("12.345")).toBe("12.35");
    expect(formatOptionalDuration(null)).toBe("—");
    expect(formatPercentage(0.125)).toBe("12.50%");
    expect(formatScore(1.2)).toBe("1.20");
  });

  it("maps execution states to semantic tones", () => {
    expect(statusTone("failed")).toBe("danger");
    expect(statusTone("queued")).toBe("warning");
    expect(statusTone("running")).toBe("success");
    expect(statusTone("received")).toBe("info");
  });
});
