import { afterEach, describe, expect, it, vi } from "vitest";

import { enhanceOrganizationSelect } from "../../datamind/console/static/assets/organization/select.js";

function setup() {
  const dialog = document.createElement("dialog");
  const select = document.createElement("select");
  select.name = "department_id";
  select.append(
    new window.Option("未设置", ""),
    new window.Option("人力资源部", "hr"),
    new window.Option("＋ 创建部门", "__create__"),
  );
  select.value = "hr";
  dialog.append(select);
  document.body.append(dialog);
  const controller = enhanceOrganizationSelect(select, dialog);
  const trigger = dialog.querySelector(".organization-select-trigger");
  const menu = dialog.querySelector(".organization-select-menu");
  return { dialog, select, trigger, menu, controller };
}

afterEach(() => {
  for (const dialog of document.querySelectorAll("dialog")) dialog.dispatchEvent(new Event("close"));
  document.body.replaceChildren();
});

describe("组织归属自定义下拉框", () => {
  it("显示当前选择及勾选，选择后同步原表单字段", () => {
    const { select, trigger, menu } = setup();
    const change = vi.fn();
    select.addEventListener("change", change);
    expect(select.hidden).toBe(true);
    expect(trigger.textContent).toBe("人力资源部");
    trigger.click();
    expect(menu.hidden).toBe(false);
    expect(menu.querySelector('[aria-selected="true"]').textContent).toContain("人力资源部");
    menu.querySelector('[role="option"]').click();
    expect(select.value).toBe("");
    expect(trigger.textContent).toBe("未设置");
    expect(change).toHaveBeenCalledOnce();
    expect(menu.hidden).toBe(true);
  });

  it("方向键导航，Escape 仅关闭下拉框", () => {
    const { dialog, trigger, menu } = setup();
    trigger.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    expect(document.activeElement.textContent).toContain("人力资源部");
    menu.dispatchEvent(new window.KeyboardEvent("keydown", { key: "End", bubbles: true }));
    expect(document.activeElement.textContent).toBe("＋ 创建部门");
    const parentKey = vi.fn();
    dialog.addEventListener("keydown", parentKey);
    menu.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(parentKey).not.toHaveBeenCalled();
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(trigger);
  });

  it("新增操作独立于选项列表，禁用状态和选项更新保持同步", () => {
    const { select, trigger, menu, controller } = setup();
    select.options[2].disabled = true;
    controller.sync();
    const action = menu.querySelector(".organization-select-create");
    expect(action.disabled).toBe(true);
    expect(action.closest('[role="listbox"]')).toBeNull();
    select.append(new window.Option("财务部", "finance"));
    select.value = "finance";
    controller.sync();
    expect(trigger.textContent).toBe("财务部");
    trigger.click();
    document.body.click();
    expect(menu.hidden).toBe(true);
  });
});
