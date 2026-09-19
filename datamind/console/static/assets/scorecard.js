"use strict";

import { createDetailIcon } from "./details/common.js";
import { DEFAULT_PAGE_SIZE, PAGE_SIZE_OPTIONS } from "./table.js";

const scorecardColumns = [
  { key: "variable", label: "变量", align: "left" },
  { key: "dtype", label: "类型", align: "left" },
  { key: "bin", label: "分箱", align: "left" },
  { key: "count", label: "样本数", format: "integer" },
  { key: "countRate", label: "样本占比", format: "percentage" },
  { key: "nonEvent", label: "非事件数", format: "integer" },
  { key: "event", label: "事件数", format: "integer" },
  { key: "eventRate", label: "事件率", format: "percentage" },
  { key: "woe", label: "WoE", format: "decimal" },
  { key: "binIv", label: "分箱 IV", format: "decimal" },
  { key: "js", label: "分箱 JS", format: "decimal" },
  { key: "coefficient", label: "回归系数", format: "decimal" },
  { key: "points", label: "分值", format: "decimal" },
];

const requiredScorecardColumnKeys = new Set(["variable", "bin", "points"]);
const defaultScorecardColumnKeys = new Set(
  scorecardColumns.map((column) => column.key),
);

const variableColumns = [
  { key: "name", label: "变量", align: "left" },
  { key: "dtype", label: "类型", align: "left" },
  { key: "status", label: "分箱状态", align: "left" },
  { key: "selected", label: "入模状态", align: "left", badge: true },
  { key: "nBins", label: "分箱数", format: "integer" },
  { key: "iv", label: "IV", format: "decimal" },
  { key: "gini", label: "Gini", format: "decimal" },
  { key: "js", label: "JS", format: "decimal" },
  { key: "qualityScore", label: "质量分", format: "decimal" },
];

function formatValue(value, digits = 4) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : String(value);
}

function formatPercentage(value) {
  if (value === null || value === undefined || value === "") return "—";
  const number = Number(value);
  return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : String(value);
}

function formatCell(value, format) {
  if (format === "percentage") return formatPercentage(value);
  if (format === "integer") {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    return Number.isFinite(number) ? number.toLocaleString("zh-CN") : String(value);
  }
  if (format === "decimal") return formatValue(value);
  return value === null || value === undefined || value === "" ? "—" : String(value);
}

function createMetric(label, value) {
  const item = document.createElement("div");
  item.className = "scorecard-page-metric";
  const name = document.createElement("span");
  name.textContent = label;
  const content = document.createElement("strong");
  content.textContent = String(value ?? "—");
  item.append(name, content);
  return item;
}

function createClassMetric(classes) {
  const item = document.createElement("div");
  item.className = "scorecard-page-metric";
  const name = document.createElement("span");
  name.textContent = "类别标签";
  const values = document.createElement("div");
  values.className = "scorecard-page-class-values";
  if (!Array.isArray(classes) || classes.length === 0) {
    values.textContent = "—";
  } else {
    for (const value of classes) {
      const badge = document.createElement("strong");
      badge.textContent = String(value);
      values.append(badge);
    }
  }
  item.append(name, values);
  return item;
}

function normalizeType(dtype) {
  return { numerical: "数值型", categorical: "类别型" }[dtype]
    || dtype
    || "类型未知";
}

function normalizeBinningStatus(status) {
  const normalized = String(status || "").toUpperCase();
  return {
    OPTIMAL: "最优",
    FEASIBLE: "可行",
    INFEASIBLE: "不可行",
    UNKNOWN: "未知",
    UNBOUNDED: "无界",
    TIME_LIMIT: "达到时限",
    USER_LIMIT: "达到用户限制",
  }[normalized] || status || "—";
}

function formatBoolean(value) {
  return value === null || value === undefined ? "—" : value ? "是" : "否";
}

