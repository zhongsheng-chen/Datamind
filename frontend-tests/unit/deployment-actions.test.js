import { describe, expect, it, vi } from "vitest";
import { createResourceManager } from "../../datamind/console/static/assets/management.js";

function actions(record, canManage = true) {
  const controller = createResourceManager({
    state: {},
    createButton: document.createElement("button"),
    changePasswordButton: document.createElement("button"),
    hasCapability: () => canManage,
    request: vi.fn(),
    sectionIdFields: { deployments: "deployment_id" },
  });
  return controller.getRecordActions("deployments", {
    deployment_id: "dep_demo", status: "active", role: "champion",
    rollout_type: "full", is_default: false, ...record,
  }).map(action => action.action);
}

describe("default deployment actions", () => {
  it("offers an explicit switch for enabled champions", () => {
    expect(actions({})).toContain("set-default");
    expect(actions({})).toContain("disable");
    expect(actions({ is_default: true })).toContain("unset-default");
    expect(actions({ is_default: true })).not.toContain("set-default");
  });

  it.each([
    { status: "inactive" },
    { role: "challenger", rollout_type: "canary" },
    { role: "shadow", rollout_type: "shadow" },
    { deleted_at: "2026-10-12" },
  ])("does not offer a default switch for an ineligible deployment %j", record => {
    expect(actions(record)).not.toContain("set-default");
  });

  it("hides default switches from readers", () => {
    expect(actions({}, false)).toEqual([]);
  });
});
