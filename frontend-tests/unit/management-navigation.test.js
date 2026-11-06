import { afterEach, describe, expect, it, vi } from "vitest";

import { createDashboardController } from "../../datamind/console/static/assets/dashboard.js";

function setup(capabilities, active = "users") {
  const navigation = document.createElement("nav");
  const sidebar = document.createElement("aside");
  const managementEntry = document.createElement("div");
  const managementTabs = document.createElement("nav");
  const accountManagement = document.createElement("div");
  sidebar.className = "open";
  sidebar.append(navigation, managementEntry);
  document.body.append(sidebar, managementTabs, accountManagement);
  const navigateToSection = vi.fn();
  const closeAccountMenu = vi.fn();
  const state = {
    active,
    snapshot: { access: { models: true, users: true, roles: true }, counts: { models: 3 } },
  };
  const controller = createDashboardController({
    managementSectionKeys: new Set(["users", "roles"]),
    managementEntry,
    managementTabs,
    accountManagement,
    closeAccountMenu,
    hasCapability: key => Boolean(capabilities[key]),
    canViewOverview: () => false,
    formatNavigationCount: String,
    formatInteger: String,
    navigateToSection,
    navigation,
    sidebar,
    sections: { models: { label: "模型" }, users: { label: "用户" }, roles: { label: "角色" } },
    state,
  });
  controller.renderNavigation();
  return { navigation, sidebar, managementEntry, managementTabs, accountManagement,
    navigateToSection, closeAccountMenu, controller, state };
}

afterEach(() => document.body.replaceChildren());

describe("管理入口与页签", () => {
  it("固定入口独立于业务滚动区，管理页签顺序固定且不显示数量", () => {
    const { navigation, sidebar, managementEntry, managementTabs, navigateToSection } = setup({
      "users.manage": true, "roles.manage": true,
    });
    expect(managementEntry.parentElement).toBe(sidebar);
    expect(navigation.contains(managementEntry)).toBe(false);
    expect(managementEntry.querySelectorAll("button")).toHaveLength(1);
    expect(managementEntry.textContent).toBe("管理");
    expect([...managementTabs.querySelectorAll("button")].map(button => button.textContent)).toEqual([
      "用户管理", "角色管理", "机构与部门",
    ]);
    expect(managementTabs.hidden).toBe(false);
    expect(managementTabs.querySelectorAll(".nav-count")).toHaveLength(0);
    expect(managementTabs.querySelector('[aria-current="page"]').textContent).toBe("用户管理");
    managementTabs.querySelector('[data-management-section="organizations"]').click();
    expect(navigateToSection).toHaveBeenCalledWith("organizations");
    expect(sidebar.classList.contains("open")).toBe(false);
  });

  it("业务页面隐藏管理页签，固定入口返回上次访问的管理页面", () => {
    const { managementEntry, managementTabs, controller, state, navigateToSection } = setup({
      "users.manage": true,
    }, "organizations");
    state.active = "models";
    controller.renderNavigation();
    expect(managementTabs.hidden).toBe(true);
    expect(managementEntry.hidden).toBe(false);
    managementEntry.querySelector("button").click();
    expect(navigateToSection).toHaveBeenCalledWith("organizations");
  });

  it("个人菜单保留用户和角色快捷入口，共用导航和关闭菜单逻辑", () => {
    const { accountManagement, navigateToSection, closeAccountMenu } = setup({
      "users.manage": true, "roles.manage": true,
    });
    expect([...accountManagement.querySelectorAll("button")].map(button => button.textContent)).toEqual([
      "用户管理", "角色管理",
    ]);
    accountManagement.querySelector('[data-account-section="roles"]').click();
    expect(navigateToSection).toHaveBeenCalledWith("roles");
    expect(closeAccountMenu).toHaveBeenCalledOnce();
  });

  it.each([
    {
      capabilities: { "users.manage": true },
      expectedTabs: ["用户管理", "机构与部门"],
      expectedShortcuts: ["用户管理"],
    },
    {
      capabilities: { "roles.manage": true },
      expectedTabs: ["角色管理"],
      expectedShortcuts: ["角色管理"],
    },
    {
      capabilities: {},
      expectedTabs: [],
      expectedShortcuts: [],
    },
  ])("管理入口、页签和个人快捷入口均按权限显示", ({ capabilities, expectedTabs, expectedShortcuts }) => {
    const { managementEntry, managementTabs, accountManagement } = setup(capabilities, "models");
    expect([...managementTabs.querySelectorAll("button")].map(button => button.textContent)).toEqual(expectedTabs);
    expect([...accountManagement.querySelectorAll("button")].map(button => button.textContent)).toEqual(expectedShortcuts);
    expect(managementEntry.hidden).toBe(expectedTabs.length === 0);
    expect(accountManagement.hidden).toBe(expectedShortcuts.length === 0);
  });
});
