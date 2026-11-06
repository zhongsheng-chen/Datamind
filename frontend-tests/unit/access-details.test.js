import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createAccessDetailController } from "../../datamind/console/static/assets/details/access.js";

function showRole(permissions) {
  const controller = createAccessDetailController({
    createCopyableSectionNavigationLink: value => document.createTextNode(value),
    createStatusBadge: value => Object.assign(document.createElement("span"), { textContent: value }),
    formatTime: value => value || "—",
  });
  controller.showRoleDrawer({ role_id: "role_test", name: "editor", status: "active", permissions });
  return [...document.querySelectorAll(".registry-detail-section")];
}

beforeEach(() => {
  HTMLDialogElement.prototype.showModal = function () {
    this.open = true;
  };
});

afterEach(() => {
  document.body.replaceChildren();
  window.history.replaceState(null, "", "#roles");
  vi.restoreAllMocks();
  delete HTMLDialogElement.prototype.showModal;
});

describe("角色权限详情", () => {
  it("权限独立分组，保留全部原始标识", () => {
    const [basic, permissions] = showRole(["model.read", "model.write", "runtime.manage", "prediction.invoke"]);
    expect([...basic.querySelectorAll("dt")].map(item => item.textContent)).not.toContain("权限");
    expect([...permissions.querySelectorAll("dt")].map(item => item.textContent)).toEqual(["模型", "运行时", "预测"]);
    expect([...permissions.querySelectorAll("code")].map(item => item.textContent))
      .toEqual(["model.read", "model.write", "runtime.manage", "prediction.invoke"]);
    expect(permissions.querySelector("dd").querySelectorAll("code")).toHaveLength(2);
    expect(permissions.querySelector("dd").textContent).toBe("model.read, model.write");
  });

  it("通配符与未知资源保持原始授权含义", () => {
    const [, permissions] = showRole(["*", "custom.read"]);
    expect([...permissions.querySelectorAll("dt")].map(item => item.textContent)).toEqual(["全局权限", "custom"]);
    expect([...permissions.querySelectorAll("code")].map(item => item.textContent)).toEqual(["*", "custom.read"]);
  });

  it.each([[[]], [null]])("无权限时显示明确空状态：%s", value => {
    const [, permissions] = showRole(value);
    expect(permissions.textContent).toContain("暂无权限");
    expect(permissions.querySelectorAll("code")).toHaveLength(0);
  });
});
