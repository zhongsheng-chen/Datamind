import { describe, expect, it, vi } from "vitest";
import { createResourceManager } from "../../datamind/console/static/assets/management.js";

function manager(hasCapability = () => false) {
  return createResourceManager({
    state: { selectedExperimentId: null },
    createButton: document.createElement("button"),
    changePasswordButton: document.createElement("button"),
    hasCapability,
    request: vi.fn(),
    sectionIdFields: { experiments: "experiment_id" },
  });
}

describe("experiment actions", () => {
  it("does not offer analysis in the action menu for readers", () => {
    const controller = manager();
    const record = { experiment_id: "exp_demo", status: "running" };
    expect(controller.getRecordActions("experiments", record).map((action) => action.label))
      .toEqual([]);
    const row = document.createElement("tr");
    controller.appendManagementCell(row, "experiments", record);
    expect(row.querySelector("button")).toBeNull();
  });

  it("keeps lifecycle actions and excludes analysis for deleted experiments", () => {
    const controller = manager(() => true);
    expect(controller.getRecordActions("experiments", { experiment_id: "exp_demo", status: "running" }).map((action) => action.label))
      .toEqual(["暂停", "停止", "完成"]);
    expect(controller.getRecordActions("experiments", { experiment_id: "exp_demo", status: "running", deleted_at: "2026-10-09" }).map((action) => action.label))
      .toEqual(["恢复"]);
  });
});
