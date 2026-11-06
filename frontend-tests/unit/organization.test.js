import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  bindDepartmentOptions,
  bindUserOrganizationOptions,
  departmentOptions,
  userOrganizationFields,
} from "../../datamind/console/static/assets/organization/forms.js";

import { createOrganizationPage } from "../../datamind/console/static/assets/organization/page.js";

const pages = [];
async function openOrganizationPage(dependencies) {
  const container = document.createElement("section");
  container.className = "organization-page";
  document.body.append(container);
  const page = createOrganizationPage({ ...dependencies, container });
  pages.push(page);
  await page.show();
  return page;
}

function selectNode(id) {
  document.querySelector(`[data-select-id="${id}"]`).click();
}

function chooseMoreAction(label) {
  document.querySelector(".organization-page-more summary").click();
  [...document.querySelectorAll('[role="menuitem"]')].find(item => item.textContent === label).click();
}

const directory = {
  organizations: [
    { organization_id: "org_hq", name: "总行", code: "HQ", is_active: true },
    { organization_id: "org_branch", name: "分行", code: "BRANCH", is_active: true },
  ],
  departments: [
    {
      department_id: "dpt_hr",
      organization_id: "org_hq",
      parent_id: null,
      name: "人力资源部",
      code: "HR",
      is_active: true,
      is_available: true,
      path: [{ department_id: "dpt_hr", name: "人力资源部", code: "HR" }],
    },
    {
      department_id: "dpt_recruitment",
      organization_id: "org_hq",
      parent_id: "dpt_hr",
      name: "招聘组",
      code: "RECRUITMENT",
      is_active: true,
      is_available: true,
      path: [
        { department_id: "dpt_hr", name: "人力资源部", code: "HR" },
        { department_id: "dpt_recruitment", name: "招聘组", code: "RECRUITMENT" },
      ],
    },
    {
      department_id: "dpt_branch_hr",
      organization_id: "org_branch",
      parent_id: null,
      name: "人力资源部",
      code: "HR",
      is_active: true,
      is_available: true,
      path: [{ department_id: "dpt_branch_hr", name: "人力资源部", code: "HR" }],
    },
  ],
};

describe("组织归属选择", () => {
  it("只提供所属机构的部门，展示完整路径", () => {
    expect(departmentOptions(directory.departments, "org_hq")).toEqual([
      ["dpt_hr", "人力资源部"],
      ["dpt_recruitment", "人力资源部 / 招聘组"],
    ]);
  });

  it("编辑上级部门时排除自身和下级部门", () => {
    expect(departmentOptions(
      directory.departments,
      "org_hq",
      "dpt_hr",
    )).toEqual([]);
  });

  it("切换机构后清除原部门，只显示新机构的部门", () => {
    const dialog = document.createElement("dialog");
    const organization = document.createElement("select");
    organization.name = "organization_id";

    for (const item of directory.organizations) {
      const option = document.createElement("option");
      option.value = item.organization_id;
      organization.append(option);
    }

    const department = document.createElement("select");
    department.name = "department_id";
    const selectedDepartment = document.createElement("option");
    selectedDepartment.value = "dpt_recruitment";
    selectedDepartment.textContent = "人力资源部 / 招聘组";
    department.append(selectedDepartment);
    dialog.append(organization, department);
    bindDepartmentOptions(dialog, directory);

    expect(organization.value).toBe("org_hq");
    expect(department.value).toBe("dpt_recruitment");

    organization.value = "org_branch";
    organization.dispatchEvent(new Event("change"));

    expect(department.value).toBe("");
    expect([...department.options].map(item => [item.value, item.textContent])).toEqual([
      ["", "未设置"],
      ["dpt_branch_hr", "人力资源部"],
    ]);
  });

  it("保留工号前导零，允许历史用户没有组织归属", () => {
    const fields = userOrganizationFields(directory, {
      employee_number: "001234",
    });
    const employeeNumber = fields.find(item => item.name === "employee_number");
    const organization = fields.find(item => item.name === "organization_id");
    const department = fields.find(item => item.name === "department_id");

    expect(employeeNumber.value).toBe("001234");
    expect(organization.value).toBe("");
    expect(department.value).toBe("");
    expect(department.options).toEqual([["", "未设置"]]);
  });
});


