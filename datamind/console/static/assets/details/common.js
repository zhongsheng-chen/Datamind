"use strict";

const svgNamespace = "http://www.w3.org/2000/svg";

const iconPaths = {
  activate: ["m9 7 8 5-8 5V7Z"],
  activity: ["M4 12h3l2-5 4 10 2-5h5"],
  add: ["M12 5v14", "M5 12h14"],
  arrow: ["m9 6 6 6-6 6"],
  assignment: ["M6 4h12v16H6Z", "M9 8h6", "M9 12h6", "M9 16h3"],
  artifact: ["M4 7h16v12H4Z", "m8 3 4 4H8l4-4Z", "M8 12h8", "M8 16h5"],
  audit: [
    "M9 5H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-3",
    "M9 3h6v4H9Z",
    "m8 14 2.5 2.5L16 11",
  ],
  braces: ["M8 3H6a2 2 0 0 0-2 2v5a2 2 0 0 1-2 2 2 2 0 0 1 2 2v5a2 2 0 0 0 2 2h2", "M16 3h2a2 2 0 0 1 2 2v5a2 2 0 0 0 2 2 2 2 0 0 0-2 2v5a2 2 0 0 1-2 2h-2"],
  change: [
    "M6 3h9l3 3v15H6Z",
    "M14 3v4h4",
    "M9 11h6",
    "M12 8v6",
    "M9 17h6",
  ],
  check: ["m5 12.5 4.2 4.2L19 7"],
  close: ["M6 6l12 12", "M18 6 6 18"],
  complete: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "m8 12 3 3 5-6"],
  copy: ["M9 9h10v10H9Z", "M5 5h10v4", "M5 5v10h4"],
  config: [
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
    "M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.51a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z",
  ],
  decision: [
    "M5 12h5",
    "M10 12c3 0 3-5 6-5h3",
    "M10 12c3 0 3 5 6 5h3",
    "M5 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
    "M19 9a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
    "M19 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  ],
  deployment: [
    "M12 3v10",
    "m8 9 4 4 4-4",
    "M4 16h16v5H4Z",
    "M8 18.5h.01",
    "M11 18.5h5",
  ],
  deactivate: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "m7.5 16.5 9-9"],
  delete: ["M4 6h16", "m9 6 1-2h4l1 2", "M19 6l-1 14H6L5 6", "M10 10v6", "M14 10v6"],
  disable: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "m7.5 16.5 9-9"],
  deploy: ["m9 7 8 5-8 5V7Z"],
  edit: ["M4 20h4L19 9l-4-4L4 16v4Z", "m13.5 6.5 4 4"],
  effective: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "m8 12 3 3 5-6"],
  enable: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "m8 12 3 3 5-6"],
  error: [
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
    "M12 7v6",
    "M12 17h.01",
  ],
  execution: [
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
    "m10 8 6 4-6 4V8Z",
  ],
  experiment: ["M9 3h6", "M10 3v6l-5 9a2 2 0 0 0 1.8 3h10.4a2 2 0 0 0 1.8-3l-5-9V3", "M8 15h8"],
  external: ["M14 4h6v6", "m20 4-9 9", "M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6"],
  help: [
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
    "M9.1 9a3 3 0 1 1 5.8 1c0 2-2.9 2.2-2.9 4",
    "M12 17h.01",
  ],
  info: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "M12 10v6", "M12 7h.01"],
  link: ["M10 13a5 5 0 0 0 7.07.07l2-2a5 5 0 0 0-7.07-7.07l-1.15 1.15", "M14 11a5 5 0 0 0-7.07-.07l-2 2A5 5 0 0 0 12 20l1.15-1.15"],
  model: ["m12 3 8 4.5-8 4.5-8-4.5L12 3Z", "m4 7.5 8 4.5v9l-8-4.5v-9Z", "m20 7.5-8 4.5v9l8-4.5v-9Z"],
  monitor: ["M4 4h16v13H4Z", "M8 21h8", "M12 17v4", "M7 11h2l2-3 2 6 2-3h2"],
  metadata: [
    "M5 6h.01",
    "M9 6h10",
    "M5 12h.01",
    "M9 12h10",
    "M5 18h.01",
    "M9 18h10",
  ],
  payload: [
    "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z",
    "M14 3v6h6",
    "M8 15h8",
    "m13 12 3 3-3 3",
  ],
  parallel: [
    "M4 12h5",
    "M9 6v12",
    "M9 6h6",
    "M9 12h6",
    "M9 18h6",
    "M19 8a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
    "M19 14a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
    "M19 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  ],
  prediction: [
    "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z",
    "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Z",
    "M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2Z",
  ],
  request: [
    "M4 7h12",
    "m13 4 3 3-3 3",
    "M20 17H8",
    "m11 14-3 3 3 3",
  ],
  response: [
    "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z",
    "M14 3v6h6",
    "M8 15h8",
    "m11 12-3 3 3 3",
  ],
  release: ["M21 3 10 14", "m21 3-7 18-4-7-7-4 18-7Z"],
  reload: ["M20 11a8 8 0 1 0-2.34 5.66", "M20 4v7h-7"],
  role: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M4 21a8 8 0 0 1 16 0"],
  routing: ["M6 5a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z", "M18 13a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z", "M18 23a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z", "M6 5v11a5 5 0 0 0 5 5h5", "M6 9h7a5 5 0 0 1 5 5"],
  rules: ["M4 4h16v16H4Z", "M8 8h8", "M8 12h5", "M8 16h7"],
  upload: [
    "M16 16l-4-4-4 4",
    "M12 12v9",
    "M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3",
  ],
  download: ["M12 3v12", "m7 10 5 5 5-5", "M4 16v5h16v-5"],
  pause: ["M9 7v10", "M15 7v10"],
  runtime: ["M3 13h4l2.2-7 4.3 13 3-9 2.2 5H21"],
  start: ["m9 7 8 5-8 5V7Z"],
  stop: ["M6 6h12v12H6Z"],
  time: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "M12 7v5l3 2"],
  traffic: ["M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z", "m8 16 8-8", "M8.5 8.5h.01", "M15.5 15.5h.01"],
  user: ["M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z", "M4 21a8 8 0 0 1 16 0"],
  variant: ["M6 4v16", "M18 4v6a4 4 0 0 1-4 4H6", "m14 4 4 4 4-4"],
  version: [
    "m12 3 8 4.5-8 4.5-8-4.5L12 3Z",
    "m4 12 8 4.5 8-4.5",
    "m4 16.5 8 4.5 8-4.5",
  ],
  versions: ["M7 3h10v5H7Z", "M5 10h14v5H5Z", "M7 17h10v4H7Z"],
  view: ["M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12Z", "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"],
};

