"use strict";

import { createExperimentAnalysisSummary, showExperimentAnalysisPanel } from "./experiment/analysis.js";

import {
  appendDetailField as appendRequestDetail,
  appendDetailFooter,
  createDetailAction,
  createDetailBadge,
  createDetailDrawer,
  createDetailIcon,
  createDetailSection,
  createDetailSummary,
  formatStatusValue,
  mountDetailDrawer,
} from "./common.js";

/**
 * 创建实验与分组详情控制器。
 *
 * 详情分别呈现实验配置、分组分配和关联资源。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   showExperimentDrawer: (record: Object) => void,
 *   showVariantDrawer: (record: Object) => void
 * }} 实验与分组详情入口
 */
export function createExperimentDetailController({
  createCopyableNavigationLink,
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
      weight.hidden = experiment.config?.strategy === "manual";
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
      const icon = [
        "edit",
        "delete",
        "start",
        "pause",
        "stop",
        "complete",
        "enable",
        "disable",
      ].includes(action.action) ? action.action : "activity";
      const tone = ["delete", "stop"].includes(action.action)
        ? "danger"
        : "";
      const button = createDetailAction(label, icon, tone);
      button.disabled = Boolean(action.disabled);
      if (action.disabledReason) button.title = action.disabledReason;
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

  function createCustomerAssignmentsSection(record, parentDialog) {
    const assignments = record.config?.manual_assignments || {};
    const entries = Object.entries(assignments);
    const editAction = record.status === "draft"
      ? getRecordActions("experiments", record).find(
        (action) => action.action === "edit" && !action.disabled,
      )
      : null;
    const editAssignments = () => {
      parentDialog.close();
      runRecordAction(editAction, record);
    };
    const section = document.createElement("section");
    section.className = "registry-detail-section";
    const headingRow = document.createElement("div");
    headingRow.className = "registry-section-heading";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("assignment", "registry-section-icon"),
      document.createTextNode("客户分配"),
    );
    headingRow.append(heading);
    const summary = document.createElement("p");
    summary.className = "experiment-assignment-summary";
    summary.textContent = entries.length
      ? `已指定 ${entries.length} 位客户 · 覆盖 ${new Set(entries.map(([, target]) => target)).size} 个分组`
      : "暂无客户分配";

    if (entries.length || editAction) {
      const action = document.createElement("button");
      action.type = "button";
      action.className = "registry-section-link";
      action.textContent = entries.length ? `查看全部 ${entries.length}` : "添加客户";
      action.addEventListener("click", () => {
        if (entries.length) {
          showCustomerAssignments(record, entries, editAction ? editAssignments : null);
        } else {
          editAssignments();
        }
      });
      headingRow.append(action);
    }

    section.append(headingRow, summary);
    return section;
  }

  function showCustomerAssignments(record, entries, onEdit) {
    const dialog = document.createElement("dialog");
    dialog.className = "experiment-assignments-dialog";
    dialog.setAttribute("aria-label", "客户分配名单");
    const header = document.createElement("header");
    const title = document.createElement("h3");
    title.textContent = "客户分配名单";
    const close = document.createElement("button");
    close.type = "button";
    close.className = "dialog-close-button";
    close.textContent = "关闭";
    close.addEventListener("click", () => dialog.close());
    header.append(title, close);

    const content = document.createElement("div");
    content.className = "experiment-assignments-content";
    const filters = document.createElement("div");
    filters.className = "experiment-assignments-filters";
    const search = document.createElement("input");
    search.type = "search";
    search.placeholder = "搜索客户标识";
    search.setAttribute("aria-label", "搜索客户标识");
    const group = document.createElement("select");
    group.setAttribute("aria-label", "筛选分组");
    const all = document.createElement("option");
    all.value = "";
    all.textContent = "全部分组";
    group.append(all);
    filters.append(search, group);

    const message = document.createElement("p");
    message.className = "experiment-assignments-message";
    message.setAttribute("role", "status");
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "registry-section-link";
    retry.textContent = "重新加载";
    retry.hidden = true;
    const table = document.createElement("table");
    const tableHead = document.createElement("thead");
    const headingRow = document.createElement("tr");
    for (const label of ["客户标识", "所属分组"]) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      headingRow.append(cell);
    }
    tableHead.append(headingRow);
    const tableBody = document.createElement("tbody");
    table.append(tableHead, tableBody);
    content.append(filters, message, retry, table);

    const footer = document.createElement("footer");
    if (onEdit) {
      const edit = createDetailAction("编辑分配", "edit");
      edit.addEventListener("click", () => {
        dialog.close();
        onEdit();
      });
      footer.append(edit);
    }
    const pagination = document.createElement("div");
    pagination.className = "experiment-assignments-pagination";
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "secondary-button";
    previous.textContent = "上一页";
    const count = document.createElement("span");
    const next = document.createElement("button");
    next.type = "button";
    next.className = "secondary-button";
    next.textContent = "下一页";
    pagination.append(previous, count, next);
    footer.append(pagination);
    dialog.append(header, content, footer);

    const pageSize = 10;
    let page = 1;
    let names = new Map();
    let loaded = false;

    function render() {
      if (!loaded) return;
      const query = search.value.trim().toLowerCase();
      const filtered = entries.filter(([customer, target]) => (
        customer.toLowerCase().includes(query)
        && (!group.value || target === group.value)
      ));
      const pages = Math.max(1, Math.ceil(filtered.length / pageSize));
      page = Math.min(page, pages);
      tableBody.replaceChildren();
      for (const [customer, target] of filtered.slice((page - 1) * pageSize, page * pageSize)) {
        const row = document.createElement("tr");
        const customerCell = document.createElement("td");
        customerCell.textContent = customer;
        const groupCell = document.createElement("td");
        groupCell.textContent = names.get(target) || "分组不可用";
        row.append(customerCell, groupCell);
        tableBody.append(row);
      }
      message.textContent = filtered.length
        ? `共 ${filtered.length} 位客户`
        : "没有匹配的客户";
      count.textContent = `${page} / ${pages}`;
      previous.disabled = page <= 1;
      next.disabled = page >= pages;
    }

    async function loadGroups() {
      loaded = false;
      search.disabled = true;
      group.disabled = true;
      previous.disabled = true;
      next.disabled = true;
      retry.hidden = true;
      message.textContent = "正在加载名单…";
      try {
        const variants = [];
        for (let currentPage = 1; ; currentPage += 1) {
          const response = await request(
            `experiments/${encodeURIComponent(record.experiment_id)}/variants?page=${currentPage}&page_size=100&deleted=false`,
          );
          if (!dialog.open) return;
          const batch = Array.isArray(response?.items) ? response.items : [];
          variants.push(...batch);
          if (batch.length < 100) break;
        }
        names = new Map(variants.map((variant) => [variant.variant_id, variant.name]));
        group.replaceChildren(all);
        for (const target of new Set(entries.map(([, value]) => value))) {
          const option = document.createElement("option");
          option.value = target;
          option.textContent = names.get(target) || "分组不可用";
          group.append(option);
        }
        loaded = true;
        search.disabled = false;
        group.disabled = false;
        render();
      } catch {
        if (!dialog.open) return;
        message.textContent = "名单加载失败，请重试";
        retry.hidden = false;
      }
    }

    search.addEventListener("input", () => {
      page = 1;
      render();
    });
    group.addEventListener("change", () => {
      page = 1;
      render();
    });
    previous.addEventListener("click", () => {
      page -= 1;
      render();
    });
    next.addEventListener("click", () => {
      page += 1;
      render();
    });
    retry.addEventListener("click", () => void loadGroups());
    dialog.addEventListener("close", () => dialog.remove());
    document.body.append(dialog);
    dialog.showModal();
    void loadGroups();
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
          ["状态", formatStatusValue(record.status, createStatusBadge)],
          ["描述", record.description],
          ["生效时间", formatTime(record.effective_from)],
          ["失效时间", formatTime(record.effective_to)],
          ["创建时间", formatTime(record.created_at)],
          ["更新时间", formatTime(record.updated_at)],
        ], dialog, "info", appendRequestDetail),
        createDetailSection("分流配置", [
          ["分配策略", strategyLabel(config.strategy)],
          ...(config.strategy === "manual" ? [] : [
            ["实验曝光比例", formatPercentage(config.traffic_ratio)],
          ]),
          ["分桶字段", config.bucket_key],
          ["分组数量", record.variant_count],
        ], dialog, "config", appendRequestDetail),
        createVariantList(record, variants, dialog),
        createExperimentAnalysisSummary({
          experimentId,
          request,
          dialog,
          onViewAnalysis: () => showExperimentAnalysisPanel({ experiment: record, request, parentDialog: dialog, createStatusBadge }),
        }),
      );
      if (config.strategy === "manual") {
        body.append(createCustomerAssignmentsSection(record, dialog));
      }
      appendResourceActions(dialog, "experiments", record, "实验");
      mountDetailDrawer(dialog, {
        section: "experiments",
        id: record.experiment_id,
      });
    } catch (error) {
      toast(error instanceof Error ? error.message : "实验详情加载失败");
    }
  }

  function createVariantRelationCard({
    iconKind,
    name,
    metadata,
    actionLabel,
    ariaLabel,
    onClick,
  }) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "variant-related-card";
    card.setAttribute("aria-label", ariaLabel);
    const icon = createDetailIcon(
      iconKind,
      "variant-related-icon",
    );
    const content = document.createElement("span");
    content.className = "variant-related-content";
    const relationName = document.createElement("strong");
    relationName.textContent = name;
    const relationMetadata = document.createElement("span");
    relationMetadata.className = "variant-related-meta";
    relationMetadata.textContent = metadata;
    content.append(relationName);
    if (metadata) content.append(relationMetadata);
    const action = document.createElement("span");
    action.className = "variant-related-action";
    const actionText = document.createElement("span");
    actionText.textContent = actionLabel;
    const arrow = document.createElement("span");
    arrow.className = "variant-related-arrow";
    arrow.textContent = "›";
    action.append(actionText, arrow);
    card.append(icon, content, action);
    card.addEventListener("click", onClick);
    return card;
  }

  function experimentAssignmentSummary(record) {
    const strategy = String(record.experiment_strategy || "").toLowerCase();
    const summary = strategy ? [strategyLabel(strategy)] : [];
    const rawTrafficRatio = record.experiment_traffic_ratio;
    const trafficRatio = Number(rawTrafficRatio);
    if (
      strategy !== "manual"
      && rawTrafficRatio !== null
      && rawTrafficRatio !== undefined
      && rawTrafficRatio !== ""
      && Number.isFinite(trafficRatio)
    ) {
      summary.push(`曝光 ${formatPercentage(trafficRatio)}`);
    }
    return summary.join(" · ");
  }

  function createVariantExperimentCard(record, dialog) {
    return createVariantRelationCard({
      iconKind: "experiment",
      name: record.experiment_name || "未命名实验",
      metadata: experimentAssignmentSummary(record),
      actionLabel: "查看实验",
      ariaLabel: `查看实验：${record.experiment_name || "未命名实验"}`,
      onClick: () => {
        dialog.close();
        navigateToSection(
          "experiments",
          1,
          `experiment_id:${record.experiment_id}`,
        );
      },
    });
  }

  function createVariantDeploymentCard(record, dialog) {
    return createVariantRelationCard({
      iconKind: "model",
      name: record.model_name || "未命名模型",
      metadata: record.model_version
        ? `版本 ${record.model_version}`
        : "未标注版本",
      actionLabel: "查看部署",
      ariaLabel: `查看部署：${record.model_name || "未命名模型"} ${record.model_version || ""}`.trim(),
      onClick: () => {
        dialog.close();
        navigateToSection(
          "deployments",
          1,
          `deployment_id:${record.deployment_id}`,
        );
      },
    });
  }

  function createVariantRelationsSection(record, dialog) {
    const section = document.createElement("section");
    section.className = "registry-detail-section variant-related-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("link", "registry-section-icon"),
      document.createTextNode("关联资源"),
    );
    const list = document.createElement("div");
    list.className = "variant-related-list";
    list.append(
      createVariantExperimentCard(record, dialog),
      createVariantDeploymentCard(record, dialog),
    );
    section.append(heading, list);
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
        ["分组名称", record.name],
        ["实验名称", record.experiment_name],
        ["状态", formatStatusValue(record.status, createStatusBadge)],
        ["分组类型", record.group_type],
        ["流量权重", formatPercentage(record.weight)],
        ["是否对照组", record.is_control ? "是" : "否"],
        ["描述", record.description],
        ["创建时间", formatTime(record.created_at)],
        ["更新时间", formatTime(record.updated_at)],
      ], dialog, "info", appendRequestDetail),
      createVariantRelationsSection(record, dialog),
    );
    appendResourceActions(dialog, "variants", record, "分组");
    mountDetailDrawer(dialog, { section: "variants", id: record.variant_id });
  }

  return {
    showExperimentDrawer,
    showVariantDrawer,
  };
}
