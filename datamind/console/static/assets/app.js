"use strict";

import { createDashboardController } from "./dashboard.js?v=20260901";
import { createResourceListController } from "./resources.js?v=20260902";
import { createNavigationController } from "./navigation.js?v=20260901";
import { createPresentationController } from "./presentation.js?v=20260902";

import { createAccessDetailController } from "./details/access.js?v=20260902-3";
import { createDeploymentDetailController } from "./details/deployment.js?v=20260902-4";
import { createAuditDetailController } from "./details/audit.js?v=20260902-4";
import { createExperimentDetailController } from "./details/experiment.js?v=20260902-4";
import { createInferenceDetailController } from "./details/inference.js?v=20260902-15";
import { createModelDetailController } from "./details/model.js?v=20260902-4";
import { createRoutingDetailController } from "./details/routing.js?v=20260902-7";
import { createRuntimeDetailController } from "./details/runtime.js?v=20260902-3";
import { createVersionDetailController } from "./details/version.js?v=20260902-4";
import {
  formatCompactPercentage,
  formatDuration,
  formatInteger,
  formatNavigationCount,
  formatOptionalDuration,
  formatOptionalPercentage,
  formatPercentage,
  formatProbability,
  formatScore,
  formatSignedPercentage,
  formatTime,
  statusTone,
} from "./format.js?v=20260901";
import { createResourceManager } from "./management.js?v=20260903-3";
import {
  createTableControls,
  DEFAULT_PAGE_SIZE,
  PAGE_SIZE_OPTIONS,
} from "./table.js?v=20260901";

/**
 * @typedef {Object} ConsoleUser
 * @property {string} username
 * @property {string | null} display_name
 * @property {string[]} roles
 * @property {string[]} permissions
 * @property {Object.<string, boolean>} capabilities
 * @property {string} environment
 */

/**
 * @typedef {Object} ConsoleRole
 * @property {string[]} permissions
 * @property {string[]} [effective_permissions]
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
 * @property {RequestSummary | null} request_summary
 * @property {RequestTrendPoint[]} request_trend
 * @property {string} request_trend_range
 * @property {string} request_trend_interval
 * @property {ModelUsageItem[]} model_usage
 */

/**
 * @typedef {Object} RequestSummary
 * @property {number} request_count
 * @property {number} success_count
 * @property {number} failed_count
 * @property {number | null} success_rate
 * @property {number | null} average_latency_ms
 * @property {number | null} p95_latency_ms
 * @property {number} previous_request_count
 * @property {number | null} change_rate
 */

/**
 * @typedef {Object} ModelUsageItem
 * @property {string} model_id
 * @property {string | null} model_name
 * @property {number} recent_count
 * @property {number} total_count
 * @property {number | null} success_rate
 * @property {number | null} average_latency_ms
 * @property {number | null} request_share
 */

/**
 * @typedef {Object} PageData
 * @property {Object[]} items
 * @property {number} page
 * @property {number} page_size
 * @property {number} total
 * @property {number} total_pages
 * @property {boolean} has_previous
 * @property {boolean} has_next
 * @property {string} query
 * @property {string | null} sort_by
 * @property {string} sort_order
 */

/**
 * @typedef {Object} ExperimentReference
 * @property {string} experiment_id
 * @property {string | null} experiment_name
 * @property {string} name
 * @property {number} [variant_count]
 */

/**
 * @typedef {Object} VariantPageData
 * @property {ExperimentReference} experiment
 * @property {ConsoleVariant[]} items
 * @property {number} page
 * @property {number} page_size
 * @property {number} total
 * @property {number} total_pages
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
 * @property {string | null} experiment_name
 * @property {string} name
 * @property {string} deployment_id
 * @property {string | null} model_name
 * @property {string | null} model_version
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
 * @property {string | null} [display_name]
 * @property {string | null} [framework]
 * @property {string | null} [model_type]
 * @property {string | null} [task_type]
 * @property {string | null} [status]
 * @property {string | null} [description]
 * @property {string | null} [latest_version]
 * @property {number} [version_count]
 * @property {Object[]} [versions]
 */

/**
 * @typedef {Object} ConsoleVersionDetail
 * @property {string} version_id
 * @property {string} model_id
 * @property {string | null} model_name
 * @property {string | null} display_name
 * @property {string | null} model_type
 * @property {string | null} task_type
 * @property {string} version
 * @property {string} framework
 * @property {number} artifact_revision
 * @property {string} status
 * @property {string | null} current_artifact_id
 * @property {string | null} artifact_sha256
 * @property {string | null} artifact_digest
 * @property {string | null} bento_tag
 * @property {string | null} model_key
 * @property {string | null} input_schema_key
 * @property {string | null} output_schema_key
 * @property {Object | null} input_schema
 * @property {Object | null} output_schema
 * @property {string | null} description
 * @property {string | null} created_by
 * @property {string | null} updated_by
 * @property {string | null} created_at
 * @property {string | null} updated_at
 */

/**
 * @typedef {Object} ModelVersionReference
 * @property {string} model_id
 * @property {string | null} model_name
 * @property {string} [version_id]
 */

/**
 * @typedef {Object} VersionPageData
 * @property {ConsoleModel} model
 * @property {Object[]} items
 * @property {number} page
 * @property {number} page_size
 * @property {number} total
 * @property {number} total_pages
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
 * @property {string | null} deployment_role
 * @property {string | null} deployment_rollout_type
 * @property {string | null} experiment_id
 * @property {string | null} experiment_name
 * @property {string | null} variant_id
 * @property {string | null} variant_name
 * @property {boolean | null} variant_is_control
 * @property {number | null} variant_weight
 * @property {string | null} assignment_id
 * @property {string | null} subject_key
 * @property {string | null} subject_type
 * @property {string} source
 * @property {string | null} strategy
 * @property {string | null} bucket
 * @property {string | null} routing_id
 * @property {string | null} routing_name
 * @property {number | null} routing_weight
 * @property {string | null} group
 * @property {number | null} weight
 * @property {Object | null} prediction
 * @property {number | null} probability
 * @property {number | null} score
 * @property {number | null} latency_ms
 * @property {Object | null} context
 * @property {ConsoleExecution[]} executions
 * @property {string} decided_at
 */

