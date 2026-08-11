"use strict";

export const DEFAULT_PAGE_SIZE = 10;
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100];

/**
 * @typedef {Object} PaginatedData
 * @property {number} page
 * @property {number} page_size
 * @property {number} total_pages
 * @property {boolean} has_previous
 * @property {boolean} has_next
 */

/**
 * 创建列表查询与分页控件。
 *
 * 控件统一管理查询栏展开状态、查询草稿和列表分页交互。
 *
 * @param {Object} options 控件配置
 * @param {HTMLElement} options.container 查询栏容器
 * @param {HTMLFormElement} options.queryForm 查询表单
 * @param {HTMLInputElement} options.queryInput 查询输入框
 * @param {HTMLButtonElement} options.queryToggle 查询展开按钮
 * @param {HTMLButtonElement} options.queryCollapse 查询收起按钮
 * @param {HTMLButtonElement} options.queryClear 查询清除按钮
 * @param {(value: unknown) => string} options.formatNumber 数字格式化方法
 * @param {(message: string) => void} options.notify 消息提示方法
 * @returns {{
 *   setQueryAvailable: (available: boolean) => void,
 *   hasQueryDraft: () => boolean,
 *   updateQuery: (query: string, placeholder: string) => void,
 *   renderPagination: (
 *     data: PaginatedData,
 *     label: string,
 *     navigate: (page: number, pageSize: number) => void,
 *   ) => void,
 * }} 查询与分页控件入口
 */
export function createTableControls({
  container,
  queryForm,
  queryInput,
  queryToggle,
  queryCollapse,
  queryClear,
  formatNumber,
  notify,
}) {
  let queryAvailable = false;
  let queryExpanded = false;
  let currentQuery = "";
  let currentPlaceholder = "";
  let queryDraftDirty = false;

  function renderQueryState() {
    queryToggle.hidden = !queryAvailable || queryExpanded;
    queryForm.hidden = !queryAvailable || !queryExpanded;
    queryToggle.setAttribute("aria-expanded", String(queryExpanded));
    queryToggle.classList.toggle("has-query", Boolean(currentQuery));
    queryToggle.title = currentQuery
      ? `当前查询：${currentQuery}`
      : "展开查询条件";
  }

  function setQueryExpanded(expanded, focus = false) {
    queryExpanded = queryAvailable && expanded;
    renderQueryState();

    if (queryExpanded && focus) queryInput.focus();
  }

  queryToggle.addEventListener("click", () => {
    setQueryExpanded(true, true);
  });
  queryCollapse.addEventListener("click", () => {
    setQueryExpanded(false);
  });
  queryInput.addEventListener("input", () => {
    queryDraftDirty = queryInput.value !== currentQuery;
    queryClear.hidden = !queryInput.value;
  });

  return {
    hasQueryDraft() {
      return queryDraftDirty || (
        document.activeElement === queryInput
        && queryInput.value !== currentQuery
      );
    },

    setQueryAvailable(available) {
      queryAvailable = available;

      if (!available) queryExpanded = false;

      renderQueryState();
    },

    updateQuery(query, placeholder) {
      const contextChanged = placeholder !== currentPlaceholder;
      const queryChanged = query !== currentQuery;
      const queryBeingEdited = document.activeElement === queryInput;
      const preserveQueryDraft = (
        (queryDraftDirty || queryBeingEdited)
        && !contextChanged
        && !queryChanged
        && queryInput.value !== query
      );
      currentQuery = query;
      currentPlaceholder = placeholder;
      if (!preserveQueryDraft) {
        queryInput.value = query;
        queryDraftDirty = false;
      }
      queryInput.placeholder = placeholder;
      queryClear.hidden = !queryInput.value;
      queryAvailable = true;

      if (contextChanged || queryChanged) {
        queryExpanded = Boolean(query);
      }

      renderQueryState();
    },

    renderPagination(data, label, navigate) {
      const pagination = document.createElement("nav");
      pagination.className = "pagination";
      pagination.setAttribute("aria-label", label);

      const previous = document.createElement("button");
      previous.type = "button";
      previous.className = "secondary-button";
      previous.textContent = "上一页";
      previous.disabled = !data.has_previous;
      previous.addEventListener("click", () => {
        navigate(data.page - 1, data.page_size);
      });

      const page = document.createElement("span");
      page.className = "page-indicator";
      page.textContent = `${formatNumber(data.page)} / ${formatNumber(data.total_pages)}`;
      page.setAttribute(
        "aria-label",
        `第 ${formatNumber(data.page)} 页，共 ${formatNumber(data.total_pages)} 页`,
      );

      const next = document.createElement("button");
      next.type = "button";
      next.className = "secondary-button";
      next.textContent = "下一页";
      next.disabled = !data.has_next;
      next.addEventListener("click", () => {
        navigate(data.page + 1, data.page_size);
      });

      const size = document.createElement("label");
      size.className = "page-size";
      size.append(document.createTextNode("每页"));
      const sizeSelect = document.createElement("select");
      sizeSelect.setAttribute("aria-label", "每页显示条数");
      for (const optionValue of PAGE_SIZE_OPTIONS) {
        const option = document.createElement("option");
        option.value = String(optionValue);
        option.textContent = formatNumber(optionValue);
        option.selected = optionValue === data.page_size;
        sizeSelect.append(option);
      }
      sizeSelect.addEventListener("change", () => {
        const pageSize = Number(sizeSelect.value);
        if (pageSize !== data.page_size) navigate(1, pageSize);
      });
      size.append(sizeSelect, document.createTextNode("条"));

      pagination.append(size, previous, page, next);

      if (data.total_pages > 1) {
        const jump = document.createElement("form");
        jump.className = "page-jump";
        jump.noValidate = true;
        const pageInput = document.createElement("input");
        pageInput.type = "number";
        pageInput.min = "1";
        pageInput.max = String(data.total_pages);
        pageInput.placeholder = "页码";
        pageInput.setAttribute(
          "aria-label",
          `跳转页码，范围 1 至 ${formatNumber(data.total_pages)}`,
        );
        const jumpButton = document.createElement("button");
        jumpButton.type = "submit";
        jumpButton.className = "secondary-button";
        jumpButton.textContent = "跳转";
        jump.addEventListener("submit", (event) => {
          event.preventDefault();
          const target = Number(pageInput.value);
          if (!Number.isInteger(target) || target < 1 || target > data.total_pages) {
            notify(`请输入 1 至 ${formatNumber(data.total_pages)} 之间的页码`);
            return;
          }
          if (target !== data.page) navigate(target, data.page_size);
        });
        jump.append(pageInput, jumpButton);
        pagination.append(jump);
      }

      container.append(pagination);
    },
  };
}