function calculateTheoreticalScoreRange(details) {
  const selectedVariables = (Array.isArray(details.variables) ? details.variables : [])
    .filter((variable) => variable.selected);
  const ranges = selectedVariables.map((variable) => (
    (Array.isArray(variable.bins) ? variable.bins : [])
      .map((bin) => Number(bin.Points))
      .filter(Number.isFinite)
  ));
  if (ranges.length === 0 || ranges.some((points) => points.length === 0)) {
    return {
      minimum: details.scaling?.minimum_score,
      maximum: details.scaling?.maximum_score,
    };
  }
  const intercept = details.scaling?.intercept_based
    ? Number(details.estimator?.intercept) || 0
    : 0;
  return {
    minimum: ranges.reduce((total, points) => total + Math.min(...points), intercept),
    maximum: ranges.reduce((total, points) => total + Math.max(...points), intercept),
  };
}

function flattenScorecard(details) {
  const rows = [];
  for (const variable of Array.isArray(details.variables) ? details.variables : []) {
    const bins = Array.isArray(variable.bins) && variable.bins.length > 0
      ? variable.bins
      : [{}];
    for (const bin of bins) {
      rows.push({
        variable: variable.name || "未命名变量",
        dtype: normalizeType(variable.dtype),
        selectedValue: Boolean(variable.selected),
        bin: bin.Bin,
        count: bin.Count,
        countRate: bin["Count (%)"],
        nonEvent: bin["Non-event"],
        event: bin.Event,
        eventRate: bin["Event rate"],
        woe: bin.WoE,
        binIv: bin.IV,
        js: bin.JS,
        coefficient: bin.Coefficient,
        points: bin.Points,
      });
    }
  }
  return rows;
}

function flattenVariables(details) {
  return (Array.isArray(details.variables) ? details.variables : []).map((variable) => ({
    name: variable.name || "未命名变量",
    dtype: normalizeType(variable.dtype),
    status: normalizeBinningStatus(variable.status),
    selected: variable.selected ? "已入模变量" : "未入模变量",
    selectedValue: Boolean(variable.selected),
    nBins: variable.n_bins,
    iv: variable.iv,
    gini: variable.gini,
    js: variable.js,
    qualityScore: variable.quality_score,
  }));
}

