"use strict";

const modelTypeLabels = {
  logistic_regression: "逻辑回归",
  decision_tree: "决策树",
  random_forest: "随机森林",
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
};

const taskTypeLabels = {
  scoring: "评分",
  classification: "分类",
  regression: "回归",
};

/**
 * 格式化模型类型枚举。
 *
 * @param {unknown} value 模型类型
 * @returns {string} 中文展示名称
 */
export function formatModelType(value) {
  if (value === null || value === undefined || value === "") return "—";
  const key = String(value).toLowerCase();
  return modelTypeLabels[key] || String(value);
}

/**
 * 格式化任务类型枚举。
 *
 * @param {unknown} value 任务类型
 * @returns {string} 中文展示名称
 */
export function formatTaskType(value) {
  if (value === null || value === undefined || value === "") return "—";
  const key = String(value).toLowerCase();
  return taskTypeLabels[key] || String(value);
}

/**
 * 格式化导航栏中的资源数量。
 *
 * @param {unknown} value 原始数量
 * @returns {string} 紧凑数量文本
 */
export function formatNavigationCount(value) {
  if (!Number.isInteger(value)) return "—";
  if (value < 1000) return String(value);

  const units = ["k", "M", "B", "T"];
  let compactValue = value / 1000;
  let unitIndex = 0;

  while (
    compactValue >= 999.95
    && unitIndex < units.length - 1
  ) {
    compactValue /= 1000;
    unitIndex += 1;
  }

  if (
    unitIndex === units.length - 1
    && compactValue > 999
  ) return "999T+";

  const compact = compactValue.toFixed(1).replace(/\.0$/, "");

  return `${compact}${units[unitIndex]}`;
}

/**
 * 格式化毫秒数值。
 *
 * @param {unknown} value 原始时长
 * @returns {string} 保留两位小数的时长文本
 */
export function formatDuration(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number);
}

/**
 * 格式化可为空的毫秒时长，并使用中文单位。
 *
 * @param {unknown} value 原始时长
 * @returns {string} 带中文毫秒单位的时长文本
 */
export function formatOptionalDuration(value) {
  if (value === null || value === undefined) return "—";
  const milliseconds = Number(value);
  if (!Number.isFinite(milliseconds)) return "—";
  return `${formatDuration(milliseconds)} 毫秒`;
}

/**
 * 格式化整数。
 *
 * @param {unknown} value 原始数值
 * @returns {string} 本地化整数文本
 */
export function formatInteger(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 0,
  }).format(number);
}

/**
 * 格式化可为空的百分比。
 *
 * @param {unknown} value 原始比例
 * @returns {string} 百分比文本
 */
export function formatOptionalPercentage(value) {
  if (value === null || value === undefined) return "—";
  return formatPercentage(value);
}

/**
 * 格式化紧凑百分比。
 *
 * @param {unknown} value 原始比例
 * @returns {string} 保留一位小数的百分比文本
 */
export function formatCompactPercentage(value) {
  if (value === null || value === undefined) return "—";
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(number);
}

/**
 * 格式化带正负号的百分比。
 *
 * @param {unknown} value 原始比例
 * @returns {string} 带方向符号的百分比文本
 */
export function formatSignedPercentage(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  const formatted = new Intl.NumberFormat("zh-CN", {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(Math.abs(number));

  if (number > 0) return `+${formatted}`;
  if (number < 0) return `-${formatted}`;
  return formatted;
}

/**
 * 格式化标准百分比。
 *
 * @param {unknown} value 原始比例
 * @returns {string} 保留两位小数的百分比文本
 */
export function formatPercentage(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    style: "percent",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(number);
}

/**
 * 格式化概率值。
 *
 * @param {unknown} value 原始概率
 * @returns {string} 百分比形式的概率文本
 */
export function formatProbability(value) {
  return formatPercentage(value);
}

/**
 * 格式化评分值。
 *
 * @param {unknown} value 原始评分
 * @returns {string} 不使用千位分隔符的评分文本
 */
export function formatScore(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "—";
  return new Intl.NumberFormat("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
    useGrouping: false,
  }).format(number);
}

/**
 * 格式化时间。
 *
 * @param {unknown} value 日期时间值
 * @returns {string} 本地化日期时间文本
 */
export function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(date);
}

/**
 * 获取状态对应的视觉色调。
 *
 * @param {unknown} value 状态值
 * @returns {string} 状态色调名称
 */
export function statusTone(value) {
  const status = String(value || "").toLowerCase();
  if (["failed", "error", "timeout", "lost", "unhealthy", "rejected", "cancelled", "disabled", "archived", "stopped"].includes(status)) return "danger";
  if (["inactive", "pending", "queued", "retrying", "paused", "starting", "stopping", "loading", "unloading", "unloaded"].includes(status)) return "warning";
  if (["healthy", "running"].includes(status)) return "success";
  if (["draft", "received"].includes(status)) return "info";
  if (status === "deprecated") return "deprecated";
  return "";
}
