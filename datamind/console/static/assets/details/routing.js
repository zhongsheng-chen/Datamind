"use strict";

import {
  appendDetailField as appendRequestDetail,
  appendDetailFooter,
  createDetailAction,
  createDetailDrawer,
  createDetailIcon,
  createDetailSection,
  createDetailSummary,
  mountDetailDrawer,
  showJsonDialog,
} from "./common.js";

/**
 * 创建路由详情抽屉控制器。
 *
 * 详情以流量分配为核心，并使用应用入口注入的数据访问、导航和资源操作
 * 能力，避免模块依赖全局状态。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {(record: Object) => void} 打开路由详情抽屉
 */
export function createRoutingDetailController({
  buildPageQuery,
  createCopyableSectionNavigationLink,
  createDeploymentRoleBadge,
  createSectionNavigationLink,
  createStatusBadge,
  formatPercentage,
  formatTime,
  getRecordActions,
  request,
  runRecordAction,
}) {
  function createTrafficItem(route, dialog) {
    const item = document.createElement("div");
    const group = String(route.rollout_group || "").toLowerCase();
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
    const percentage = document.createElement("strong");
    percentage.textContent = formatPercentage(route.traffic_ratio);
    const track = document.createElement("div");
    track.className = "routing-traffic-track";
    const fill = document.createElement("span");
    fill.style.width = `${Math.max(
      0,
      Math.min(100, Number(route.traffic_ratio || 0) * 100),
    )}%`;
    track.append(fill);
    content.append(identity, track, percentage);
    if (route.deployment_id) {
      const viewDeployment = createSectionNavigationLink(
        route.deployment_id,
        "deployments",
        dialog,
        "›",
      );
      if (viewDeployment instanceof HTMLElement) {
        viewDeployment.classList.add("routing-traffic-deployment-link");
        viewDeployment.setAttribute("aria-label", "查看部署");
        viewDeployment.title = "查看部署";
      }
      content.append(viewDeployment);
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
    const help = document.createElement("button");
    help.type = "button";
    help.className = "routing-traffic-help";
    help.setAttribute("aria-label", `${title}说明`);
    const tooltip = document.createElement("span");
    tooltip.className = "routing-traffic-tooltip";
    tooltip.setAttribute("role", "tooltip");
    tooltip.textContent = description;
    const tooltipId = `routing-${kind}-traffic-tooltip`;
    tooltip.id = tooltipId;
    help.setAttribute("aria-describedby", tooltipId);
    help.append(
      createDetailIcon("help", "routing-traffic-help-icon"),
      tooltip,
    );
    heading.append(label, help);
    group.append(heading);
    if (routes.length === 0) {
      const empty = document.createElement("p");
      empty.className = "routing-traffic-empty";
      empty.textContent = "暂无流量";
      group.append(empty);
    } else {
      const items = document.createElement("div");
      items.className = "routing-traffic-items";
      items.append(...routes.map((route) => createTrafficItem(route, dialog)));
      group.append(items);
    }
    return group;
  }

  function createTrafficSection(routes, dialog) {
    const section = document.createElement("section");
    section.className = "routing-detail-section routing-traffic-section";
    const heading = document.createElement("h4");
    const headingText = document.createElement("span");
    headingText.textContent = "流量分配";
    heading.append(
      createDetailIcon("traffic", "routing-section-icon"),
      headingText,
    );
    const productionRoutes = routes.filter(
      (route) => String(route.rollout_group || "").toLowerCase() !== "shadow",
    ).sort(
      (left, right) => Number(right.traffic_ratio || 0)
        - Number(left.traffic_ratio || 0),
    );
    const shadowRoutes = routes.filter(
      (route) => String(route.rollout_group || "").toLowerCase() === "shadow",
    );
    const groups = document.createElement("div");
    groups.className = "routing-traffic-groups";
    groups.append(
      createTrafficGroup(
        "生产流量",
        "用户请求按比例转发",
        productionRoutes,
        "production",
        dialog,
      ),
      createTrafficGroup(
        "影子流量",
        "仅复制请求，不返回响应",
        shadowRoutes,
        "shadow",
        dialog,
      ),
    );
    section.append(heading, groups);
    return section;
  }

  function formatRuleOperator(value) {
    const operators = {
      eq: "等于",
      ne: "不等于",
      gt: "大于",
      gte: "大于等于",
      lt: "小于",
      lte: "小于等于",
      in: "包含于",
      not_in: "不包含于",
    };
    return operators[String(value || "").toLowerCase()] || value || "—";
  }

  function createRulesSection(rules) {
    const normalizedRules = (
      rules !== null
      && typeof rules === "object"
      && !Array.isArray(rules)
    ) ? rules : {};
    const hasRules = Object.keys(normalizedRules).length > 0;
    const ruleConditions = Reflect.get(normalizedRules, "conditions");
    const conditions = Array.isArray(ruleConditions)
      ? ruleConditions
      : [];
    const section = document.createElement("section");
    section.className = "routing-detail-section routing-rules-section";
    const heading = document.createElement("div");
    heading.className = "routing-section-heading";
    const title = document.createElement("h4");
    const titleText = document.createElement("span");
    titleText.textContent = "规则配置";
    title.append(
      createDetailIcon("rules", "routing-section-icon"),
      titleText,
    );
    heading.append(title);
    if (hasRules) {
      const viewJson = document.createElement("button");
      viewJson.type = "button";
      viewJson.className = "registry-json-view-button";
      viewJson.textContent = "查看";
      viewJson.addEventListener("click", () => {
        showJsonDialog("规则配置 JSON", normalizedRules);
      });
      heading.append(viewJson);
    }

    const matchMode = document.createElement("dl");
    matchMode.className = "routing-detail-list routing-match-mode";
    if (conditions.length > 0) {
      appendRequestDetail(
        matchMode,
        "匹配方式",
        normalizedRules.match === "any" ? "任一满足" : "全部满足",
      );
    }
    const conditionList = document.createElement("div");
    conditionList.className = "routing-condition-list";
    if (conditions.length === 0) {
      const empty = document.createElement("p");
      empty.className = "routing-condition-empty";
      empty.textContent = hasRules ? "未配置匹配条件" : "未配置";
      conditionList.append(empty);
    } else {
      conditions.forEach((condition, index) => {
        const card = document.createElement("article");
        card.className = "routing-condition-card";
        const cardTitle = document.createElement("h5");
        cardTitle.textContent = `条件 ${index + 1}`;
        const details = document.createElement("dl");
        details.className = "routing-detail-list";
        appendRequestDetail(details, "字段", condition.field);
        appendRequestDetail(
          details,
          "运算符",
          formatRuleOperator(condition.op || condition.operator),
        );
        appendRequestDetail(
          details,
          "值",
          typeof condition.value === "object"
            ? JSON.stringify(condition.value)
            : condition.value,
        );
        card.append(cardTitle, details);
        conditionList.append(card);
      });
    }
    section.append(heading);
    if (conditions.length > 0) section.append(matchMode);
    section.append(conditionList);
    return section;
  }

  async function loadRelatedRoutes(record, section, dialog) {
    try {
      const data = await request(
        `sections/routings?${buildPageQuery(
          1,
          100,
          String(record.model_name || record.model_id || ""),
          "updated_at",
          "desc",
        )}`,
      );
      if (!section.isConnected) return;
      const relatedRoutes = Array.isArray(data?.items)
        ? data.items.filter((route) => (
          record.model_id
            ? route.model_id === record.model_id
            : route.model_name === record.model_name
        ))
        : [];
      section.replaceWith(createTrafficSection(
        relatedRoutes.length > 0 ? relatedRoutes : [record],
        dialog,
      ));
    } catch {
      // 当前路由仍可完整展示，流量分配退化为当前记录。
    }
  }

  function showRoutingDrawer(record) {
    const { dialog, body } = createDetailDrawer(
      "路由详情",
      "routing-detail-drawer",
    );
    const trafficSection = createTrafficSection([record], dialog);
    body.append(
      createDetailSummary({
        icon: "routing",
        title: record.name || "未命名路由",
        subtitle:
          [record.model_name, record.model_version].filter(Boolean).join(" · ") ||
          "未关联模型",
        status: record.status,
        badges: record.rollout_group
          ? [createDeploymentRoleBadge(record.rollout_group)]
          : [],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["路由 ID", (drawer) => createCopyableSectionNavigationLink(
          record.routing_id,
          "routings",
          drawer,
          "路由 ID",
        )],
        ["路由名称", record.name],
        ["状态", createStatusBadge(record.status)],
        ["描述", record.description],
        ["创建时间", formatTime(record.created_at)],
        ["更新时间", formatTime(record.updated_at)],
      ], dialog, "info", appendRequestDetail),
      trafficSection,
      createRulesSection(record.rules),
      createDetailSection("路由配置", [
        ["发布类型", record.rollout_type],
        ["路由角色", createDeploymentRoleBadge(record.rollout_group)],
        ["流量比例", formatPercentage(record.traffic_ratio)],
      ], dialog, "routing", appendRequestDetail),
      createDetailSection("生效配置", [
        ["生效时间", formatTime(record.effective_from)],
        ["失效时间", formatTime(record.effective_to)],
      ], dialog, "effective", appendRequestDetail),
    );

    const buttons = [];
    const actions = getRecordActions("routings", record).filter(
      (actionConfig) => ["edit", "enable", "disable", "delete"].includes(
        actionConfig.action,
      ),
    );
    for (const actionConfig of actions) {
      let label = `${actionConfig.label}路由`;
      let icon = actionConfig.action === "enable" ? "start" : "stop";
      if (actionConfig.action === "edit") {
        label = "编辑路由";
        icon = "edit";
      } else if (actionConfig.action === "delete") {
        label = "删除路由";
        icon = "delete";
      }
      const button = createDetailAction(
        label,
        icon,
        ["disable", "delete"].includes(actionConfig.action)
          ? "danger"
          : actionConfig.action === "enable" ? "primary" : "",
      );
      button.addEventListener("click", () => {
        dialog.close();
        runRecordAction(actionConfig, record);
      });
      buttons.push(button);
    }

    appendDetailFooter(dialog, buttons);
    mountDetailDrawer(dialog, { section: "routings", id: record.routing_id });
    void loadRelatedRoutes(record, trafficSection, dialog);
  }

  return showRoutingDrawer;
}