/**
 * 创建详情页内联图标。
 *
 * @param {string} kind 图标类型
 * @param {string} [className=""] 附加样式类名
 * @returns {HTMLSpanElement} 图标容器
 */
export function createDetailIcon(kind, className = "") {
  const container = document.createElement("span");
  container.className = ["registry-detail-icon", className]
    .filter(Boolean)
    .join(" ");
  container.setAttribute("aria-hidden", "true");
  const svg = document.createElementNS(svgNamespace, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  for (const data of iconPaths[kind] || iconPaths.info) {
    const path = document.createElementNS(svgNamespace, "path");
    path.setAttribute("d", data);
    svg.append(path);
  }
  container.append(svg);
  return container;
}

/**
 * 创建详情摘要徽标。
 *
 * @param {unknown} value 徽标内容
 * @param {string} [tone=""] 徽标色调
 * @returns {HTMLSpanElement} 徽标元素
 */
export function createDetailBadge(value, tone = "") {
  const badge = document.createElement("span");
  badge.className = ["registry-summary-badge", tone]
    .filter(Boolean)
    .join(" ");
  badge.textContent = value ?? "—";
  return badge;
}

/**
 * 将徽标的本地化文案用于详情字段的纯文本展示。
 *
 * @param {unknown} value 字段值
 * @param {(value: unknown, ...args: unknown[]) => HTMLElement} createBadge 徽标工厂
 * @param {...unknown} args 徽标工厂的附加参数
 * @returns {string} 徽标的本地化文本
 */
export function formatBadgeValue(value, createBadge, ...args) {
  return createBadge(value, ...args).textContent || "—";
}

/**
 * 将状态值格式化为用于基本信息字段的纯文本。
 *
 * @param {unknown} value 状态值
 * @param {(value: unknown, context?: string) => HTMLElement} createStatusBadge 状态徽标工厂
 * @param {string} [context="default"] 状态上下文
 * @returns {string} 本地化状态文本
 */
export function formatStatusValue(
  value,
  createStatusBadge,
  context = "default",
) {
  return formatBadgeValue(value, createStatusBadge, context);
}

/**
 * 向详情定义列表追加信息项。
 *
 * @param {HTMLElement} container 信息项容器
 * @param {string} label 信息项名称
 * @param {unknown} value 信息项内容
 * @param {string} [className=""] 内容样式类名
 * @returns {void} 无返回值
 */
export function appendDetailField(container, label, value, className = "") {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = label;
  const detail = document.createElement("dd");
  if (value instanceof Node) {
    detail.append(value);
  } else {
    const hasValue = value !== null && value !== undefined;
    detail.textContent = hasValue ? String(value) : "—";
    if (className && hasValue) detail.className = className;
  }
  wrapper.append(term, detail);
  container.append(wrapper);
}

/**
 * 创建详情抽屉骨架。
 *
 * @param {string} title 抽屉标题
 * @param {string} [className=""] 附加样式类名
 * @returns {{dialog: HTMLDialogElement, body: HTMLDivElement}} 抽屉及内容容器
 */
export function createDetailDrawer(title, className = "") {
  const dialog = document.createElement("dialog");
  dialog.className = ["request-drawer", "registry-detail-drawer", className]
    .filter(Boolean)
    .join(" ");
  const header = document.createElement("header");
  const heading = document.createElement("h3");
  heading.textContent = title;
  const close = document.createElement("button");
  close.type = "button";
  close.className = "registry-drawer-close";
  close.setAttribute("aria-label", `关闭${title}`);
  close.append(createDetailIcon("close"));
  const dismiss = () => {
    dialog.dataset.userDismissed = "true";
    clearDetailRoute(
      dialog.dataset.detailSection,
      dialog.dataset.detailId,
    );
    dialog.close();
  };
  close.addEventListener("click", dismiss);
  header.append(heading, close);
  const body = document.createElement("div");
  body.className = "request-drawer-body registry-detail-body";
  dialog.append(header, body);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dismiss();
  });
  dialog.addEventListener("cancel", () => {
    dialog.dataset.userDismissed = "true";
  });
  dialog.addEventListener("close", () => dialog.remove());
  return { dialog, body };
}

