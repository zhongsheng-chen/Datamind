"use strict";

import { createOrganizationEditors } from "./forms.js";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

/**
 * 创建机构与部门管理页面，组织树与详情共用服务端目录。
 *
 * @param {Object.<string, *>} dependencies 页面容器、请求、表单及提示组件
 * @returns {{show: () => Promise<void>, refresh: () => Promise<void>, destroy: () => void}} 页面生命周期
 */
export function createOrganizationPage({ container, request, createDialog, toast }) {
  let directory = null;
  let selectedId = null;
  let loading = null;
  let destroyed = false;
  let mounted = false;
  let signature = "";
  const collapsed = new Set();
  const records = new Map();
  const children = new Map();
  const sidebar = element("aside", "organization-page-sidebar");
  const treeHeading = element("div", "organization-page-tree-heading");
  const tree = element("div", "organization-page-tree");
  tree.setAttribute("aria-label", "组织结构");
  const search = element("input", "organization-page-search");
  search.type = "search";
  search.placeholder = "搜索机构、部门或编码";
  search.setAttribute("aria-label", "搜索组织");
  const detail = element("section", "organization-page-detail");
  detail.setAttribute("aria-label", "组织详情");
  const button = (text, callback, className = "secondary-button") => {
    const control = element("button", className, text);
    control.type = "button";
    control.addEventListener("click", callback);
    return control;
  };
  const addOrganization = button("＋ 创建机构", () => editors().editOrganization(), "organization-page-add");
  treeHeading.append(element("h2", "", "组织结构"), addOrganization);
  sidebar.append(treeHeading, search, tree);
  const status = record => {
    const inactive = record.is_active === false || record.is_available === false;
    return element("span", `organization-page-status${inactive ? " inactive" : ""}`,
      record.is_active === false ? "已停用" : record.is_available === false ? "上级已停用" : "已启用");
  };
  const idOf = record => record.department_id || record.organization_id;
  const getParent = record => record.department_id
    ? record.parent_id || record.path.at(-2)?.department_id || record.organization_id
    : null;
  const lineage = record => {
    const path = [];
    const visited = new Set();
    for (let current = record; current && !visited.has(idOf(current)); current = records.get(getParent(current))) {
      path.unshift(current);
      visited.add(idOf(current));
    }
    return path;
  };
  const editors = () => createOrganizationEditors({
    directory, request, createDialog, toast,
    onSuccess: async result => {
      if (result?.department_id || result?.organization_id) selectedId = idOf(result);
      await refresh();
    },
  });
  function select(id, restoreFocus = false) {
    if (!records.has(id)) return;
    selectedId = id;
    renderTree(restoreFocus ? id : null);
    renderDetail();
  }
  function renderTree(focusId = null) {
    tree.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    const matched = new Set();
    if (query) {
      for (const record of records.values()) {
        if (`${record.name} ${record.code || ""}`.toLocaleLowerCase().includes(query)) {
          for (const parent of lineage(record)) matched.add(idOf(parent));
        }
      }
    }
    const selectedPath = new Set(selectedId && records.has(selectedId)
      ? lineage(records.get(selectedId)).map(idOf) : []);
    const visit = (record, depth) => {
      const id = idOf(record);
      if (query && !matched.has(id)) return;
      const descendants = children.get(id) || [];
      const expanded = Boolean(query) || !collapsed.has(id);
      const row = element("div", "organization-page-node");
      row.style.setProperty("--organization-depth", depth);
      row.dataset.nodeId = id;
      if (record.department_id) row.dataset.departmentId = id;
      else row.dataset.organizationId = id;
      row.classList.toggle("selected", id === selectedId || (!expanded && selectedPath.has(id)));
      const toggle = button("", () => {
        if (collapsed.has(id)) collapsed.delete(id);
        else collapsed.add(id);
        renderTree(id);
      }, "organization-page-toggle");
      toggle.disabled = !descendants.length;
      toggle.setAttribute("aria-label", `${record.name}的下级组织`);
      if (descendants.length) {
        toggle.setAttribute("aria-expanded", String(expanded));
      }
      const pick = button("", () => select(id, true), "organization-page-pick");
      pick.dataset.selectId = id;
      pick.setAttribute("aria-pressed", String(id === selectedId));
      pick.title = record.name;
      const icon = element("span", `organization-page-node-icon ${record.department_id ? "department" : "institution"}`);
      icon.setAttribute("aria-hidden", "true");
      pick.append(icon, element("span", "organization-page-node-name", record.name));
      row.append(toggle, pick);
      tree.append(row);
      if (expanded) for (const child of descendants) visit(child, depth + 1);
    };
    for (const record of directory.organizations) visit(record, 0);
    if (!tree.childElementCount) {
      tree.append(element("p", "organization-page-empty", query ? "未找到匹配的机构或部门" : "暂无机构"));
    }
    if (focusId) [...tree.querySelectorAll("[data-select-id]")]
      .find(node => node.dataset.selectId === focusId)?.focus({ preventScroll: true });
  }
  function openStatusDialog(record) {
    const department = Boolean(record.department_id);
    const label = department ? "部门" : "机构";
    const resource = department ? "departments" : "organizations";
    const enabling = record.is_active === false;
    createDialog({
      title: `${enabling ? "启用" : "停用"}${label}`,
      description: enabling
        ? `确认启用“${record.name}”？下级部门独立设置的停用状态将保留。`
        : `确认停用“${record.name}”？已有用户归属将保留，该${label}及其下级部门不再接收新关联。`,
      submitLabel: enabling ? "确认启用" : "确认停用",
      fields: [],
      onSubmit: () => request(`${resource}/${encodeURIComponent(idOf(record))}/${enabling ? "enable" : "disable"}`, {
        method: "POST",
      }),
      onSuccess: () => refresh(),
      refreshAfterSubmit: false,
    });
  }
  function openDeleteDialog(record) {
    const department = Boolean(record.department_id);
    const label = department ? "部门" : "机构";
    createDialog({
      title: `删除${label}`,
      description: `确认删除“${record.name}”？该操作无法撤销。有关联用户或下级组织时，请先解除关联。`,
      submitLabel: "确认删除",
      fields: [],
      onSubmit: () => request(`${department ? "departments" : "organizations"}/${encodeURIComponent(idOf(record))}`, {
        method: "DELETE",
      }),
      refreshAfterSubmit: false,
      onSuccess: async () => {
        selectedId = getParent(record);
        await refresh();
      },
    });
  }
  function renderDetail() {
    detail.replaceChildren();
    const record = records.get(selectedId);
    if (!record) {
      detail.append(element("p", "organization-page-empty", "暂无机构，请先创建机构。"));
      return;
    }
    const department = Boolean(record.department_id);
    const path = lineage(record);
    const breadcrumb = element("nav", "organization-page-breadcrumb");
    breadcrumb.setAttribute("aria-label", "组织路径");
    path.forEach((item, index) => {
      if (index) breadcrumb.append(element("span", "organization-page-path-separator", "/"));
      if (index === path.length - 1) breadcrumb.append(element("span", "", item.name));
      else breadcrumb.append(button(item.name, () => select(idOf(item)), "organization-page-link"));
    });
    const header = element("div", "organization-page-detail-header");
    const heading = element("div");
    const title = element("div", "organization-page-title");
    title.append(element("h2", "", record.name), status(record));
    heading.append(title, element("p", "organization-page-kind", department ? "部门" : "机构"));
    const actions = element("div", "organization-page-detail-actions");
    const edit = button("编辑", () => department ? editors().editDepartment(record) : editors().editOrganization(record),
      "primary-button");
    const addChild = button(department ? "创建子部门" : "创建部门", () => editors().editDepartment(null, {
      organizationId: record.organization_id,
      parentId: department ? record.department_id : null,
    }));
    addChild.disabled = record.is_active === false || record.is_available === false;
    if (addChild.disabled) addChild.title = "请先启用所属机构及上级部门";
    const more = element("details", "organization-page-more");
    const summary = element("summary", "", "⋯");
    summary.setAttribute("aria-label", `${record.name}的更多操作`);
    summary.setAttribute("aria-haspopup", "menu");
    const menu = element("div", "organization-page-menu");
    menu.setAttribute("role", "menu");
    const changeStatus = button(record.is_active === false ? "启用" : "停用", () => {
      more.open = false;
      openStatusDialog(record);
    }, "organization-page-menu-item");
    const remove = button("删除", () => {
      more.open = false;
      openDeleteDialog(record);
    }, "organization-page-menu-item danger");
    const siblings = department ? children.get(getParent(record)) || [] : directory.organizations;
    const position = siblings.findIndex(item => idOf(item) === idOf(record));
    const moves = ["up", "down"].map((direction, index) => {
      const move = button(index === 0 ? "上移" : "下移", async () => {
        more.open = false;
        move.disabled = true;
        try {
          await request(`${department ? "departments" : "organizations"}/${encodeURIComponent(idOf(record))}/move`, {
            method: "POST", body: JSON.stringify({ direction }),
          });
          await refresh();
        } catch (error) {
          toast(error.message || "调整顺序失败", "error");
          renderDetail();
        }
      }, "organization-page-menu-item");
      move.disabled = index === 0 ? position <= 0 : position >= siblings.length - 1;
      return move;
    });
    for (const item of [...moves, changeStatus, remove]) item.setAttribute("role", "menuitem");
    menu.append(...moves, changeStatus, remove);
    more.append(summary, menu);
    more.addEventListener("keydown", event => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        more.open = false;
        summary.focus();
      } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
        event.preventDefault();
        const items = [...menu.querySelectorAll("button:not(:disabled)")];
        const current = items.indexOf(document.activeElement);
        const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
          : (current + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        more.open = true;
        items[next]?.focus();
      }
    });
    actions.append(edit, addChild, more);
    header.append(heading, actions);
    const information = element("section", "organization-page-information");
    information.append(element("h3", "", "基本信息"));
    const facts = element("dl", "organization-page-facts");
    const entries = [[`${department ? "部门" : "机构"}编码`, record.code || "—"]];
    if (department) {
      const parent = records.get(getParent(record));
      entries.push(["所属机构", path[0].name], ["上级部门", parent?.department_id ? parent.name : "无上级部门"]);
    }
    for (const [label, value] of entries) {
      const fact = element("div");
      fact.append(element("dt", "", label), element("dd", label.endsWith("编码") ? "mono" : "", value));
      facts.append(fact);
    }
    information.append(facts);
    const lower = element("section", "organization-page-lower");
    const descendants = children.get(selectedId) || [];
    const lowerHeading = element("h3", "", "下级部门");
    lowerHeading.append(element("span", "organization-page-count", String(descendants.length)));
    lower.append(lowerHeading);
    const table = element("table", "organization-page-table");
    const thead = element("thead");
    const headRow = element("tr");
    for (const label of ["部门名称", "部门编码", "状态"]) {
      const th = element("th", "", label);
      th.scope = "col";
      headRow.append(th);
    }
    thead.append(headRow);
    const tbody = element("tbody");
    for (const child of descendants) {
      const row = element("tr");
      const name = element("td");
      name.append(button(child.name, () => select(child.department_id), "organization-page-link"));
      const state = element("td");
      state.append(status(child));
      row.append(name, element("td", "mono", child.code || "—"), state);
      tbody.append(row);
    }
    table.append(thead, tbody);
    lower.append(table);
    if (!descendants.length) lower.append(element("p", "organization-page-empty", "暂无下级部门"));
    detail.append(breadcrumb, header, information, lower);
  }
  async function refresh() {
    if (destroyed) return;
    if (loading) return loading;
    loading = (async () => {
      try {
        const result = await request("directory");
        if (destroyed) return;
        const nextSignature = JSON.stringify(result);
        if (signature === nextSignature && records.has(selectedId)) return;
        signature = nextSignature;
        directory = result;
        records.clear();
        children.clear();
        for (const record of [...directory.organizations, ...directory.departments]) records.set(idOf(record), record);
        for (const record of directory.departments) {
          const parentId = getParent(record);
          if (!children.has(parentId)) children.set(parentId, []);
          children.get(parentId).push(record);
        }
        if (!records.has(selectedId)) selectedId = directory.organizations[0]?.organization_id || null;
        const focused = tree.querySelector(".organization-page-pick:focus")?.dataset.selectId;
        renderTree(focused);
        renderDetail();
      } catch (error) {
        if (!destroyed && !directory) {
          detail.replaceChildren(element("p", "organization-page-empty", error.message));
          detail.append(button("重试", () => { void refresh().catch(failure => toast(failure.message)); }));
        }
        throw error;
      } finally {
        loading = null;
      }
    })();
    return loading;
  }
  search.addEventListener("input", () => { if (directory) renderTree(); });
  tree.addEventListener("keydown", event => {
    const pick = event.target.closest("[data-select-id]");
    if (!pick || !["ArrowDown", "ArrowUp", "ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const id = pick.dataset.selectId;
    const items = [...tree.querySelectorAll("[data-select-id]")];
    const current = items.indexOf(pick);
    if (event.key === "ArrowRight") {
      if (collapsed.has(id)) { collapsed.delete(id); renderTree(id); }
      else if (children.get(id)?.length) items[current + 1]?.focus();
    } else if (event.key === "ArrowLeft") {
      if (children.get(id)?.length && !collapsed.has(id)) { collapsed.add(id); renderTree(id); }
      else [...tree.querySelectorAll("[data-select-id]")].find(item => (
        item.dataset.selectId === getParent(records.get(id))
      ))?.focus();
    } else {
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1
        : Math.max(0, Math.min(items.length - 1, current + (event.key === "ArrowDown" ? 1 : -1)));
      items[next]?.focus();
    }
  });
  const outsideClick = event => {
    for (const more of detail.querySelectorAll("details[open]")) if (!more.contains(event.target)) more.open = false;
  };
  document.addEventListener("click", outsideClick);
  return {
    show: async () => {
      if (destroyed) return;
      if (!mounted) {
        container.replaceChildren(sidebar, detail);
        detail.append(element("p", "organization-page-empty", "正在加载组织结构…"));
        mounted = true;
      }
      if (!directory) await refresh();
    },
    refresh,
    destroy: () => {
      destroyed = true;
      document.removeEventListener("click", outsideClick);
      container.replaceChildren();
    },
  };
}
