"use strict";

/**
 * @typedef {Object} ConsoleUser
 * @property {string} username
 * @property {string | null} display_name
 * @property {string[]} roles
 */

/**
 * @typedef {Object} RequestTrendPoint
 * @property {string} time
 * @property {number} count
 * @property {number} success_count
 * @property {number} failed_count
 */

/**
 * @typedef {Object} ConsoleSnapshot
 * @property {string} generated_at
 * @property {Object.<string, boolean>} access
 * @property {Object.<string, number>} counts
 * @property {Object.<string, Object[]>} sections
 * @property {RequestTrendPoint[]} request_trend
 */

/**
 * @typedef {Object} PageData
 * @property {Object[]} items
 * @property {number} page
 * @property {number} page_size
 * @property {boolean} has_previous
 * @property {boolean} has_next
 * @property {string} query
 * @property {string | null} sort_by
 * @property {string} sort_order
 */

/**
 * @typedef {Object} ExperimentReference
 * @property {string} experiment_id
 * @property {string} name
 * @property {number} [variant_count]
 */

/**
 * @typedef {Object} VariantPageData
 * @property {ExperimentReference} experiment
 * @property {ConsoleVariant[]} items
 * @property {number} page
 * @property {number} page_size
 * @property {boolean} has_previous
 * @property {boolean} has_next
 * @property {string} query
 * @property {string | null} sort_by
 * @property {string} sort_order
 */

/**
 * @typedef {Object} ConsoleVariant
 * @property {string} variant_id
 * @property {string} experiment_id
 * @property {string} name
 * @property {string} deployment_id
 * @property {number} weight
 * @property {boolean} is_control
 * @property {string} group_type
 * @property {string} status
 * @property {Object | null} config
 * @property {string | null} description
 * @property {string | null} created_by
 * @property {string | null} updated_by
 * @property {string | null} created_at
 * @property {string | null} updated_at
 */

/**
 * @typedef {Object} ConsoleModel
 * @property {string} model_id
 * @property {string} name
 * @property {Object[]} [versions]
 */

/**
 * @typedef {Object} VersionPageData
 * @property {ConsoleModel} model
 * @property {Object[]} items
 * @property {number} page
 * @property {number} page_size
 * @property {boolean} has_previous
 * @property {boolean} has_next
 * @property {string} query
 * @property {string | null} sort_by
 * @property {string} sort_order
 */

/**
 * @typedef {[string, string, string?, string?]} ColumnConfig
 */

/**
 * @typedef {Object} SectionConfig
 * @property {string} label
 * @property {string} title
 * @property {ColumnConfig[]} columns
 */

/**
 * @typedef {Object} ConsoleRequest
 * @property {string} request_id
 * @property {string} model_id
 * @property {string | null} model_name
 * @property {string | null} model_version
 * @property {string | null} deployment_id
 * @property {string | null} decision_id
 * @property {Object | null} payload
 * @property {Object | null} response
 * @property {Object | null} prediction
 * @property {string} source
 * @property {string} status
 * @property {string | null} error
 * @property {number | null} latency_ms
 * @property {string | null} user
 * @property {string | null} ip
 * @property {string} created_at
 */

/**
 * @typedef {Object} ConsoleDecision
 * @property {string} decision_id
 * @property {string} request_id
 * @property {string} model_id
 * @property {string | null} model_name
 * @property {string} version_id
 * @property {string | null} model_version
 * @property {string | null} deployment_id
 * @property {string | null} experiment_id
 * @property {string | null} variant_id
 * @property {string | null} assignment_id
 * @property {string | null} subject_key
 * @property {string | null} subject_type
 * @property {string} source
 * @property {string | null} strategy
 * @property {string | null} bucket
 * @property {string | null} group
 * @property {number | null} weight
 * @property {Object | null} prediction
 * @property {number | null} probability
 * @property {number | null} score
 * @property {number | null} latency_ms
 * @property {Object | null} context
 * @property {string} decided_at
 */