function escapeCsvCell(value) {
  if (value === null || value === undefined) return "";
  let text = String(value);
  if (typeof value === "string" && /^[=+\-@]/.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function downloadBlob(content, type, filename) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function safeFilename(value) {
  return String(value || "scorecard").replace(/[\\/:*?"<>|\s]+/g, "_");
}

function exportScorecardCsv(version, rows) {
  const metadataColumns = ["模型名称", "版本", "版本 ID"];
  const headers = [...metadataColumns, ...scorecardColumns.map(({ label }) => label)];
  const records = rows.map((row) => [
    version.model_name || "",
    version.version || "",
    version.version_id || "",
    ...scorecardColumns.map(({ key }) => row[key]),
  ]);
  const csv = [headers, ...records]
    .map((record) => record.map(escapeCsvCell).join(","))
    .join("\r\n");
  const filename = `${safeFilename(version.model_name)}_${safeFilename(version.version)}_评分表.csv`;
  downloadBlob(`\uFEFF${csv}`, "text/csv;charset=utf-8", filename);
}

function exportScorecardJson(version, details) {
  const selectedVariables = (Array.isArray(details.variables) ? details.variables : [])
    .filter((variable) => variable.selected);
  const payload = {
    model_id: version.model_id ?? null,
    model_name: version.model_name ?? null,
    version_id: version.version_id ?? null,
    version: version.version ?? null,
    scorecard: {
      scaling: details.scaling,
      estimator: details.estimator,
      selected_variable_count: selectedVariables.length,
      variables: selectedVariables,
    },
  };
  const filename = `${safeFilename(version.model_name)}_${safeFilename(version.version)}_评分表.json`;
  downloadBlob(
    `${JSON.stringify(payload, null, 2)}\n`,
    "application/json;charset=utf-8",
    filename,
  );
}

function createScaleSummary(details) {
  const scaling = details.scaling || {};
  const parameters = scaling.parameters || {};
  const estimator = details.estimator || {};
  const theoreticalRange = calculateTheoreticalScoreRange(details);
  const section = document.createElement("section");
  section.className = "scorecard-page-summary";
  const title = document.createElement("h3");
  title.append(createDetailIcon("prediction"), document.createTextNode("评分表概览"));
  const grid = document.createElement("div");
  grid.className = "scorecard-page-summary-grid";
  const method = { pdo_odds: "PDO 与赔率", min_max: "最小值与最大值" }[scaling.method]
    || scaling.method
    || "—";
  grid.append(
    createMetric("评分刻度", method),
    createMetric("理论最低分", formatValue(theoreticalRange.minimum, 2)),
    createMetric("理论最高分", formatValue(theoreticalRange.maximum, 2)),
    createMetric("变量数", details.variable_count ?? 0),
    createMetric("入模变量数", details.selected_variable_count ?? 0),
    createMetric("估计器", estimator.class_name || "—"),
    createMetric("截距", formatValue(estimator.intercept)),
    createClassMetric(estimator.classes),
  );
  if (scaling.method === "pdo_odds") {
    grid.append(
      createMetric("基准分", parameters.scorecard_points ?? "—"),
      createMetric("PDO", parameters.pdo ?? "—"),
      createMetric("基准赔率", parameters.odds ?? "—"),
    );
  } else if (scaling.method === "min_max") {
    grid.append(
      createMetric("目标最低分", parameters.min ?? "—"),
      createMetric("目标最高分", parameters.max ?? "—"),
    );
  }
  grid.append(
    createMetric("截距计分", formatBoolean(scaling.intercept_based)),
    createMetric("反向评分", formatBoolean(scaling.reverse_scorecard)),
    createMetric("分值取整", formatBoolean(scaling.rounding)),
  );
  section.append(title, grid);
  return section;
}

function createDataTable(rows, columns, className = "") {
  const scroll = document.createElement("div");
  scroll.className = "scorecard-page-table-scroll";
  scroll.tabIndex = 0;
  const table = document.createElement("table");
  table.className = `scorecard-page-binning-table ${className}`.trim();
  const columnGroup = document.createElement("colgroup");
  for (const column of columns) {
    const tableColumn = document.createElement("col");
    tableColumn.className = `scorecard-page-column-${column.key}`;
    columnGroup.append(tableColumn);
  }
  const head = document.createElement("thead");
  const heading = document.createElement("tr");
  for (const column of columns) {
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.textContent = column.label;
    if (column.align === "left") cell.classList.add("is-left");
    heading.append(cell);
  }
  head.append(heading);
  const body = document.createElement("tbody");
  for (const row of rows) {
    const tableRow = document.createElement("tr");
    if (row.selectedValue === false) tableRow.className = "is-unselected";
    for (const column of columns) {
      const cell = document.createElement("td");
      if (column.badge) {
        const badge = document.createElement("span");
        badge.className = `scorecard-page-status ${row.selectedValue ? "is-selected" : "is-unselected"}`;
        badge.textContent = formatCell(row[column.key], column.format);
        cell.append(badge);
      } else {
        cell.textContent = formatCell(row[column.key], column.format);
      }
      if (column.align === "left") cell.classList.add("is-left");
      tableRow.append(cell);
    }
    body.append(tableRow);
  }
  table.append(columnGroup, head, body);
  scroll.append(table);
  return scroll;
}

function createPagination(page, pageSize, totalPages, navigate) {
  const pagination = document.createElement("nav");
  pagination.className = "pagination";
  pagination.setAttribute("aria-label", "评分表分页");

  const size = document.createElement("label");
  size.className = "page-size";
  size.append(document.createTextNode("每页"));
  const sizeSelect = document.createElement("select");
  sizeSelect.setAttribute("aria-label", "每页显示条数");
  for (const value of PAGE_SIZE_OPTIONS) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = value.toLocaleString("zh-CN");
    option.selected = value === pageSize;
    sizeSelect.append(option);
  }
  sizeSelect.addEventListener("change", () => navigate(1, Number(sizeSelect.value)));
  size.append(sizeSelect, document.createTextNode("条"));

  const previous = document.createElement("button");
  previous.type = "button";
  previous.className = "secondary-button";
  previous.textContent = "上一页";
  previous.disabled = page <= 1;
  previous.addEventListener("click", () => navigate(page - 1, pageSize));

  const indicator = document.createElement("span");
  indicator.className = "page-indicator";
  indicator.textContent = `${page} / ${totalPages}`;

  const next = document.createElement("button");
  next.type = "button";
  next.className = "secondary-button";
  next.textContent = "下一页";
  next.disabled = page >= totalPages;
  next.addEventListener("click", () => navigate(page + 1, pageSize));

  pagination.append(size, previous, indicator, next);
  if (totalPages > 1) {
    const jump = document.createElement("form");
    jump.className = "page-jump";
    jump.noValidate = true;
    const input = document.createElement("input");
    input.type = "number";
    input.min = "1";
    input.max = String(totalPages);
    input.placeholder = "页码";
    input.setAttribute("aria-label", `跳转页码，范围 1 至 ${totalPages}`);
    const button = document.createElement("button");
    button.type = "submit";
    button.className = "secondary-button";
    button.textContent = "跳转";
    jump.addEventListener("submit", (event) => {
      event.preventDefault();
      const target = Number(input.value);
      if (!Number.isInteger(target) || target < 1 || target > totalPages) {
        input.setCustomValidity(`请输入 1 至 ${totalPages} 之间的页码`);
        input.reportValidity();
        return;
      }
      input.setCustomValidity("");
      if (target !== page) navigate(target, pageSize);
    });
    input.addEventListener("input", () => input.setCustomValidity(""));
    jump.append(input, button);
    pagination.append(jump);
  }
  return pagination;
}

/**
 * 创建独立的完整评分表页面。
 *
 * 页面按分箱行分页渲染，导出始终包含完整评分表，不受当前页影响。
 *
 * @param {Object.<string, *>} version 模型版本详情
 * @returns {HTMLElement} 评分表页面
 */
export function createScorecardPage(version) {
  const root = document.createElement("div");
  root.className = "scorecard-page";
  const scorecardDetails = version.scorecard?.details;
  if (!scorecardDetails) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "当前版本没有可展示的评分表。";
    root.append(empty);
    return root;
  }

  const allRows = flattenScorecard(scorecardDetails);
  const scoreRows = allRows.filter((row) => row.selectedValue);
  const variableRows = flattenVariables(scorecardDetails);
  root.append(createScaleSummary(scorecardDetails));

  const section = document.createElement("section");
  section.className = "scorecard-page-variables";
  const heading = document.createElement("div");
  heading.className = "scorecard-page-variables-heading";
  const identity = document.createElement("div");
  identity.className = "scorecard-page-heading-identity";
  const title = document.createElement("h3");
  title.append(createDetailIcon("assignment"), document.createTextNode("最终评分表"));
  const resultText = document.createElement("span");
  identity.append(title, resultText);

  const actions = document.createElement("div");
  actions.className = "scorecard-page-actions";
  const search = document.createElement("input");
  search.type = "search";
  search.className = "scorecard-page-search";
  search.placeholder = "搜索变量或分箱";
  search.setAttribute("aria-label", "搜索评分表变量或分箱");
  const exportFormat = document.createElement("select");
  exportFormat.className = "scorecard-page-export-format";
  exportFormat.setAttribute("aria-label", "选择导出格式");
  exportFormat.innerHTML = '<option value="csv">CSV</option><option value="json">JSON</option>';
  const exportButton = document.createElement("button");
  exportButton.type = "button";
  exportButton.className = "scorecard-page-export";
  exportButton.append(createDetailIcon("download"), document.createTextNode("导出评分表"));
  exportButton.addEventListener("click", () => {
    if (exportFormat.value === "json") {
      exportScorecardJson(version, scorecardDetails);
    } else {
      exportScorecardCsv(version, scoreRows);
    }
  });
  let visibleColumnKeys = new Set(defaultScorecardColumnKeys);
  const columnPicker = document.createElement("details");
  columnPicker.className = "scorecard-page-column-picker";
  const closeColumnPickerOnOutside = (event) => {
    if (!columnPicker.contains(event.target)) columnPicker.open = false;
  };
  const closeColumnPickerOnEscape = (event) => {
    if (event.key !== "Escape") return;
    columnPicker.open = false;
    columnPicker.querySelector("summary")?.focus();
  };
  columnPicker.addEventListener("toggle", () => {
    const action = columnPicker.open ? "addEventListener" : "removeEventListener";
    document[action]("pointerdown", closeColumnPickerOnOutside, true);
    document[action]("keydown", closeColumnPickerOnEscape);
  });
  const columnPickerSummary = document.createElement("summary");
  const updateColumnPickerSummary = () => {
    columnPickerSummary.textContent = `列设置 ${visibleColumnKeys.size}/${scorecardColumns.length}`;
  };
  updateColumnPickerSummary();
  const columnPickerPanel = document.createElement("div");
  columnPickerPanel.className = "scorecard-page-column-panel";
  const columnPickerActions = document.createElement("div");
  columnPickerActions.className = "scorecard-page-column-actions";
  const columnPickerOptions = document.createElement("div");
  columnPickerOptions.className = "scorecard-page-column-options";
  const columnCheckboxes = new Map();
  const syncColumnSelection = () => {
    for (const [key, checkbox] of columnCheckboxes) {
      checkbox.checked = visibleColumnKeys.has(key);
    }
    updateColumnPickerSummary();
    render();
  };
  const selectAllColumns = document.createElement("button");
  selectAllColumns.type = "button";
  selectAllColumns.textContent = "全选";
  selectAllColumns.addEventListener("click", () => {
    visibleColumnKeys = new Set(defaultScorecardColumnKeys);
    syncColumnSelection();
  });
  const invertColumns = document.createElement("button");
  invertColumns.type = "button";
  invertColumns.textContent = "反选";
  invertColumns.addEventListener("click", () => {
    visibleColumnKeys = new Set(scorecardColumns
      .filter(({ key }) => (
        requiredScorecardColumnKeys.has(key) || !visibleColumnKeys.has(key)
      ))
      .map(({ key }) => key));
    syncColumnSelection();
  });
  columnPickerActions.append(selectAllColumns, invertColumns);
  for (const column of scorecardColumns) {
    const label = document.createElement("label");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = column.key;
    checkbox.checked = visibleColumnKeys.has(column.key);
    checkbox.disabled = requiredScorecardColumnKeys.has(column.key);
    columnCheckboxes.set(column.key, checkbox);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) visibleColumnKeys.add(column.key);
      else visibleColumnKeys.delete(column.key);
      updateColumnPickerSummary();
      render();
    });
    label.append(checkbox, document.createTextNode(column.label));
    columnPickerOptions.append(label);
  }
  columnPickerPanel.append(columnPickerActions, columnPickerOptions);
  columnPicker.append(columnPickerSummary, columnPickerPanel);
  actions.append(search, columnPicker, exportFormat, exportButton);
  heading.append(identity, actions);

  const tableHost = document.createElement("div");
  tableHost.className = "scorecard-page-table-host";
  const paginationHost = document.createElement("div");
  section.append(heading, tableHost, paginationHost);
  root.append(section);

  let query = "";
  let page = 1;
  let pageSize = DEFAULT_PAGE_SIZE;
  const render = () => {
    const normalized = query.toLowerCase();
    const filtered = scoreRows.filter((row) => (
        String(row.variable).toLowerCase().includes(normalized)
        || String(row.bin ?? "").toLowerCase().includes(normalized)
      ));
    const variableCount = new Set(filtered.map((row) => row.variable)).size;
    const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
    page = Math.min(page, totalPages);
    const start = (page - 1) * pageSize;
    const pageRows = filtered.slice(start, start + pageSize);
    resultText.textContent = `共 ${variableCount} 个入模变量 · 评分规则 ${filtered.length} 条`;
    tableHost.replaceChildren();
    if (pageRows.length > 0) {
      const visibleColumns = scorecardColumns.filter((column) => (
        visibleColumnKeys.has(column.key)
      ));
      tableHost.append(createDataTable(
        pageRows,
        visibleColumns,
        "scorecard-page-complete-table",
      ));
    } else {
      const empty = document.createElement("p");
      empty.className = "scorecard-page-empty";
      empty.textContent = "没有符合条件的评分规则";
      tableHost.append(empty);
    }
    paginationHost.replaceChildren(createPagination(
      page,
      pageSize,
      totalPages,
      (targetPage, targetPageSize) => {
        page = targetPage;
        pageSize = targetPageSize;
        render();
      },
    ));
  };
  search.addEventListener("input", () => {
    query = search.value.trim();
    page = 1;
    render();
  });
  render();

  const diagnosticSection = document.createElement("section");
  diagnosticSection.className = "scorecard-page-variables scorecard-page-diagnostics";
  const diagnosticHeading = document.createElement("div");
  diagnosticHeading.className = "scorecard-page-variables-heading";
  const diagnosticIdentity = document.createElement("div");
  diagnosticIdentity.className = "scorecard-page-heading-identity";
  const diagnosticTitle = document.createElement("h3");
  diagnosticTitle.append(
    createDetailIcon("prediction"),
    document.createTextNode("变量筛选结果"),
  );
  const diagnosticResult = document.createElement("span");
  diagnosticIdentity.append(diagnosticTitle, diagnosticResult);
  const diagnosticActions = document.createElement("div");
  diagnosticActions.className = "scorecard-page-actions";
  const variableSearch = document.createElement("input");
  variableSearch.type = "search";
  variableSearch.className = "scorecard-page-search";
  variableSearch.placeholder = "搜索候选变量";
  variableSearch.setAttribute("aria-label", "搜索候选变量");
  const variableFilter = document.createElement("select");
  variableFilter.className = "scorecard-page-filter";
  variableFilter.setAttribute("aria-label", "筛选变量入模状态");
  variableFilter.innerHTML = '<option value="all">全部候选变量</option><option value="selected">已入模变量</option><option value="unselected">未入模变量</option>';
  diagnosticActions.append(variableSearch, variableFilter);
  diagnosticHeading.append(diagnosticIdentity, diagnosticActions);
  const diagnosticHost = document.createElement("div");
  diagnosticHost.className = "scorecard-page-table-host";
  diagnosticSection.append(diagnosticHeading, diagnosticHost);
  root.append(diagnosticSection);

  const renderDiagnostics = () => {
    const normalized = variableSearch.value.trim().toLowerCase();
    const filter = variableFilter.value;
    const filtered = variableRows.filter((row) => {
      const matchesStatus = filter === "all"
        || (filter === "selected" && row.selectedValue)
        || (filter === "unselected" && !row.selectedValue);
      return matchesStatus && row.name.toLowerCase().includes(normalized);
    });
    const selectedCount = filtered.filter((row) => row.selectedValue).length;
    const unselectedCount = filtered.length - selectedCount;
    diagnosticResult.textContent = `共 ${filtered.length} 个候选变量 · 已入模 ${selectedCount} · 未入模 ${unselectedCount}`;
    diagnosticHost.replaceChildren();
    if (filtered.length > 0) {
      diagnosticHost.append(createDataTable(
        filtered,
        variableColumns,
        "scorecard-page-variable-table",
      ));
    } else {
      const empty = document.createElement("p");
      empty.className = "scorecard-page-empty";
      empty.textContent = "没有符合条件的候选变量";
      diagnosticHost.append(empty);
    }
  };
  variableSearch.addEventListener("input", renderDiagnostics);
  variableFilter.addEventListener("change", renderDiagnostics);
  renderDiagnostics();
  return root;
}