/**
 * 创建带复制能力的 JSON 代码区域。
 *
 * @param {unknown} value JSON 数据
 * @param {string} title 数据标题
 * @returns {HTMLElement} JSON 代码区域
 */
export function createJsonCode(value, title) {
  const content = document.createElement("pre");
  const code = document.createElement("div");
  code.className = "registry-json-code";
  const serialized = value === null || value === undefined
    ? "暂无数据"
    : JSON.stringify(value, null, 2);
  content.textContent = serialized;
  if (value === null || value === undefined) {
    code.append(content);
    return code;
  }

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "registry-json-copy";
  copy.setAttribute("aria-label", `复制${title}`);
  copy.title = `复制${title}`;
  copy.append(createDetailIcon("copy"));
  let resetTimer = null;
  copy.addEventListener("click", async () => {
    window.clearTimeout(resetTimer);
    copy.classList.remove("copied", "failed");
    try {
      await navigator.clipboard.writeText(serialized);
      copy.classList.add("copied");
      copy.replaceChildren(createDetailIcon("check"));
      copy.setAttribute("aria-label", `${title}已复制`);
      copy.title = "已复制";
    } catch {
      copy.classList.add("failed");
      copy.replaceChildren(createDetailIcon("error"));
      copy.setAttribute("aria-label", `${title}复制失败`);
      copy.title = "复制失败";
    }
    resetTimer = window.setTimeout(() => {
      copy.classList.remove("copied", "failed");
      copy.replaceChildren(createDetailIcon("copy"));
      copy.setAttribute("aria-label", `复制${title}`);
      copy.title = `复制${title}`;
    }, 1800);
  });
  code.append(content, copy);
  return code;
}