const sections = {
  models: {
    label: "模型",
    title: "模型列表",
    columns: [
      ["name", "名称"], ["model_id", "模型 ID", "mono"],
      ["framework", "框架"], ["model_type", "模型类型"],
      ["task_type", "任务类型"], ["status", "状态", "status"],
      ["latest_version", "最新版本"], ["updated_at", "更新时间", "time"],
      ["versions", "版本", "action"],
    ],
  },
  versions: {
    label: "版本",
    title: "版本列表",
    columns: [
      ["version", "版本号"], ["version_id", "版本 ID", "mono"],
      ["model_id", "模型 ID", "mono"], ["framework", "框架"],
      ["artifact_revision", "制品修订"], ["status", "状态", "status"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  deployments: {
    label: "部署",
    title: "部署列表",
    columns: [
      ["deployment_id", "部署 ID", "mono"], ["model_name", "模型名称"],
      ["model_version", "模型版本"], ["rollout_type", "发布类型"],
      ["role", "角色"], ["environment", "环境"],
      ["framework", "框架"], ["status", "状态", "status"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  routings: {
    label: "路由",
    title: "路由列表",
    columns: [
      ["routing_id", "路由 ID", "mono"], ["deployment_id", "部署 ID", "mono"],
      ["environment", "环境"], ["rollout_type", "发布类型"],
      ["rollout_group", "发布分组"], ["traffic_ratio", "流量比例"],
      ["status", "状态", "status"], ["updated_at", "更新时间", "time"],
    ],
  },
  experiments: {
    label: "实验",
    title: "实验列表",
    columns: [
      ["name", "名称"], ["experiment_id", "实验 ID", "mono"],
      ["model_id", "模型 ID", "mono"], ["environment", "环境"],
      ["status", "状态", "status"], ["effective_from", "生效时间", "time"],
      ["effective_to", "结束时间", "time"], ["updated_at", "更新时间", "time"],
      ["variant_count", "分组", "action"],
    ],
  },
  runtimes: {
    label: "运行状态",
    title: "最近运行实例",
    columns: [
      ["runtime_id", "运行 ID", "mono"], ["deployment_id", "部署 ID", "mono"],
      ["worker_id", "Worker", "mono"], ["framework", "框架"],
      ["status", "状态", "status"], ["last_heartbeat_at", "最近心跳", "time"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  requests: {
    label: "API 调用",
    title: "最近 API 调用",
    columns: [
      ["request_id", "请求 ID", "request"], ["model_id", "模型 ID", "mono"],
      ["source", "来源"], ["status", "状态", "status"],
      ["latency_ms", "耗时（毫秒）", "duration"], ["user", "调用用户"],
      ["ip", "客户端 IP"], ["created_at", "调用时间", "time"],
    ],
  },
  decisions: {
    label: "决策记录",
    title: "最近决策记录",
    columns: [
      ["decision_id", "决策 ID", "decision"], ["request_id", "请求 ID", "mono"],
      ["model_name", "模型名称"], ["model_version", "模型版本"],
      ["source", "来源"], ["probability", "概率", "probability"],
      ["score", "评分", "score"], ["decided_at", "决策时间", "time"],
    ],
  },
  audits: {
    label: "审计记录",
    title: "最近审计记录",
    columns: [
      ["action", "操作"], ["audit_id", "审计 ID", "mono"],
      ["target_type", "目标类型"], ["target_id", "目标 ID", "mono"],
      ["user", "操作人"], ["source", "来源"],
      ["status", "状态", "status"], ["occurred_at", "发生时间", "time"],
    ],
  },
};

const versionColumns = [
  ["version", "版本号"], ["version_id", "版本 ID", "mono"],
  ["framework", "框架"], ["artifact_revision", "制品修订"],
  ["status", "状态", "status"], ["updated_at", "更新时间", "time"],
];

const variantColumns = [
  ["name", "分组名称"], ["variant_id", "分组 ID", "variant"],
  ["group_type", "分组类型", undefined, "is_control"], ["deployment_id", "部署 ID", "mono"],
  ["weight", "权重", "percentage"], ["status", "状态", "status"],
  ["updated_at", "更新时间", "time"],
];

const autoRefreshInterval = 30_000;
const state = {
  user: /** @type {ConsoleUser | null} */ (null),
  snapshot: /** @type {ConsoleSnapshot | null} */ (null),
  active: null,
  selectedModelId: /** @type {string | null} */ (null),
  selectedModel: /** @type {ConsoleModel | null} */ (null),
  selectedExperimentId: /** @type {string | null} */ (null),
  selectedExperiment: /** @type {ExperimentReference | null} */ (null),
  sectionPage: 1,
  sectionQuery: "",
  sectionSort: "",
  sectionOrder: "asc",
  sectionData: /** @type {PageData | null} */ (null),
  sectionError: null,
  versionPage: 1,
  versionQuery: "",
  versionSort: "",
  versionOrder: "asc",
  versionData: /** @type {VersionPageData | null} */ (null),
  versionError: null,
  variantPage: 1,
  variantQuery: "",
  variantSort: "",
  variantOrder: "asc",
  variantData: /** @type {VariantPageData | null} */ (null),
  variantError: null,
};
let autoRefreshTimer = null;
let overviewRequest = null;
let eventSource = null;
let sectionRequestKey = null;
let versionRequestKey = null;
let variantRequestKey = null;
const loginView = document.querySelector("#login-view");
const dashboardView = document.querySelector("#dashboard-view");
const loginForm = document.querySelector("#login-form");
const loginButton = document.querySelector("#login-button");
const loginError = document.querySelector("#login-error");
const navigation = document.querySelector("#navigation");
const summaryGrid = document.querySelector("#summary-grid");
const tableContainer = document.querySelector("#table-container");
const dataPanel = document.querySelector(".data-panel");
const sidebar = document.querySelector(".sidebar");
const backButton = document.querySelector("#back-button");
const heroCard = document.querySelector(".hero-card");
const trendPanel = document.querySelector("#request-trend");
const trendChart = document.querySelector("#request-trend-chart");
const searchForm = document.querySelector("#search-form");
const searchInput = document.querySelector("#search-input");
const clearSearchButton = document.querySelector("#clear-search-button");

async function request(path, options = {}, retry = true) {
  const response = await fetch(`./api/${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (response.status === 401 && retry && !["login", "refresh"].includes(path)) {
    const refreshed = await fetch("./api/refresh", { method: "POST", credentials: "same-origin" });
    if (refreshed.ok) return request(path, options, false);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.error || "请求失败");
    error.status = response.status;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

function showLogin(message = "") {
  stopAutoRefresh();
  stopRealtimeUpdates();
  state.user = null;
  state.snapshot = null;
  state.selectedModelId = null;
  state.selectedModel = null;
  state.selectedExperimentId = null;
  state.selectedExperiment = null;
  state.sectionQuery = "";
  state.sectionSort = "";
  state.sectionOrder = "asc";
  state.sectionData = null;
  state.sectionError = null;
  state.versionQuery = "";
  state.versionSort = "";
  state.versionOrder = "asc";
  state.versionData = null;
  state.versionError = null;
  state.variantQuery = "";
  state.variantSort = "";
  state.variantOrder = "asc";
  state.variantData = null;
  state.variantError = null;
  dashboardView.hidden = true;
  loginView.hidden = false;
  loginError.hidden = !message;
  loginError.textContent = message;
  document.querySelector("#password").value = "";
}

function showDashboard() {
  const user = state.user;

  if (user === null) return;

  loginView.hidden = true;
  dashboardView.hidden = false;
  document.querySelector("#account-name").textContent = user.display_name || user.username;
  document.querySelector("#account-roles").textContent = user.roles.join(", ") || "未分配角色";
}

function loadOverview({ silent = false } = {}) {
  if (overviewRequest) return overviewRequest;

  overviewRequest = refreshOverview(silent).finally(() => {
    overviewRequest = null;
  });

  return overviewRequest;
}

async function refreshOverview(silent) {
  const button = document.querySelector("#refresh-button");
  button.disabled = true;
  try {
    const snapshot = /** @type {ConsoleSnapshot} */ (await request("overview"));
    state.snapshot = snapshot;
    state.sectionData = null;
    state.sectionError = null;
    if (state.selectedModelId !== null) {
      state.versionData = null;
      state.versionError = null;
    }
    if (state.selectedExperimentId !== null) {
      state.variantData = null;
      state.variantError = null;
    }
    const available = Object.keys(sections).filter((key) => snapshot.access[key]);
    if (state.active !== "overview" && !available.includes(state.active)) {
      state.active = "overview";
    }
    applyRoute(available);
    renderNavigation();
    renderSummary();
    renderRequestTrend();
    renderSection();
    document.querySelector("#snapshot-time").textContent = formatTime(snapshot.generated_at);
  } catch (error) {
    if (error.status === 401) showLogin("登录会话已过期，请重新登录。");
    else if (!silent) toast(error.message);
  } finally {
    button.disabled = false;
  }
}

function startAutoRefresh() {
  stopAutoRefresh();
  if (document.hidden || dashboardView.hidden) return;

  autoRefreshTimer = window.setTimeout(async () => {
    await loadOverview({ silent: true });
    startAutoRefresh();
  }, autoRefreshInterval);
}

function stopAutoRefresh() {
  if (autoRefreshTimer !== null) {
    window.clearTimeout(autoRefreshTimer);
    autoRefreshTimer = null;
  }
}

function startRealtimeUpdates() {
  stopRealtimeUpdates();
  if (document.hidden || dashboardView.hidden) return;

  setRealtimeStatus("正在建立实时连接", false);
  eventSource = new EventSource("./api/events", { withCredentials: true });
  eventSource.addEventListener("open", () => {
    setRealtimeStatus("实时更新", true);
  });
  eventSource.addEventListener("sync", async () => {
    await loadOverview({ silent: true });
  });
  eventSource.addEventListener("changed", async () => {
    await loadOverview({ silent: true });
  });
  eventSource.addEventListener("authentication", async () => {
    stopRealtimeUpdates();
    await loadOverview({ silent: true });
    if (!dashboardView.hidden) startRealtimeUpdates();
  });
  eventSource.addEventListener("error", () => {
    setRealtimeStatus("实时连接中断 · 30 秒兜底更新", false);
  });
}

function stopRealtimeUpdates() {
  if (eventSource !== null) {
    eventSource.close();
    eventSource = null;
  }
}

function setRealtimeStatus(message, connected) {
  const element = document.querySelector("#realtime-status");
  element.textContent = message;
  element.closest(".auto-refresh-status").classList.toggle("connected", connected);
}

function renderNavigation() {
  const snapshot = state.snapshot;

  if (snapshot === null) return;

  navigation.replaceChildren();
  const overviewButton = document.createElement("button");
  overviewButton.type = "button";
  overviewButton.className = `nav-button${state.active === "overview" ? " active" : ""}`;
  const overviewLabel = document.createElement("span");
  overviewLabel.textContent = "概览";
  overviewButton.append(overviewLabel);
  overviewButton.addEventListener("click", () => {
    navigateToOverview();
    sidebar.classList.remove("open");
  });
  navigation.append(overviewButton);

  for (const [key, config] of Object.entries(sections)) {
    if (!snapshot.access[key]) continue;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `nav-button${state.active === key ? " active" : ""}`;
    const label = document.createElement("span");
    label.textContent = config.label;
    const count = document.createElement("span");
    count.className = "nav-count";
    count.textContent = sectionCount(key);
    button.append(label, count);
    button.addEventListener("click", () => {
      navigateToSection(key);
      sidebar.classList.remove("open");
    });
    navigation.append(button);
  }
}

function renderSummary() {
  const snapshot = state.snapshot;

  if (snapshot === null) return;

  summaryGrid.replaceChildren();
  for (const [key, config] of Object.entries(sections)) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = `summary-card${snapshot.access[key] ? "" : " denied"}`;
    card.disabled = !snapshot.access[key];
    card.setAttribute("aria-label", `查看${config.label}`);
    const label = document.createElement("span");
    label.textContent = config.label;
    const value = document.createElement("strong");
    value.textContent = snapshot.access[key]
      ? sectionCount(key)
      : "无查看权限";
    card.append(label, value);
    card.addEventListener("click", () => {
      navigateToSection(key);
      document.querySelector(".data-panel").scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
    summaryGrid.append(card);
  }
}

function renderRequestTrend() {
  const snapshot = state.snapshot;

  if (snapshot === null) return;

  const records = Array.isArray(snapshot.request_trend)
    ? snapshot.request_trend
    : [];
  const canViewRequests = Boolean(snapshot.access.requests);
  trendPanel.hidden = !canViewRequests;
  trendChart.replaceChildren();

  if (!canViewRequests) return;

  const normalizeCount = (value) => {
    const count = Number(value);
    return Number.isFinite(count) && count > 0 ? count : 0;
  };
  const counts = records.map((record) => normalizeCount(record.count));
  const successCounts = records.map((record) => normalizeCount(record.success_count));
  const failedCounts = records.map((record) => normalizeCount(record.failed_count));
  const total = counts.reduce((sum, count) => sum + count, 0);
  const successTotal = successCounts.reduce((sum, count) => sum + count, 0);
  const failedTotal = failedCounts.reduce((sum, count) => sum + count, 0);
  document.querySelector("#request-trend-total").textContent = String(total);
  document.querySelector("#request-trend-success").textContent = String(successTotal);
  document.querySelector("#request-trend-failed").textContent = String(failedTotal);

  if (!records.length) {
    const empty = document.createElement("div");
    empty.className = "trend-empty";
    empty.textContent = "暂无 API 调用趋势数据";
    trendChart.append(empty);
    return;
  }

  const namespace = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(namespace, "svg");
  svg.setAttribute("viewBox", "0 0 960 250");
  svg.setAttribute("role", "img");
  svg.setAttribute(
    "aria-label",
    `最近 24 小时共 ${total} 次 API 调用，成功 ${successTotal} 次，失败 ${failedTotal} 次`,
  );

  const left = 48;
  const right = 942;
  const top = 18;
  const bottom = 210;
  const scaleMaximum = Math.max(
    1,
    ...successCounts,
    ...failedCounts,
  );
  const x = (index) => left + ((right - left) * index) / Math.max(records.length - 1, 1);
  const y = (count) => bottom - ((bottom - top) * count) / scaleMaximum;

  for (let index = 0; index <= 4; index += 1) {
    const position = top + ((bottom - top) * index) / 4;
    const line = document.createElementNS(namespace, "line");
    line.setAttribute("class", "trend-grid-line");
    line.setAttribute("x1", String(left));
    line.setAttribute("x2", String(right));
    line.setAttribute("y1", String(position));
    line.setAttribute("y2", String(position));
    svg.append(line);

    const label = document.createElementNS(namespace, "text");
    label.setAttribute("class", "trend-axis-label");
    label.setAttribute("x", "38");
    label.setAttribute("y", String(position + 4));
    label.setAttribute("text-anchor", "end");
    label.textContent = String(Math.round(scaleMaximum * (1 - index / 4)));
    svg.append(label);
  }

  const appendSeries = (values, kind, label) => {
    const points = values.map((count, index) => `${x(index)},${y(count)}`);
    const line = document.createElementNS(namespace, "polyline");
    line.setAttribute("class", `trend-line ${kind}`);
    line.setAttribute("points", points.join(" "));
    svg.append(line);

    records.forEach((record, index) => {
      const point = document.createElementNS(namespace, "circle");
      point.setAttribute("class", `trend-point ${kind}`);
      point.setAttribute("cx", String(x(index)));
      point.setAttribute("cy", String(y(values[index])));
      point.setAttribute("r", "3");
      const title = document.createElementNS(namespace, "title");
      title.textContent = `${formatHour(record.time)}：${label} ${values[index]} 次`;
      point.append(title);
      svg.append(point);
    });
  };

  appendSeries(successCounts, "success", "成功");
  appendSeries(failedCounts, "failed", "失败");

  const labelIndexes = new Set([0, 4, 8, 12, 16, 20, records.length - 1]);
  records.forEach((record, index) => {
    if (!labelIndexes.has(index)) return;
    const label = document.createElementNS(namespace, "text");
    label.setAttribute("class", "trend-axis-label");
    label.setAttribute("x", String(x(index)));
    label.setAttribute("y", "235");
    label.setAttribute("text-anchor", index === 0 ? "start" : (index === records.length - 1 ? "end" : "middle"));
    label.textContent = formatHour(record.time);
    svg.append(label);
  });

  trendChart.append(svg);
}

function formatHour(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function sectionCount(section) {
  const count = state.snapshot?.counts[section];
  return Number.isInteger(count) ? String(count) : "-";
}

function renderSection() {
  const snapshot = state.snapshot;

  if (snapshot === null) return;

  tableContainer.replaceChildren();
  backButton.hidden = true;
  document.querySelector("#section-caption").hidden = true;

  if (state.active === "overview") {
    heroCard.hidden = false;
    summaryGrid.hidden = false;
    dataPanel.hidden = true;
    trendPanel.hidden = !snapshot.access.requests;
    document.querySelector("#page-title").textContent = "概览";
    return;
  }

  heroCard.hidden = true;
  summaryGrid.hidden = true;
  dataPanel.hidden = false;
  trendPanel.hidden = true;

  const config = sections[state.active];
  const overviewRecords = snapshot.sections[state.active] || [];

  const selectedModelId = state.selectedModelId;

  if (state.active === "models" && selectedModelId !== null) {
    const modelRecords = /** @type {ConsoleModel[]} */ (overviewRecords);
    const model = /** @type {ConsoleModel} */ (
      state.selectedModel
      || modelRecords.find((record) => record.model_id === selectedModelId)
      || { model_id: selectedModelId, name: selectedModelId }
    );
    renderModelVersionsPage(model);
    return;
  }

  const selectedExperimentId = state.selectedExperimentId;

  if (state.active === "experiments" && selectedExperimentId !== null) {
    const experimentRecords = /** @type {ExperimentReference[]} */ (overviewRecords);
    const experiment = /** @type {ExperimentReference} */ (
      state.selectedExperiment
      || experimentRecords.find((record) => record.experiment_id === selectedExperimentId)
      || { experiment_id: selectedExperimentId, name: selectedExperimentId }
    );
    renderExperimentVariantsPage(experiment);
    return;
  }

  renderSectionPage(config);
}

/**
 * @param {SectionConfig} config
 */
function renderSectionPage(config) {
  document.querySelector("#section-title").textContent = config.title;
  document.querySelector("#page-title").textContent = config.label;
  const caption = document.querySelector("#section-caption");
  updateSearchForm(
    state.sectionQuery,
    `查询${config.label}`,
  );
  caption.textContent = `第 ${state.sectionPage} 页`;
  caption.hidden = false;

  if (state.sectionError !== null) {
    renderEmpty(`${config.label}加载失败`, state.sectionError);
    return;
  }

  if (state.sectionData === null) {
    renderEmpty(`正在加载${config.label}`, "请稍候…");
    void loadSectionPage(
      state.active,
      state.sectionPage,
    );
    return;
  }

  const records = state.sectionData.items;
  caption.textContent = state.sectionQuery
    ? `查询“${state.sectionQuery}” · 第 ${state.sectionData.page} 页 · 本页 ${records.length} 条`
    : `第 ${state.sectionData.page} 页 · 本页 ${records.length} 条`;

  if (!records.length) {
    renderEmpty(
      state.sectionQuery ? "没有匹配的记录" : `暂无${config.label}记录`,
      state.sectionQuery ? "请尝试其他关键词。" : "数据产生后将在这里显示。",
    );
    if (state.sectionData.has_previous) {
      renderPagination(
        state.sectionData,
        `${config.label}分页`,
        (page) => navigateToSection(
          state.active,
          page,
          state.sectionQuery,
          state.sectionSort,
          state.sectionOrder,
        ),
      );
    }
    return;
  }

  if (state.active === "models") {
    renderModelTable(
      /** @type {ConsoleModel[]} */ (records),
      config,
    );
  } else if (state.active === "experiments") {
    renderExperimentTable(
      /** @type {ExperimentReference[]} */ (records),
      config,
    );
  } else {
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    for (const column of config.columns) {
      headerRow.append(createSortHeader(
        column,
        state.sectionSort,
        state.sectionOrder,
        (sortBy, sortOrder) => navigateToSection(
          state.active,
          1,
          state.sectionQuery,
          sortBy,
          sortOrder,
        ),
      ));
    }
    thead.append(headerRow);

    const tbody = document.createElement("tbody");
    for (const record of records) {
      const row = document.createElement("tr");
      for (const [field, , kind] of config.columns) {
        row.append(createDataCell(record[field], kind, record));
      }
      tbody.append(row);
    }
    table.append(thead, tbody);
    tableContainer.append(table);
  }

  renderPagination(
    state.sectionData,
    `${config.label}分页`,
    (page) => navigateToSection(
      state.active,
      page,
      state.sectionQuery,
      state.sectionSort,
      state.sectionOrder,
    ),
  );
}

/**
 * @param {ConsoleModel[]} records
 * @param {SectionConfig} config
 */
function renderModelTable(records, config) {
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const column of config.columns) {
    headerRow.append(createSortHeader(
      column,
      state.sectionSort,
      state.sectionOrder,
      (sortBy, sortOrder) => navigateToSection(
        state.active,
        1,
        state.sectionQuery,
        sortBy,
        sortOrder,
      ),
    ));
  }
  thead.append(headerRow);

  const tbody = document.createElement("tbody");
  for (const record of records) {
    const versions = Array.isArray(record.versions) ? record.versions : [];
    const row = document.createElement("tr");
    row.className = "model-row";

    for (const [field, , kind] of config.columns) {
      if (field !== "versions") {
        row.append(createDataCell(record[field], kind, record));
        continue;
      }

      const cell = document.createElement("td");
      if (!versions.length) {
        cell.textContent = "-";
      } else {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "related-records-link";
        button.textContent = "查看版本";
        button.addEventListener("click", () => {
          navigateToModelVersions(record);
        });
        cell.append(button);
      }
      row.append(cell);
    }
    tbody.append(row);
  }

  table.append(thead, tbody);
  tableContainer.append(table);
}

/**
 * @param {ExperimentReference[]} records
 * @param {SectionConfig} config
 */
function renderExperimentTable(records, config) {
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const column of config.columns) {
    headerRow.append(createSortHeader(
      column,
      state.sectionSort,
      state.sectionOrder,
      (sortBy, sortOrder) => navigateToSection(
        state.active,
        1,
        state.sectionQuery,
        sortBy,
        sortOrder,
      ),
    ));
  }
  thead.append(headerRow);

  const tbody = document.createElement("tbody");
  for (const record of records) {
    const row = document.createElement("tr");
    for (const [field, , kind] of config.columns) {
      if (field !== "variant_count") {
        row.append(createDataCell(record[field], kind, record));
        continue;
      }

      const cell = document.createElement("td");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "related-records-link";
      button.textContent = `${Number(record.variant_count || 0)} 个分组`;
      button.addEventListener("click", () => {
        navigateToExperimentVariants(record);
      });
      cell.append(button);
      row.append(cell);
    }
    tbody.append(row);
  }

  table.append(thead, tbody);
  tableContainer.append(table);
}

/**
 * @param {ConsoleModel} model
 */
function renderModelVersionsPage(model) {
  heroCard.hidden = true;
  summaryGrid.hidden = true;
  document.querySelector("#page-title").textContent = "版本";
  document.querySelector("#section-title").textContent = `${model.name} 的版本`;
  const caption = document.querySelector("#section-caption");
  updateSearchForm(
    state.versionQuery,
    "查询当前模型的版本",
  );
  caption.textContent = `第 ${state.versionPage} 页`;
  caption.hidden = false;
  backButton.textContent = "返回模型";
  backButton.hidden = false;

  if (state.versionError !== null) {
    renderEmpty("版本加载失败", state.versionError);
    return;
  }

  if (state.versionData === null) {
    renderEmpty("正在加载版本", "请稍候…");
    void loadVersionPage(
      model.model_id,
      state.versionPage,
    );
    return;
  }

  const versions = state.versionData.items;
  caption.textContent = state.versionQuery
    ? `查询“${state.versionQuery}” · 第 ${state.versionData.page} 页 · 本页 ${versions.length} 个版本`
    : `第 ${state.versionData.page} 页 · 本页 ${versions.length} 个版本`;

  if (!versions.length) {
    renderEmpty(
      state.versionQuery ? "没有匹配的版本" : "暂无版本",
      state.versionQuery ? "请尝试其他关键词。" : "注册版本后将在这里显示。",
    );
    if (state.versionData.has_previous) {
      renderPagination(
        state.versionData,
        "版本分页",
        (page) => navigateToModelVersions(
          model,
          page,
          state.versionQuery,
          state.versionSort,
          state.versionOrder,
        ),
      );
    }
    return;
  }

  const table = document.createElement("table");
  table.className = "version-page-table";
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const column of versionColumns) {
    headerRow.append(createSortHeader(
      column,
      state.versionSort,
      state.versionOrder,
      (sortBy, sortOrder) => navigateToModelVersions(
        model,
        1,
        state.versionQuery,
        sortBy,
        sortOrder,
      ),
    ));
  }
  thead.append(headerRow);

  const tbody = document.createElement("tbody");
  for (const version of versions) {
    const versionRow = document.createElement("tr");
    for (const [field, , kind] of versionColumns) {
      versionRow.append(createDataCell(version[field], kind, version));
    }
    tbody.append(versionRow);
  }
  table.append(thead, tbody);
  tableContainer.append(table);
  renderPagination(
    state.versionData,
    "版本分页",
    (page) => navigateToModelVersions(
      model,
      page,
      state.versionQuery,
      state.versionSort,
      state.versionOrder,
    ),
  );
}

/**
 * @param {ExperimentReference} experiment
 */
function renderExperimentVariantsPage(experiment) {
  heroCard.hidden = true;
  summaryGrid.hidden = true;
  document.querySelector("#page-title").textContent = "实验分组";
  document.querySelector("#section-title").textContent = `${experiment.name} 的实验分组`;
  const caption = document.querySelector("#section-caption");
  updateSearchForm(
    state.variantQuery,
    "查询当前实验的分组",
  );
  caption.textContent = `第 ${state.variantPage} 页`;
  caption.hidden = false;
  backButton.textContent = "返回实验";
  backButton.hidden = false;

  if (state.variantError !== null) {
    renderEmpty("实验分组加载失败", state.variantError);
    return;
  }

  if (state.variantData === null) {
    renderEmpty("正在加载实验分组", "请稍候…");
    void loadVariantPage(
      experiment.experiment_id,
      state.variantPage,
    );
    return;
  }

  const variants = state.variantData.items;
  caption.textContent = state.variantQuery
    ? `查询“${state.variantQuery}” · 第 ${state.variantData.page} 页 · 本页 ${variants.length} 个分组`
    : `第 ${state.variantData.page} 页 · 本页 ${variants.length} 个分组`;

  if (!variants.length) {
    renderEmpty(
      state.variantQuery ? "没有匹配的实验分组" : "暂无实验分组",
      state.variantQuery ? "请尝试其他关键词。" : "创建实验分组后将在这里显示。",
    );
    if (state.variantData.has_previous) {
      renderPagination(
        state.variantData,
        "实验分组分页",
        (page) => navigateToExperimentVariants(
          experiment,
          page,
          state.variantQuery,
          state.variantSort,
          state.variantOrder,
        ),
      );
    }
    return;
  }

  const table = document.createElement("table");
  table.className = "version-page-table";
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  for (const column of variantColumns) {
    headerRow.append(createSortHeader(
      column,
      state.variantSort,
      state.variantOrder,
      (sortBy, sortOrder) => navigateToExperimentVariants(
        experiment,
        1,
        state.variantQuery,
        sortBy,
        sortOrder,
      ),
    ));
  }
  thead.append(headerRow);

  const tbody = document.createElement("tbody");
  for (const variant of variants) {
    const variantRow = document.createElement("tr");
    for (const [field, , kind] of variantColumns) {
      variantRow.append(createDataCell(variant[field], kind, variant));
    }
    tbody.append(variantRow);
  }
  table.append(thead, tbody);
  tableContainer.append(table);
  renderPagination(
    state.variantData,
    "实验分组分页",
    (page) => navigateToExperimentVariants(
      experiment,
      page,
      state.variantQuery,
      state.variantSort,
      state.variantOrder,
    ),
  );
}

async function loadSectionPage(section, page) {
  const query = state.sectionQuery;
  const sortBy = state.sectionSort;
  const sortOrder = state.sectionOrder;
  const requestKey = `${section}:${page}:${query}:${sortBy}:${sortOrder}`;
  if (sectionRequestKey === requestKey) return;

  sectionRequestKey = requestKey;
  try {
    const data = /** @type {PageData} */ (await request(
      `sections/${section}?${buildPageQuery(page, query, sortBy, sortOrder)}`,
    ));
    if (
      state.active !== section
      || state.sectionPage !== page
      || state.sectionQuery !== query
      || state.sectionSort !== sortBy
      || state.sectionOrder !== sortOrder
    ) return;
    state.sectionData = data;
    state.sectionError = null;
    renderSection();
  } catch (error) {
    if (error.status === 401) {
      showLogin("登录会话已过期，请重新登录。");
      return;
    }
    if (
      state.active !== section
      || state.sectionPage !== page
      || state.sectionQuery !== query
      || state.sectionSort !== sortBy
      || state.sectionOrder !== sortOrder
    ) return;
    state.sectionError = error.message;
    renderSection();
  } finally {
    if (sectionRequestKey === requestKey) sectionRequestKey = null;
  }
}

async function loadVersionPage(modelId, page) {
  const query = state.versionQuery;
  const sortBy = state.versionSort;
  const sortOrder = state.versionOrder;
  const requestKey = `${modelId}:${page}:${query}:${sortBy}:${sortOrder}`;
  if (versionRequestKey === requestKey) return;

  versionRequestKey = requestKey;
  try {
    const data = /** @type {VersionPageData} */ (await request(
      `models/${encodeURIComponent(modelId)}/versions?${buildPageQuery(page, query, sortBy, sortOrder)}`,
    ));
    if (
      state.selectedModelId !== modelId
      || state.versionPage !== page
      || state.versionQuery !== query
      || state.versionSort !== sortBy
      || state.versionOrder !== sortOrder
    ) return;
    state.versionData = data;
    state.selectedModel = data.model;
    state.versionError = null;
    renderSection();
  } catch (error) {
    if (error.status === 401) {
      showLogin("登录会话已过期，请重新登录。");
      return;
    }
    if (
      state.selectedModelId !== modelId
      || state.versionPage !== page
      || state.versionQuery !== query
      || state.versionSort !== sortBy
      || state.versionOrder !== sortOrder
    ) return;
    state.versionError = error.message;
    renderSection();
  } finally {
    if (versionRequestKey === requestKey) versionRequestKey = null;
  }
}

async function loadVariantPage(experimentId, page) {
  const query = state.variantQuery;
  const sortBy = state.variantSort;
  const sortOrder = state.variantOrder;
  const requestKey = `${experimentId}:${page}:${query}:${sortBy}:${sortOrder}`;
  if (variantRequestKey === requestKey) return;

  variantRequestKey = requestKey;
  try {
    const data = /** @type {VariantPageData} */ (await request(
      `experiments/${encodeURIComponent(experimentId)}/variants?${buildPageQuery(page, query, sortBy, sortOrder)}`,
    ));
    if (
      state.selectedExperimentId !== experimentId
      || state.variantPage !== page
      || state.variantQuery !== query
      || state.variantSort !== sortBy
      || state.variantOrder !== sortOrder
    ) return;
    state.variantData = data;
    state.selectedExperiment = data.experiment;
    state.variantError = null;
    renderSection();
  } catch (error) {
    if (error.status === 401) {
      showLogin("登录会话已过期，请重新登录。");
      return;
    }
    if (
      state.selectedExperimentId !== experimentId
      || state.variantPage !== page
      || state.variantQuery !== query
      || state.variantSort !== sortBy
      || state.variantOrder !== sortOrder
    ) return;
    state.variantError = error.message;
    renderSection();
  } finally {
    if (variantRequestKey === requestKey) variantRequestKey = null;
  }
}

/**
 * @param {PageData | VersionPageData | VariantPageData} data
 * @param {string} label
 * @param {function(number): void} navigate
 */
function renderPagination(data, label, navigate) {
  const pagination = document.createElement("nav");
  pagination.className = "pagination";
  pagination.setAttribute("aria-label", label);

  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "secondary-button";
  previous.textContent = "上一页";
  previous.disabled = !data.has_previous;
  previous.addEventListener("click", () => {
    navigate(data.page - 1);
  });

  const page = document.createElement("span");
  page.textContent = `第 ${data.page} 页`;

  const next = document.createElement("button");
  next.type = "button";
  next.className = "secondary-button";
  next.textContent = "下一页";
  next.disabled = !data.has_next;
  next.addEventListener("click", () => {
    navigate(data.page + 1);
  });

  pagination.append(previous, page, next);
  tableContainer.append(pagination);
}

function buildPageQuery(page, query, sortBy = "", sortOrder = "asc") {
  const parameters = new URLSearchParams({
    page: String(page),
    page_size: "10",
  });
  if (query) parameters.set("q", query);
  if (sortBy) {
    parameters.set("sort", sortBy);
    parameters.set("order", sortOrder);
  }
  return parameters.toString();
}

function buildHashQuery(page, query, sortBy = "", sortOrder = "asc") {
  const parameters = new URLSearchParams();
  if (page > 1) parameters.set("page", String(page));
  if (query) parameters.set("q", query);
  if (sortBy) {
    parameters.set("sort", sortBy);
    parameters.set("order", sortOrder);
  }
  const value = parameters.toString();
  return value ? `?${value}` : "";
}

function updateSearchForm(query, placeholder) {
  searchInput.value = query;
  searchInput.placeholder = placeholder;
  clearSearchButton.hidden = !query;
}

function navigateToOverview() {
  state.active = "overview";
  state.selectedModelId = null;
  state.selectedModel = null;
  state.selectedExperimentId = null;
  state.selectedExperiment = null;
  state.sectionData = null;
  state.sectionError = null;
  state.versionData = null;
  state.versionError = null;
  state.variantData = null;
  state.variantError = null;
  window.history.pushState(null, "", "#overview");
  renderNavigation();
  renderSection();
}

function navigateToSection(
  section,
  page = 1,
  query = "",
  sortBy = "",
  sortOrder = "asc",
) {
  state.active = section;
  state.selectedModelId = null;
  state.selectedModel = null;
  state.selectedExperimentId = null;
  state.selectedExperiment = null;
  state.sectionPage = page;
  state.sectionQuery = query;
  state.sectionSort = sortBy;
  state.sectionOrder = sortOrder;
  state.sectionData = null;
  state.sectionError = null;
  state.versionQuery = "";
  state.versionSort = "";
  state.versionOrder = "asc";
  state.versionData = null;
  state.versionError = null;
  state.variantQuery = "";
  state.variantSort = "";
  state.variantOrder = "asc";
  state.variantData = null;
  state.variantError = null;
  const pageQuery = buildHashQuery(page, query, sortBy, sortOrder);
  window.history.pushState(null, "", `#${section}${pageQuery}`);
  renderNavigation();
  renderSection();
}

/**
 * @param {ConsoleModel} model
 * @param {number} page
 * @param {string} query
 * @param {string} sortBy
 * @param {string} sortOrder
 */
function navigateToModelVersions(
  model,
  page = 1,
  query = "",
  sortBy = "",
  sortOrder = "asc",
) {
  const modelId = model.model_id;
  state.active = "models";
  state.selectedModelId = modelId;
  state.selectedModel = model;
  state.selectedExperimentId = null;
  state.selectedExperiment = null;
  state.versionPage = page;
  state.versionQuery = query;
  state.versionSort = sortBy;
  state.versionOrder = sortOrder;
  state.versionData = null;
  state.versionError = null;
  const pageQuery = buildHashQuery(page, query, sortBy, sortOrder);
  window.history.pushState(
    null,
    "",
    `#models/${encodeURIComponent(modelId)}/versions${pageQuery}`,
  );
  renderNavigation();
  renderSection();
}

/**
 * @param {ExperimentReference} experiment
 * @param {number} page
 * @param {string} query
 * @param {string} sortBy
 * @param {string} sortOrder
 */
function navigateToExperimentVariants(
  experiment,
  page = 1,
  query = "",
  sortBy = "",
  sortOrder = "asc",
) {
  const experimentId = experiment.experiment_id;
  state.active = "experiments";
  state.selectedModelId = null;
  state.selectedModel = null;
  state.selectedExperimentId = experimentId;
  state.selectedExperiment = experiment;
  state.variantPage = page;
  state.variantQuery = query;
  state.variantSort = sortBy;
  state.variantOrder = sortOrder;
  state.variantData = null;
  state.variantError = null;
  const pageQuery = buildHashQuery(page, query, sortBy, sortOrder);
  window.history.pushState(
    null,
    "",
    `#experiments/${encodeURIComponent(experimentId)}/variants${pageQuery}`,
  );
  renderNavigation();
  renderSection();
}

function applyRoute(available) {
  const route = window.location.hash.slice(1);

  if (!route || route === "overview") {
    state.active = "overview";
    state.selectedModelId = null;
    state.selectedModel = null;
    state.selectedExperimentId = null;
    state.selectedExperiment = null;
    return;
  }

  const versionRoute = route.match(/^models\/([^/]+)\/versions(?:\?(.+))?$/);

  if (versionRoute && available.includes("models")) {
    const parameters = new URLSearchParams(versionRoute[2] || "");
    const parsedPage = Number.parseInt(parameters.get("page") || "1", 10);
    const modelId = decodeURIComponent(versionRoute[1]);
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const query = parameters.get("q") || "";
    const sortBy = parameters.get("sort") || "";
    const sortOrder = parameters.get("order") === "desc" ? "desc" : "asc";

    if (
      state.selectedModelId !== modelId
      || state.versionPage !== page
      || state.versionQuery !== query
      || state.versionSort !== sortBy
      || state.versionOrder !== sortOrder
    ) {
      state.versionData = null;
      state.versionError = null;
    }

    state.active = "models";
    state.selectedModelId = modelId;
    state.selectedExperimentId = null;
    state.selectedExperiment = null;
    state.versionPage = page;
    state.versionQuery = query;
    state.versionSort = sortBy;
    state.versionOrder = sortOrder;
    return;
  }

  const variantRoute = route.match(/^experiments\/([^/]+)\/variants(?:\?(.+))?$/);

  if (variantRoute && available.includes("experiments")) {
    const parameters = new URLSearchParams(variantRoute[2] || "");
    const parsedPage = Number.parseInt(parameters.get("page") || "1", 10);
    const experimentId = decodeURIComponent(variantRoute[1]);
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const query = parameters.get("q") || "";
    const sortBy = parameters.get("sort") || "";
    const sortOrder = parameters.get("order") === "desc" ? "desc" : "asc";

    if (
      state.selectedExperimentId !== experimentId
      || state.variantPage !== page
      || state.variantQuery !== query
      || state.variantSort !== sortBy
      || state.variantOrder !== sortOrder
    ) {
      state.variantData = null;
      state.variantError = null;
    }

    state.active = "experiments";
    state.selectedModelId = null;
    state.selectedModel = null;
    state.selectedExperimentId = experimentId;
    state.variantPage = page;
    state.variantQuery = query;
    state.variantSort = sortBy;
    state.variantOrder = sortOrder;
    return;
  }

  const sectionRoute = route.match(/^([^?]+)(?:\?(.+))?$/);
  const section = sectionRoute ? sectionRoute[1] : "";
  const parameters = new URLSearchParams(sectionRoute ? sectionRoute[2] || "" : "");
  const parsedPage = Number.parseInt(parameters.get("page") || "1", 10);
  const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
  const query = parameters.get("q") || "";
  const sortBy = parameters.get("sort") || "";
  const sortOrder = parameters.get("order") === "desc" ? "desc" : "asc";

  if (!available.includes(section)) {
    state.active = "overview";
    return;
  }

  if (
    state.sectionPage !== page
    || state.active !== section
    || state.sectionQuery !== query
    || state.sectionSort !== sortBy
    || state.sectionOrder !== sortOrder
  ) {
    state.sectionData = null;
    state.sectionError = null;
  }
  state.active = section;
  state.sectionPage = page;
  state.sectionQuery = query;
  state.sectionSort = sortBy;
  state.sectionOrder = sortOrder;
  state.selectedModelId = null;
  state.selectedModel = null;
  state.selectedExperimentId = null;
  state.selectedExperiment = null;
  state.versionData = null;
  state.versionError = null;
  state.variantData = null;
  state.variantError = null;
}

/**
 * @param {ColumnConfig} column
 * @param {string} activeSort
 * @param {string} activeOrder
 * @param {function(string, string): void} navigate
 * @returns {HTMLTableCellElement}
 */
function createSortHeader(column, activeSort, activeOrder, navigate) {
  const [field, label, , configuredSort] = column;
  const sortBy = configuredSort || field;
  const selected = activeSort === sortBy;
  const th = document.createElement("th");
  th.scope = "col";
  th.setAttribute(
    "aria-sort",
    selected ? (activeOrder === "asc" ? "ascending" : "descending") : "none",
  );

  const button = document.createElement("button");
  button.type = "button";
  button.className = `sort-button${selected ? " active" : ""}`;
  button.title = `按${label}排序`;

  const text = document.createElement("span");
  text.textContent = label;
  const indicator = document.createElement("span");
  indicator.className = `sort-indicator${selected ? ` ${activeOrder}` : ""}`;
  indicator.setAttribute("aria-hidden", "true");
  button.append(text, indicator);
  button.addEventListener("click", () => {
    navigate(
      sortBy,
      selected && activeOrder === "asc" ? "desc" : "asc",
    );
  });
  th.append(button);
  return th;
}

function createDataCell(value, kind, record = null) {
  const cell = document.createElement("td");
  if (kind === "status") {
    cell.append(createStatusBadge(value));
  } else if (kind === "request" && record !== null) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "request-link mono";
    button.textContent = value ?? "-";
    button.title = "查看 API 调用详情";
    button.addEventListener("click", () => showRequestDrawer(
      /** @type {ConsoleRequest} */ (record),
    ));
    cell.append(button);
  } else if (kind === "decision" && record !== null) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "request-link mono";
    button.textContent = value ?? "-";
    button.title = "查看决策记录详情";
    button.addEventListener("click", () => showDecisionDrawer(
      /** @type {ConsoleDecision} */ (record),
    ));
    cell.append(button);
  } else if (kind === "variant" && record !== null) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "request-link mono";
    button.textContent = value ?? "-";
    button.title = "查看实验分组详情";
    button.addEventListener("click", () => showVariantDrawer(
      /** @type {ConsoleVariant} */ (record),
    ));
    cell.append(button);
  } else if (kind === "duration") {
    cell.textContent = formatDuration(value);
  } else if (kind === "percentage") {
    cell.textContent = formatPercentage(value);
  } else if (kind === "probability") {
    cell.textContent = formatProbability(value);
  } else if (kind === "score") {
    cell.textContent = formatScore(value);
  } else {
    cell.textContent = kind === "time" ? formatTime(value) : (value ?? "—");
    if (kind === "mono") cell.className = "mono";
  }
  return cell;
}

function createStatusBadge(value) {
  const badge = document.createElement("span");
  badge.className = `status ${statusTone(value)}`.trim();
  badge.textContent = value ?? "-";
  return badge;
}

/**
 * @param {string} value
 * @param {function(): void} navigate
 * @returns {HTMLButtonElement}
 */
function createNavigationLink(value, navigate) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "request-link mono";
  button.textContent = value;
  button.addEventListener("click", navigate);
  return button;
}

/**
 * @param {string | null} value
 * @param {string} section
 * @param {HTMLDialogElement} dialog
 * @returns {string | null | HTMLButtonElement}
 */
function createSectionNavigationLink(value, section, dialog) {
  const snapshot = state.snapshot;

  if (!value || snapshot === null || !snapshot.access[section]) return value;

  return createNavigationLink(value, () => {
    dialog.close();
    navigateToSection(section, 1, value);
  });
}

/**
 * @param {ConsoleRequest | ConsoleDecision} record
 * @param {HTMLDialogElement} dialog
 * @returns {string | HTMLButtonElement}
 */
function createModelNavigationLink(record, dialog) {
  const snapshot = state.snapshot;

  if (snapshot === null || !snapshot.access.models) return record.model_id;

  return createNavigationLink(record.model_id, () => {
    dialog.close();
    navigateToModelVersions({
      model_id: record.model_id,
      name: record.model_name || record.model_id,
    });
  });
}

/**
 * @param {ConsoleDecision} record
 * @param {HTMLDialogElement} dialog
 * @returns {string | HTMLButtonElement}
 */
function createVersionNavigationLink(record, dialog) {
  const snapshot = state.snapshot;

  if (snapshot === null || !snapshot.access.models) return record.version_id;

  return createNavigationLink(record.version_id, () => {
    dialog.close();
    navigateToModelVersions(
      {
        model_id: record.model_id,
        name: record.model_name || record.model_id,
      },
      1,
      record.version_id,
    );
  });
}

/**
 * @param {ConsoleRequest | null} record
 */
function showRequestDrawer(record) {
  if (record === null) return;

  const dialog = document.createElement("dialog");
  dialog.className = "request-drawer";
  const header = document.createElement("header");
  const headingCopy = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = "API 调用详情";
  const identifier = document.createElement("span");
  identifier.className = "drawer-request-id mono";
  identifier.textContent = record.request_id ?? "-";
  headingCopy.append(heading, identifier);
  const close = document.createElement("button");
  close.type = "button";
  close.className = "dialog-close-button";
  close.setAttribute("aria-label", "关闭 API 调用详情");
  close.textContent = "关闭";
  close.addEventListener("click", () => dialog.close());
  header.append(headingCopy, close);

  const body = document.createElement("div");
  body.className = "request-drawer-body";
  const summary = document.createElement("dl");
  summary.className = "request-detail-grid";
  appendRequestDetail(summary, "状态", createStatusBadge(record.status));
  appendRequestDetail(summary, "模型名称", record.model_name);
  appendRequestDetail(
    summary,
    "模型 ID",
    createModelNavigationLink(record, dialog),
  );
  appendRequestDetail(summary, "模型版本", record.model_version);
  appendRequestDetail(
    summary,
    "部署 ID",
    createSectionNavigationLink(record.deployment_id, "deployments", dialog),
  );
  appendRequestDetail(
    summary,
    "决策 ID",
    createSectionNavigationLink(record.decision_id, "decisions", dialog),
  );
  appendRequestDetail(summary, "来源", record.source);
  appendRequestDetail(summary, "耗时（毫秒）", formatDuration(record.latency_ms));
  appendRequestDetail(summary, "调用用户", record.user);
  appendRequestDetail(summary, "客户端 IP", record.ip, "mono");
  appendRequestDetail(summary, "调用时间", formatTime(record.created_at));
  body.append(summary);
  if (record.error) {
    body.append(createRequestError(record.error));
  }
  body.append(
    createJsonSection("请求载荷", record.payload),
    createJsonSection(
      "响应结果",
      record.response ?? record.prediction,
    ),
  );
  dialog.append(header, body);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

/**
 * @param {ConsoleDecision | null} record
 */
function showDecisionDrawer(record) {
  if (record === null) return;

  const dialog = document.createElement("dialog");
  dialog.className = "request-drawer";
  const header = document.createElement("header");
  const headingCopy = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = "决策记录详情";
  const identifier = document.createElement("span");
  identifier.className = "drawer-request-id mono";
  identifier.textContent = record.decision_id ?? "-";
  headingCopy.append(heading, identifier);
  const close = document.createElement("button");
  close.type = "button";
  close.className = "dialog-close-button";
  close.setAttribute("aria-label", "关闭决策记录详情");
  close.textContent = "关闭";
  close.addEventListener("click", () => dialog.close());
  header.append(headingCopy, close);

  const body = document.createElement("div");
  body.className = "request-drawer-body";
  const summary = document.createElement("dl");
  summary.className = "request-detail-grid";
  appendRequestDetail(
    summary,
    "请求 ID",
    createSectionNavigationLink(record.request_id, "requests", dialog),
  );
  appendRequestDetail(summary, "模型名称", record.model_name);
  appendRequestDetail(
    summary,
    "模型 ID",
    createModelNavigationLink(record, dialog),
  );
  appendRequestDetail(summary, "模型版本", record.model_version);
  appendRequestDetail(
    summary,
    "版本 ID",
    createVersionNavigationLink(record, dialog),
  );
  appendRequestDetail(
    summary,
    "部署 ID",
    createSectionNavigationLink(record.deployment_id, "deployments", dialog),
  );
  appendRequestDetail(summary, "来源", record.source);
  appendRequestDetail(summary, "策略", record.strategy);
  appendRequestDetail(summary, "概率", formatProbability(record.probability));
  appendRequestDetail(summary, "评分", formatScore(record.score));
  appendRequestDetail(summary, "耗时（毫秒）", formatDuration(record.latency_ms));
  appendRequestDetail(summary, "实验 ID", record.experiment_id, "mono");
  appendRequestDetail(summary, "分组 ID", record.variant_id, "mono");
  appendRequestDetail(summary, "分配 ID", record.assignment_id, "mono");
  appendRequestDetail(summary, "主体标识", record.subject_key, "mono");
  appendRequestDetail(summary, "主体类型", record.subject_type);
  appendRequestDetail(summary, "分桶", record.bucket, "mono");
  appendRequestDetail(summary, "实验组别", record.group);
  appendRequestDetail(summary, "命中权重", formatPercentage(record.weight));
  appendRequestDetail(summary, "决策时间", formatTime(record.decided_at));
  body.append(
    summary,
    createJsonSection("预测结果", record.prediction),
    createJsonSection("路由上下文", record.context),
  );
  dialog.append(header, body);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

/**
 * @param {ConsoleVariant | null} record
 */
function showVariantDrawer(record) {
  if (record === null) return;

  const dialog = document.createElement("dialog");
  dialog.className = "request-drawer";
  const header = document.createElement("header");
  const headingCopy = document.createElement("div");
  const heading = document.createElement("h3");
  heading.textContent = "实验分组详情";
  const identifier = document.createElement("span");
  identifier.className = "drawer-request-id mono";
  identifier.textContent = record.variant_id ?? "-";
  headingCopy.append(heading, identifier);
  const close = document.createElement("button");
  close.type = "button";
  close.className = "dialog-close-button";
  close.setAttribute("aria-label", "关闭实验分组详情");
  close.textContent = "关闭";
  close.addEventListener("click", () => dialog.close());
  header.append(headingCopy, close);

  const body = document.createElement("div");
  body.className = "request-drawer-body";
  const summary = document.createElement("dl");
  summary.className = "request-detail-grid";
  appendRequestDetail(summary, "分组名称", record.name);
  appendRequestDetail(summary, "分组类型", record.group_type);
  appendRequestDetail(summary, "状态", createStatusBadge(record.status));
  appendRequestDetail(summary, "实验 ID", record.experiment_id, "mono");
  appendRequestDetail(
    summary,
    "部署 ID",
    createSectionNavigationLink(record.deployment_id, "deployments", dialog),
  );
  appendRequestDetail(summary, "权重", formatPercentage(record.weight));
  appendRequestDetail(summary, "描述", record.description);
  appendRequestDetail(summary, "创建人", record.created_by);
  appendRequestDetail(summary, "更新人", record.updated_by);
  appendRequestDetail(summary, "创建时间", formatTime(record.created_at));
  appendRequestDetail(summary, "更新时间", formatTime(record.updated_at));
  body.append(
    summary,
    createJsonSection("分组配置", record.config),
  );
  dialog.append(header, body);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

function createRequestError(error) {
  const section = document.createElement("section");
  section.className = "request-error-section";
  const heading = document.createElement("h4");
  heading.textContent = "错误信息";
  const message = document.createElement("p");
  message.textContent = String(error);
  section.append(heading, message);
  return section;
}

function appendRequestDetail(container, label, value, className = "") {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  if (value instanceof Node) {
    detail.append(value);
  } else {
    const hasValue = value !== null && value !== undefined;
    detail.textContent = hasValue ? value : "—";
    if (className && hasValue) detail.className = className;
  }
  wrapper.append(term, detail);
  container.append(wrapper);
}

function createJsonSection(title, value) {
  const section = document.createElement("section");
  section.className = "request-json-section";
  const heading = document.createElement("h4");
  heading.textContent = title;
  const content = document.createElement("pre");
  content.textContent = value === null || value === undefined
    ? "暂无数据"
    : formatJsonValue(value);
  section.append(heading, content);
  return section;
}

/**
 * @param {*} value
 * @returns {string}
 */
function formatJsonValue(value) {
  return formatJsonNode(value, "", "", 0);
}

/**
 * @param {*} value
 * @param {string} field
 * @param {string} parentField
 * @param {number} depth
 * @returns {string}
 */
function formatJsonNode(value, field, parentField, depth) {
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";

    const indentation = "  ".repeat(depth);
    const childIndentation = "  ".repeat(depth + 1);
    const items = value.map((item) => (
      childIndentation
      + formatJsonNode(item, field, parentField, depth + 1)
    ));

    return `[\n${items.join(",\n")}\n${indentation}]`;
  }

  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value).filter(([, item]) => (
      item !== undefined
    ));

    if (entries.length === 0) return "{}";

    const indentation = "  ".repeat(depth);
    const childIndentation = "  ".repeat(depth + 1);
    const items = entries.map(([key, item]) => (
      `${childIndentation}${JSON.stringify(key)}: `
      + formatJsonNode(item, key, field, depth + 1)
    ));

    return `{\n${items.join(",\n")}\n${indentation}}`;
  }

  if (typeof value !== "number") return JSON.stringify(value) ?? "null";
  if (!Number.isFinite(value)) return "null";

  if (
    field === "score"
    || field.endsWith("_score")
    || parentField === "feature_scores"
  ) return value.toFixed(2);

  if (field === "latency_ms") return value.toFixed(2);
  if (Number.isInteger(value)) return String(value);

  return String(
    Number(value.toFixed(6))
  );
}

function formatDuration(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: false,
  }).format(number);
}

function formatPercentage(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number);
}

function formatProbability(value) {
  return formatPercentage(value);
}

function formatScore(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: false,
  }).format(number);
}

function renderEmpty(title, detail) {
  const empty = document.createElement("div");
  empty.className = "empty-state";
  const copy = document.createElement("div");
  const heading = document.createElement("strong");
  heading.textContent = title;
  const paragraph = document.createElement("span");
  paragraph.textContent = detail;
  copy.append(heading, paragraph);
  empty.append(copy);
  tableContainer.append(empty);
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(date);
}

function statusTone(value) {
  const status = String(value || "").toLowerCase();
  if (["failed", "error", "disabled", "archived", "stopped"].includes(status)) return "danger";
  if (["inactive", "pending", "paused", "unloaded"].includes(status)) return "warning";
  return "";
}

function toast(message) {
  const element = document.querySelector("#toast");
  element.textContent = message;
  element.hidden = false;
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => { element.hidden = true; }, 2800);
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginButton.disabled = true;
  loginButton.textContent = "正在登录…";
  loginError.hidden = true;
  try {
    state.user = await request("login", {
      method: "POST",
      body: JSON.stringify({
        username: document.querySelector("#username").value,
        password: document.querySelector("#password").value,
      }),
    }, false);
    showDashboard();
    await loadOverview();
    startAutoRefresh();
    startRealtimeUpdates();
  } catch (error) {
    loginError.textContent = error.message;
    loginError.hidden = false;
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "登录";
  }
});