describe("组织维护", () => {
  beforeEach(() => {
    HTMLDialogElement.prototype.showModal = vi.fn();
    HTMLDialogElement.prototype.close = function (returnValue = "") {
      this.returnValue = returnValue;
      this.dispatchEvent(new Event("close"));
    };
  });

  afterEach(() => {
    for (const page of pages.splice(0)) page.destroy();
    document.body.replaceChildren();
    vi.restoreAllMocks();
    delete HTMLDialogElement.prototype.showModal;
    delete HTMLDialogElement.prototype.close;
  });

  it("排序遵循后台顺序，边界操作禁用，移动后保留选中项", async () => {
    const updated = { ...directory, organizations: [...directory.organizations].reverse() };
    const request = vi.fn().mockResolvedValueOnce(directory).mockResolvedValueOnce({}).mockResolvedValueOnce(updated);
    await openOrganizationPage({ request, createDialog: vi.fn(), toast: vi.fn() });
    const action = label => [...document.querySelectorAll('[role="menuitem"]')].find(item => item.textContent === label);
    expect(action("上移").disabled).toBe(true);
    expect(action("下移").disabled).toBe(false);
    chooseMoreAction("下移");
    await vi.waitFor(() => {
      expect([...document.querySelectorAll('[data-organization-id]')].map(item => item.dataset.organizationId))
        .toEqual(["org_branch", "org_hq"]);
    });
    expect(request).toHaveBeenCalledWith("organizations/org_hq/move", {
      method: "POST", body: JSON.stringify({ direction: "down" }),
    });
    expect(document.querySelector('[data-select-id="org_hq"]').getAttribute("aria-pressed")).toBe("true");
    expect(action("下移").disabled).toBe(true);
    selectNode("dpt_recruitment");
    expect(action("上移").disabled).toBe(true);
    expect(action("下移").disabled).toBe(true);
  });

  it("排序失败保留原顺序并恢复操作", async () => {
    const toast = vi.fn();
    const request = vi.fn().mockResolvedValueOnce(directory).mockRejectedValueOnce(new Error("保存失败"));
    await openOrganizationPage({ request, createDialog: vi.fn(), toast });
    chooseMoreAction("下移");
    await vi.waitFor(() => expect(toast).toHaveBeenCalledWith("保存失败", "error"));
    expect([...document.querySelectorAll('[data-organization-id]')].map(item => item.dataset.organizationId))
      .toEqual(["org_hq", "org_branch"]);
    expect([...document.querySelectorAll('[role="menuitem"]')].find(item => item.textContent === "下移").disabled)
      .toBe(false);
  });

  it("组织层级可折叠，操作菜单可用 Escape 关闭", async () => {
    await openOrganizationPage({
      request: vi.fn().mockResolvedValue(directory), createDialog: vi.fn(), toast: vi.fn(),
    });
    let toggle = document.querySelector('[data-organization-id="org_hq"] .organization-page-toggle');
    expect(document.querySelector('[data-department-id="dpt_hr"]')).not.toBeNull();
    toggle.click();
    expect(document.querySelector('[data-department-id="dpt_hr"]')).toBeNull();
    toggle = document.querySelector('[data-organization-id="org_hq"] .organization-page-toggle');
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    toggle.click();
    expect(document.querySelector('[data-department-id="dpt_hr"]')).not.toBeNull();
    const more = document.querySelector(".organization-page-more");
    const trigger = more.querySelector("summary");
    const menu = more.querySelector('[role="menu"]');
    trigger.click();
    expect(more.open).toBe(true);
    expect([...menu.querySelectorAll("button")].map(item => item.textContent)).toEqual(["上移", "下移", "停用", "删除"]);
    menu.dispatchEvent(new window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(more.open).toBe(false);
    expect(document.activeElement).toBe(trigger);
  });

  it.each([
    ["org_branch", null],
    ["org_hq", "dpt_hr"],
  ])("在 %s 下创建部门时自动带入所属机构和上级", async (organizationId, parentId) => {
    const createDialog = vi.fn(config => {
      const form = document.createElement("dialog");
      for (const field of config.fields.filter(item => item.type === "select")) {
        const select = document.createElement("select");
        select.name = field.name;
        select.append(...field.options.map(([value, label]) => new window.Option(label, value)));
        select.value = field.value;
        form.append(select);
      }
      return form;
    });
    await openOrganizationPage({ request: vi.fn().mockResolvedValue(directory), createDialog, toast: vi.fn() });
    selectNode(parentId || organizationId);
    [...document.querySelectorAll(".organization-page-detail-actions button")]
      .find(item => item.textContent === (parentId ? "创建子部门" : "创建部门")).click();
    const config = createDialog.mock.calls[0][0];
    expect(config.title).toBe(parentId ? "创建子部门" : "创建部门");
    expect(config.fields.find(item => item.name === "organization_id").value).toBe(organizationId);
    expect(config.fields.find(item => item.name === "parent_id").value).toBe(parentId || "");
  });

  it("搜索按名称和编码筛选并保留祖先，刷新后保留选择与搜索", async () => {
    const request = vi.fn().mockResolvedValue(directory);
    const page = await openOrganizationPage({ request, createDialog: vi.fn(), toast: vi.fn() });
    selectNode("dpt_recruitment");
    const search = document.querySelector(".organization-page-search");
    search.value = "RECRUITMENT";
    search.dispatchEvent(new Event("input"));
    expect(document.querySelector('[data-department-id="dpt_hr"]')).not.toBeNull();
    expect(document.querySelector('[data-organization-id="org_branch"]')).toBeNull();
    request.mockResolvedValueOnce({
      ...directory,
      departments: directory.departments.map(item => ({ ...item, code: item.code + "_updated" })),
    });
    await page.refresh();
    expect(search.value).toBe("RECRUITMENT");
    expect(document.querySelector(".organization-page-title h2").textContent).toBe("招聘组");
    expect(document.querySelector('[data-select-id="dpt_recruitment"]').getAttribute("aria-pressed")).toBe("true");
  });

  it("页面销毁后忽略未完成的目录请求", async () => {
    let resolve;
    const request = vi.fn().mockReturnValue(new Promise(done => { resolve = done; }));
    const container = document.createElement("section");
    const page = createOrganizationPage({ container, request, createDialog: vi.fn(), toast: vi.fn() });
    const pending = page.show();
    page.destroy();
    resolve(directory);
    await pending;
    expect(container.childElementCount).toBe(0);
  });

  it.each([
    ["删除机构", "organizations/org_hq"],
    ["删除部门", "departments/dpt_recruitment"],
  ])("%s 须确认后发送 DELETE，成功后刷新目录", async (label, path) => {
    vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(() => {});
    vi.spyOn(HTMLDialogElement.prototype, "close").mockImplementation(function () {
      this.dispatchEvent(new Event("close"));
    });
    const deletingOrganization = label === "删除机构";
    const initial = { ...directory };
    if (deletingOrganization) {
      initial.departments = initial.departments.filter(item => item.organization_id !== "org_hq");
    }
    const collection = deletingOrganization ? "organizations" : "departments";
    const key = deletingOrganization ? "organization_id" : "department_id";
    const identifier = deletingOrganization ? "org_hq" : "dpt_recruitment";
    const record = initial[collection].find(item => item[key] === identifier);
    const updated = { ...initial, [collection]: initial[collection].filter(item => item[key] !== identifier) };
    const request = vi.fn().mockResolvedValueOnce(initial).mockResolvedValueOnce(record).mockResolvedValueOnce(updated);
    const createDialog = vi.fn();
    await openOrganizationPage({ request, createDialog, toast: vi.fn() });
    selectNode(identifier);
    chooseMoreAction("删除");
    expect(request).toHaveBeenCalledTimes(1);
    const confirmation = createDialog.mock.calls[0][0];
    expect(confirmation.submitLabel).toBe("确认删除");
    expect(confirmation.description).toContain(record.name);
    await confirmation.onSubmit();
    expect(request).toHaveBeenLastCalledWith(path, { method: "DELETE" });
    await confirmation.onSuccess();
    expect(request).toHaveBeenLastCalledWith("directory");
  });

  it.each([
    ["停用机构", "organizations/org_hq/disable", false],
    ["启用机构", "organizations/org_hq/enable", true],
    ["停用部门", "departments/dpt_hr/disable", false],
    ["启用部门", "departments/dpt_hr/enable", true],
  ])("%s 确认后发送状态操作", async (label, path, inactive) => {
    const state = {
      organizations: directory.organizations.map(item => ({ ...item, is_active: !inactive })),
      departments: directory.departments.map(item => ({ ...item, is_active: !inactive, is_available: !inactive })),
    };
    const request = vi.fn().mockResolvedValue(state);
    const createDialog = vi.fn();
    await openOrganizationPage({ request, createDialog, toast: vi.fn() });
    selectNode(label.endsWith("部门") ? "dpt_hr" : "org_hq");
    chooseMoreAction(inactive ? "启用" : "停用");
    expect(request).toHaveBeenCalledTimes(1);
    const confirmation = createDialog.mock.calls[0][0];
    expect(confirmation.submitLabel).toBe(inactive ? "确认启用" : "确认停用");
    await confirmation.onSubmit();
    expect(request).toHaveBeenLastCalledWith(path, { method: "POST" });
    await confirmation.onSuccess();
    expect(request).toHaveBeenLastCalledWith("directory");
  });

  it("删除冲突交给表单展示，不刷新或移除现有目录", async () => {
    vi.spyOn(HTMLDialogElement.prototype, "showModal").mockImplementation(() => {});
    const request = vi.fn().mockResolvedValueOnce(directory)
      .mockRejectedValueOnce(new Error("部门仍关联 0 名用户、1 个直属下级部门，请先解除关联"));
    const createDialog = vi.fn();
    await openOrganizationPage({ request, createDialog, toast: vi.fn() });
    selectNode("dpt_hr");
    chooseMoreAction("删除");
    await expect(createDialog.mock.calls[0][0].onSubmit()).rejects.toThrow("1 个直属下级部门");
    expect(document.querySelector(".organization-page")).not.toBeNull();
    expect(request).toHaveBeenCalledTimes(2);
  });
});


describe("停用组织的归属选择", () => {
  const inactiveDirectory = {
    organizations: [
      { organization_id: "org_hq", name: "总行", is_active: false },
      { organization_id: "org_branch", name: "分行", is_active: true },
    ],
    departments: directory.departments.map(item => ({
      ...item,
      is_active: true,
      is_available: item.organization_id !== "org_hq",
    })),
  };

  it("创建用户时排除停用机构和上级停用的部门", () => {
    const fields = userOrganizationFields(inactiveDirectory);
    expect(fields.find(item => item.name === "organization_id").options).toEqual([
      ["", "未设置"], ["org_branch", "分行"],
    ]);
    expect(departmentOptions(inactiveDirectory.departments, "org_hq")).toEqual([]);
  });

  it("编辑已有用户时保留原停用归属，其他不可用部门不加入选项", () => {
    const fields = userOrganizationFields(inactiveDirectory, {
      organization_id: "org_hq", department_id: "dpt_recruitment",
    });
    expect(fields.find(item => item.name === "organization_id").options).toContainEqual([
      "org_hq", "总行（已停用）",
    ]);
    expect(fields.find(item => item.name === "department_id").options).toEqual([
      ["", "未设置"], ["dpt_recruitment", "人力资源部 / 招聘组（已停用）"],
    ]);
  });
});


describe("用户归属内新增组织", () => {
  function setup(record = {}) {
    const currentDirectory = window.structuredClone(directory);
    const dialog = document.createElement("dialog");
    const fields = userOrganizationFields(currentDirectory, record);
    for (const field of fields.filter(field => field.type === "select")) {
      const select = document.createElement("select");
      select.name = field.name;
      select.append(...field.options.map(([value, label]) => new window.Option(label, value)));
      select.value = field.value;
      dialog.append(select);
    }
    const request = vi.fn();
    const createDialog = vi.fn(config => {
      const form = document.createElement("dialog");
      for (const field of config.fields.filter(field => field.type === "select")) {
        const select = document.createElement("select");
        select.name = field.name;
        select.append(...field.options.map(([value, label]) => new window.Option(label, value)));
        select.value = field.value;
        form.append(select);
      }
      return form;
    });
    bindUserOrganizationOptions(dialog, currentDirectory, { request, createDialog, toast: vi.fn() });
    const organization = dialog.querySelector('[name="organization_id"]');
    const department = dialog.querySelector('[name="department_id"]');
    return { dialog, organization, department, request, createDialog, currentDirectory };
  }

  function selectAction(select) {
    select.value = "__create__";
    select.dispatchEvent(new Event("change"));
  }

  it("创建机构前保留归属，成功后选中新机构并清空部门", async () => {
    const context = setup({ organization_id: "org_hq", department_id: "dpt_hr" });
    const unrelated = document.createElement("input");
    unrelated.value = "alice";
    context.dialog.append(unrelated);
    selectAction(context.organization);
    expect(context.organization.value).toBe("org_hq");
    expect(context.department.value).toBe("dpt_hr");
    const config = context.createDialog.mock.calls[0][0];
    expect(config.title).toBe("创建机构");
    const created = { organization_id: "org_new", name: "新机构", is_active: true };
    context.request.mockResolvedValueOnce({
      ...context.currentDirectory,
      organizations: [...context.currentDirectory.organizations, created],
    });
    await config.onSuccess(created);
    expect(context.organization.value).toBe("org_new");
    expect(context.department.value).toBe("");
    expect(unrelated.value).toBe("alice");
  });

  it("创建部门默认归属当前机构，保存后自动选中", async () => {
    const context = setup({ organization_id: "org_branch" });
    selectAction(context.department);
    const config = context.createDialog.mock.calls[0][0];
    expect(config.title).toBe("创建部门");
    expect(config.fields.find(field => field.name === "organization_id").value).toBe("org_branch");
    const data = new FormData();
    data.set("organization_id", "org_branch");
    data.set("name", "财务部");
    await config.onSubmit(data);
    expect(context.request).toHaveBeenLastCalledWith("departments", {
      method: "POST",
      body: JSON.stringify({ organization_id: "org_branch", code: null, name: "财务部", parent_id: null }),
    });
    const created = {
      department_id: "dpt_new", organization_id: "org_branch", name: "财务部",
      path: [{ department_id: "dpt_new", name: "财务部" }],
    };
    context.request.mockResolvedValueOnce({
      ...context.currentDirectory,
      departments: [...context.currentDirectory.departments, created],
    });
    await config.onSuccess(created);
    expect(context.department.value).toBe("dpt_new");
    context.organization.value = "org_hq";
    context.organization.dispatchEvent(new Event("change"));
    expect(context.department.value).toBe("");
    expect([...context.department.options].some(option => option.value === "dpt_new")).toBe(false);
  });

  it("未选机构时禁用创建部门，机构新增入口始终可用", () => {
    const { organization, department } = setup();
    expect(organization.options[organization.options.length - 1].disabled).toBe(false);
    expect(department.options[department.options.length - 1].disabled).toBe(true);
  });
});
