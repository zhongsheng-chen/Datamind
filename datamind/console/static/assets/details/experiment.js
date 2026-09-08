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
  createJsonDetailSection,
  mountDetailDrawer,
} from "./common.js";

/**
 * 创建实验与分组详情控制器。
 *
 * 详情分别呈现实验配置、分组分配和关联部署。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   showExperimentDrawer: (record: Object) => void,
 *   showVariantDrawer: (record: Object) => void
 * }} 实验与分组详情入口
 */
export function createExperimentDetailController({
  createCopyableNavigationLink,
  createSectionNavigationLink,
  createStatusBadge,
  formatPercentage,
  formatTime,
  getRecordActions,
  navigateToExperimentVariants,
  navigateToSection,
  request,
  runRecordAction,
  toast,
}) {
  function strategyLabel(value) {
    return {
      hash: "稳定哈希",
      manual: "手动分配",
    }[String(value || "").toLowerCase()] || value || "—";
  }

  function createVariantList(experiment, variants, dialog) {
    const section = document.createElement("section");
    section.className = "registry-detail-section";
    const headingRow = document.createElement("div");
    headingRow.className = "registry-section-heading";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("assignment", "registry-section-icon"),
      document.createTextNode("分组分配"),
    );
    const viewAll = document.createElement("button");
    viewAll.type = "button";
    viewAll.className = "registry-section-link";
    viewAll.textContent = `查看全部 ${Number(experiment.variant_count || variants.length)}`;
    viewAll.addEventListener("click", () => {
      dialog.close();
      navigateToExperimentVariants(experiment);
    });
    headingRow.append(heading, viewAll);

    const list = document.createElement("div");
    list.className = "registry-related-list";
    if (variants.length === 0) {
      const empty = document.createElement("p");
      empty.className = "registry-related-empty";
      empty.textContent = "暂无分组";
      list.append(empty);
    }
    for (const variant of variants) {
      const item = document.createElement("div");
      item.className = "registry-related-item";
      const identity = document.createElement("button");
      identity.type = "button";
      identity.className = "registry-related-identity";
      const nameRow = document.createElement("span");
      nameRow.className = "registry-related-name";
      const name = document.createElement("strong");
      name.textContent = variant.name || "未命名分组";
      nameRow.append(
        name,
        createDetailBadge(
          variant.group_type,
          variant.is_control ? "blue" : "purple",
        ),
        createStatusBadge(variant.status),
      );
      const meta = document.createElement("span");
      meta.className = "registry-related-meta";
      meta.textContent = [variant.model_name, variant.model_version]
        .filter(Boolean)
        .join(" · ") || "—";
      identity.append(nameRow, meta);
      const navigateToVariant = () => {
        dialog.close();
        navigateToExperimentVariants(
          experiment,
          1,
          `variant_id:${variant.variant_id}`,
        );
      };
      identity.addEventListener("click", navigateToVariant);
      const weight = document.createElement("strong");
      weight.className = "registry-related-value";
      weight.textContent = formatPercentage(variant.weight);
      const viewVariant = document.createElement("button");
      viewVariant.type = "button";
      viewVariant.className = "registry-related-link";
      viewVariant.textContent = "›";
      viewVariant.setAttribute("aria-label", "查看分组");
      viewVariant.addEventListener("click", navigateToVariant);
      item.append(identity, weight, viewVariant);
      list.append(item);
    }
    section.append(headingRow, list);
    return section;
  }

  function appendResourceActions(dialog, section, record, resourceName) {
    const buttons = getRecordActions(section, record).map((action) => {
      const label = action.action === "edit"
        ? `编辑${resourceName}`
        : action.action === "delete"
          ? `删除${resourceName}`
          : `${action.label}${resourceName}`;
      const icon = action.action === "edit"
        ? "edit"
        : action.action === "delete"
          ? "delete"
          : action.action === "start"
            ? "start"
            : action.action === "pause" || action.action === "stop"
              ? "stop"
              : "activity";
      const tone = action.action === "delete"
        ? "danger"
        : action.action === "start" ? "primary" : "";
      const button = createDetailAction(label, icon, tone);
      button.addEventListener("click", () => {
        dialog.close();
        runRecordAction(action, record);
      });
      return button;
    });
    appendDetailFooter(dialog, buttons);
  }

  function showExperimentDrawer(record) {
    void loadExperimentDrawer(record);
  }

  async function loadExperimentDrawer(record) {
    if (!record?.experiment_id) return;
    const experimentId = record.experiment_id;
    let variants = [];
    try {
      const response = await request(
        `experiments/${encodeURIComponent(experimentId)}/variants?page=1&page_size=100&sort=weight&order=desc&deleted=false`,
      );
      variants = Array.isArray(response?.items) ? response.items : [];
    } catch {
      // 基本详情仍可展示，分组列表退化为空状态。
    }
    try {
      const config = record.config || {};
      const { dialog, body } = createDetailDrawer(
        "实验详情",
        "experiment-detail-drawer",
      );
      body.append(
        createDetailSummary({
          icon: "experiment",
          title: record.name,
          subtitle: record.model_name || "未关联模型",
          status: record.status,
          badges: [
            createDetailBadge(strategyLabel(config.strategy), "blue"),
          ],
          createStatusBadge,
        }),
        createDetailSection("基本信息", [
          ["实验 ID", () => createCopyableNavigationLink(
            record.experiment_id,
            () => {
              dialog.close();
              navigateToSection(
                "experiments",
                1,
                `experiment_id:${record.experiment_id}`,
              );
            },
            "实验 ID",
          )],
          ["实验名称", record.name],
          ["状态", createStatusBadge(record.status)],
          ["描述", record.description],
          ["生效时间", formatTime(record.effective_from)],
          ["失效时间", formatTime(record.effective_to)],
          ["创建时间", formatTime(record.created_at)],
          ["更新时间", formatTime(record.updated_at)],
        ], dialog, "info", appendRequestDetail),
        createDetailSection("分流配置", [
          ["分配策略", strategyLabel(config.strategy)],
          ["实验流量", formatPercentage(config.traffic_ratio)],
          ["分桶字段", config.bucket_key],
          ["分组数量", record.variant_count],
        ], dialog, "config", appendRequestDetail),
        createVariantList(record, variants, dialog),
      );
      appendResourceActions(dialog, "experiments", record, "实验");
      mountDetailDrawer(dialog, {
        section: "experiments",
        id: record.experiment_id,
      });
    } catch (error) {
      toast(error instanceof Error ? error.message : "实验详情加载失败");
    }
  }

  function createVariantDeploymentSection(record, dialog) {
    const section = document.createElement("section");
    section.className = [
      "registry-detail-section",
      "variant-deployment-section",
    ].join(" ");
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("external", "registry-section-icon"),
      document.createTextNode("关联部署"),
    );
    const card = document.createElement("button");
    card.type = "button";
    card.className = "variant-deployment-card";
    card.setAttribute(
      "aria-label",
      `查看部署：${record.model_name || "未命名模型"} ${record.model_version || ""}`.trim(),
    );
    const icon = createDetailIcon(
      "model",
      "variant-deployment-icon",
    );
    const content = document.createElement("span");
    content.className = "variant-deployment-content";
    const modelName = document.createElement("strong");
    modelName.textContent = record.model_name || "未命名模型";
    const metadata = document.createElement("span");
    metadata.className = "variant-deployment-meta";
    metadata.textContent = record.model_version
      ? `版本 ${record.model_version}`
      : "未标注版本";
    content.append(modelName, metadata);
    const action = document.createElement("span");
    action.className = "variant-deployment-action";
    const actionLabel = document.createElement("span");
    actionLabel.textContent = "查看部署";
    const arrow = document.createElement("span");
    arrow.className = "variant-deployment-arrow";
    arrow.textContent = "›";
    action.append(actionLabel, arrow);
    card.append(icon, content, action);
    card.addEventListener("click", () => {
      dialog.close();
      navigateToSection(
        "deployments",
        1,
        `deployment_id:${record.deployment_id}`,
      );
    });
    section.append(heading, card);
    return section;
  }

  function showVariantDrawer(record) {
    if (!record) return;
    const { dialog, body } = createDetailDrawer(
      "分组详情",
      "variant-detail-drawer",
    );
    body.append(
      createDetailSummary({
        icon: "variant",
        title: record.name,
        subtitle: record.experiment_name || "未命名实验",
        status: record.status,
        badges: [
          createDetailBadge(
            record.group_type,
            record.is_control ? "blue" : "purple",
          ),
          createDetailBadge(formatPercentage(record.weight)),
        ],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["分组 ID", () => createCopyableNavigationLink(
          record.variant_id,
          () => {
            dialog.close();
            navigateToSection(
              "variants",
              1,
              `variant_id:${record.variant_id}`,
            );
          },
          "分组 ID",
        )],
        ["分组名称", () => createSectionNavigationLink(
          record.variant_id,
          "variants",
          dialog,
          record.name || record.variant_id,
        )],
        ["实验名称", () => createSectionNavigationLink(
          record.experiment_id,
          "experiments",
          dialog,
          record.experiment_name || record.experiment_id,
        )],
        ["状态", createStatusBadge(record.status)],
        ["分组类型", record.group_type],
        ["流量权重", formatPercentage(record.weight)],
        ["是否对照组", record.is_control ? "是" : "否"],
        ["描述", record.description],
        ["创建时间", formatTime(record.created_at)],
        ["更新时间", formatTime(record.updated_at)],
      ], dialog, "info", appendRequestDetail),
      createVariantDeploymentSection(record, dialog),
    );
    if (record.config !== null && record.config !== undefined) {
      body.append(createJsonDetailSection("分组配置", record.config, "config"));
    }
    appendResourceActions(dialog, "variants", record, "分组");
    mountDetailDrawer(dialog, { section: "variants", id: record.variant_id });
  }

  return {
    showExperimentDrawer,
    showVariantDrawer,
  };
}
