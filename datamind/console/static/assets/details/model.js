"use strict";

import {
  appendDetailField as appendRequestDetail,
  appendDetailFooter,
  createDetailAction,
  createDetailBadge,
  createDetailDrawer,
  createDetailIcon,
  createDetailSection,
  createDetailSummary,
  mountDetailDrawer,
} from "./common.js?v=20260902-5";

/**
 * 创建模型详情控制器。
 *
 * 详情通过注入的导航与资源操作保持组件独立于应用全局状态。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {(record: Object) => void} 打开模型详情抽屉
 */
export function createModelDetailController({
  buildPageQuery,
  createCopyableNavigationLink,
  createDeploymentRoleBadge,
  createSectionNavigationLink,
  createStatusBadge,
  formatPercentage,
  formatTime,
  getRecordActions,
  hasCapability,
  navigateToModelVersions,
  navigateToSection,
  openVersionCreateDialog,
  request,
  runRecordAction,
  toast,
}) {
  function createUsageItem({
    icon,
    label,
    total,
    onClick,
  }) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "registry-model-usage-item";
    button.setAttribute("aria-label", `查看${label}，共 ${total} 个`);
    const iconContainer = createDetailIcon(icon, "registry-model-usage-icon");
    iconContainer.classList.add(icon);
    const content = document.createElement("span");
    const name = document.createElement("span");
    name.className = "registry-model-usage-label";
    name.textContent = label;
    const value = document.createElement("strong");
    value.textContent = String(total);
    content.append(name, value);
    button.append(iconContainer, content);
    button.addEventListener("click", onClick);
    return button;
  }

  function createUsageSection(model, related, dialog) {
    const section = document.createElement("section");
    section.className = "registry-detail-section registry-model-usage-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("assignment", "registry-section-icon"),
      document.createTextNode("关联资源"),
    );
    const grid = document.createElement("div");
    grid.className = "registry-model-usage-grid";
    grid.append(createUsageItem({
      icon: "version",
      label: "版本",
      total: Number(model.version_count || 0),
      onClick: () => {
        dialog.close();
        navigateToModelVersions(model);
      },
    }));
    const definitions = [
      ["deployments", "model", "部署"],
      ["routings", "routing", "路由"],
      ["runtimes", "runtime", "运行实例"],
      ["experiments", "experiment", "实验"],
    ];
    for (const [key, icon, label] of definitions) {
      const data = related[key];
      if (data === null) continue;
      grid.append(createUsageItem({
        icon,
        label,
        total: Number(data.total || 0),
        onClick: () => {
          dialog.close();
          navigateToSection(
            key,
            1,
            `model_id:${model.model_id}`,
          );
        },
      }));
    }
    section.append(heading, grid);
    return section;
  }

  function createTrafficHelp(title, description, kind) {
    const help = document.createElement("button");
    help.type = "button";
    help.className = "routing-traffic-help";
    help.setAttribute("aria-label", `${title}说明`);
    const tooltip = document.createElement("span");
    tooltip.className = "routing-traffic-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.textContent = description;
    const tooltipId = `model-${kind}-traffic-tooltip`;
    tooltip.id = tooltipId;
    help.setAttribute("aria-describedby", tooltipId);
    help.append(createDetailIcon("help", "routing-traffic-help-icon"), tooltip);
    return help;
  }

  function createTrafficItem(route, dialog) {
    const group = String(route.rollout_group || "").toLowerCase();
    const item = document.createElement("div");
    item.className = `routing-traffic-item ${group}`.trim();
    const content = document.createElement("div");
    content.className = "routing-traffic-content";
    const identity = document.createElement("div");
    identity.append(
      createDeploymentRoleBadge(route.rollout_group),
      Object.assign(document.createElement("span"), {
        textContent: route.model_version || "—",
      }),
    );
    const track = document.createElement("div");
    track.className = "routing-traffic-track";
    const fill = document.createElement("span");
    fill.style.width = `${Math.max(
      0,
      Math.min(100, Number(route.traffic_ratio || 0) * 100),
    )}%`;
    track.append(fill);
    const percentage = document.createElement("strong");
    percentage.textContent = formatPercentage(route.traffic_ratio);
    content.append(identity, track, percentage);
    if (route.deployment_id) {
      const deployment = createSectionNavigationLink(
        route.deployment_id,
        "deployments",
        dialog,
        "›",
      );
      if (deployment instanceof HTMLElement) {
        deployment.classList.add("routing-traffic-deployment-link");
        deployment.setAttribute("aria-label", "查看部署");
        deployment.title = "查看部署";
      }
      content.append(deployment);
    }
    item.append(content);
    return item;
  }

  function createTrafficGroup(title, description, routes, kind, dialog) {
    const group = document.createElement("div");
    group.className = `routing-traffic-group ${kind}`;
    const heading = document.createElement("div");
    heading.className = "routing-traffic-heading";
    const label = document.createElement("h5");
    label.textContent = title;
    heading.append(label, createTrafficHelp(title, description, kind));
    const items = document.createElement("div");
    items.className = "routing-traffic-items";
    if (routes.length === 0) {
      const empty = document.createElement("p");
      empty.className = "routing-traffic-empty";
      empty.textContent = "暂无流量";
      group.append(heading, empty);
      return group;
    }
    items.append(...routes.map((route) => createTrafficItem(route, dialog)));
    group.append(heading, items);
    return group;
  }

  function createTrafficSection(routes, dialog) {
    const section = document.createElement("section");
    section.className = "registry-detail-section registry-model-traffic-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("traffic", "registry-section-icon"),
      document.createTextNode("流量分配"),
    );
    section.append(heading);
    if (routes.length === 0) {
      const empty = document.createElement("p");
      empty.className = "registry-model-traffic-empty";
      empty.textContent = "暂无流量分配";
      section.append(empty);
      return section;
    }
    const productionRoutes = routes.filter(
      (route) => String(route.rollout_group || "").toLowerCase() !== "shadow",
    ).sort(
      (left, right) => Number(right.traffic_ratio || 0)
        - Number(left.traffic_ratio || 0),
    );
    const shadowRoutes = routes.filter(
      (route) => String(route.rollout_group || "").toLowerCase() === "shadow",
    ).sort(
      (left, right) => Number(right.traffic_ratio || 0)
        - Number(left.traffic_ratio || 0),
    );
    const groups = document.createElement("div");
    groups.className = "routing-traffic-groups";
    groups.append(createTrafficGroup(
      "生产流量",
      "用户请求按比例转发",
      productionRoutes,
      "production",
      dialog,
    ));
    if (shadowRoutes.length > 0) {
      groups.append(createTrafficGroup(
        "影子流量",
        "仅复制请求，不返回响应",
        shadowRoutes,
        "shadow",
        dialog,
      ));
    }
    section.append(groups);
    return section;
  }

  async function loadRelatedModelData(model) {
    const query = `model_id:${model.model_id}`;
    const sections = ["deployments", "routings", "runtimes", "experiments"];
    const results = await Promise.allSettled(sections.map((section) => request(
      `sections/${section}?${buildPageQuery(
        1,
        100,
        query,
        "updated_at",
        "desc",
      )}`,
    )));
    return Object.fromEntries(sections.map((section, index) => {
      const result = results[index];
      return [section, result.status === "fulfilled" ? result.value : null];
    }));
  }

  function appendModelFooter(dialog, model) {
    const buttons = [];
    const actions = getRecordActions("models", model);
    const edit = actions.find((action) => action.action === "edit");
    const remove = actions.find((action) => action.action === "delete");
    if (edit) {
      const button = createDetailAction("编辑模型", "edit");
      button.addEventListener("click", () => {
        dialog.close();
        runRecordAction(edit, model);
      });
      buttons.push(button);
    }
    if (!model.deleted_at && hasCapability("models.create")) {
      const button = createDetailAction("添加版本", "add", "primary");
      button.addEventListener("click", () => {
        dialog.close();
        Promise.resolve(openVersionCreateDialog(model)).catch(
          (error) => toast(error.message),
        );
      });
      buttons.push(button);
    }
    if (remove) {
      const button = createDetailAction("删除模型", "delete", "danger");
      button.addEventListener("click", () => {
        dialog.close();
        runRecordAction(remove, model);
      });
      buttons.push(button);
    }
    appendDetailFooter(dialog, buttons);
  }

  function showModelDrawer(record) {
    void loadModelDrawer(record);
  }

  async function loadModelDrawer(record) {
    const modelId = String(record.model_id || "");
    if (!modelId) {
      toast("模型 ID 不存在");
      return;
    }
    try {
      const model = await request(`models/${encodeURIComponent(modelId)}/detail`);
      const related = await loadRelatedModelData(model);
      const { dialog, body } = createDetailDrawer("模型详情");
      body.append(
        createDetailSummary({
          icon: "model",
          title: model.name,
          subtitle: model.display_name || "未设置显示名称",
          status: model.status,
          badges: [
            createDetailBadge(model.framework, "framework"),
            createDetailBadge(model.model_type, "type"),
            createDetailBadge(model.task_type, "task"),
          ],
          createStatusBadge,
        }),
        createDetailSection("基本信息", [
          ["模型 ID", () => createCopyableNavigationLink(
            model.model_id,
            () => {
              dialog.close();
              navigateToSection(
                "models",
                1,
                `model_id:${model.model_id}`,
              );
            },
            "模型 ID",
          )],
          ["模型名称", model.name],
          ["显示名称", model.display_name],
          ["状态", createStatusBadge(model.status)],
          ["框架", model.framework],
          ["类型", model.model_type],
          ["任务类型", model.task_type],
          ["描述", model.description],
          ["创建时间", formatTime(model.created_at)],
          ["更新时间", formatTime(model.updated_at)],
        ], dialog, "info", appendRequestDetail),
        createUsageSection(model, related, dialog),
      );
      if (related.routings !== null) {
        body.append(createTrafficSection(
          Array.isArray(related.routings.items)
            ? related.routings.items
            : [],
          dialog,
        ));
      }
      appendModelFooter(dialog, model);
      mountDetailDrawer(dialog, { section: "models", id: model.model_id });
    } catch (error) {
      toast(error instanceof Error ? error.message : "模型详情加载失败");
    }
  }

  return showModelDrawer;
}