/**
 * 按接口字段和模型变量顺序整理预测详情，保留扩展字段及原始数据。
 *
 * @param {unknown} value 预测结果
 * @param {string[]} [featureNames=[]] 模型版本的变量顺序
 * @returns {unknown} 用于展示和复制的预测结果
 */
export function formatPredictionDetails(value, featureNames = []) {
  const isObject = (item) => item !== null
    && typeof item === "object" && !Array.isArray(item);
  if (!isObject(value)) return value;

  const orderFields = (item, fields) => Object.fromEntries(
    [...new Set([...fields, ...Object.keys(item)])]
      .filter((key) => Object.hasOwn(item, key))
      .map((key) => [key, item[key]]),
  );
  const result = orderFields(value, [
    "success", "error", "error_type", "score", "probability", "prediction",
    "decision", "threshold", "score_intercept", "features", "request_id",
  ]);
  if (isObject(result.features)) {
    result.features = Object.fromEntries(
      Object.entries(orderFields(result.features, featureNames)).map(([name, feature]) => [
        name,
        isObject(feature)
          ? orderFields(feature, ["value", "bin", "woe", "points"])
          : feature,
      ]),
    );
  }
  return result;
}

/**
 * 打开统一的 JSON 查看对话框。
 *
 * @param {string} title 对话框标题
 * @param {unknown} value JSON 数据
 * @returns {void}
 */
export function showJsonDialog(title, value) {
  const dialog = document.createElement("dialog");
  dialog.className = "registry-json-dialog";
  const header = document.createElement("header");
  const heading = document.createElement("h3");
  heading.textContent = title;
  const close = document.createElement("button");
  close.type = "button";
  close.setAttribute("aria-label", `关闭${title}`);
  close.textContent = "×";
  close.addEventListener("click", () => dialog.close());
  header.append(heading, close);
  dialog.append(header, createJsonCode(value ?? {}, title));
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
}

/**
 * 创建详情身份摘要。
 *
 * @param {Object} options 摘要配置
 * @param {string} options.icon 资源图标类型
 * @param {string | null | undefined} options.title 主标题
 * @param {string | null | undefined} options.subtitle 副标题
 * @param {unknown} options.status 状态值
 * @param {HTMLElement[]} [options.badges=[]] 补充徽标
 * @param {(status: unknown) => HTMLElement} options.createStatusBadge 状态徽标创建器
 * @returns {HTMLElement} 身份摘要区块
 */