/**
 * @typedef {Object} ConsoleExecution
 * @property {string} execution_id
 * @property {string} decision_id
 * @property {string | null} request_id
 * @property {string} execution_type
 * @property {string} status
 * @property {string} model_id
 * @property {string | null} model_name
 * @property {string} version_id
 * @property {string | null} model_version
 * @property {string | null} deployment_id
 * @property {string | null} routing_id
 * @property {string | null} routing_name
 * @property {number | null} routing_weight
 * @property {Object | null} prediction
 * @property {number | null} probability
 * @property {number | null} score
 * @property {number | null} latency_ms
 * @property {string | null} error_type
 * @property {string | null} error
 * @property {Object | null} context
 * @property {string | null} started_at
 * @property {string | null} finished_at
 * @property {string | null} created_at
 */

const sections = {
  models: {
    label: "模型",
    title: "模型列表",
    columns: [
      ["name", "模型名称"],
      ["display_name", "显示名称"],
      ["framework", "框架"],
      ["model_type", "类型"],
      ["task_type", "任务类型"],
      ["status", "状态", "status"],
      ["latest_version", "最新版本"],
      ["version_count", "版本数", "version-count"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  versions: {
    label: "版本",
    title: "版本列表",
    columns: [
      ["model_name", "模型名称"],
      ["version", "版本"],
      ["framework", "框架"],
      ["status", "状态", "status"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  deployments: {
    label: "部署",
    title: "部署列表",
    columns: [
      ["model_name", "模型名称"],
      ["model_version", "版本"],
      ["rollout_type", "发布类型"],
      ["role", "角色", "deployment-role"],
      ["framework", "框架"],
      ["status", "状态", "status"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  routings: {
    label: "路由",
    title: "路由列表",
    columns: [
      ["name", "路由名称"],
      ["model_name", "模型名称"],
      ["model_version", "版本"],
      ["rollout_type", "发布类型"],
      ["rollout_group", "发布分组", "deployment-role"],
      ["traffic_ratio", "流量比例", "percentage"],
      ["status", "状态", "status"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  experiments: {
    label: "实验",
    title: "实验列表",
    columns: [
      ["name", "实验名称"],
      ["model_name", "模型名称"],
      ["status", "状态", "status"],
      ["effective_from", "生效时间", "time"],
      ["effective_to", "结束时间", "time"],
      ["updated_at", "更新时间", "time"],
      ["variant_count", "分组", "variant-count"],
    ],
  },
  variants: {
    label: "分组",
    title: "分组列表",
    columns: [
      ["name", "分组名称"],
      ["experiment_name", "实验名称"],
      ["group_type", "分组类型", undefined, "is_control"],
      ["model_name", "模型名称"],
      ["model_version", "版本"],
      ["deployment_id", "部署 ID", "mono"],
      ["weight", "权重", "percentage"],
      ["status", "状态", "status"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  runtimes: {
    label: "运行状态",
    title: "运行实例",
    columns: [
      ["model_name", "模型名称"],
      ["model_version", "版本"],
      ["role", "角色", "deployment-role"],
      ["worker_id", "运行节点", "runtime-worker"],
      ["status", "状态", "status"],
      ["health_status", "健康状态", "status"],
      ["last_heartbeat_at", "最近心跳", "time"],
    ],
  },
  requests: {
    label: "API 调用",
    title: "API 调用记录",
    columns: [
      ["request_id", "请求 ID", "mono"],
      ["model_name", "模型名称"],
      ["model_version", "版本"],
      ["source", "来源"],
      ["status", "状态", "status"],
      ["latency_ms", "耗时（毫秒）", "duration"],
      ["user", "调用用户"],
      ["ip", "客户端 IP"],
      ["created_at", "调用时间", "time"],
    ],
  },
  decisions: {
    label: "决策记录",
    title: "决策记录列表",
    columns: [
      ["request_id", "请求 ID", "request-link"],
      ["model_name", "模型名称"],
      ["model_version", "版本"],
      ["source", "来源"],
      ["probability", "概率", "probability"],
      ["score", "评分", "score"],
      ["decided_at", "决策时间", "time"],
    ],
  },
  executions: {
    label: "执行记录",
    title: "执行记录列表",
    columns: [
      ["request_id", "请求 ID", "request-link"],
      ["execution_type", "执行类型", "execution-type"],
      ["model_name", "模型名称"],
      ["model_version", "版本"],
      ["status", "状态", "status"],
      ["probability", "概率", "probability"],
      ["score", "评分", "score"],
      ["latency_ms", "耗时（毫秒）", "duration"],
      ["finished_at", "完成时间", "time"],
    ],
  },
  audits: {
    label: "审计记录",
    title: "审计记录列表",
    columns: [
      ["action", "操作"],
      ["target_type", "目标类型"],
      ["target_id", "目标 ID", "mono"],
      ["user", "操作人"],
      ["source", "来源"],
      ["status", "状态", "status"],
      ["occurred_at", "发生时间", "time"],
    ],
  },
  users: {
    label: "用户",
    title: "用户列表",
    columns: [
      ["username", "用户名"],
      ["display_name", "显示名称"],
      ["email", "邮箱", "blank"],
      ["roles", "角色", "list"],
      ["status", "状态", "status"],
      ["last_login_at", "最近登录", "time"],
      ["updated_at", "更新时间", "time"],
    ],
  },
  roles: {
    label: "角色",
    title: "角色列表",
    columns: [
      ["name", "角色名称"],
      ["description", "描述"],
      ["permissions", "权限", "permissions"],
      ["status", "状态", "status"],
      ["updated_at", "更新时间", "time"],
    ],
  },
};

const versionColumns = [
  ["version", "版本"],
  ["framework", "框架"],
  ["artifact_revision", "制品修订"],
  ["status", "状态", "status"],
  ["updated_at", "更新时间", "time"],
];

const deletionMetadataColumns = [
  ["deleted_by", "删除人", "blank"],
  ["deletion_reason", "删除原因", "blank"],
  ["deleted_at", "删除时间", "time"],
];

const deletedModelVersionColumns = [
  ["version", "版本"],
  ["framework", "框架"],
  ...deletionMetadataColumns,
];

const deletedSectionColumns = {
  models: [
    ["name", "模型名称"],
    ["display_name", "显示名称", "blank"],
    ["framework", "框架"],
    ["version_count", "版本数"],
    ...deletionMetadataColumns,
  ],
  versions: [
    ["model_name", "模型名称"],
    ...deletedModelVersionColumns,
  ],
  deployments: [
    ["model_name", "模型名称"],
    ["model_version", "版本"],
    ...deletionMetadataColumns,
  ],
  routings: [
    ["name", "路由名称"],
    ["model_name", "模型名称"],
    ["model_version", "版本"],
    ...deletionMetadataColumns,
  ],
  experiments: [
    ["name", "实验名称"],
    ["model_name", "模型名称"],
    ...deletionMetadataColumns,
  ],
  variants: [
    ["name", "分组名称"],
    ["experiment_name", "实验名称"],
    ["deployment_id", "部署 ID", "mono"],
    ...deletionMetadataColumns,
  ],
};

const recyclableSections = new Set(Object.keys(deletedSectionColumns));

const variantColumns = [
  ["name", "分组名称"],
  ["group_type", "分组类型", undefined, "is_control"],
  ["model_name", "模型名称"],
  ["model_version", "版本"],
  ["deployment_id", "部署 ID", "mono"],
  ["weight", "权重", "percentage"],
  ["status", "状态", "status"],
  ["updated_at", "更新时间", "time"],
];

const sectionIdFields = {
  models: "model_id",
  versions: "version_id",
  deployments: "deployment_id",
  routings: "routing_id",
  experiments: "experiment_id",
  variants: "variant_id",
  runtimes: "runtime_id",
  requests: "request_id",
  decisions: "decision_id",
  executions: "execution_id",
  audits: "audit_id",
  users: "user_id",
  roles: "role_id",
};
const defaultPageSize = DEFAULT_PAGE_SIZE;
const pageSizeOptions = PAGE_SIZE_OPTIONS;

const autoRefreshInterval = 30_000;
const realtimeRefreshDelay = 200;
const maxSortFields = 3;
/** @type {Object.<string, string>} */
const trendRangeDescriptions = {
  "1h": "最近 1 小时 · 每分钟聚合",
  "24h": "最近 24 小时 · 每 5 分钟聚合",
  "7d": "最近 7 天 · 每小时聚合",
  "30d": "最近 30 天 · 每天聚合",
};
const state = {
  user: /** @type {ConsoleUser | null} */ (null),
  snapshot: /** @type {ConsoleSnapshot | null} */ (null),
  trendRange: "24h",
  active: null,
  selectedModelId: /** @type {string | null} */ (null),
  selectedModel: /** @type {ConsoleModel | null} */ (null),
  selectedExperimentId: /** @type {string | null} */ (null),
  selectedExperiment: /** @type {ExperimentReference | null} */ (null),
  sectionPage: 1,
  sectionPageSize: defaultPageSize,
  sectionQuery: "",
  sectionSort: "",
  sectionOrder: "asc",
  sectionView: "active",
  sectionData: /** @type {PageData | null} */ (null),
  sectionError: null,
  versionPage: 1,
  versionPageSize: defaultPageSize,
  versionQuery: "",
  versionSort: "",
  versionOrder: "asc",
  versionView: "versions",
  versionData: /** @type {VersionPageData | null} */ (null),
  versionError: null,
  variantPage: 1,
  variantPageSize: defaultPageSize,
  variantQuery: "",
  variantSort: "",
  variantOrder: "asc",
  variantView: "active",
  variantData: /** @type {VariantPageData | null} */ (null),
  variantError: null,
  selectionScope: "",
  selectedRecordIds: /** @type {Set<string>} */ (new Set()),
};
let autoRefreshTimer = null;
let overviewRequest = null;
let eventSource = null;
let realtimeRefreshTimer = null;
let realtimeRefreshRunning = false;
let pendingRealtimeChanges = [];
let exportInProgress = false;
/** @type {Promise<boolean> | null} */
let sessionRefreshRequest = null;
const loginView = document.querySelector("#login-view");
const dashboardView = document.querySelector("#dashboard-view");
const loginForm = document.querySelector("#login-form");
const loginButton = document.querySelector("#login-button");
const loginError = document.querySelector("#login-error");
const navigation = document.querySelector("#navigation");
const summaryGrid = document.querySelector("#summary-grid");
const tableContainer = /** @type {HTMLElement} */ (
  document.querySelector("#table-container")
);
const dataPanel = document.querySelector(".data-panel");
const sidebar = document.querySelector(".sidebar");
const backButton = document.querySelector("#back-button");
const resourceViewToggle = document.querySelector("#resource-view-toggle");
const createButton = document.querySelector("#create-button");
const selectionSummary = document.querySelector("#selection-summary");
const selectionCount = document.querySelector("#selection-count");
const selectedExportButton = /** @type {HTMLButtonElement} */ (
  document.querySelector("#selected-export-button")
);
const clearSelectionButton = document.querySelector("#clear-selection-button");
const trendPanel = document.querySelector("#request-trend");
const trendChart = document.querySelector("#request-trend-chart");
const trendVolumeTotal = document.querySelector("#trend-volume-total");
const trendFailureRate = document.querySelector("#trend-failure-rate");
const trendRangeSelector = document.querySelector("#trend-range-selector");
const trendRangeDescription = document.querySelector("#trend-range-description");
const modelUsagePanel = document.querySelector("#model-usage");
const recentModelUsageContent = document.querySelector("#recent-model-usage");
const totalModelUsageContent = document.querySelector("#total-model-usage");
const searchForm = /** @type {HTMLFormElement} */ (
  document.querySelector("#search-form")
);
const searchInput = /** @type {HTMLInputElement} */ (
  document.querySelector("#search-input")
);
const searchToggleButton = /** @type {HTMLButtonElement} */ (
  document.querySelector("#search-toggle-button")
);
const collapseSearchButton = /** @type {HTMLButtonElement} */ (
  document.querySelector("#collapse-search-button")
);
const clearSearchButton = /** @type {HTMLButtonElement} */ (
  document.querySelector("#clear-search-button")
);
const account = document.querySelector(".account");
const accountMenuButton = document.querySelector("#account-menu-button");
const accountMenu = document.querySelector("#account-menu");
const accountRoleList = document.querySelector("#account-role-list");
const accountManagement = document.querySelector("#account-management");
const changePasswordButton = document.querySelector("#change-password-button");
const accountSectionKeys = new Set(["users", "roles"]);
const tableControls = createTableControls({
  container: tableContainer,
  queryForm: searchForm,
  queryInput: searchInput,
  queryToggle: searchToggleButton,
  queryCollapse: collapseSearchButton,
  queryClear: clearSearchButton,
  formatNumber: formatInteger,
  notify: toast,
});

const navigationController = createNavigationController({
  applyDefaultRoute,
  buildHashQuery: (page, pageSize, query, sortBy, sortOrder) => (
    resourceListController.buildHashQuery(
      page,
      pageSize,
      query,
      sortBy,
      sortOrder,
    )
  ),
  canViewOverview,
  defaultPageSize,
  getAvailableSections,
  loadOverview,
  normalizeSortParameters: (sortBy, sortOrder) => (
    resourceListController.normalizeSortParameters(sortBy, sortOrder)
  ),
  parsePageSize: (value) => resourceListController.parsePageSize(value),
  recyclableSections,
  renderNavigation: () => dashboardController.renderNavigation(),
  renderSection: () => resourceListController.renderSection(),
  resetDetailRoute,
  state,
  tableControls,
});
const presentationController = createPresentationController({
  formatDuration,
  formatInteger,
  formatPercentage,
  formatProbability,
  formatScore,
  formatTime,
  maxSortFields,
  navigateToExperimentVariants: navigationController.navigateToExperimentVariants,
  navigateToModelVersions: navigationController.navigateToModelVersions,
  navigateToSection: navigationController.navigateToSection,
  parseSortRules: (sortBy, sortOrder) => (
    resourceListController.parseSortRules(sortBy, sortOrder)
  ),
  sectionIdFields,
  state,
  statusTone,
  toast,
});
const dashboardController = createDashboardController({
  accountSectionKeys,
  canViewOverview,
  formatCompactPercentage,
  formatDuration,
  formatInteger,
  formatNavigationCount,
  formatOptionalDuration,
  formatOptionalPercentage,
  formatPercentage,
  formatSignedPercentage,
  modelUsagePanel,
  navigateToOverview: navigationController.navigateToOverview,
  navigateToSection: navigationController.navigateToSection,
  navigation,
  recentModelUsageContent,
  renderAccountManagement,
  sections,
  sidebar,
  state,
  summaryGrid,
  totalModelUsageContent,
  trendChart,
  trendFailureRate,
  trendPanel,
  trendRangeDescriptions,
  trendRangeDescription,
  trendRangeSelector,
  trendVolumeTotal,
});
const resourceListController = createResourceListController({
  appendManagementCell: (row, section, record) => (
    managementController.appendManagementCell(row, section, record)
  ),
  appendManagementHeader: (row, section) => (
    managementController.appendManagementHeader(row, section)
  ),
  backButton,
  createButton,
  createDataCell: presentationController.createDataCell,
  createSortHeader: presentationController.createSortHeader,
  dashboardView,
  dataPanel,
  defaultPageSize,
  deletedModelVersionColumns,
  deletedSectionColumns,
  formatInteger,
  isExportInProgress: () => exportInProgress,
  maxSortFields,
  modelUsagePanel,
  navigateToExperimentVariants: navigationController.navigateToExperimentVariants,
  navigateToModelVersions: navigationController.navigateToModelVersions,
  navigateToSection: navigationController.navigateToSection,
  pageSizeOptions,
  recyclableSections,
  renderEmpty,
  renderNavigation: dashboardController.renderNavigation,
  request,
  resourceViewToggle,
  sectionIdFields,
  sections,
  selectedExportButton,
  selectionCount,
  selectionSummary,
  showAuditDetails: (record) => showAuditDetails(record),
  showDecisionDetails: (record) => (
    inferenceDetailController.showDecisionDrawer(record)
  ),
  showDeploymentDrawer: (record) => showDeploymentDrawer(record),
  showExecutionDetails: (record) => (
    inferenceDetailController.showExecutionDrawer(record)
  ),
  showExperimentDetails: (record) => (
    experimentDetailController.showExperimentDrawer(record)
  ),
  showLogin,
  showModelDrawer: (record) => showModelDrawer(record),
  showRequestDetails: (record) => (
    inferenceDetailController.showRequestDrawer(record)
  ),
  showRoleDrawer: (record) => accessDetailController.showRoleDrawer(record),
  showRoutingDrawer: (record) => showRoutingDrawer(record),
  showRuntimeDetails: (record) => showRuntimeDetails(record),
  showUserDrawer: (record) => accessDetailController.showUserDrawer(record),
  showVariantDetails: (record) => (
    experimentDetailController.showVariantDrawer(record)
  ),
  showVersionDrawer: (record) => showVersionDrawer(record),
  state,
  summaryGrid,
  tableContainer,
  tableControls,
  toast,
  trendPanel,
  updateCreateButton: () => managementController.updateCreateButton(),
  updateSearchForm: navigationController.updateSearchForm,
  variantColumns,
  versionColumns,
});
/** @returns {Promise<boolean>} */
function refreshSession() {
  if (sessionRefreshRequest !== null) return sessionRefreshRequest;

  const refreshRequest = fetch("./api/refresh", {
    method: "POST",
    credentials: "same-origin",
  })
    .then((response) => response.ok);

  sessionRefreshRequest = refreshRequest;
  void refreshRequest.then(
    () => {
      sessionRefreshRequest = null;
    },
    () => {
      sessionRefreshRequest = null;
    },
  );

  return refreshRequest;
}

const csrfErrorMessage = "请求安全校验失败，请刷新页面后重试";

const environmentLabels = {
  development: "开发环境",
  testing: "测试环境",
  staging: "预发布环境",
  production: "生产环境",
};

const environmentCodes = {
  development: "DEV",
  testing: "TEST",
  staging: "STG",
  production: "PROD",
};

/** @returns {Promise<boolean>} */
async function restoreCsrfSession() {
  const response = await fetch("./api/session", {
    method: "GET",
    credentials: "same-origin",
  });

  if (response.ok && getCookie("datamind_console_csrf")) return true;
  return refreshSession();
}

async function request(path, options = {}, retry = true) {
  const headers = { ...(options.headers || {}) };
  const method = String(options.method || "GET").toUpperCase();
  const requiresCsrf = !["GET", "HEAD", "OPTIONS"].includes(method);
  const refreshable = !["login", "refresh"].includes(path);

  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }

  if (requiresCsrf) {
    let csrfToken = getCookie("datamind_console_csrf");

    if (!csrfToken && retry && refreshable && await restoreCsrfSession()) {
      return request(path, options, false);
    }

    csrfToken = getCookie("datamind_console_csrf");
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(`./api/${path}`, {
    credentials: "same-origin",
    ...options,
    headers,
  });

  if (response.status === 401 && retry && refreshable) {
    if (await refreshSession()) return request(path, options, false);
  }

  if (!response.ok) {
    const responseText = await response.text();
    let body;
    try {
      body = responseText ? JSON.parse(responseText) : {};
    } catch (_) {
      body = {};
    }
    if (
      response.status === 403
      && retry
      && refreshable
      && body.error === csrfErrorMessage
      && await restoreCsrfSession()
    ) {
      return request(path, options, false);
    }
    const error = new Error(
      body.error
      || body.detail
      || `请求失败（HTTP ${response.status}）`,
    );
    error.status = response.status;
    throw error;
  }

  return response.status === 204 ? null : response.json();
}

function getCookie(name) {
  const prefix = `${encodeURIComponent(name)}=`;
  const value = document.cookie
    .split("; ")
    .find((item) => item.startsWith(prefix));

  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}

function hasCapability(name) {
  return Boolean(state.user?.capabilities?.[name]);
}

let showModelDrawer;
let showVersionDrawer;

const managementController = createResourceManager({
  state,
  createButton,
  changePasswordButton,
  closeAccountMenu: () => setAccountMenuOpen(false),
  hasCapability,
  request,
  refresh: loadOverview,
  toast,
  sectionIdFields,
  onCurrentUserUpdated: (user) => {
    const updatedUser = {
      ...(state.user || {}),
      ...user,
    };
    state.user = updatedUser;
    renderAccount(updatedUser);
  },
  onAccessChanged: async () => {
    const user = await request("session");
    state.user = user;
    renderAccount(user);
  },
  onSessionEnded: showLogin,
  onShowModel: (record) => showModelDrawer(record),
  onShowModelVersions: navigationController.navigateToModelVersions,
  onShowVersion: (record) => showVersionDrawer(record),
});

showModelDrawer = createModelDetailController({
  buildPageQuery: resourceListController.buildPageQuery,
  createCopyableNavigationLink: presentationController.createCopyableNavigationLink,
  createDeploymentRoleBadge: presentationController.createDeploymentRoleBadge,
  createSectionNavigationLink: presentationController.createSectionNavigationLink,
  createStatusBadge: presentationController.createStatusBadge,
  formatPercentage,
  formatTime,
  getRecordActions: managementController.getRecordActions,
  hasCapability,
  navigateToModelVersions: navigationController.navigateToModelVersions,
  navigateToSection: navigationController.navigateToSection,
  openVersionCreateDialog: managementController.openVersionCreateDialog,
  request,
  runRecordAction: managementController.runRecordAction,
  toast,
});

showVersionDrawer = createVersionDetailController({
  buildPageQuery: resourceListController.buildPageQuery,
  createCopyableNavigationLink: presentationController.createCopyableNavigationLink,
  createStatusBadge: presentationController.createStatusBadge,
  formatTime,
  getRecordActions: managementController.getRecordActions,
  hasCapability,
  navigateToModelVersions: navigationController.navigateToModelVersions,
  navigateToSection: navigationController.navigateToSection,
  openDeploymentCreateDialog: managementController.openDeploymentCreateDialog,
  request,
  runRecordAction: managementController.runRecordAction,
  showModelDrawer,
  toast,
});

const showDeploymentDrawer = createDeploymentDetailController({
  buildPageQuery: resourceListController.buildPageQuery,
  createCopyableSectionNavigationLink: presentationController.createCopyableSectionNavigationLink,
  createDeploymentRoleBadge: presentationController.createDeploymentRoleBadge,
  createStatusBadge: presentationController.createStatusBadge,
  formatTime,
  getRecordActions: managementController.getRecordActions,
  navigateToSection: navigationController.navigateToSection,
  request,
  runRecordAction: managementController.runRecordAction,
});

const showRoutingDrawer = createRoutingDetailController({
  buildPageQuery: resourceListController.buildPageQuery,
  createCopyableSectionNavigationLink: presentationController.createCopyableSectionNavigationLink,
  createDeploymentRoleBadge: presentationController.createDeploymentRoleBadge,
  createSectionNavigationLink: presentationController.createSectionNavigationLink,
  createStatusBadge: presentationController.createStatusBadge,
  formatPercentage,
  formatTime,
  getRecordActions: managementController.getRecordActions,
  request,
  runRecordAction: managementController.runRecordAction,
});

const showRuntimeDetails = createRuntimeDetailController({
  createCopyableNavigationLink: presentationController.createCopyableNavigationLink,
  createDeploymentRoleBadge: presentationController.createDeploymentRoleBadge,
  createStatusBadge: presentationController.createStatusBadge,
  formatTime,
  navigateToSection: navigationController.navigateToSection,
});

const experimentDetailController = createExperimentDetailController({
  createCopyableNavigationLink: presentationController.createCopyableNavigationLink,
  createSectionNavigationLink: presentationController.createSectionNavigationLink,
  createStatusBadge: presentationController.createStatusBadge,
  formatPercentage,
  formatTime,
  getRecordActions: managementController.getRecordActions,
  navigateToExperimentVariants: navigationController.navigateToExperimentVariants,
  navigateToSection: navigationController.navigateToSection,
  request,
  runRecordAction: managementController.runRecordAction,
  toast,
});

const inferenceDetailController = createInferenceDetailController({
  createCopyableNavigationLink: presentationController.createCopyableNavigationLink,
  createExecutionTypeBadge: presentationController.createExecutionTypeBadge,
  createSectionNavigationLink: presentationController.createSectionNavigationLink,
  createStatusBadge: presentationController.createStatusBadge,
  formatOptionalDuration,
  formatPercentage,
  formatProbability,
  formatScore,
  formatTime,
  navigateToSection: navigationController.navigateToSection,
  sectionIdFields,
});

const showAuditDetails = createAuditDetailController({
  createCopyableNavigationLink: presentationController.createCopyableNavigationLink,
  createSectionNavigationLink: presentationController.createSectionNavigationLink,
  createStatusBadge: presentationController.createStatusBadge,
  formatTime,
  navigateToSection: navigationController.navigateToSection,
  sectionIdFields,
});

const accessDetailController = createAccessDetailController({
  createCopyableSectionNavigationLink: presentationController.createCopyableSectionNavigationLink,
  createStatusBadge: presentationController.createStatusBadge,
  formatTime,
});

async function download(path, options = {}, retry = true) {
  const response = await fetch(`./api/${path}`, {
    credentials: "same-origin",
    ...options,
  });

  if (response.status === 401 && retry) {
    if (await refreshSession()) return download(path, options, false);
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error(body.error || "导出失败");
    error.status = response.status;
    throw error;
  }

  const disposition = response.headers.get("content-disposition") || "";
  const filenameMatch = disposition.match(/filename="([^"]+)"/i);
  const filename = filenameMatch ? filenameMatch[1] : "datamind_export.csv";
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

function setAccountMenuOpen(open) {
  accountMenu.hidden = !open;
  accountMenuButton.setAttribute("aria-expanded", String(open));
  accountMenuButton.setAttribute(
    "aria-label",
    open ? "关闭账户菜单" : "打开账户菜单",
  );
}

function getAccountInitials(name) {
  const normalized = String(name || "").trim();

  if (!normalized) return "?";

  const parts = normalized.split(/\s+/);

  if (parts.length > 1) {
    return (
      parts[0].charAt(0)
      + parts[parts.length - 1].charAt(0)
    ).toUpperCase();
  }

  return Array.from(normalized)[0].toUpperCase();
}

function getAccountAvatarTone(username) {
  const normalized = String(username || "").trim().toLowerCase();
  let hash = 0;

  for (const character of Array.from(normalized)) {
    hash = ((hash * 31) + character.codePointAt(0)) >>> 0;
  }

  return String(hash % 8);
}

function renderAccount(user) {
  const displayName = user.display_name || user.username;
  const environment = user.environment || "unknown";
  const environmentLabel = environmentLabels[environment] || environment;
  const environmentCode = environmentCodes[environment] || environment.toUpperCase();
  const environmentBadge = /** @type {HTMLElement} */ (
    document.querySelector("#service-environment")
  );
  const topbar = /** @type {HTMLElement} */ (
    document.querySelector(".topbar")
  );
  document.querySelector("#account-name").textContent = displayName;
  const accountAvatar = /** @type {HTMLElement} */ (
    document.querySelector("#account-avatar")
  );
  accountAvatar.textContent = getAccountInitials(displayName);
  accountAvatar.dataset.tone = getAccountAvatarTone(user.username);
  document.querySelector("#account-menu-name").textContent = displayName;
  document.querySelector("#account-menu-username").textContent = user.username;
  environmentBadge.textContent = environmentCode;
  environmentBadge.dataset.environment = environment;
  environmentBadge.title = environmentLabel;
  environmentBadge.setAttribute("aria-label", `当前服务环境：${environmentLabel}`);
  topbar.dataset.environment = environment;
  accountMenuButton.setAttribute("aria-label", "打开账户菜单");
  accountRoleList.replaceChildren();

  const roles = Array.isArray(user.roles) ? user.roles : [];

  if (!roles.length) {
    const empty = document.createElement("span");
    empty.className = "account-role empty";
    empty.textContent = "未分配角色";
    accountRoleList.append(empty);
    return;
  }

  for (const role of roles) {
    const item = document.createElement("span");
    item.className = "account-role";
    item.textContent = role;
    accountRoleList.append(item);
  }
}

function renderAccountManagement() {
  const capabilityBySection = {
    users: "users.manage",
    roles: "roles.manage",
  };
  let visibleCount = 0;

  for (const button of accountManagement.querySelectorAll("[data-account-section]")) {
    const section = button.dataset.accountSection;
    const capability = section ? capabilityBySection[section] : null;
    const visible = Boolean(capability && hasCapability(capability));
    button.hidden = !visible;
    if (visible) visibleCount += 1;
  }

  accountManagement.hidden = visibleCount === 0;
}

function showLogin(message = "") {
  document.documentElement.classList.remove("auth-pending");
  setAccountMenuOpen(false);
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
  state.sectionView = "active";
  state.sectionData = null;
  state.sectionError = null;
  state.versionQuery = "";
  state.versionSort = "";
  state.versionOrder = "asc";
  state.versionView = "versions";
  state.versionData = null;
  state.versionError = null;
  state.variantQuery = "";
  state.variantSort = "";
  state.variantOrder = "asc";
  state.variantView = "active";
  state.variantData = null;
  state.variantError = null;
  state.selectionScope = "";
  state.selectedRecordIds.clear();
  dashboardView.hidden = true;
  loginView.hidden = false;
  loginError.hidden = !message;
  loginError.textContent = message;
  document.querySelector("#password").value = "";
}

function showDashboard() {
  const user = state.user;

  if (user === null) return;

  document.documentElement.classList.remove("auth-pending");
  loginView.hidden = true;
  dashboardView.hidden = false;
  renderAccount(user);
}

function loadOverview({ silent = false } = {}) {
  if (overviewRequest) return overviewRequest;

  overviewRequest = refreshOverview(silent).finally(() => {
    overviewRequest = null;
  });

  return overviewRequest;
}

async function refreshOverview(silent) {
  const requestedTrendRange = state.trendRange;
  try {
    const snapshot = /** @type {ConsoleSnapshot} */ (await request(
      `overview?range=${encodeURIComponent(requestedTrendRange)}`,
    ));

    if (requestedTrendRange !== state.trendRange) return;

    state.snapshot = snapshot;
    const available = getAvailableSections(snapshot);

    if (state.active === null) {
      navigationController.applyRoute(available);
    } else if (
      (state.active === "overview" && !canViewOverview(snapshot))
      || (state.active !== "overview" && !available.includes(state.active))
    ) {
      applyDefaultRoute(available);
    }

    const listRefreshPaused = (
      state.active !== null
      && state.active !== "overview"
      && tableControls.hasQueryDraft()
    );

    dashboardController.renderNavigation();
    dashboardController.renderSummary();
    dashboardController.renderRequestTrend();
    dashboardController.renderModelUsage();
    if (!listRefreshPaused) resourceListController.renderSection();

    if (
      state.active !== null
      && state.active !== "overview"
      && !listRefreshPaused
    ) {
      await refreshVisiblePage();
    }
    await resourceListController.syncDetailRoute();
    document.querySelector("#snapshot-time").textContent = formatTime(snapshot.generated_at);
  } catch (error) {
    if (error.status === 401) showLogin("登录会话已过期，请重新登录。");
    else if (!silent) toast(error.message);
  }
}

async function refreshVisiblePage() {
  if (tableControls.hasQueryDraft()) return;

  if (state.selectedModelId !== null) {
    await resourceListController.loadVersionPage(
      state.selectedModelId,
      state.versionPage,
    );
    return;
  }

  if (state.selectedExperimentId !== null) {
    await resourceListController.loadVariantPage(
      state.selectedExperimentId,
      state.variantPage,
    );
    return;
  }

  if (state.active !== null && state.active !== "overview") {
    await resourceListController.loadSectionPage(
      state.active,
      state.sectionPage,
    );
  }
}

function startAutoRefresh() {
  if (
    autoRefreshTimer !== null
    || document.hidden
    || dashboardView.hidden
  ) return;

  autoRefreshTimer = window.setTimeout(async () => {
    autoRefreshTimer = null;
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

function startRealtimeUpdates(skipInitialSync = false) {
  stopRealtimeUpdates();
  if (document.hidden || dashboardView.hidden) return;

  setRealtimeStatus("正在建立实时连接", false);
  startAutoRefresh();
  eventSource = new EventSource("./api/events", { withCredentials: true });
  eventSource.addEventListener("open", () => {
    setRealtimeStatus("实时更新", true);
  });
  eventSource.addEventListener("sync", (event) => {
    if (skipInitialSync) {
      skipInitialSync = false;
      return;
    }

    queueRealtimeRefresh(event);
  });
  eventSource.addEventListener("changed", (event) => {
    queueRealtimeRefresh(event);
  });
  eventSource.addEventListener("authentication", async () => {
    stopRealtimeUpdates();
    await loadOverview({ silent: true });
    if (!dashboardView.hidden) startRealtimeUpdates(true);
  });
  eventSource.addEventListener("error", () => {
    startAutoRefresh();
    setRealtimeStatus("实时连接中断 · 30 秒校准中", false);
  });
}

function stopRealtimeUpdates() {
  clearRealtimeRefresh();
  if (eventSource !== null) {
    eventSource.close();
    eventSource = null;
  }
}

function queueRealtimeRefresh(event) {
  let payload;

  try {
    payload = JSON.parse(event.data);
  } catch (_) {
    payload = { topics: [], changes: [] };
  }

  const changes = Array.isArray(payload.changes)
    ? payload.changes
    : (Array.isArray(payload.topics)
      ? payload.topics.map((topic) => ({ topic, action: "update" }))
      : []);
  pendingRealtimeChanges.push(...changes);
  scheduleRealtimeRefresh();
}

function scheduleRealtimeRefresh() {
  if (
    realtimeRefreshTimer !== null
    || realtimeRefreshRunning
    || pendingRealtimeChanges.length === 0
  ) return;

  realtimeRefreshTimer = window.setTimeout(async () => {
    realtimeRefreshTimer = null;
    realtimeRefreshRunning = true;
    const queuedChanges = pendingRealtimeChanges;
    pendingRealtimeChanges = [];

    try {
      await applyRealtimeChanges(queuedChanges);
    } finally {
      realtimeRefreshRunning = false;
      scheduleRealtimeRefresh();
    }
  }, realtimeRefreshDelay);
}

async function applyRealtimeChanges(changes) {
  const snapshot = state.snapshot;

  if (snapshot === null || changes.length === 0) return;

  const topics = new Set();

  for (const change of changes) {
    const topic = change.topic;

    if (typeof topic !== "string" || !snapshot.access[topic]) continue;

    topics.add(topic);
  }

  if (topics.size === 0) return;
  await loadOverview({ silent: true });
}

function clearRealtimeRefresh() {
  pendingRealtimeChanges = [];

  if (realtimeRefreshTimer !== null) {
    window.clearTimeout(realtimeRefreshTimer);
    realtimeRefreshTimer = null;
  }
}

function setRealtimeStatus(message, connected) {
  const element = document.querySelector("#realtime-status");
  element.textContent = message;
  element.closest(".auto-refresh-status").classList.toggle("connected", connected);
}

/**
 * 判断当前快照是否允许访问概览。
 *
 * @param {ConsoleSnapshot} snapshot 控制台快照
 * @returns {boolean} 是否可以访问概览
 */
function canViewOverview(snapshot) {
  return Boolean(snapshot.access.requests);
}

/**
 * 获取当前用户可访问的资源分区。
 *
 * @param {ConsoleSnapshot} snapshot 控制台快照
 * @returns {string[]} 可访问的资源分区标识
 */
function getAvailableSections(snapshot) {
  return Object.keys(sections).filter((key) => snapshot.access[key]);
}

function resetDetailRoute() {
  state.selectedModelId = null;
  state.selectedModel = null;
  state.selectedExperimentId = null;
  state.selectedExperiment = null;
  state.versionView = "versions";
  state.sectionView = "active";
  state.variantView = "active";
}

function applyDefaultRoute(available) {
  const snapshot = state.snapshot;
  const target = (
    snapshot !== null && canViewOverview(snapshot)
      ? "overview"
      : (available[0] || null)
  );
  state.active = target;
  resetDetailRoute();
  state.sectionPage = 1;
  state.sectionQuery = "";
  state.sectionData = null;
  state.sectionError = null;
  state.versionData = null;
  state.versionError = null;
  state.variantData = null;
  state.variantError = null;
  window.history.replaceState(
    null,
    "",
    target === null ? window.location.pathname : `#${target}`,
  );
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
    await loadOverview();
    showDashboard();
    startRealtimeUpdates(true);
  } catch (error) {
    loginError.textContent = error.message;
    loginError.hidden = false;
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = "登录";
  }
});

accountMenuButton.addEventListener("click", () => {
  setAccountMenuOpen(accountMenu.hidden);
});
accountManagement.addEventListener("click", (event) => {
  const target = event.target;

  if (!(target instanceof Element)) return;

  const button = target.closest("[data-account-section]");

  if (!(button instanceof HTMLButtonElement)) return;

  const section = button.dataset.accountSection;

  if (!section) return;

  if (!hasCapability(`${section}.manage`)) return;

  setAccountMenuOpen(false);
  navigationController.navigateToSection(section);
});
document.addEventListener("click", (event) => {
  const target = event.target;

  if (target instanceof Node && !account.contains(target)) {
    setAccountMenuOpen(false);
  }
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || accountMenu.hidden) return;

  setAccountMenuOpen(false);
  accountMenuButton.focus();
});
document.querySelector("#logout-button").addEventListener("click", async () => {
  setAccountMenuOpen(false);
  await request("logout", { method: "POST" }, false).catch(() => null);
  showLogin();
});
trendRangeSelector.addEventListener("click", async (event) => {
  const target = event.target;

  if (!(target instanceof Element)) return;

  const button = target.closest("[data-trend-range]");

  if (!(button instanceof HTMLButtonElement)) return;

  const trendRange = button.dataset.trendRange;

  if (!trendRange || trendRange === state.trendRange) return;

  state.trendRange = trendRange;
  dashboardController.renderTrendRangeSelector();

  if (overviewRequest !== null) await overviewRequest;

  await loadOverview();
});
async function exportRecords(recordIds) {
  if (!recordIds.length) return;

  exportInProgress = true;
  resourceListController.updateSelectionControls();
  selectedExportButton.textContent = "正在下载…";

  try {
    await download(
      resourceListController.buildExportPath(),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          record_ids: recordIds,
        }),
      },
    );
    toast("已选记录下载完成");
  } catch (error) {
    if (error.status === 401) {
      showLogin("登录会话已过期，请重新登录。");
      return;
    }
    toast(error.message);
  } finally {
    exportInProgress = false;
    selectedExportButton.textContent = "下载已选";
    resourceListController.updateSelectionControls();
  }
}

selectedExportButton.addEventListener("click", async () => {
  await exportRecords(
    Array.from(state.selectedRecordIds)
  );
});
clearSelectionButton.addEventListener("click", () => {
  state.selectedRecordIds.clear();
  resourceListController.updateVisibleSelectionState();
});
/**
 * 获取当前选中的模型。
 *
 * @returns {ConsoleModel | null} 当前模型；未选中时返回空值
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
 * 获取当前选中的实验。
 *
 * @returns {ExperimentReference | null} 当前实验；未选中时返回空值
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
    navigationController.navigateToExperimentVariants(
      experiment,
      1,
      query,
      state.variantSort,
      state.variantOrder,
      state.variantPageSize,
    );
    return;
  }

  if (model !== null) {
    navigationController.navigateToModelVersions(
      model,
      1,
      query,
      state.versionSort,
      state.versionOrder,
      state.versionPageSize,
    );
    return;
  }

  navigationController.navigateToSection(
    state.active,
    1,
    query,
    state.sectionSort,
    state.sectionOrder,
    state.sectionPageSize,
    resourceListController.getSectionView(state.active),
  );
});
clearSearchButton.addEventListener("click", () => {
  const experiment = getSelectedExperiment();
  const model = getSelectedModel();

  if (experiment !== null) {
    navigationController.navigateToExperimentVariants(
      experiment,
      1,
      "",
      state.variantSort,
      state.variantOrder,
      state.variantPageSize,
    );
    return;
  }

  if (model !== null) {
    navigationController.navigateToModelVersions(
      model,
      1,
      "",
      state.versionSort,
      state.versionOrder,
      state.versionPageSize,
    );
    return;
  }

  navigationController.navigateToSection(
    state.active,
    1,
    "",
    state.sectionSort,
    state.sectionOrder,
    state.sectionPageSize,
    resourceListController.getSectionView(state.active),
  );
});
resourceViewToggle.addEventListener("click", () => {
  const targetView = resourceViewToggle.dataset.targetView;
  const view = ["active", "trash"].includes(targetView)
    ? targetView
    : "active";
  const model = getSelectedModel();
  if (model !== null) {
    if (view === (state.versionView === "trash" ? "trash" : "active")) return;
    navigationController.navigateToModelVersions(
      model,
      1,
      "",
      state.versionSort,
      state.versionOrder,
      state.versionPageSize,
      view,
    );
    return;
  }

  const experiment = getSelectedExperiment();
  if (experiment !== null) {
    if (view === state.variantView) return;
    navigationController.navigateToExperimentVariants(
      experiment,
      1,
      "",
      state.variantSort,
      state.variantOrder,
      state.variantPageSize,
      view,
    );
    return;
  }

  if (recyclableSections.has(state.active)) {
    const currentView = state.active === "versions"
      ? (state.versionView === "trash" ? "trash" : "active")
      : state.sectionView;
    if (view === currentView) return;
    navigationController.navigateToSection(
      state.active,
      1,
      "",
      state.sectionSort,
      state.sectionOrder,
      state.sectionPageSize,
      view,
    );
  }
});
document.querySelector("#console-home-button").addEventListener("click", () => {
  navigationController.navigateToOverview();
  sidebar.classList.remove("open");
});
backButton.addEventListener("click", () => navigationController.navigateToSection(
  state.selectedExperimentId !== null ? "experiments" : "models",
));
window.addEventListener("popstate", () => {
  const snapshot = state.snapshot;

  if (snapshot === null) return;

  const available = getAvailableSections(snapshot);
  navigationController.applyRoute(available);
  dashboardController.renderNavigation();
  resourceListController.renderSection();
  void resourceListController.syncDetailRoute();
});
document.querySelector("#menu-button").addEventListener("click", () => sidebar.classList.toggle("open"));
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopAutoRefresh();
    stopRealtimeUpdates();
    return;
  }

  if (!dashboardView.hidden) {
    startRealtimeUpdates();
  }
});

(async function boot() {
  try {
    state.user = await request("session");
    await loadOverview();
    showDashboard();
    startRealtimeUpdates(true);
  } catch (_) {
    showLogin();
  }
})();
