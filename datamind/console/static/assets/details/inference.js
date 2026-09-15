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
  createErrorDetailSection,
  createJsonDetailSection,
  formatPredictionDetails,
  mountDetailDrawer,
} from "./common.js";

/**
 * 创建推理链路详情控制器。
 *
 * 详情串联 API 调用、决策结果和模型执行记录。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   showDecisionDrawer: (record: Object) => void,
 *   showExecutionDrawer: (record: Object) => void,
 *   showRequestDrawer: (record: Object) => void
 * }} API 调用、决策与执行详情入口
 */
export function createInferenceDetailController({
  createDecisionBadge,
  createCopyableNavigationLink,
  createExecutionTypeBadge,
  createSectionNavigationLink,
  createStatusBadge,
  formatOptionalDuration,
  formatPercentage,
  formatProbability,
  formatScore,
  formatTime,
  navigateToSection,
  request,
  sectionIdFields,
}) {
  /**
   * 创建预测详情，并按对应版本的变量顺序更新展示。
   *
   * @param {string} title 区块标题
   * @param {Object} record 推理记录
   * @param {unknown} value 预测结果
   * @param {string} icon 图标类型
   * @returns {HTMLElement} 预测详情区块
   */
  function createPredictionSection(title, record, value, icon) {
    const section = createJsonDetailSection(title, formatPredictionDetails(value), icon);
    if (!record.version_id || !value?.features) return section;
    request(`versions/${encodeURIComponent(record.version_id)}/detail`)
      .then((version) => {
        const variables = version?.scorecard?.details?.variables;
        if (!section.isConnected || !Array.isArray(variables)) return;
        const names = variables.map((variable) => variable?.name)
          .filter((name) => typeof name === "string");
        section.replaceWith(createJsonDetailSection(
          title, formatPredictionDetails(value, names), icon,
        ));
      })
      .catch(() => {
        // 版本详情不可用时保留预测结果，不阻断查看和复制。
      });
    return section;
  }

  const strategyLabels = {
    fallback: "回退选择",
    hash: "稳定哈希",
    manual: "手动分配",
    weighted: "加权路由",
  };
  const roleLabels = {
    champion: "Champion",
    challenger: "Challenger",
    shadow: "Shadow",
  };

  function createNavigationAction(label, icon, section, identifier, dialog) {
    if (!identifier) return null;
    const button = createDetailAction(label, icon);
    button.addEventListener("click", () => {
      dialog.close();
      navigateToSection(
        section,
        1,
        `${sectionIdFields[section]}:${identifier}`,
      );
    });
    return button;
  }

  function createExecutionList(executions, dialog) {
    const section = document.createElement("section");
    section.className = "registry-detail-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("execution", "registry-section-icon"),
      document.createTextNode("模型执行"),
    );
    const list = document.createElement("div");
    list.className = "registry-related-list";
    if (executions.length === 0) {
      const empty = document.createElement("p");
      empty.className = "registry-related-empty";
      empty.textContent = "暂无执行记录";
      list.append(empty);
    }
    for (const execution of executions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "registry-related-item registry-execution-item";
      const identity = document.createElement("span");
      identity.className = "registry-related-identity";
      const nameRow = document.createElement("span");
      nameRow.className = "registry-related-name";
      const name = document.createElement("strong");
      name.textContent = execution.model_name || "未命名模型";
      nameRow.append(
        name,
        createExecutionTypeBadge(execution.execution_type),
        createStatusBadge(execution.status),
      );
      const meta = document.createElement("span");
      meta.className = "registry-related-meta";
      meta.textContent = [
        execution.model_version,
        formatOptionalDuration(execution.latency_ms),
      ].filter((value) => value && value !== "—").join(" · ") || "—";
      identity.append(nameRow, meta);
      const result = document.createElement("span");
      result.className = "registry-related-result";
      result.textContent = [
        `概率 ${formatProbability(execution.probability)}`,
        `评分 ${formatScore(execution.score)}`,
      ].join(" · ");
      button.append(identity, result, createDetailIcon("external"));
      button.addEventListener("click", () => {
        dialog.close();
        showExecutionDrawer(execution);
      });
      list.append(button);
    }
    section.append(heading, list);
    return section;
  }

  function createDecisionPathAction(label, section, identifier, dialog) {
    if (!identifier) return null;
    const navigation = createSectionNavigationLink(
      identifier,
      section,
      dialog,
      label,
    );
    if (!(navigation instanceof HTMLButtonElement)) return null;
    navigation.className = "registry-decision-path-action";
    navigation.append(createDetailIcon("arrow"));
    return navigation;
  }

  function createDecisionPathStep({
    icon,
    tone,
    label,
    title,
    meta,
    detail,
    action,
  }) {
    const step = document.createElement("article");
    step.className = `registry-decision-path-step ${tone}`;
    const marker = document.createElement("span");
    marker.className = "registry-decision-path-marker";
    marker.append(createDetailIcon(icon));
    const content = document.createElement("div");
    content.className = "registry-decision-path-content";
    const heading = document.createElement("div");
    heading.className = "registry-decision-path-heading";
    const identity = document.createElement("div");
    const eyebrow = document.createElement("span");
    eyebrow.className = "registry-decision-path-label";
    eyebrow.textContent = label;
    const name = document.createElement("strong");
    name.textContent = title || "—";
    identity.append(eyebrow, name);
    heading.append(identity);
    if (action) heading.append(action);
    content.append(heading);
    const visibleMeta = meta.filter(Boolean);
    if (visibleMeta.length) {
      const metadata = document.createElement("p");
      metadata.className = "registry-decision-path-meta";
      visibleMeta.forEach((item, index) => {
        if (index) metadata.append(document.createTextNode(" · "));
        metadata.append(item instanceof Node ? item : document.createTextNode(item));
      });
      content.append(metadata);
    }
    if (detail) {
      const description = document.createElement("p");
      description.className = "registry-decision-path-detail";
      description.textContent = detail;
      content.append(description);
    }
    step.append(marker, content);
    return step;
  }

  function createDecisionPath(record, dialog) {
    const section = document.createElement("section");
    section.className = "registry-detail-section registry-decision-path-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("assignment", "registry-section-icon"),
      document.createTextNode("决策路径"),
    );
    const path = document.createElement("div");
    path.className = "registry-decision-path";

    if (record.routing_id) {
      const routingWeight = record.routing_weight ?? (
        record.source === "routing" ? record.weight : null
      );
      path.append(createDecisionPathStep({
        icon: "routing",
        tone: "routing",
        label: "命中路由",
        title: record.routing_name || "未命名路由",
        meta: [
          strategyLabels[record.strategy] || record.strategy,
          routingWeight !== null && routingWeight !== undefined
            ? `流量 ${formatPercentage(routingWeight)}`
            : null,
        ],
        detail: null,
        action: createDecisionPathAction(
          "查看路由",
          "routings",
          record.routing_id,
          dialog,
        ),
      }));
    }

    if (record.experiment_id) {
      const variantWeight = record.variant_weight ?? record.weight;
      /** @type {{ assignment_source?: string | null } | null | undefined} */
      const context = record.context;
      const assignmentSource = context?.assignment_source;
      const assignmentSourceLabels = {
        new_assignment: "新分配",
        existing_assignment: "复用分配",
      };
      const assignmentSourceLabel = typeof assignmentSource === "string"
        ? assignmentSourceLabels[assignmentSource] || assignmentSource
        : null;
      let assignmentSourceMeta = null;
      if (assignmentSourceLabel) {
        assignmentSourceMeta = document.createElement("span");
        assignmentSourceMeta.textContent = assignmentSourceLabel;
        const descriptions = {
          new_assignment: "本次请求为该主体创建了新的实验分组分配",
          existing_assignment: "本次请求沿用该主体已有的实验分组",
        };
        const description = descriptions[assignmentSource];
        if (description) {
          assignmentSourceMeta.title = description;
          assignmentSourceMeta.setAttribute("aria-label", `${assignmentSourceLabel}：${description}`);
        }
      }
      path.append(createDecisionPathStep({
        icon: "experiment",
        tone: "experiment",
        label: "命中实验",
        title: record.experiment_name || "未命名实验",
        meta: [
          strategyLabels[record.strategy] || record.strategy,
          record.variant_is_control === true
            ? "对照组"
            : (record.variant_is_control === false ? "实验组" : null),
          record.strategy !== "manual"
            && variantWeight !== null && variantWeight !== undefined
            ? `权重 ${formatPercentage(variantWeight)}`
            : null,
          assignmentSourceMeta,
        ],
        detail: null,
        action: createDecisionPathAction(
          "查看实验",
          "experiments",
          record.experiment_id,
          dialog,
        ),
      }));
    }

    const deploymentRole = String(record.deployment_role || "").toLowerCase();
    path.append(createDecisionPathStep({
      icon: "model",
      tone: "target",
      label: "命中部署",
      title: record.model_name || "未命名模型",
      meta: [
        record.model_version,
        roleLabels[deploymentRole] || record.deployment_role,
        "主执行",
      ],
      detail: null,
      action: createDecisionPathAction(
        "查看部署",
        "deployments",
        record.deployment_id,
        dialog,
      ),
    }));

    section.append(heading, path);
    return section;
  }

  function createExecutionRoutingSection(record, dialog) {
    if (!record.routing_id) return null;
    const section = document.createElement("section");
    section.className = "registry-detail-section registry-decision-path-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("link", "registry-section-icon"),
      document.createTextNode("路由来源"),
    );
    const path = document.createElement("div");
    path.className = "registry-decision-path";
    const routingWeight = record.routing_weight;
    path.append(createDecisionPathStep({
      icon: "routing",
      tone: "routing",
      label: "命中路由",
      title: record.routing_name || record.routing_id,
      meta: [
        [record.model_name, record.model_version].filter(Boolean).join(" · "),
        routingWeight !== null && routingWeight !== undefined
          ? `流量 ${formatPercentage(routingWeight)}`
          : null,
      ],
      detail: null,
      action: createDecisionPathAction(
        "查看路由",
        "routings",
        record.routing_id,
        dialog,
      ),
    }));
    section.append(heading, path);
    return section;
  }

  function showRequestDrawer(record) {
    if (!record) return;
    const { dialog, body } = createDetailDrawer(
      "API 调用详情",
      "inference-detail-drawer api-detail-drawer",
    );
    body.append(
      createDetailSummary({
        icon: "request",
        title: record.model_name || "API 调用",
        subtitle: [record.model_version, record.ip]
          .filter(Boolean)
          .join(" · "),
        status: record.status,
        badges: [
          record.source
            ? createDetailBadge(record.source)
            : null,
          record.user
            ? createDetailBadge(record.user, "purple")
            : null,
          record.latency_ms !== null && record.latency_ms !== undefined
            ? createDetailBadge(
              formatOptionalDuration(record.latency_ms),
              "blue",
            )
            : null,
        ],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["调用 ID", () => createCopyableNavigationLink(
          record.request_id,
          () => {
            dialog.close();
            navigateToSection(
              "requests",
              1,
              `request_id:${record.request_id}`,
            );
          },
          "调用 ID",
        )],
        ["状态", createStatusBadge(record.status)],
        ["来源", record.source],
        ["模型名称", record.model_name],
        ["任务类型", record.task_type],
        ["版本", record.model_version],
        ["耗时", formatOptionalDuration(record.latency_ms)],
        ["调用用户", record.user],
        ["客户端 IP", record.ip],
        ["调用时间", formatTime(record.created_at)],
      ], dialog, "info", appendRequestDetail),
    );
    if (record.error) body.append(createErrorDetailSection(record.error));
    body.append(
      createJsonDetailSection("请求载荷", record.payload, "payload"),
      createPredictionSection(
        "响应结果",
        record,
        record.response ?? record.prediction,
        "response",
      ),
    );
    appendDetailFooter(dialog, [
      createNavigationAction(
        "查看决策",
        "decision",
        "decisions",
        record.decision_id,
        dialog,
      ),
      createNavigationAction(
        "查看部署",
        "external",
        "deployments",
        record.deployment_id,
        dialog,
      ),
    ]);
    mountDetailDrawer(dialog, { section: "requests", id: record.request_id });
  }

  function showDecisionDrawer(record) {
    if (!record) return;
    const executions = Array.isArray(record.executions)
      ? record.executions
      : [];
    const executionTypes = ["primary", "shadow"].filter(
      (executionType) => executions.some(
        (execution) => String(execution.execution_type || "").toLowerCase()
          === executionType,
      ),
    );
    const { dialog, body } = createDetailDrawer(
      "决策记录详情",
      "inference-detail-drawer decision-detail-drawer",
    );
    const showSubjectHistory = () => {
      const quote = (value) => `'${String(value).replaceAll("'", "'\"'\"'")}'`;
      const filters = [`subject_key:${quote(record.subject_key)}`];
      if (record.subject_type) {
        filters.push(`subject_type:${quote(record.subject_type)}`);
      }
      dialog.close();
      navigateToSection("decisions", 1, filters.join(" "));
    };
    const subjectTypeLabels = {
      customer: "客户",
      user: "用户",
      company: "企业",
      device: "设备",
    };
    const routingContext = record.bucket
      ? { ...record.context, bucket: record.bucket }
      : record.context;
    body.append(
      createDetailSummary({
        icon: "decision",
        title: record.model_name || "模型决策",
        subtitle: [record.strategy, record.source].filter(Boolean).join(" · "),
        status: record.decision,
        badges: [
          createDetailBadge(record.model_version || "未指定版本"),
          record.group ? createDetailBadge(record.group, "purple") : null,
          ...executionTypes.map(createExecutionTypeBadge),
        ],
        createStatusBadge: createDecisionBadge,
      }),
      createDetailSection("基本信息", [
        ["决策 ID", () => createCopyableNavigationLink(
          record.decision_id,
          () => {
            dialog.close();
            navigateToSection(
              "decisions",
              1,
              `decision_id:${record.decision_id}`,
            );
          },
          "决策 ID",
        )],
        ["主体标识", () => {
          if (!record.subject_key) return "—";
          const identifier = createCopyableNavigationLink(
            record.subject_key,
            showSubjectHistory,
            "主体标识",
          );
          if (identifier instanceof HTMLElement) {
            identifier.classList.add("registry-subject-identifier");
            identifier.title = record.subject_key;
          }
          return identifier;
        }],
        ["主体类型", subjectTypeLabels[record.subject_type] || record.subject_type],
        ["来源", record.source],
        ["策略", record.strategy],
        ["决策结果", createDecisionBadge(record.decision)],
        ["概率", formatProbability(record.probability)],
        ["评分", formatScore(record.score)],
        ["耗时", formatOptionalDuration(record.latency_ms)],
        ["决策时间", formatTime(record.decided_at)],
      ], dialog, "info", appendRequestDetail),
      createDecisionPath(record, dialog),
      createExecutionList(executions, dialog),
      createPredictionSection("预测结果", record, record.prediction, "prediction"),
      createJsonDetailSection("路由上下文", routingContext, "metadata"),
    );
    appendDetailFooter(dialog, [
      createNavigationAction(
        "查看 API 调用",
        "request",
        "requests",
        record.request_id,
        dialog,
      ),
      createNavigationAction(
        "查看部署",
        "external",
        "deployments",
        record.deployment_id,
        dialog,
      ),
    ]);
    mountDetailDrawer(dialog, { section: "decisions", id: record.decision_id });
  }

  function showExecutionDrawer(record) {
    if (!record) return;
    const { dialog, body } = createDetailDrawer(
      "执行记录详情",
      "inference-detail-drawer execution-detail-drawer",
    );
    body.append(
      createDetailSummary({
        icon: "execution",
        title: record.model_name || "模型执行",
        subtitle: record.model_version || "未指定版本",
        status: record.status,
        badges: [
          createExecutionTypeBadge(record.execution_type),
          createDetailBadge(formatOptionalDuration(record.latency_ms), "blue"),
        ],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["执行 ID", () => createCopyableNavigationLink(
          record.execution_id,
          () => {
            dialog.close();
            navigateToSection(
              "executions",
              1,
              `execution_id:${record.execution_id}`,
            );
          },
          "执行 ID",
        )],
        ["执行类型", createExecutionTypeBadge(record.execution_type)],
        ["状态", createStatusBadge(record.status)],
        ["模型名称", record.model_name],
        ["版本", record.model_version],
        ["概率", formatProbability(record.probability)],
        ["评分", formatScore(record.score)],
        ["耗时", formatOptionalDuration(record.latency_ms)],
        ["开始时间", formatTime(record.started_at)],
        ["完成时间", formatTime(record.finished_at)],
      ], dialog, "info", appendRequestDetail),
    );
    const routingSection = createExecutionRoutingSection(record, dialog);
    if (routingSection) body.append(routingSection);
    if (record.error) {
      body.append(createErrorDetailSection(
        record.error_type
          ? `${record.error_type}: ${record.error}`
          : record.error,
      ));
    }
    body.append(
      createPredictionSection("执行结果", record, record.prediction, "prediction"),
      createJsonDetailSection("执行上下文", record.context, "metadata"),
    );
    appendDetailFooter(dialog, [
      createNavigationAction(
        "查看 API 调用",
        "request",
        "requests",
        record.request_id,
        dialog,
      ),
      createNavigationAction(
        "查看决策",
        "decision",
        "decisions",
        record.decision_id,
        dialog,
      ),
      createNavigationAction(
        "查看部署",
        "external",
        "deployments",
        record.deployment_id,
        dialog,
      ),
    ]);
    mountDetailDrawer(dialog, {
      section: "executions",
      id: record.execution_id,
    });
  }

  return { showDecisionDrawer, showExecutionDrawer, showRequestDrawer };
}