export function createDetailSummary({
  icon,
  title,
  subtitle,
  status,
  badges = [],
  createStatusBadge,
}) {
  const summary = document.createElement("section");
  summary.className = "registry-detail-summary";
  const row = document.createElement("div");
  row.className = "registry-summary-heading";
  const content = document.createElement("div");
  content.className = "registry-summary-content";
  const identity = document.createElement("div");
  const heading = document.createElement("h4");
  heading.textContent = title || "—";
  const secondary = document.createElement("p");
  secondary.textContent = subtitle || "—";
  identity.append(heading, secondary);
  const badgeRow = document.createElement("div");
  badgeRow.className = "registry-summary-badges";
  badgeRow.append(...badges.filter(Boolean));
  content.append(identity, badgeRow);
  row.append(
    createDetailIcon(icon, "registry-summary-icon"),
    content,
    createStatusBadge(status),
  );
  summary.append(row);
  return summary;
}

/**
 * 创建结构化详情区块。
 *
 * @param {string} title 区块标题
 * @param {Array<[string, unknown, string?]>} fields 信息项配置
 * @param {HTMLDialogElement} dialog 所属抽屉
 * @param {string} iconKind 区块图标类型
 * @param {(container: HTMLElement, label: string, value: unknown, kind?: string) => void} appendRequestDetail 信息项渲染器
 * @returns {HTMLElement} 详情区块
 */
export function createDetailSection(
  title,
  fields,
  dialog,
  iconKind,
  appendRequestDetail,
) {
  const section = document.createElement("section");
  section.className = "registry-detail-section";
  const heading = document.createElement("h4");
  heading.append(
    createDetailIcon(iconKind, "registry-section-icon"),
    document.createTextNode(title),
  );
  const details = document.createElement("dl");
  details.className = "registry-detail-list";
  for (const [label, value, kind] of fields) {
    appendRequestDetail(
      details,
      label,
      typeof value === "function" ? value(dialog) : value,
      kind,
    );
  }
  section.append(heading, details);
  return section;
}

/**
 * 创建 JSON 数据详情区块。
 *
 * @param {string} title 区块标题
 * @param {unknown} value JSON 数据
 * @param {string} [iconKind="braces"] 区块图标类型
 * @returns {HTMLElement} JSON 详情区块
 */
export function createJsonDetailSection(
  title,
  value,
  iconKind = "braces",
) {
  const section = document.createElement("section");
  section.className = "registry-detail-section registry-json-section";
  const heading = document.createElement("h4");
  heading.append(
    createDetailIcon(iconKind, "registry-section-icon"),
    document.createTextNode(title),
  );
  section.append(heading, createJsonCode(value, title));
  return section;
}

/**
 * 创建错误信息详情区块。
 *
 * @param {unknown} error 错误信息
 * @returns {HTMLElement} 错误详情区块
 */
export function createErrorDetailSection(error) {
  const section = document.createElement("section");
  section.className = "registry-detail-section registry-error-section";
  const heading = document.createElement("h4");
  heading.append(
    createDetailIcon("error", "registry-section-icon"),
    document.createTextNode("错误信息"),
  );
  const message = document.createElement("p");
  message.textContent = String(error);
  section.append(heading, message);
  return section;
}

/**
 * 创建详情操作按钮。
 *
 * @param {string} label 按钮文本
 * @param {string} iconKind 图标类型
 * @param {string} [tone=""] 按钮色调
 * @returns {HTMLButtonElement} 操作按钮
 */
export function createDetailAction(label, iconKind, tone = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = ["registry-detail-action", tone]
    .filter(Boolean)
    .join(" ");
  button.append(
    createDetailIcon(iconKind),
    document.createTextNode(label),
  );
  return button;
}

/**
 * 向详情抽屉追加底部操作区。
 *
 * @param {HTMLDialogElement} dialog 详情抽屉
 * @param {Array<HTMLElement | null | undefined>} buttons 操作按钮
 * @returns {void} 无返回值
 */
export function appendDetailFooter(dialog, buttons) {
  const visible = buttons.filter((button) => button instanceof HTMLElement);
  if (visible.length === 0) return;
  const footer = document.createElement("footer");
  footer.className = "registry-detail-actions";
  footer.append(...visible);
  dialog.append(footer);
}