document.querySelector("#logout-button").addEventListener("click", async () => {
  await request("logout", { method: "POST" }, false).catch(() => null);
  showLogin();
});
document.querySelector("#refresh-button").addEventListener("click", async () => {
  await loadOverview();
  startAutoRefresh();
});

/**
 * @returns {ConsoleModel | null}
 */
function getSelectedModel() {
  const selectedModelId = state.selectedModelId;

  if (selectedModelId === null) return null;

  return /** @type {ConsoleModel} */ (
    state.selectedModel || {
      model_id: selectedModelId,
      name: selectedModelId,
    }
  );
}

/**
 * @returns {ExperimentReference | null}
 */
function getSelectedExperiment() {
  const selectedExperimentId = state.selectedExperimentId;

  if (selectedExperimentId === null) return null;

  return /** @type {ExperimentReference} */ (
    state.selectedExperiment || {
      experiment_id: selectedExperimentId,
      name: selectedExperimentId,
    }
  );
}

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = searchInput.value.trim();
  const experiment = getSelectedExperiment();
  const model = getSelectedModel();

  if (experiment !== null) {
    navigateToExperimentVariants(
      experiment,
      1,
      query,
      state.variantSort,
      state.variantOrder,
    );
    return;
  }

  if (model !== null) {
    navigateToModelVersions(
      model,
      1,
      query,
      state.versionSort,
      state.versionOrder,
    );
    return;
  }

  navigateToSection(
    state.active,
    1,
    query,
    state.sectionSort,
    state.sectionOrder,
  );
});
clearSearchButton.addEventListener("click", () => {
  const experiment = getSelectedExperiment();
  const model = getSelectedModel();

  if (experiment !== null) {
    navigateToExperimentVariants(
      experiment,
      1,
      "",
      state.variantSort,
      state.variantOrder,
    );
    return;
  }

  if (model !== null) {
    navigateToModelVersions(
      model,
      1,
      "",
      state.versionSort,
      state.versionOrder,
    );
    return;
  }

  navigateToSection(
    state.active,
    1,
    "",
    state.sectionSort,
    state.sectionOrder,
  );
});
document.querySelector("#console-home-button").addEventListener("click", () => {
  navigateToOverview();
  sidebar.classList.remove("open");
});
backButton.addEventListener("click", () => navigateToSection(
  state.selectedExperimentId !== null ? "experiments" : "models",
));
window.addEventListener("popstate", () => {
  const snapshot = state.snapshot;

  if (snapshot === null) return;

  const available = Object.keys(sections).filter((key) => snapshot.access[key]);
  applyRoute(available);
  renderNavigation();
  renderSection();
});
document.querySelector("#menu-button").addEventListener("click", () => sidebar.classList.toggle("open"));
document.addEventListener("visibilitychange", async () => {
  if (document.hidden) {
    stopAutoRefresh();
    stopRealtimeUpdates();
    return;
  }

  if (!dashboardView.hidden) {
    await loadOverview({ silent: true });
    startAutoRefresh();
    startRealtimeUpdates();
  }
});

(async function boot() {
  try {
    state.user = await request("session");
    showDashboard();
    await loadOverview();
    startAutoRefresh();
    startRealtimeUpdates();
  } catch (_) {
    showLogin();
  }
})();
