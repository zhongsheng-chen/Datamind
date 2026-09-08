"use strict";

import { createDetailIcon } from "./details/common.js";

/**
 * 创建通用展示组件控制器。
 *
 * 控制器集中提供表格单元格、状态徽标和资源跳转组件。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   createCopyableNavigationLink: (value: string | null, navigate: (() => void) | null, label?: string) => string | HTMLElement,
 *   createCopyableSectionNavigationLink: (value: string | null, section: string, dialog: HTMLDialogElement, label?: string) => string | HTMLElement,
 *   createDataCell: (value: unknown, kind?: string, record?: Object | null) => HTMLTableCellElement,
 *   createDeploymentRoleBadge: (value: unknown) => HTMLSpanElement,
 *   createExecutionTypeBadge: (value: unknown) => HTMLSpanElement,
 *   createSectionNavigationLink: (value: string | null, section: string, dialog: HTMLDialogElement, label?: string | null) => string | null | HTMLButtonElement,
 *   createSortHeader: (column: ColumnConfig, activeSort: string, activeOrder: string, navigate: (sortBy: string, sortOrder: string) => void) => HTMLTableCellElement,
 *   createStatusBadge: (value: unknown) => HTMLSpanElement
 * }} 通用展示组件入口
 */
export function createPresentationController({
  formatDuration,
  formatInteger,
  formatPercentage,
  formatProbability,
  formatScore,
  formatTime,
  maxSortFields,
  navigateToExperimentVariants,
  navigateToModelVersions,
  navigateToSection,
  parseSortRules,
  sectionIdFields,
  state,
  statusTone,
  toast,
}) {
  /**
   * 创建支持多字段排序的表头。
   *
   * @param {ColumnConfig} column 列配置
   * @param {string} activeSort 当前排序字段
   * @param {string} activeOrder 当前排序方向
   * @param {(sortBy: string, sortOrder: string) => void} navigate 排序导航方法
   * @returns {HTMLTableCellElement} 排序表头单元格
   */
  function createSortHeader(column, activeSort, activeOrder, navigate) {
    const [field, label, , configuredSort] = column;
    const sortBy = configuredSort || field;
    const rules = parseSortRules(activeSort, activeOrder);
    const selectedIndex = rules.findIndex((rule) => rule.field === sortBy);
    const selected = selectedIndex >= 0;
    const selectedOrder = selected ? rules[selectedIndex].order : "asc";
    const th = document.createElement("th");
    th.scope = "col";
    th.setAttribute(
      "aria-sort",
      selected
        ? (selectedIndex === 0
          ? (selectedOrder === "asc" ? "ascending" : "descending")
          : "other")
        : "none",
    );
  
    const button = document.createElement("button");
    button.type = "button";
    button.className = `sort-button${selected ? " active" : ""}`;
    button.title = selected
      ? `第 ${selectedIndex + 1} 排序·${selectedOrder === "asc" ? "升序" : "降序"}；单击排序，Shift + 单击添加次级排序`
      : `按${label}排序；Shift + 单击添加次级排序`;
    button.setAttribute(
      "aria-label",
      selected
        ? `${label}，第 ${selectedIndex + 1} 排序，${selectedOrder === "asc" ? "升序" : "降序"}`
        : `${label}，未排序`,
    );
  
    const text = document.createElement("span");
    text.textContent = label;
    const indicator = document.createElement("span");
    indicator.className = `sort-indicator${selected ? ` ${selectedOrder}` : ""}`;
    indicator.setAttribute("aria-hidden", "true");
    button.append(text, indicator);
    if (selected) {
      const priority = document.createElement("span");
      priority.className = "sort-priority";
      priority.textContent = String(selectedIndex + 1);
      priority.setAttribute("aria-hidden", "true");
      button.append(priority);
    }
    button.addEventListener("click", (event) => {
      const append = event.shiftKey || event.ctrlKey || event.metaKey;
      let nextRules;
  
      if (append) {
        if (!selected && rules.length >= maxSortFields) {
          toast(`最多支持 ${maxSortFields} 个排序字段`);
          return;
        }
        nextRules = rules.map((rule) => ({ ...rule }));
        if (!selected) {
          nextRules.push({ field: sortBy, order: "asc" });
        } else if (selectedOrder === "asc") {
          nextRules[selectedIndex].order = "desc";
        } else {
          nextRules.splice(selectedIndex, 1);
        }
      } else if (!selected) {
        nextRules = [{ field: sortBy, order: "asc" }];
      } else if (selectedOrder === "asc") {
        nextRules = [{ field: sortBy, order: "desc" }];
      } else {
        nextRules = [];
      }
  
      navigate(
        nextRules.map((rule) => rule.field).join(","),
        nextRules.length
          ? nextRules.map((rule) => rule.order).join(",")
          : "asc",
      );
    });
    th.append(button);
    return th;
  }
  
  function createDataCell(value, kind = "", record = null) {
    const cell = document.createElement("td");
    if (kind === "status") {
      cell.append(createStatusBadge(value));
    } else if (kind === "runtime-worker" && record !== null) {
      const workerId = String(value || "");
      const match = workerId.match(/^(.*)-(\d+)$/);
      const summary = document.createElement("span");
      summary.className = "worker-summary";
  
      const hostname = document.createElement("span");
      hostname.className = "worker-hostname";
      hostname.title = workerId || "未知节点";
      hostname.textContent = match ? match[1] : (workerId || "—");
      summary.append(hostname);
  
      if (match) {
        const process = document.createElement("span");
        process.className = "worker-process";
        process.textContent = `PID ${match[2]}`;
        process.title = `进程 ID：${match[2]}`;
        summary.append(process);
      }
      cell.append(summary);
    } else if (kind === "deployment-role") {
      cell.append(createDeploymentRoleBadge(value));
    } else if (kind === "execution-type") {
      cell.append(createExecutionTypeBadge(value));
    } else if (kind === "version-count" && record !== null && value != null) {
      const link = createNavigationLink(
        String(value),
        () => navigateToModelVersions(
          /** @type {ConsoleModel} */ (record),
        ),
      );
      link.classList.remove("mono");
      link.title = "查看全部版本";
      cell.append(link);
    } else if (kind === "variant-count" && record !== null && value != null) {
      const link = createNavigationLink(
        `${formatInteger(value)} 个分组`,
        () => navigateToExperimentVariants(
          /** @type {ExperimentReference} */ (record),
        ),
      );
      link.classList.remove("mono");
      link.title = "查看全部分组";
      cell.append(link);
    } else if (kind === "request-link" && value != null) {
      const requestId = String(value);
      const link = createNavigationLink(
        requestId,
        () => navigateToSection(
          "requests",
          1,
          `request_id:${requestId}`,
        ),
      );
      link.title = "查看 API 调用";
      cell.append(link);
    } else if (kind === "permissions") {
      cell.append(createPermissionSummary(value, record));
    } else if (kind === "blank") {
      cell.textContent = value ?? "";
    } else if (kind === "list") {
      const values = Array.isArray(value) ? value : [];
      cell.textContent = values.length > 0
        ? values.join(", ")
        : "—";
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
  
  /**
   * 创建权限摘要。
   *
   * @param {unknown} value 权限值
   * @param {ConsoleRole | null} record 角色记录
   * @returns {HTMLDivElement} 权限摘要容器
   */
  function createPermissionSummary(value, record = null) {
    const summary = document.createElement("div");
    summary.className = "permission-summary";
    const permissions = Array.isArray(value)
      ? value.map(String)
      : [];
    const effectivePermissions = (
      record !== null
      && Array.isArray(record.effective_permissions)
    )
      ? record.effective_permissions.map(String)
      : permissions;
  
    if (!effectivePermissions.length) {
      summary.textContent = "—";
      return summary;
    }
  
    summary.title = permissions.includes("*")
      ? `全部权限（${formatInteger(effectivePermissions.length)} 项）`
      : effectivePermissions.join(", ");
    const visiblePermissions = effectivePermissions.slice(0, 2);
  
    for (const permission of visiblePermissions) {
      const chip = document.createElement("span");
      chip.className = "permission-chip";
      chip.textContent = permission;
      summary.append(chip);
    }
  
    if (effectivePermissions.length > visiblePermissions.length) {
      const overflow = document.createElement("span");
      const hiddenCount = (
        effectivePermissions.length
        - visiblePermissions.length
      );
      overflow.className = "permission-overflow";
      overflow.textContent = `+${hiddenCount}`;
      overflow.setAttribute(
        "aria-label",
        `另有 ${hiddenCount} 项权限`,
      );
      summary.append(overflow);
    }
  
    return summary;
  }
  
  function createStatusBadge(value) {
    const badge = document.createElement("span");
    badge.className = `status ${statusTone(value)}`.trim();
    badge.textContent = value ?? "—";
    return badge;
  }
  
  function createDeploymentRoleBadge(value) {
    const role = String(value || "").toLowerCase();
    const badge = document.createElement("span");
    badge.className = `deployment-role ${role}`.trim();
    badge.textContent = role || "—";
    return badge;
  }
  
  function createExecutionTypeBadge(value) {
    const executionType = String(value || "").toLowerCase();
    const badge = document.createElement("span");
    badge.className = `execution-type ${executionType}`.trim();
    badge.textContent = executionType === "primary"
      ? "主执行"
      : (executionType === "shadow" ? "影子执行" : (value ?? "—"));
    return badge;
  }
  
  /**
   * 创建资源导航链接。
   *
   * @param {string} value 链接文本
   * @param {() => void} navigate 导航方法
   * @returns {HTMLButtonElement} 导航按钮
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
   * 创建指向资源分区的导航链接。
   *
   * @param {string | null} value 资源标识
   * @param {string} section 目标分区
   * @param {HTMLDialogElement} dialog 当前详情抽屉
   * @param {string | null} [label=value] 链接显示文本
   * @returns {string | null | HTMLButtonElement} 导航按钮或静态文本
   */
  function createSectionNavigationLink(value, section, dialog, label = value) {
    const snapshot = state.snapshot;
  
    if (!value || snapshot === null || !snapshot.access[section]) return label;
  
    return createNavigationLink(label, () => {
      dialog.close();
      navigateToSection(
        section,
        1,
        `${sectionIdFields[section]}:${value}`,
      );
    });
  }
  
  function createCopyableSectionNavigationLink(
    value,
    section,
    dialog,
    label = "ID",
  ) {
    const snapshot = state.snapshot;
    const navigate = value && snapshot !== null && snapshot.access[section]
      ? () => {
        dialog.close();
        navigateToSection(
          section,
          1,
          `${sectionIdFields[section]}:${value}`,
        );
      }
      : null;
    return createCopyableNavigationLink(value, navigate, label);
  }
  
  function createCopyableNavigationLink(value, navigate, label = "ID") {
    if (!value) return "—";
  
    const container = document.createElement("span");
    container.className = "detail-identifier";
    if (typeof navigate === "function") {
      container.append(createNavigationLink(value, navigate));
    } else {
      const identifier = document.createElement("span");
      identifier.className = "mono";
      identifier.textContent = value;
      container.append(identifier);
    }
  
    const copyButton = document.createElement("button");
    copyButton.type = "button";
    copyButton.className = "detail-copy-button";
    copyButton.append(createDetailIcon("copy"));
    copyButton.setAttribute("aria-label", `复制${label}`);
    copyButton.title = `复制${label}`;
  
    const feedback = document.createElement("span");
    feedback.className = "detail-copy-feedback";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-live", "polite");
    feedback.hidden = true;
    let feedbackTimer = null;
  
    function showCopiedIcon() {
      copyButton.replaceChildren(createDetailIcon("check"));
    }
  
    copyButton.addEventListener("click", async () => {
      window.clearTimeout(feedbackTimer);
      try {
        await navigator.clipboard.writeText(value);
        showCopiedIcon();
        copyButton.classList.add("copied");
        copyButton.setAttribute("aria-label", `${label}已复制`);
        feedback.textContent = "已复制";
        feedback.classList.remove("failed");
      } catch {
        feedback.textContent = "复制失败";
        feedback.classList.add("failed");
      }
      feedback.hidden = false;
      feedbackTimer = window.setTimeout(() => {
        copyButton.replaceChildren(createDetailIcon("copy"));
        copyButton.classList.remove("copied");
        copyButton.setAttribute("aria-label", `复制${label}`);
        feedback.hidden = true;
      }, 1800);
    });
    container.append(copyButton, feedback);
    return container;
  }

  return {
    createCopyableNavigationLink,
    createCopyableSectionNavigationLink,
    createDataCell,
    createDeploymentRoleBadge,
    createExecutionTypeBadge,
    createSectionNavigationLink,
    createSortHeader,
    createStatusBadge,
  };
}
