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
  formatBadgeValue,
  formatPredictionDetails,
  formatStatusValue,
  mountDetailDrawer,
} from "./common.js";

import {
  buildAttemptSummaryBadges,
  buildAttemptSummaryCopy,
  buildShardTimelineData,
  formatTimelineDateTime,
  formatTimelineTick,
  getAttemptShards,
  layoutTimelineRows,
} from "./attempt/timeline.js";

/** @typedef {import("./attempt/timeline.js").BatchShardRecord} BatchShardRecord */

/**
 * 创建推理链路详情控制器。
 *
 * 详情串联 API 调用、决策结果和模型执行记录。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   createAttemptExecutionPage: (record: Object, view: string) => HTMLElement,
 *   showAttemptDrawer: (record: Object) => void,
 *   showBatchDrawer: (record: Object) => void,
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
  formatDecisionSource,
  formatDecisionStrategy,
  formatTime,
  navigateToAttemptView,
  navigateToSection,
  request,
  sectionIdFields,
}) {
  const createTaskStatusBadge = (value) => createStatusBadge(value, "task");
  const taskStatusLabels = {
    queued: "排队中",
    running: "执行中",
    retrying: "等待重试",
    succeeded: "成功",
    partially_succeeded: "部分成功",
    failed: "失败",
    cancelled: "已取消",
  };
  const formatTaskStatus = (value) => (
    taskStatusLabels[String(value || "").toLowerCase()]
    || String(value || "未知")
  );
  const attemptTableScrollPositions = new Map();
  const attemptShardViewStates = new Map();
  let closeAttemptActionMenu = null;

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

  const roleLabels = {
    champion: "Champion",
    challenger: "Challenger",
    shadow: "Shadow",
  };

  function createNavigationAction(label, section, identifier, dialog) {
    if (!identifier) return null;
    const button = createDetailAction(label, "view");
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

  function formatElapsedTime(startValue, endValue) {
    if (!startValue || !endValue) return "—";
    const elapsed = Date.parse(endValue) - Date.parse(startValue);
    if (!Number.isFinite(elapsed) || elapsed < 0) return "—";
    return `${(elapsed / 1_000).toFixed(2)} 秒`;
  }

  function createWorkerNodes(workerIds, kind = "executors") {
    const values = (Array.isArray(workerIds) ? workerIds : [workerIds])
      .map((value) => String(value || "").trim())
      .filter(Boolean);
    const nodes = document.createElement("div");
    nodes.className = `attempt-worker-text ${kind}`;
    nodes.setAttribute("aria-label", kind === "coordinator"
      ? "协调节点"
      : `${values.length} 个执行节点`);
    if (!values.length) {
      const empty = document.createElement("span");
      empty.className = "attempt-worker-empty";
      empty.textContent = "尚未分配";
      nodes.append(empty);
      return nodes;
    }
    for (const value of values) {
      const node = document.createElement("span");
      node.title = value;
      node.textContent = value;
      nodes.append(node);
    }
    return nodes;
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
        createTaskStatusBadge(execution.status),
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

  function createBatchDeploymentList(deployments, dialog) {
    const section = document.createElement("section");
    section.className = "registry-detail-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("deployment", "registry-section-icon"),
      document.createTextNode("命中部署"),
    );
    const grid = document.createElement("div");
    grid.className = "batch-deployment-grid";
    if (!Array.isArray(deployments) || deployments.length === 0) {
      const empty = document.createElement("p");
      empty.className = "registry-related-empty";
      empty.textContent = "暂无部署执行记录";
      grid.append(empty);
    }
    for (const deployment of deployments || []) {
      const isShadow = deployment.execution_type === "shadow";
      const card = document.createElement("article");
      card.className = `batch-deployment-card ${isShadow ? "shadow" : "primary"}`;
      const summary = document.createElement("div");
      summary.className = "batch-deployment-summary";
      const label = document.createElement("span");
      label.className = "batch-deployment-label";
      label.textContent = isShadow ? "影子执行部署" : "主执行部署";
      const count = document.createElement("span");
      count.className = "batch-deployment-count";
      count.textContent = `${deployment.execution_count ?? 0} 条执行`;
      const model = document.createElement("div");
      model.className = "batch-deployment-model";
      const modelName = document.createElement("strong");
      modelName.textContent = deployment.model_name || "未知模型";
      const modelVersion = document.createElement("span");
      modelVersion.textContent = deployment.model_version
        ? `版本 ${deployment.model_version}`
        : "版本未知";
      model.append(modelName, modelVersion);
      const viewDeployment = document.createElement("button");
      viewDeployment.type = "button";
      viewDeployment.className = "batch-deployment-action";
      viewDeployment.setAttribute(
        "aria-label",
        `查看部署：${deployment.model_name || "未知模型"} ${deployment.model_version || ""}`.trim(),
      );
      viewDeployment.append(
        document.createTextNode("查看部署"),
        createDetailIcon("arrow"),
      );
      viewDeployment.addEventListener("click", () => {
        dialog.close();
        navigateToSection(
          "deployments",
          1,
          `deployment_id:${deployment.deployment_id}`,
        );
      });
      summary.append(label, viewDeployment);
      card.append(summary, model, count);
      grid.append(card);
    }
    section.append(heading, grid);
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
          formatDecisionStrategy(record.strategy),
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
          formatDecisionStrategy(record.strategy),
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
              `耗时 ${formatOptionalDuration(record.latency_ms)}`,
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
        ...(record.batch_id ? [
          ["批次 ID", () => createCopyableNavigationLink(
            record.batch_id,
            () => {
              dialog.close();
              navigateToSection(
                "batches",
                1,
                `batch_id:${record.batch_id}`,
              );
            },
            "批次 ID",
          )],
          ["批次位置", record.batch_index !== null
            && record.batch_index !== undefined
            ? Number(record.batch_index) + 1
            : null],
        ] : []),
        ["状态", formatStatusValue(record.status, createStatusBadge)],
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
        "decisions",
        record.decision_id,
        dialog,
      ),
      createNavigationAction(
        "查看部署",
        "deployments",
        record.deployment_id,
        dialog,
      ),
    ]);
    mountDetailDrawer(dialog, { section: "requests", id: record.request_id });
  }

  function showBatchDrawer(record) {
    if (!record) return;
    const { dialog, body } = createDetailDrawer(
      "批量任务详情",
      "inference-detail-drawer batch-detail-drawer",
    );
    body.append(
      createDetailSummary({
        icon: "request",
        title: record.model_name || "批量预测",
        subtitle: record.source || "",
        status: record.status,
        badges: [
          createDetailBadge(`${record.completed_count ?? 0}/${record.total_count ?? 0} 已完成`),
          createDetailBadge(
            `执行 ${record.attempt_count ?? 0} 次 · 重试 ${record.retry_count ?? 0} 次`,
            "blue",
          ),
        ],
        createStatusBadge: createTaskStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["批次 ID", () => createCopyableNavigationLink(
          record.batch_id,
          () => {
            dialog.close();
            navigateToSection(
              "batches",
              1,
              `batch_id:${record.batch_id}`,
            );
          },
          "批次 ID",
        )],
        ["任务 ID", () => {
          if (!record.task_id) return "—";
          return createCopyableNavigationLink(
            record.task_id,
            () => {
              dialog.close();
              navigateToSection(
                "attempts",
                1,
                `task_id:${record.task_id}`,
              );
            },
            "任务 ID",
          );
        }],
        ["状态", formatStatusValue(record.status, createStatusBadge, "task")],
        ["总数", record.total_count],
        ["已完成", record.completed_count],
        ["成功", record.succeeded_count],
        ["失败", record.failed_count],
        ["执行次数", record.attempt_count],
        ["重试次数", record.retry_count],
        ["提交用户", record.user],
        ["客户端 IP", record.ip],
        ["提交时间", formatTime(record.created_at)],
        ["开始时间", formatTime(record.started_at)],
        ["完成时间", formatTime(record.finished_at)],
        ...(["cancelling", "cancelled"].includes(record.status)
          ? [["取消请求时间", formatTime(record.cancel_requested_at)]]
          : []),
      ], dialog, "info", appendRequestDetail),
    );
    body.append(createBatchDeploymentList(record.deployments, dialog));
    if (record.error) body.append(createErrorDetailSection(record.error));
    body.append(
      createJsonDetailSection("请求负载", record.payload, "payload"),
      createJsonDetailSection("执行结果", record.result, "response"),
    );
    appendDetailFooter(dialog, [
      (() => {
        const action = createDetailAction("查看任务执行", "view");
        action.addEventListener("click", () => {
          dialog.close();
          navigateToSection(
            "attempts",
            1,
            `batch_id:${record.batch_id}`,
            "attempt_number",
            "asc",
            20,
          );
        });
        return action;
      })(),
      (() => {
        const action = createDetailAction("查看批次调用", "view");
        action.addEventListener("click", () => {
          dialog.close();
          navigateToSection(
            "requests",
            1,
            `batch_id:${record.batch_id}`,
          );
        });
        return action;
      })(),
    ]);
    mountDetailDrawer(dialog, {
      section: "batches",
      id: record.batch_id,
    });
  }

  function showAttemptDrawer(record) {
    if (!record) return;
    const queueDuration = formatElapsedTime(
      record.queued_at,
      record.started_at,
    );
    const executionDuration = formatElapsedTime(
      record.started_at,
      record.finished_at,
    );
    const totalDuration = formatElapsedTime(
      record.queued_at,
      record.finished_at,
    );
    const { dialog, body } = createDetailDrawer(
      "任务执行详情",
      "inference-detail-drawer attempt-detail-drawer",
    );
    const shards = getAttemptShards(record);
    const workerIds = Array.isArray(record.worker_ids) ? record.worker_ids : [];
    const summaryCopy = buildAttemptSummaryCopy(record, workerIds.length);
    const navigateToShardRequests = (shard) => {
      const rangeStart = Number(shard.start_index || 0);
      const rangeEnd = Math.max(
        rangeStart,
        Number(shard.end_index || rangeStart + 1) - 1,
      );
      const pageSize = Math.max(
        1,
        Math.min(100, Number(shard.total_count) || 20),
      );
      dialog.close();
      navigateToSection(
        "requests",
        1,
        `batch_id:${record.batch_id} batch_index:${rangeStart}..${rangeEnd}`,
        "batch_index",
        "asc",
        pageSize,
      );
    };
    const progressSection = document.createElement("section");
    progressSection.className = "registry-detail-section attempt-progress-section";
    const progressHeading = document.createElement("h4");
    progressHeading.append(
      createDetailIcon("parallel", "registry-section-icon"),
      document.createTextNode("执行进度"),
    );
    const progressHeader = document.createElement("div");
    progressHeader.className = "attempt-progress-heading";
    const progressDetailsAction = document.createElement("button");
    progressDetailsAction.type = "button";
    progressDetailsAction.className = "registry-section-link attempt-progress-details-action";
    progressDetailsAction.textContent = "查看全部";
    progressDetailsAction.addEventListener("click", () => {
      dialog.close();
      navigateToAttemptView(record, "shards");
    });
    progressHeader.append(progressHeading, progressDetailsAction);
    const succeededCount = shards.reduce(
      (total, shard) => total + Number(shard.succeeded_count || 0), 0,
    );
    const failedCount = shards.reduce(
      (total, shard) => total + Number(shard.failed_count || 0), 0,
    );
    const summaryGrid = document.createElement("div");
    summaryGrid.className = "attempt-execution-summary";
    for (const [label, value, tone] of [
      ["处理进度", `${record.completed_count ?? 0}/${record.total_count ?? 0}`, ""],
      ["成功", succeededCount, "success"],
      ["失败", failedCount, failedCount ? "danger" : ""],
      ["执行节点", workerIds.length, ""],
    ]) {
      const metric = document.createElement("div");
      if (tone) metric.classList.add(tone);
      const metricValue = document.createElement("strong");
      metricValue.textContent = String(value);
      const metricLabel = document.createElement("span");
      metricLabel.textContent = label;
      metric.append(metricValue, metricLabel);
      summaryGrid.append(metric);
    }
    const progressLine = document.createElement("div");
    progressLine.className = "attempt-progress-line";
    const progressTrack = document.createElement("span");
    progressTrack.className = "attempt-progress-track";
    const progressBar = document.createElement("span");
    progressBar.style.width = `${Math.max(0, Math.min(100, Number(record.progress_percent) || 0))}%`;
    progressTrack.append(progressBar);
    const progressPercent = document.createElement("span");
    progressPercent.textContent = `${record.progress_percent ?? 0}%`;
    progressLine.append(progressTrack, progressPercent);
    const timelineData = buildShardTimelineData(shards);
    const timeline = document.createElement("div");
    timeline.className = "attempt-shard-timeline";
    const timelineHeading = document.createElement("div");
    timelineHeading.className = "attempt-timeline-heading";
    const timelineTitle = document.createElement("h5");
    timelineTitle.textContent = "时间轴";
    const timelinePeak = document.createElement("span");
    timelinePeak.textContent = timelineData.peak > 0
      ? `峰值并行 ${timelineData.peak} 个子任务`
      : "尚无执行时间";
    timelineHeading.append(timelineTitle, timelinePeak);
    timeline.append(timelineHeading);
    if (timelineData.entries.length) {
      const duration = timelineData.end - timelineData.start;
      const axis = document.createElement("div");
      axis.className = "attempt-timeline-axis";
      const axisSpacer = document.createElement("span");
      const axisTicks = document.createElement("div");
      for (const ratio of [0, 0.5, 1]) {
        const tick = document.createElement("time");
        const value = timelineData.start + duration * ratio;
        tick.textContent = formatTimelineTick(value);
        tick.dateTime = new Date(value).toISOString();
        axisTicks.append(tick);
      }
      axis.append(axisSpacer, axisTicks);
      timeline.append(axis);
      const lanes = new Map();
      for (const entry of timelineData.entries) {
        const workerId = entry.shard.worker_id || "待分配";
        if (!lanes.has(workerId)) lanes.set(workerId, []);
        lanes.get(workerId).push(entry);
      }
      let laneIndex = 0;
      for (const [workerId, entries] of lanes) {
        const layout = layoutTimelineRows(entries);
        const lane = document.createElement("div");
        lane.className = "attempt-timeline-lane";
        const label = document.createElement("span");
        label.className = "attempt-timeline-worker";
        const [workerName, workerHost] = String(workerId).split("@");
        const labelPrimary = document.createElement("strong");
        labelPrimary.textContent = workerName;
        label.append(labelPrimary);
        if (workerHost) {
          const labelSecondary = document.createElement("span");
          labelSecondary.textContent = workerHost;
          label.append(labelSecondary);
        }
        const track = document.createElement("div");
        track.className = "attempt-timeline-track";
        track.style.height = `${layout.rowCount * 18 + 8}px`;
        for (const entry of layout.entries) {
          const shard = entry.shard;
          const segment = document.createElement("button");
          const left = (entry.start - timelineData.start) * 100 / duration;
          const width = Math.max(0.35, (entry.end - entry.start) * 100 / duration);
          const first = (shard.start_index ?? 0) + 1;
          const last = shard.end_index ?? "末尾";
          segment.type = "button";
          segment.className = `attempt-timeline-segment worker-${laneIndex % 4}`;
          segment.style.top = `${entry.row * 18 + 4}px`;
          segment.style.left = `calc(${left}% + 1px)`;
          segment.style.width = `max(3px, calc(${Math.min(100 - left, width)}% - 2px))`;
          segment.title = [
            `子任务 ${first}–${last}`,
            `开始：${formatTime(shard.started_at)}`,
            `完成：${formatTime(shard.finished_at)}`,
            `耗时：${formatElapsedTime(shard.started_at, shard.finished_at)}`,
          ].join("\n");
          segment.setAttribute(
            "aria-label",
            `查看子任务 ${first} 至 ${last} 的 API 调用；${segment.title.replaceAll("\n", "；")}`,
          );
          segment.addEventListener("click", () => navigateToShardRequests(shard));
          track.append(segment);
        }
        lane.append(label, track);
        timeline.append(lane);
        laneIndex += 1;
      }
    }
    const shardFilters = document.createElement("div");
    shardFilters.className = "attempt-shard-filters";
    const shardSearch = document.createElement("input");
    shardSearch.type = "search";
    shardSearch.placeholder = "查询子任务 ID、分片 ID、数据范围或执行节点";
    shardSearch.setAttribute("aria-label", "查询子任务");
    const shardStatus = document.createElement("select");
    shardStatus.setAttribute("aria-label", "筛选子任务状态");
    for (const [value, label] of [
      ["", "全部状态"],
      ["queued", "排队中"],
      ["running", "执行中"],
      ["retrying", "等待重试"],
      ["succeeded", "成功"],
      ["partially_succeeded", "部分成功"],
      ["failed", "失败"],
      ["cancelled", "已取消"],
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      shardStatus.append(option);
    }
    const shardFilterResult = document.createElement("span");
    shardFilterResult.className = "attempt-shard-filter-result";
    shardFilterResult.setAttribute("aria-live", "polite");
    shardFilters.append(shardSearch, shardStatus, shardFilterResult);
    const tableWrap = document.createElement("div");
    tableWrap.className = "attempt-shard-table-wrap";
    const table = document.createElement("table");
    table.className = "attempt-shard-table";
    const tableHead = document.createElement("thead");
    const headingRow = document.createElement("tr");
    for (const label of [
      "数据范围", "状态", "进度", "执行节点", "开始时间", "完成时间", "耗时",
    ]) {
      const cell = document.createElement("th");
      cell.textContent = label;
      headingRow.append(cell);
    }
    tableHead.append(headingRow);
    const tableBody = document.createElement("tbody");
    const shardRows = [];
    for (const shard of shards) {
      const row = document.createElement("tr");
      row.title = shard.task_id ? `子任务 ID：${shard.task_id}` : "";
      row.dataset.status = String(shard.status || "");
      row.dataset.search = [
        `${(shard.start_index ?? 0) + 1}-${shard.end_index ?? ""}`,
        shard.shard_id,
        shard.task_id,
        shard.worker_id,
        shard.status,
      ].filter(Boolean).join(" ").toLocaleLowerCase();
      const rangeCell = document.createElement("td");
      rangeCell.className = "attempt-shard-range";
      const identity = document.createElement("span");
      identity.className = "attempt-shard-identity";
      const range = document.createElement("button");
      range.type = "button";
      range.className = "attempt-shard-range-action";
      range.textContent = `${(shard.start_index ?? 0) + 1}–${shard.end_index ?? "—"}`;
      range.setAttribute(
        "aria-label",
        `查看第 ${(shard.start_index ?? 0) + 1} 至 ${shard.end_index ?? "末尾"} 条 API 调用`,
      );
      range.addEventListener("click", () => {
        navigateToShardRequests(shard);
      });
      const taskId = document.createElement("span");
      taskId.textContent = shard.task_id || "尚未分配任务";
      taskId.title = shard.task_id || "";
      identity.append(range, taskId);
      rangeCell.append(identity);
      const statusCell = document.createElement("td");
      statusCell.append(createTaskStatusBadge(shard.status));
      const completedCell = document.createElement("td");
      completedCell.textContent = `${shard.completed_count ?? 0}/${shard.total_count ?? 0}`;
      const workerCell = document.createElement("td");
      const worker = document.createElement("span");
      worker.className = "attempt-shard-worker";
      const [workerName, workerHost] = String(shard.worker_id || "").split("@");
      const workerPrimary = document.createElement("strong");
      workerPrimary.textContent = workerName || "待分配";
      worker.append(workerPrimary);
      if (workerHost) {
        const host = document.createElement("span");
        host.textContent = workerHost;
        worker.append(host);
      }
      workerCell.append(worker);
      const startedCell = document.createElement("td");
      startedCell.className = "attempt-shard-time";
      startedCell.textContent = formatTime(shard.started_at);
      const finishedCell = document.createElement("td");
      finishedCell.className = "attempt-shard-time";
      finishedCell.textContent = formatTime(shard.finished_at);
      const durationCell = document.createElement("td");
      durationCell.textContent = formatElapsedTime(
        shard.started_at, shard.finished_at,
      );
      row.append(
        rangeCell,
        statusCell,
        completedCell,
        workerCell,
        startedCell,
        finishedCell,
        durationCell,
      );
      tableBody.append(row);
      shardRows.push(row);
    }
    let filteredEmpty = null;
    if (shards.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.className = "attempt-shard-empty";
      empty.textContent = "没有匹配的子任务";
      row.append(empty);
      row.hidden = true;
      filteredEmpty = row;
      tableBody.append(row);
    }
    if (!shards.length) {
      const row = document.createElement("tr");
      const empty = document.createElement("td");
      empty.colSpan = 7;
      empty.className = "attempt-shard-empty";
      empty.textContent = "尚未生成子任务";
      row.append(empty);
      tableBody.append(row);
    }
    const applyShardFilters = () => {
      const query = shardSearch.value.trim().toLocaleLowerCase();
      const selectedStatus = shardStatus.value;
      let visibleCount = 0;
      for (const row of shardRows) {
        const matchesQuery = !query || row.dataset.search.includes(query);
        const matchesStatus = (
          !selectedStatus || row.dataset.status === selectedStatus
        );
        row.hidden = !(matchesQuery && matchesStatus);
        if (!row.hidden) visibleCount += 1;
      }
      if (filteredEmpty) filteredEmpty.hidden = visibleCount > 0;
      shardFilterResult.textContent = `显示 ${visibleCount}/${shards.length} 个子任务`;
    };
    shardSearch.addEventListener("input", applyShardFilters);
    shardStatus.addEventListener("change", applyShardFilters);
    applyShardFilters();
    table.append(tableHead, tableBody);
    tableWrap.append(table);
    progressSection.append(
      progressHeader,
      summaryGrid,
      progressLine,
    );

    body.append(
      createDetailSummary({
        icon: "monitor",
        title: summaryCopy.title,
        subtitle: summaryCopy.subtitle,
        status: record.status,
        badges: buildAttemptSummaryBadges(record, executionDuration)
          .map(([value, tone]) => createDetailBadge(value, tone)),
        createStatusBadge: createTaskStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["执行实例 ID", () => createCopyableNavigationLink(
          record.attempt_id,
          () => {
            dialog.close();
            navigateToSection(
              "attempts",
              1,
              `attempt_id:${record.attempt_id}`,
            );
          },
          "执行实例 ID",
        )],
        ["批次 ID", () => createCopyableNavigationLink(
          record.batch_id,
          () => {
            dialog.close();
            navigateToSection("batches", 1, `batch_id:${record.batch_id}`);
          },
          "批次 ID",
        )],
        ["任务 ID", () => createCopyableNavigationLink(
          record.task_id,
          () => {
            dialog.close();
            navigateToSection(
              "attempts",
              1,
              `task_id:${record.task_id}`,
            );
          },
          "任务 ID",
        )],
        ["执行序号", record.attempt_number],
        ["状态", formatStatusValue(record.status, createStatusBadge, "task")],
        ["协调节点", () => createWorkerNodes(record.worker_id, "coordinator")],
        ["执行节点", () => createWorkerNodes(workerIds)],
      ], dialog, "info", appendRequestDetail),
      progressSection,
      createDetailSection("执行时序", [
        ["排队时间", formatTime(record.queued_at)],
        ["开始时间", formatTime(record.started_at)],
        ["完成时间", formatTime(record.finished_at)],
        ...(record.retry_scheduled_at
          ? [["自动重试时间", formatTime(record.retry_scheduled_at)]]
          : []),
        ["排队耗时", queueDuration],
        ["执行耗时", executionDuration],
        ["总耗时", totalDuration],
      ], dialog, "time", appendRequestDetail),
    );
    if (record.error) body.append(createErrorDetailSection(record.error));
    appendDetailFooter(dialog, [
      createNavigationAction(
        "查看批量任务",
        "batches",
        record.batch_id,
        dialog,
      ),
    ]);
    mountDetailDrawer(dialog, {
      section: "attempts",
      id: record.attempt_id,
    });
  }

  function navigateToShardRequests(record, shard) {
    const rangeStart = Number(shard.start_index || 0);
    const rangeEnd = Math.max(
      rangeStart,
      Number(shard.end_index || rangeStart + 1) - 1,
    );
    navigateToSection(
      "requests",
      1,
      `batch_id:${record.batch_id} batch_index:${rangeStart}..${rangeEnd}`,
      "batch_index",
      "asc",
      Math.max(1, Math.min(100, Number(shard.total_count) || 20)),
    );
  }

  function openShardActionMenu(anchor, record, shard) {
    const isCurrentMenu = anchor.getAttribute("aria-expanded") === "true";
    closeAttemptActionMenu?.();
    if (isCurrentMenu) return;

    const menu = document.createElement("div");
    menu.className = "row-action-menu";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", "子任务操作");
    const view = document.createElement("button");
    view.type = "button";
    view.className = "row-action-menu-button";
    view.textContent = "查看调用";
    view.setAttribute("role", "menuitem");
    view.addEventListener("click", () => {
      closeMenu();
      navigateToShardRequests(record, shard);
    });
    menu.append(view);

    function closeMenu() {
      document.removeEventListener("pointerdown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeydown);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      menu.remove();
      anchor.setAttribute("aria-expanded", "false");
      if (closeAttemptActionMenu === closeMenu) closeAttemptActionMenu = null;
    }

    function handleOutsideClick(event) {
      if (!menu.contains(event.target) && event.target !== anchor) closeMenu();
    }

    function handleKeydown(event) {
      if (event.key !== "Escape") return;
      closeMenu();
      anchor.focus();
    }

    menu.style.visibility = "hidden";
    document.body.append(menu);
    const anchorBounds = anchor.getBoundingClientRect();
    const menuBounds = menu.getBoundingClientRect();
    const viewportPadding = 12;
    menu.style.left = `${Math.min(
      window.innerWidth - menuBounds.width - viewportPadding,
      Math.max(viewportPadding, anchorBounds.right - menuBounds.width),
    )}px`;
    menu.style.top = `${window.innerHeight - anchorBounds.bottom >= menuBounds.height + 8
      ? anchorBounds.bottom + 6
      : Math.max(viewportPadding, anchorBounds.top - menuBounds.height - 6)}px`;
    menu.style.visibility = "visible";
    anchor.setAttribute("aria-expanded", "true");
    closeAttemptActionMenu = closeMenu;
    document.addEventListener("pointerdown", handleOutsideClick);
    document.addEventListener("keydown", handleKeydown);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    view.focus();
  }

  function createShardActionButton(record, shard) {
    const button = document.createElement("button");
    const icon = document.createElement("span");
    button.type = "button";
    button.className = "row-action-button";
    button.title = "更多操作";
    button.setAttribute("aria-label", `${shard.task_id || "子任务"}的更多操作`);
    button.setAttribute("aria-haspopup", "menu");
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", () => openShardActionMenu(button, record, shard));
    icon.className = "row-action-icon";
    icon.setAttribute("aria-hidden", "true");
    button.append(icon);
    return button;
  }

  function createAttemptPageSummary(record) {
    const shards = getAttemptShards(record);
    const workers = Array.isArray(record.worker_ids) ? record.worker_ids : [];
    const succeeded = shards.reduce(
      (total, shard) => total + Number(shard.succeeded_count || 0), 0,
    );
    const failed = shards.reduce(
      (total, shard) => total + Number(shard.failed_count || 0), 0,
    );
    const summary = document.createElement("div");
    summary.className = "attempt-page-summary";
    for (const [label, value, tone] of [
      ["处理进度", `${record.completed_count ?? 0}/${record.total_count ?? 0}`, ""],
      ["成功", succeeded, "success"],
      ["失败", failed, failed ? "danger" : ""],
      ["执行节点", workers.length, ""],
      ["执行耗时", formatElapsedTime(record.started_at, record.finished_at), ""],
    ]) {
      const metric = document.createElement("div");
      if (tone) metric.classList.add(tone);
      const strong = document.createElement("strong");
      strong.textContent = String(value);
      const span = document.createElement("span");
      span.textContent = label;
      metric.append(strong, span);
      summary.append(metric);
    }
    return summary;
  }

  function createAttemptTimelinePage(record) {
    const shards = getAttemptShards(record);
    const data = buildShardTimelineData(shards);
    const section = document.createElement("section");
    section.className = "attempt-page-panel attempt-page-timeline";
    const heading = document.createElement("div");
    heading.className = "attempt-page-panel-heading";
    const title = document.createElement("h3");
    title.textContent = "时间轴";
    heading.append(title);
    section.append(heading);

    if (!data.entries.length) {
      const empty = document.createElement("p");
      empty.className = "attempt-page-empty";
      empty.textContent = "当前执行实例尚无可展示的子任务时间数据。";
      section.append(empty);
      return section;
    }

    const chart = document.createElement("div");
    chart.className = "attempt-page-chart";
    const tooltip = document.createElement("div");
    tooltip.className = "attempt-timeline-tooltip";
    tooltip.hidden = true;
    const duration = data.end - data.start;
    const positionTooltip = (event) => {
      const chartBounds = chart.getBoundingClientRect();
      const tooltipBounds = tooltip.getBoundingClientRect();
      const pointerX = event.clientX - chartBounds.left;
      const pointerY = event.clientY - chartBounds.top;
      const maximumX = Math.max(12, chartBounds.width - tooltipBounds.width - 12);
      const left = Math.min(Math.max(12, pointerX + 14), maximumX);
      const above = pointerY - tooltipBounds.height - 14;
      const preferredTop = above >= 12 ? above : pointerY + 14;
      const maximumY = Math.max(12, chartBounds.height - tooltipBounds.height - 12);
      const top = Math.min(Math.max(12, preferredTop), maximumY);
      tooltip.style.left = `${left}px`;
      tooltip.style.top = `${top}px`;
    };
    const showTooltip = (event, entry, first, last) => {
      const shard = entry.shard;
      const heading = document.createElement("div");
      heading.className = "attempt-timeline-tooltip-heading";
      const title = document.createElement("strong");
      title.textContent = "子任务";
      const status = document.createElement("span");
      status.className = "attempt-timeline-tooltip-status";
      status.dataset.status = String(shard.status || "").toLowerCase();
      status.textContent = formatTaskStatus(shard.status);
      heading.append(title, status);
      const taskId = document.createElement("span");
      taskId.className = "attempt-timeline-tooltip-id";
      taskId.textContent = shard.task_id || "尚未分配子任务 ID";
      const rangeValue = String(first) === String(last)
        ? String(first)
        : `${first}–${last}`;
      const details = document.createElement("dl");
      details.className = "attempt-timeline-tooltip-details";
      for (const [label, value] of [
        ["数据范围", rangeValue],
        ["开始时间", formatTimelineDateTime(shard.started_at)],
        ["完成时间", formatTimelineDateTime(shard.finished_at)],
        ["耗时", formatElapsedTime(shard.started_at, shard.finished_at)],
        ["进度", `${shard.completed_count ?? 0}/${shard.total_count ?? 0}`],
      ]) {
        const term = document.createElement("dt");
        term.textContent = label;
        const description = document.createElement("dd");
        description.textContent = value;
        details.append(term, description);
      }
      tooltip.replaceChildren(heading, taskId, details);
      tooltip.hidden = false;
      positionTooltip(event);
    };
    const axis = document.createElement("div");
    axis.className = "attempt-page-axis";
    axis.append(document.createElement("span"));
    const ticks = document.createElement("div");
    for (const ratio of [0, 0.25, 0.5, 0.75, 1]) {
      const tick = document.createElement("time");
      const value = data.start + duration * ratio;
      tick.textContent = formatTimelineTick(value).split(".")[0];
      tick.dateTime = new Date(value).toISOString();
      ticks.append(tick);
    }
    axis.append(ticks);
    chart.append(axis);
    const shardColorIndexes = new Map(
      data.entries.map((entry, index) => [entry.shard, index]),
    );
    const lanes = new Map();
    for (const entry of data.entries) {
      const workerId = entry.shard.worker_id || "待分配";
      if (!lanes.has(workerId)) lanes.set(workerId, []);
      lanes.get(workerId).push(entry);
    }
    let laneNumber = 0;
    for (const [workerId, entries] of lanes) {
      laneNumber += 1;
      const layout = layoutTimelineRows(entries);
      const lane = document.createElement("div");
      lane.className = "attempt-page-lane";
      const label = document.createElement("span");
      label.className = "attempt-timeline-worker attempt-page-worker-label";
      label.title = String(workerId);
      const [workerName, workerHost] = String(workerId).split("@");
      const index = document.createElement("span");
      index.className = "attempt-page-worker-index";
      index.textContent = String(laneNumber).padStart(2, "0");
      const primary = document.createElement("strong");
      primary.textContent = workerName;
      label.append(index, primary);
      if (workerHost) {
        const secondary = document.createElement("span");
        secondary.className = "attempt-page-worker-host";
        secondary.textContent = workerHost;
        label.append(secondary);
      }
      const track = document.createElement("div");
      track.className = "attempt-timeline-track";
      track.style.height = `${layout.rowCount * 32 + 8}px`;
      for (const entry of layout.entries) {
        const shard = entry.shard;
        const first = Number(shard.start_index || 0) + 1;
        const last = shard.end_index ?? "末尾";
        const left = (entry.start - data.start) * 100 / duration;
        const width = Math.max(0.35, (entry.end - entry.start) * 100 / duration);
        const segment = document.createElement("span");
        segment.className = "attempt-timeline-segment";
        const colorIndex = shardColorIndexes.get(shard) ?? 0;
        const hue = Math.round((168 + colorIndex * 137.508) % 360);
        segment.style.backgroundColor = `hsl(${hue} 58% 42%)`;
        segment.style.top = `${entry.row * 32 + 8}px`;
        segment.style.left = `calc(${left}% + 1px)`;
        segment.style.width = `max(4px, calc(${Math.min(100 - left, width)}% - 2px))`;
        segment.textContent = `${first}–${last}`;
        segment.setAttribute(
          "aria-label",
          `子任务 ${first} 至 ${last}，${formatTaskStatus(shard.status)}`,
        );
        segment.addEventListener("pointerenter", (event) => {
          showTooltip(event, entry, first, last);
        });
        segment.addEventListener("pointermove", positionTooltip);
        segment.addEventListener("pointerleave", () => {
          tooltip.hidden = true;
        });
        track.append(segment);
      }
      lane.append(label, track);
      chart.append(lane);
    }
    chart.append(tooltip);
    section.append(chart);
    return section;
  }

  function createAttemptShardPage(record) {
    closeAttemptActionMenu?.();
    const shards = getAttemptShards(record);
    const viewKey = String(record.attempt_id || "");
    const savedView = attemptShardViewStates.get(viewKey) || {
      query: "",
      status: "",
      pageSize: 10,
      currentPage: 1,
    };
    const section = document.createElement("section");
    section.className = "attempt-page-panel attempt-page-shards";
    const filters = document.createElement("div");
    filters.className = "attempt-page-filters";
    const search = document.createElement("input");
    search.type = "search";
    search.value = savedView.query;
    search.dataset.renderFocusKey = "attempt-shard-search";
    search.placeholder = "查询子任务 ID、分片 ID、数据范围或执行节点";
    search.setAttribute("aria-label", "查询子任务");
    const status = document.createElement("select");
    status.setAttribute("aria-label", "筛选子任务状态");
    for (const [value, label] of [
      ["", "全部状态"], ["queued", "排队中"], ["running", "执行中"],
      ["retrying", "等待重试"], ["succeeded", "成功"],
      ["partially_succeeded", "部分成功"], ["failed", "失败"],
      ["cancelled", "已取消"],
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label;
      status.append(option);
    }
    status.value = savedView.status;
    const result = document.createElement("span");
    result.setAttribute("aria-live", "polite");
    filters.append(search, status, result);
    const wrap = document.createElement("div");
    wrap.className = "attempt-page-table-wrap";
    const scrollPosition = attemptTableScrollPositions.get(viewKey)
      || { left: 0, top: 0 };
    window.requestAnimationFrame(() => {
      if (!wrap.isConnected) return;
      wrap.scrollLeft = scrollPosition.left;
      wrap.scrollTop = scrollPosition.top;
    });
    wrap.addEventListener("scroll", () => {
      attemptTableScrollPositions.set(viewKey, {
        left: wrap.scrollLeft,
        top: wrap.scrollTop,
      });
    }, { passive: true });
    const table = document.createElement("table");
    table.className = "attempt-page-table";
    const head = document.createElement("thead");
    const headingRow = document.createElement("tr");
    for (const label of [
      "子任务 ID", "分片 ID", "数据范围", "状态", "进度", "执行节点",
      "开始时间", "完成时间", "耗时", "操作",
    ]) {
      const cell = document.createElement("th");
      cell.textContent = label;
      headingRow.append(cell);
    }
    head.append(headingRow);
    const body = document.createElement("tbody");
    const rows = [];
    for (const shard of shards) {
      const first = Number(shard.start_index || 0) + 1;
      const last = shard.end_index ?? "—";
      const row = document.createElement("tr");
      row.dataset.status = String(shard.status || "");
      row.dataset.search = [
        `${first}-${last}`, shard.shard_id, shard.task_id, shard.worker_id,
      ].filter(Boolean).join(" ").toLocaleLowerCase();
      const shardId = document.createElement("td");
      shardId.className = "attempt-page-id";
      shardId.textContent = shard.shard_id || "—";
      const rangeCell = document.createElement("td");
      rangeCell.className = "attempt-page-range";
      const range = document.createElement("strong");
      range.textContent = `${first}–${last}`;
      rangeCell.append(range);
      const taskId = document.createElement("td");
      taskId.className = "attempt-page-id";
      taskId.textContent = shard.task_id || "尚未分配";
      const statusCell = document.createElement("td");
      statusCell.append(createTaskStatusBadge(shard.status));
      const progress = document.createElement("td");
      progress.textContent = `${shard.completed_count ?? 0}/${shard.total_count ?? 0}`;
      const worker = document.createElement("td");
      worker.textContent = shard.worker_id || "待分配";
      const started = document.createElement("td");
      started.className = "attempt-page-time";
      started.textContent = formatTime(shard.started_at);
      const finished = document.createElement("td");
      finished.className = "attempt-page-time";
      finished.textContent = formatTime(shard.finished_at);
      const elapsed = document.createElement("td");
      elapsed.textContent = formatElapsedTime(shard.started_at, shard.finished_at);
      const operation = document.createElement("td");
      operation.className = "attempt-page-actions";
      operation.append(createShardActionButton(record, shard));
      row.append(
        taskId, shardId, rangeCell, statusCell, progress, worker,
        started, finished, elapsed, operation,
      );
      body.append(row);
      rows.push(row);
    }
    const emptyRow = document.createElement("tr");
    const empty = document.createElement("td");
    empty.colSpan = 10;
    empty.className = "attempt-page-empty";
    empty.textContent = shards.length ? "没有匹配的子任务" : "尚未生成子任务";
    emptyRow.append(empty);
    emptyRow.hidden = shards.length > 0;
    body.append(emptyRow);
    const pagination = document.createElement("div");
    pagination.className = "pagination attempt-page-pagination";
    const pageSizeLabel = document.createElement("label");
    pageSizeLabel.className = "page-size";
    pageSizeLabel.append(document.createTextNode("每页"));
    const pageSizeSelect = document.createElement("select");
    pageSizeSelect.setAttribute("aria-label", "每页显示的子任务数量");
    for (const value of [10, 20, 50]) {
      const option = document.createElement("option");
      option.value = String(value);
      option.textContent = String(value);
      pageSizeSelect.append(option);
    }
    pageSizeSelect.value = String(savedView.pageSize);
    if (!pageSizeSelect.value) pageSizeSelect.value = "10";
    pageSizeLabel.append(pageSizeSelect, document.createTextNode("条"));
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "secondary-button";
    previous.textContent = "上一页";
    const pageIndicator = document.createElement("span");
    pageIndicator.className = "page-indicator";
    pageIndicator.setAttribute("aria-live", "polite");
    const next = document.createElement("button");
    next.type = "button";
    next.className = "secondary-button";
    next.textContent = "下一页";
    pagination.append(pageSizeLabel, previous, pageIndicator, next);
    let currentPage = Math.max(1, Number(savedView.currentPage) || 1);
    let pageSize = Number(pageSizeSelect.value);
    const renderRows = (resetPage = false) => {
      if (resetPage) currentPage = 1;
      const query = search.value.trim().toLocaleLowerCase();
      const matchingRows = rows.filter((row) => (
          (!query || row.dataset.search.includes(query))
          && (!status.value || row.dataset.status === status.value)
      ));
      const totalPages = Math.max(1, Math.ceil(matchingRows.length / pageSize));
      currentPage = Math.min(currentPage, totalPages);
      const firstIndex = (currentPage - 1) * pageSize;
      const visibleRows = new Set(
        matchingRows.slice(firstIndex, firstIndex + pageSize),
      );
      for (const row of rows) {
        row.hidden = !visibleRows.has(row);
      }
      emptyRow.hidden = matchingRows.length > 0;
      result.textContent = `共 ${matchingRows.length} 个子任务`;
      pageIndicator.textContent = `${currentPage} / ${totalPages}`;
      previous.disabled = currentPage <= 1;
      next.disabled = currentPage >= totalPages;
      attemptShardViewStates.set(viewKey, {
        query: search.value,
        status: status.value,
        pageSize,
        currentPage,
      });
    };
    search.addEventListener("input", () => renderRows(true));
    status.addEventListener("change", () => renderRows(true));
    pageSizeSelect.addEventListener("change", () => {
      pageSize = Number(pageSizeSelect.value);
      renderRows(true);
    });
    previous.addEventListener("click", () => {
      currentPage = Math.max(1, currentPage - 1);
      renderRows();
    });
    next.addEventListener("click", () => {
      currentPage += 1;
      renderRows();
    });
    renderRows();
    table.append(head, body);
    wrap.append(table);
    section.append(filters, wrap, pagination);
    return section;
  }

  function createAttemptExecutionPage(record, view) {
    const currentView = view === "shards" ? "shards" : "timeline";
    const shards = getAttemptShards(record);
    const page = document.createElement("article");
    page.className = "attempt-execution-page";
    const navigation = document.createElement("nav");
    navigation.className = "attempt-page-navigation";
    navigation.setAttribute("aria-label", "执行进度视图");
    for (const [target, label] of [
      ["shards", `子任务 ${shards.length}`],
      ["timeline", "时间轴"],
    ]) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = label;
      button.classList.toggle("active", target === currentView);
      button.setAttribute("aria-current", target === currentView ? "page" : "false");
      button.addEventListener("click", () => navigateToAttemptView(record, target));
      navigation.append(button);
    }
    page.append(
      createAttemptPageSummary(record),
      navigation,
      currentView === "timeline"
        ? createAttemptTimelinePage(record)
        : createAttemptShardPage(record),
    );
    return page;
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
        subtitle: [
          formatDecisionStrategy(record.strategy),
          formatDecisionSource(record.source),
        ].filter((value) => value !== "—").join(" · "),
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
        ["来源", formatDecisionSource(record.source)],
        ["策略", formatDecisionStrategy(record.strategy)],
        ["决策结果", formatBadgeValue(record.decision, createDecisionBadge)],
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
        "requests",
        record.request_id,
        dialog,
      ),
      createNavigationAction(
        "查看部署",
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
          createDetailBadge(
            `耗时 ${formatOptionalDuration(record.latency_ms)}`,
            "blue",
          ),
        ],
        createStatusBadge: createTaskStatusBadge,
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
        ["执行类型", formatBadgeValue(
          record.execution_type,
          createExecutionTypeBadge,
        )],
        ["状态", formatStatusValue(record.status, createStatusBadge, "task")],
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
        "requests",
        record.request_id,
        dialog,
      ),
      createNavigationAction(
        "查看决策",
        "decisions",
        record.decision_id,
        dialog,
      ),
      createNavigationAction(
        "查看部署",
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

  return {
    createAttemptExecutionPage,
    showAttemptDrawer,
    showBatchDrawer,
    showDecisionDrawer,
    showExecutionDrawer,
    showRequestDrawer,
  };
}