/**
 * 读取当前详情路由。
 *
 * @returns {{section: string, id: string} | null} 详情路由
 */
export function getDetailRoute() {
  const [, query = ""] = window.location.hash.slice(1).split("?", 2);
  const value = new URLSearchParams(query).get("detail") || "";
  const separator = value.indexOf(":");

  if (separator <= 0 || separator === value.length - 1) return null;

  return {
    section: value.slice(0, separator),
    id: value.slice(separator + 1),
  };
}

/**
 * 在当前地址中同步清除指定详情路由。
 *
 * @param {string | undefined} section 详情资源分区
 * @param {string | undefined} id 详情记录标识
 * @returns {boolean} 是否清除了当前详情路由
 */
function clearDetailRoute(section, id) {
  const activeRoute = getDetailRoute();
  if (
    !section
    || !id
    || activeRoute?.section !== section
    || activeRoute.id !== id
  ) return false;

  const [path, query = ""] = window.location.hash.slice(1).split("?", 2);
  const parameters = new URLSearchParams(query);
  parameters.delete("detail");
  const normalizedQuery = parameters.toString();
  const nextState = { ...(window.history.state || {}) };
  delete nextState.detailRoute;
  window.history.replaceState(
    Object.keys(nextState).length > 0 ? nextState : null,
    "",
    `#${path}${normalizedQuery ? `?${normalizedQuery}` : ""}`,
  );
  return true;
}

/**
 * 关闭与当前路由不一致的详情抽屉。
 *
 * @param {{section: string, id: string} | null} route 当前详情路由
 * @returns {boolean} 是否已有匹配的详情抽屉
 */
export function synchronizeDetailDrawer(route) {
  const opened = [...document.querySelectorAll(
    "dialog.registry-detail-drawer[data-detail-section]",
  )].filter((dialog) => dialog instanceof HTMLDialogElement);
  let matched = false;

  for (const dialog of opened) {
    const isMatch = (
      !matched
      && dialog.open
      && route !== null
      && dialog.dataset.detailSection === route.section
      && dialog.dataset.detailId === route.id
    );
    if (isMatch) {
      matched = true;
      continue;
    }

    dialog.dataset.routeSync = "true";
    if (dialog.open) dialog.close();
    else dialog.remove();
  }
  return matched;
}

/**
 * 挂载并打开详情抽屉。
 *
 * @param {HTMLDialogElement} dialog 详情抽屉
 * @param {{section: string, id: string | number}} route 详情路由
 * @returns {void} 无返回值
 */
export function mountDetailDrawer(dialog, route) {
  const section = String(route.section);
  const id = String(route.id);
  const routeKey = `${section}:${id}`;
  const currentRoute = getDetailRoute();
  dialog.dataset.detailSection = section;
  dialog.dataset.detailId = id;

  for (const opened of document.querySelectorAll(
    "dialog.registry-detail-drawer[data-detail-section]",
  )) {
    if (!(opened instanceof HTMLDialogElement) || opened === dialog) continue;
    opened.dataset.routeSync = "true";
    if (opened.open) opened.close();
    else opened.remove();
  }

  if (
    currentRoute?.section !== section
    || currentRoute.id !== id
  ) {
    const [path, query = ""] = window.location.hash.slice(1).split("?", 2);
    const parameters = new URLSearchParams(query);
    parameters.set("detail", routeKey);
    window.history.pushState(
      { ...(window.history.state || {}), detailRoute: routeKey },
      "",
      `#${path || section}?${parameters.toString()}`,
    );
  }

  dialog.addEventListener("close", () => {
    const clearActiveRoute = () => {
      if (dialog.dataset.routeSync === "true") return;
      clearDetailRoute(section, id);
    };

    if (dialog.dataset.userDismissed === "true") {
      clearActiveRoute();
      return;
    }
    window.queueMicrotask(clearActiveRoute);
  });
  document.body.append(dialog);
  dialog.showModal();
}
