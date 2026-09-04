"use strict";

import {
  appendDetailField as appendRequestDetail,
  appendDetailFooter,
  createDetailAction,
  createDetailDrawer,
  createDetailSection,
  createDetailSummary,
  mountDetailDrawer,
  showJsonDialog,
} from "./common.js?v=20260902-4";

/**
 * 创建部署详情抽屉控制器。
 *
 * 模块仅负责部署详情的展示与交互。数据访问、导航和资源操作由应用入口
 * 注入，使详情组件不依赖全局状态，也不反向引用 app.js。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {(record: Object) => void} 打开部署详情抽屉
 */
export function createDeploymentDetailController({
  buildPageQuery,
  createCopyableSectionNavigationLink,
  createDeploymentRoleBadge,
  createStatusBadge,
  formatTime,
  getRecordActions,
  navigateToSection,
  request,
  runRecordAction,
}) {
  const deploymentConfigLabels = {
    threshold: "决策阈值",
  };

  function createDeploymentRolloutBadge(value) {
    const rolloutType = String(value || "").toLowerCase();
    const badge = document.createElement("span");
    badge.className = `deployment-rollout-type ${rolloutType}`.trim();
    badge.textContent = rolloutType || "—";
    return badge;
  }

  function formatDeploymentConfigValue(key, value) {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "number") {
      return String(value);
    }
    if (typeof value === "object") return JSON.stringify(value);
    return String(value);
  }

  function createDeploymentConfigFields(config) {
    if (config === null || typeof config !== "object" || Array.isArray(config)) {
      return [["配置", config]];
    }

    const preferredOrder = ["threshold"];
    const keys = Object.keys(config).sort((left, right) => {
      const leftIndex = preferredOrder.indexOf(left);
      const rightIndex = preferredOrder.indexOf(right);
      if (leftIndex === -1 && rightIndex === -1) {
        return left.localeCompare(right);
      }
      if (leftIndex === -1) return 1;
      if (rightIndex === -1) return -1;
      return leftIndex - rightIndex;
    });
    return keys.map((key) => [
      deploymentConfigLabels[key] || key,
      formatDeploymentConfigValue(key, config[key]),
    ]);
  }

  function createDeploymentConfigSection(config, dialog) {
    const section = createDetailSection(
      "部署配置",
      createDeploymentConfigFields(config),
      dialog,
      "config",
      appendRequestDetail,
    );
    const title = section.firstElementChild;
    if (!(title instanceof HTMLHeadingElement)) return section;
    const heading = document.createElement("div");
    heading.className = "registry-section-heading";
    const viewJson = document.createElement("button");
    viewJson.type = "button";
    viewJson.className = "registry-json-view-button";
    viewJson.textContent = "查看";
    viewJson.addEventListener("click", () => {
      showJsonDialog("部署配置 JSON", config);
    });
    title.replaceWith(heading);
    heading.append(title, viewJson);
    return section;
  }

  function createDeploymentRuntimeFields(
    record,
    runtimeData = null,
    loadState = "loading",
  ) {
    const fields = [["当前状态", createStatusBadge(record.status)]];
    const deploymentActive = String(record.status || "").toLowerCase()
      === "active";
    if (!deploymentActive) {
      fields.push(["运行实例", "当前没有运行实例"]);
      return fields;
    }
    if (loadState === "loading") {
      fields.push(["运行数据", "正在获取…"]);
      return fields;
    }
    if (loadState === "error") {
      fields.push(["运行数据", "运行状态暂不可用"]);
      return fields;
    }

    const activeStatuses = new Set(["starting", "running", "stopping"]);
    const runtimes = Array.isArray(runtimeData?.items)
      ? runtimeData.items.filter(
        (runtime) => (
          runtime.deployment_id === record.deployment_id
          && activeStatuses.has(String(runtime.status || "").toLowerCase())
        ),
      )
      : [];
    if (runtimes.length === 0) {
      fields.push(["运行实例", "暂未发现在线运行实例"]);
      return fields;
    }

    const healthStatuses = runtimes.map(
      (runtime) => String(runtime.health_status || "").toLowerCase(),
    );
    const healthStatus = healthStatuses.some((status) => status === "unhealthy")
      ? "unhealthy"
      : healthStatuses.every((status) => status === "healthy")
        ? "healthy"
        : "unknown";
    const generations = [...new Set(runtimes
      .map((runtime) => runtime.applied_generation)
      .filter((generation) => (
        generation !== null && generation !== undefined
      )))];
    const lastHeartbeat = runtimes
      .map((runtime) => runtime.last_heartbeat_at)
      .filter(Boolean)
      .sort((left, right) => (
        new Date(right).getTime() - new Date(left).getTime()
      ))[0];

    fields.push(["健康状态", createStatusBadge(healthStatus)]);
    if (generations.length === 1) {
      fields.push(["控制版本", generations[0]]);
    } else if (generations.length > 1) {
      fields.push(["控制版本", "实例版本不一致"]);
    }
    if (lastHeartbeat) {
      fields.push(["最后同步时间", formatTime(lastHeartbeat)]);
    }
    return fields;
  }

  async function refreshDeploymentRuntimeSection(record, dialog, section) {
    try {
      const runtimeData = await request(
        `sections/runtimes?${buildPageQuery(
          1,
          100,
          `deployment_id:${record.deployment_id}`,
          "last_heartbeat_at",
          "desc",
        )}`,
      );
      if (!section.isConnected || !dialog.open) return;
      section.replaceWith(createDetailSection(
        "运行状态",
        createDeploymentRuntimeFields(record, runtimeData, "loaded"),
        dialog,
        "monitor",
        appendRequestDetail,
      ));
    } catch {
      if (!section.isConnected || !dialog.open) return;
      section.replaceWith(createDetailSection(
        "运行状态",
        createDeploymentRuntimeFields(record, null, "error"),
        dialog,
        "monitor",
        appendRequestDetail,
      ));
    }
  }

  function showDeploymentDrawer(record) {
    const { dialog, body } = createDetailDrawer(
      "部署详情",
      "deployment-detail-drawer",
    );
    const runtimeSection = createDetailSection(
      "运行状态",
      createDeploymentRuntimeFields(record),
      dialog,
      "monitor",
      appendRequestDetail,
    );
    body.append(
      createDetailSummary({
        icon: "model",
        title: record.model_name || "未命名模型",
        subtitle: record.model_version,
        status: record.status,
        badges: [
          createDeploymentRolloutBadge(record.rollout_type),
          createDeploymentRoleBadge(record.role),
        ],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["部署 ID", (drawer) => createCopyableSectionNavigationLink(
          record.deployment_id,
          "deployments",
          drawer,
          "部署 ID",
        )],
        ["模型名称", record.model_name],
        ["版本", record.model_version],
        ["框架", record.framework],
        ["描述", record.description],
        ["创建时间", formatTime(record.created_at)],
        ["更新时间", formatTime(record.updated_at)],
      ], dialog, "info", appendRequestDetail),
    );
    if (record.config !== null && record.config !== undefined) {
      body.append(createDeploymentConfigSection(record.config, dialog));
    }
    body.append(
      createDetailSection("发布配置", [
        ["发布类型", createDeploymentRolloutBadge(record.rollout_type)],
        ["角色", createDeploymentRoleBadge(record.role)],
        ["开始时间", formatTime(record.effective_from)],
        ...(record.effective_to
          ? [["结束时间", formatTime(record.effective_to)]]
          : []),
      ], dialog, "release", appendRequestDetail),
      runtimeSection,
    );

    const buttons = [];
    const runtimeButton = createDetailAction("查看运行实例", "monitor");
    runtimeButton.addEventListener("click", () => {
      dialog.close();
      navigateToSection(
        "runtimes",
        1,
        `deployment_id:${record.deployment_id}`,
        "last_heartbeat_at",
        "desc",
      );
    });
    buttons.push(runtimeButton);

    const actions = getRecordActions("deployments", record).filter(
      (actionConfig) => ["edit", "enable", "disable"].includes(
        actionConfig.action,
      ),
    );
    for (const actionConfig of actions) {
      const label = actionConfig.action === "edit"
        ? "编辑部署"
        : `${actionConfig.label}部署`;
      const button = createDetailAction(
        label,
        actionConfig.action === "edit"
          ? "edit"
          : actionConfig.action === "enable" ? "start" : "stop",
        actionConfig.action === "disable"
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
    mountDetailDrawer(dialog, {
      section: "deployments",
      id: record.deployment_id,
    });
    if (String(record.status || "").toLowerCase() === "active") {
      void refreshDeploymentRuntimeSection(record, dialog, runtimeSection);
    }
  }

  return showDeploymentDrawer;
}
