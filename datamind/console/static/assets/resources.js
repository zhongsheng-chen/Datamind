"use strict";

import {
  getDetailRoute,
  synchronizeDetailDrawer,
} from "./details/common.js?v=20260901";

/**
 * 创建资源列表控制器。
 *
 * 控制器负责资源列表、层级子列表、查询排序、分页和选择状态。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   buildExportPath: () => string,
 *   buildHashQuery: (page: number, pageSize: number, query: string, sortBy?: string, sortOrder?: string) => string,
 *   buildPageQuery: (page: number, pageSize: number, query: string, sortBy?: string, sortOrder?: string) => string,
 *   getSectionView: (section: string) => string,
 *   loadSectionPage: (section: string, page: number) => Promise<void>,
 *   loadVariantPage: (experimentId: string, page: number) => Promise<void>,
 *   loadVersionPage: (modelId: string, page: number) => Promise<void>,
 *   normalizeSortParameters: (sortBy: string | null | undefined, sortOrder: string | null | undefined) => [string, string],
 *   parseSortRules: (sortBy: string, sortOrder: string) => {field: string, order: string}[],
 *   parsePageSize: (value: string | null | undefined) => number,
 *   renderSection: () => void,
 *   syncDetailRoute: () => Promise<void>,
 *   updateSelectionControls: () => void,
 *   updateVisibleSelectionState: () => void
 * }} 资源列表入口
 */
export function createResourceListController({
  appendManagementCell,
  appendManagementHeader,
  backButton,
  createButton,
  createDataCell,
  createSortHeader,
  dashboardView,
  dataPanel,
  defaultPageSize,
  deletedModelVersionColumns,
  deletedSectionColumns,
  formatInteger,
  isExportInProgress,
  maxSortFields,
  modelUsagePanel,
  navigateToExperimentVariants,
  navigateToModelVersions,
  navigateToSection,
  pageSizeOptions,
  recyclableSections,
  renderEmpty,
  renderNavigation,
  request,
  resourceViewToggle,
  sectionIdFields,
  sections,
  selectedExportButton,
  selectionCount,
  selectionSummary,
  showAuditDetails,
  showDecisionDetails,
  showDeploymentDrawer,
  showExecutionDetails,
  showExperimentDetails,
  showLogin,
  showModelDrawer,
  showRequestDetails,
  showRoleDrawer,
  showRoutingDrawer,
  showRuntimeDetails,
  showUserDrawer,
  showVariantDetails,
  showVersionDrawer,
  state,
  summaryGrid,
  tableContainer,
  tableControls,
  toast,
  trendPanel,
  updateCreateButton,
  updateSearchForm,
  variantColumns,
  versionColumns,
}) {
  let sectionRequestKey = null;
  let versionRequestKey = null;
  let variantRequestKey = null;
  let detailRequestKey = null;
  const tableScrollPositions = new Map();

  function renderSection() {
    const snapshot = state.snapshot;
  
    if (snapshot === null) return;
  
    dashboardView.classList.toggle(
      "overview-active",
      state.active === "overview",
    );
    dataPanel.classList.remove("access-empty");
  
    tableContainer.replaceChildren();
    backButton.hidden = true;
    createButton.hidden = true;
    selectionSummary.hidden = true;
    document.querySelector("#section-caption").hidden = true;
    resourceViewToggle.hidden = true;
  
    if (state.active === null) {
      summaryGrid.hidden = true;
      dataPanel.hidden = false;
      trendPanel.hidden = true;
      modelUsagePanel.hidden = true;
      tableControls.setQueryAvailable(false);
      dataPanel.classList.add("access-empty");
      document.querySelector("#page-title").textContent = "控制台";
      renderEmpty(
        "当前账户暂无可访问内容",
        "请联系管理员分配角色或查看权限。",
      );
      return;
    }
  
    if (state.active === "overview") {
      tableControls.setQueryAvailable(false);
      summaryGrid.hidden = !snapshot.access.requests;
      dataPanel.hidden = true;
      trendPanel.hidden = !snapshot.access.requests;
      modelUsagePanel.hidden = !snapshot.access.requests;
      document.querySelector("#page-title").textContent = "概览";
      return;
    }
  
    summaryGrid.hidden = true;
    dataPanel.hidden = false;
    trendPanel.hidden = true;
    modelUsagePanel.hidden = true;
    updateCreateButton();
    syncSelectionScope();
    updateSelectionControls();
  
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
   * 隐藏没有数据时不可用的列表操作。
   *
   * 查询无匹配结果时保留查询入口，方便修改或清除条件。
   *
   * @param {string} query 当前查询条件
   * @returns {void} 无返回值
   */
  function configureEmptyListControls(query) {
    tableControls.setQueryAvailable(Boolean(query));
  }
  
  function showResourceViewToggle(label, view) {
    const inTrash = view === "trash";
    resourceViewToggle.hidden = false;
    resourceViewToggle.textContent = inTrash ? "返回列表" : "回收站";
    resourceViewToggle.dataset.targetView = inTrash ? "active" : "trash";
    resourceViewToggle.setAttribute(
      "aria-label",
      inTrash ? `返回${label}列表` : `打开${label}回收站`,
    );
  }
  
  function getSectionView(section) {
    if (section === "versions") {
      return state.versionView === "trash" ? "trash" : "active";
    }
    return recyclableSections.has(section) ? state.sectionView : "active";
  }
  
  function showRecordDetails(section, record) {
    const handlers = {
      models: showModelDrawer,
      versions: showVersionDrawer,
      deployments: showDeploymentDrawer,
      routings: showRoutingDrawer,
      experiments: showExperimentDetails,
      variants: showVariantDetails,
      runtimes: showRuntimeDetails,
      requests: showRequestDetails,
      decisions: showDecisionDetails,
      executions: showExecutionDetails,
      audits: showAuditDetails,
      users: showUserDrawer,
      roles: showRoleDrawer,
    };
    const handler = handlers[section];
    if (handler === undefined) return false;
    handler(record);
    return true;
  }

  async function syncDetailRoute() {
    const route = getDetailRoute();

    if (synchronizeDetailDrawer(route) || route === null) return;
    if (!Object.hasOwn(sectionIdFields, route.section)) return;
    if (detailRequestKey === `${route.section}:${route.id}`) return;

    detailRequestKey = `${route.section}:${route.id}`;
    try {
      const idField = sectionIdFields[route.section];
      const localRecords = [
        ...(state.active === route.section
          && Array.isArray(state.sectionData?.items)
          ? state.sectionData.items
          : []),
        ...(route.section === "versions"
          && Array.isArray(state.versionData?.items)
          ? state.versionData.items
          : []),
        ...(route.section === "variants"
          && Array.isArray(state.variantData?.items)
          ? state.variantData.items
          : []),
        ...(Array.isArray(state.snapshot?.sections?.[route.section])
          ? state.snapshot.sections[route.section]
          : []),
      ];
      let record = localRecords.find((item) => String(item[idField]) === route.id);

      if (!record) {
        const query = `${idField}:${route.id}`;
        let path;

        if (route.section === "versions" && state.selectedModelId !== null) {
          path = `models/${encodeURIComponent(state.selectedModelId)}/versions`;
        } else if (
          route.section === "variants"
          && state.selectedExperimentId !== null
        ) {
          path = `experiments/${encodeURIComponent(state.selectedExperimentId)}/variants`;
        } else {
          path = `sections/${route.section}`;
        }
        const response = await request(
          `${path}?${buildPageQuery(1, 100, query)}&deleted=${getSectionView(route.section) === "trash"}`,
        );
        record = (Array.isArray(response?.items) ? response.items : [])
          .find((item) => String(item[idField]) === route.id);
      }

      const activeRoute = getDetailRoute();
      if (
        activeRoute?.section !== route.section
        || activeRoute.id !== route.id
      ) return;
      if (!record) {
        toast("详情记录不存在或无权查看");
        return;
      }
      showRecordDetails(route.section, record);
    } catch (error) {
      if (getDetailRoute()?.id === route.id) {
        toast(error instanceof Error ? error.message : "详情加载失败");
      }
    } finally {
      if (detailRequestKey === `${route.section}:${route.id}`) {
        detailRequestKey = null;
      }
    }
  }
  
  function isInteractiveRowTarget(target, row) {
    if (!(target instanceof Element)) return false;
    const interactive = target.closest(
      "button, a, input, select, textarea, label, [role='button']",
    );
    return interactive !== null && row.contains(interactive);
  }
  
  function enableDetailRow(row, section, record) {
    const hasDetails = Object.hasOwn(sectionIdFields, section);
    if (!hasDetails) return;
  
    row.classList.add("detail-row");
    row.tabIndex = 0;
    row.setAttribute("aria-label", `查看${sections[section]?.label || "记录"}详情`);
  
    row.addEventListener("click", (event) => {
      if (isInteractiveRowTarget(event.target, row)) return;
      const selection = window.getSelection();
      if (selection !== null && !selection.isCollapsed) return;
      showRecordDetails(section, record);
    });
    row.addEventListener("keydown", (event) => {
      if (event.target !== row || event.key !== "Enter") return;
      event.preventDefault();
      showRecordDetails(section, record);
    });
  }
  
  /**
   * 渲染当前资源分区列表。
   *
   * @param {SectionConfig} config 分区配置
   * @returns {void} 无返回值
   */
  function renderSectionPage(config) {
    document.querySelector("#section-title").textContent = config.title;
    document.querySelector("#page-title").textContent = config.label;
    const caption = document.querySelector("#section-caption");
    updateSearchForm(
      state.sectionQuery,
      `查询${config.label}`,
    );
    caption.textContent = `第 ${formatInteger(state.sectionPage)} 页`;
    caption.hidden = false;
    const inRecyclableSection = recyclableSections.has(state.active);
    const currentView = getSectionView(state.active);
    const inTrash = inRecyclableSection && currentView === "trash";
    const columns = inTrash ? deletedSectionColumns[state.active] : config.columns;
  
    if (inRecyclableSection) {
      showResourceViewToggle(config.label, currentView);
      if (inTrash) createButton.hidden = true;
    }
  
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
    const total = formatInteger(state.sectionData.total);
    const page = formatInteger(state.sectionData.page);
    const totalPages = formatInteger(state.sectionData.total_pages);
    const pageCount = formatInteger(records.length);
    const itemLabel = inTrash
      ? `条已删除${config.label}`
      : "条";
    caption.textContent = state.sectionQuery
      ? `查询“${state.sectionQuery}” · 共 ${total} ${itemLabel} · 第 ${page}/${totalPages} 页 · 本页 ${pageCount} 条`
      : `共 ${total} ${itemLabel} · 第 ${page}/${totalPages} 页 · 本页 ${pageCount} 条`;
  
    if (!records.length) {
      configureEmptyListControls(state.sectionQuery);
      renderEmpty(
        state.sectionQuery
          ? "没有匹配的记录"
          : (inTrash ? "回收站为空" : `暂无${config.label}记录`),
        state.sectionQuery
          ? "请尝试其他关键词。"
          : (inTrash
            ? `删除的${config.label}将在这里显示。`
            : (state.active === "runtimes"
              ? "当前没有在线或正在加载的实例。"
              : "数据产生后将在这里显示。")),
      );
      return;
    }
  
    if (state.active === "models" && !inTrash) {
      renderModelTable(
        /** @type {ConsoleModel[]} */ (records),
        config,
      );
    } else if (state.active === "experiments" && !inTrash) {
      renderExperimentTable(
        /** @type {ExperimentReference[]} */ (records),
        config,
      );
    } else {
      const table = document.createElement("table");
      const thead = document.createElement("thead");
      const headerRow = document.createElement("tr");
      appendSelectionHeader(
        headerRow,
        records,
        sectionIdFields[state.active],
      );
      for (const column of columns) {
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
            state.sectionPageSize,
            currentView,
          ),
        ));
      }
      appendManagementHeader(headerRow, state.active);
      thead.append(headerRow);
  
      const tbody = document.createElement("tbody");
      for (const record of records) {
        const row = document.createElement("tr");
        enableDetailRow(row, state.active, record);
        appendSelectionCell(
          row,
          record,
          sectionIdFields[state.active],
        );
        for (const [field, , kind] of columns) {
          row.append(createDataCell(record[field], kind, record));
        }
        appendManagementCell(row, state.active, record);
        tbody.append(row);
      }
      table.append(thead, tbody);
      appendScrollableTable(table);
    }
  
    renderPagination(
      state.sectionData,
      `${config.label}分页`,
      (page, pageSize) => navigateToSection(
        state.active,
        page,
        state.sectionQuery,
        state.sectionSort,
        state.sectionOrder,
        pageSize,
        currentView,
      ),
    );
  }
  
  /**
   * 渲染模型列表表格。
   *
   * @param {ConsoleModel[]} records 模型记录
   * @param {SectionConfig} config 分区配置
   * @returns {void} 无返回值
   */
  function renderModelTable(records, config) {
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    appendSelectionHeader(
      headerRow,
      records,
      sectionIdFields.models,
    );
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
          state.sectionPageSize,
        ),
      ));
    }
    appendManagementHeader(headerRow, "models");
    thead.append(headerRow);
  
    const tbody = document.createElement("tbody");
    for (const record of records) {
      const row = document.createElement("tr");
      row.className = "model-row";
      enableDetailRow(row, "models", record);
      appendSelectionCell(
        row,
        record,
        sectionIdFields.models,
      );
  
      for (const [field, , kind] of config.columns) {
        row.append(createDataCell(record[field], kind, record));
      }
      appendManagementCell(row, "models", record);
      tbody.append(row);
    }
  
    table.append(thead, tbody);
    appendScrollableTable(table);
  }
  
  /**
   * 渲染实验列表表格。
   *
   * @param {ExperimentReference[]} records 实验记录
   * @param {SectionConfig} config 分区配置
   * @returns {void} 无返回值
   */
  function renderExperimentTable(records, config) {
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    appendSelectionHeader(
      headerRow,
      records,
      sectionIdFields.experiments,
    );
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
          state.sectionPageSize,
        ),
      ));
    }
    appendManagementHeader(headerRow, "experiments");
    thead.append(headerRow);
  
    const tbody = document.createElement("tbody");
    for (const record of records) {
      const row = document.createElement("tr");
      enableDetailRow(row, "experiments", record);
      appendSelectionCell(
        row,
        record,
        sectionIdFields.experiments,
      );
      for (const [field, , kind] of config.columns) {
        row.append(createDataCell(record[field], kind, record));
      }
      appendManagementCell(row, "experiments", record);
      tbody.append(row);
    }
  
    table.append(thead, tbody);
    appendScrollableTable(table);
  }
  
  /**
   * 渲染指定模型的版本列表。
   *
   * @param {ConsoleModel} model 目标模型
   * @returns {void} 无返回值
   */
  function renderModelVersionsPage(model) {
    summaryGrid.hidden = true;
    document.querySelector("#page-title").textContent = "版本";
    document.querySelector("#section-title").textContent = `${model.name} 的版本`;
    const caption = document.querySelector("#section-caption");
    updateSearchForm(
      state.versionQuery,
      "查询当前模型的版本",
    );
    caption.textContent = `第 ${formatInteger(state.versionPage)} 页`;
    caption.hidden = false;
    backButton.textContent = "返回模型";
    backButton.hidden = false;
    showResourceViewToggle(
      "版本",
      state.versionView === "trash" ? "trash" : "active",
    );
  
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
    const inTrash = state.versionView === "trash";
    const currentVersionColumns = inTrash
      ? deletedModelVersionColumns
      : versionColumns;
    if (inTrash) createButton.hidden = true;
    const total = formatInteger(state.versionData.total);
    const page = formatInteger(state.versionData.page);
    const totalPages = formatInteger(state.versionData.total_pages);
    const pageCount = formatInteger(versions.length);
    const itemLabel = inTrash ? "条已删除版本" : "个版本";
    caption.textContent = state.versionQuery
      ? `查询“${state.versionQuery}” · 共 ${total} ${itemLabel} · 第 ${page}/${totalPages} 页 · 本页 ${pageCount} 条`
      : `共 ${total} ${itemLabel} · 第 ${page}/${totalPages} 页 · 本页 ${pageCount} 条`;
  
    if (!versions.length) {
      configureEmptyListControls(state.versionQuery);
      renderEmpty(
        state.versionQuery ? "没有匹配的版本" : (inTrash ? "回收站为空" : "暂无版本"),
        state.versionQuery ? "请尝试其他关键词。" : (inTrash ? "删除的版本将在这里显示。" : "注册版本后将在这里显示。"),
      );
      return;
    }
  
    const table = document.createElement("table");
    table.className = "version-page-table";
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    appendSelectionHeader(
      headerRow,
      versions,
      sectionIdFields.versions,
    );
    for (const column of currentVersionColumns) {
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
          state.versionPageSize,
        ),
      ));
    }
    appendManagementHeader(headerRow, "versions");
    thead.append(headerRow);
  
    const tbody = document.createElement("tbody");
    for (const version of versions) {
      const versionRow = document.createElement("tr");
      enableDetailRow(versionRow, "versions", version);
      appendSelectionCell(
        versionRow,
        version,
        sectionIdFields.versions,
      );
      for (const [field, , kind] of currentVersionColumns) {
        versionRow.append(createDataCell(version[field], kind, version));
      }
      appendManagementCell(versionRow, "versions", version);
      tbody.append(versionRow);
    }
    table.append(thead, tbody);
    appendScrollableTable(table);
    renderPagination(
      state.versionData,
      "版本分页",
      (page, pageSize) => navigateToModelVersions(
        model,
        page,
        state.versionQuery,
        state.versionSort,
        state.versionOrder,
        pageSize,
      ),
    );
  }
  
  /**
   * 渲染指定实验的分组列表。
   *
   * @param {ExperimentReference} experiment 目标实验
   * @returns {void} 无返回值
   */
  function renderExperimentVariantsPage(experiment) {
    summaryGrid.hidden = true;
    document.querySelector("#page-title").textContent = "实验分组";
    document.querySelector("#section-title").textContent = `${experiment.name} 的实验分组`;
    const caption = document.querySelector("#section-caption");
    updateSearchForm(
      state.variantQuery,
      "查询当前实验的分组",
    );
    caption.textContent = `第 ${formatInteger(state.variantPage)} 页`;
    caption.hidden = false;
    backButton.textContent = "返回实验";
    backButton.hidden = false;
    showResourceViewToggle("分组", state.variantView);
  
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
    const inTrash = state.variantView === "trash";
    const currentVariantColumns = inTrash
      ? deletedSectionColumns.variants
      : variantColumns;
    if (inTrash) createButton.hidden = true;
    const total = formatInteger(state.variantData.total);
    const page = formatInteger(state.variantData.page);
    const totalPages = formatInteger(state.variantData.total_pages);
    const pageCount = formatInteger(variants.length);
    const itemLabel = inTrash ? "条已删除分组" : "个分组";
    caption.textContent = state.variantQuery
      ? `查询“${state.variantQuery}” · 共 ${total} ${itemLabel} · 第 ${page}/${totalPages} 页 · 本页 ${pageCount} 条`
      : `共 ${total} ${itemLabel} · 第 ${page}/${totalPages} 页 · 本页 ${pageCount} 条`;
  
    if (!variants.length) {
      configureEmptyListControls(state.variantQuery);
      renderEmpty(
        state.variantQuery ? "没有匹配的实验分组" : (inTrash ? "回收站为空" : "暂无实验分组"),
        state.variantQuery ? "请尝试其他关键词。" : (inTrash ? "删除的分组将在这里显示。" : "创建实验分组后将在这里显示。"),
      );
      return;
    }
  
    const table = document.createElement("table");
    table.className = "version-page-table";
    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");
    appendSelectionHeader(
      headerRow,
      variants,
      sectionIdFields.variants,
    );
    for (const column of currentVariantColumns) {
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
          state.variantPageSize,
        ),
      ));
    }
    appendManagementHeader(headerRow, "variants");
    thead.append(headerRow);
  
    const tbody = document.createElement("tbody");
    for (const variant of variants) {
      const variantRow = document.createElement("tr");
      enableDetailRow(variantRow, "variants", variant);
      appendSelectionCell(
        variantRow,
        variant,
        sectionIdFields.variants,
      );
      for (const [field, , kind] of currentVariantColumns) {
        variantRow.append(createDataCell(variant[field], kind, variant));
      }
      appendManagementCell(variantRow, "variants", variant);
      tbody.append(variantRow);
    }
    table.append(thead, tbody);
    appendScrollableTable(table);
    renderPagination(
      state.variantData,
      "实验分组分页",
      (page, pageSize) => navigateToExperimentVariants(
        experiment,
        page,
        state.variantQuery,
        state.variantSort,
        state.variantOrder,
        pageSize,
      ),
    );
  }
  
  async function loadSectionPage(section, page) {
    const query = state.sectionQuery;
    const sortBy = state.sectionSort;
    const sortOrder = state.sectionOrder;
    const pageSize = state.sectionPageSize;
    const view = getSectionView(section);
    const requestKey = `${section}:${view}:${page}:${pageSize}:${query}:${sortBy}:${sortOrder}`;
    if (sectionRequestKey === requestKey) return;
  
    sectionRequestKey = requestKey;
    try {
      const deletedQuery = recyclableSections.has(section)
        ? `&deleted=${view === "trash"}`
        : "";
      const data = /** @type {PageData} */ (await request(
        `sections/${section}?${buildPageQuery(page, pageSize, query, sortBy, sortOrder)}${deletedQuery}`,
      ));
      if (
        state.active !== section
        || state.sectionPage !== page
        || state.sectionPageSize !== pageSize
        || state.sectionQuery !== query
        || state.sectionSort !== sortBy
        || state.sectionOrder !== sortOrder
        || (
          recyclableSections.has(section)
          && (section === "versions"
            ? (state.versionView === "trash" ? "trash" : "active")
            : state.sectionView) !== view
        )
      ) return;
      const snapshot = state.snapshot;
      if (
        snapshot !== null
        && query.trim() === ""
        && view === "active"
        && Number.isInteger(data.total)
        && snapshot.counts[section] !== data.total
      ) {
        snapshot.counts[section] = data.total;
        renderNavigation();
      }
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
        || state.sectionPageSize !== pageSize
        || state.sectionQuery !== query
        || state.sectionSort !== sortBy
        || state.sectionOrder !== sortOrder
        || (
          recyclableSections.has(section)
          && (section === "versions"
            ? (state.versionView === "trash" ? "trash" : "active")
            : state.sectionView) !== view
        )
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
    const pageSize = state.versionPageSize;
    const view = state.versionView;
    const requestKey = `${modelId}:${view}:${page}:${pageSize}:${query}:${sortBy}:${sortOrder}`;
    if (versionRequestKey === requestKey) return;
  
    versionRequestKey = requestKey;
    try {
      const data = /** @type {VersionPageData} */ (await request(
        `models/${encodeURIComponent(modelId)}/versions?${buildPageQuery(page, pageSize, query, sortBy, sortOrder)}&deleted=${view === "trash"}`,
      ));
      if (
        state.selectedModelId !== modelId
        || state.versionPage !== page
        || state.versionPageSize !== pageSize
        || state.versionQuery !== query
        || state.versionSort !== sortBy
        || state.versionOrder !== sortOrder
        || state.versionView !== view
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
        || state.versionPageSize !== pageSize
        || state.versionQuery !== query
        || state.versionSort !== sortBy
        || state.versionOrder !== sortOrder
        || state.versionView !== view
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
    const pageSize = state.variantPageSize;
    const view = state.variantView;
    const requestKey = `${experimentId}:${view}:${page}:${pageSize}:${query}:${sortBy}:${sortOrder}`;
    if (variantRequestKey === requestKey) return;
  
    variantRequestKey = requestKey;
    try {
      const data = /** @type {VariantPageData} */ (await request(
        `experiments/${encodeURIComponent(experimentId)}/variants?${buildPageQuery(page, pageSize, query, sortBy, sortOrder)}&deleted=${view === "trash"}`,
      ));
      if (
        state.selectedExperimentId !== experimentId
        || state.variantPage !== page
        || state.variantPageSize !== pageSize
        || state.variantQuery !== query
        || state.variantSort !== sortBy
        || state.variantOrder !== sortOrder
        || state.variantView !== view
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
        || state.variantPageSize !== pageSize
        || state.variantQuery !== query
        || state.variantSort !== sortBy
        || state.variantOrder !== sortOrder
        || state.variantView !== view
      ) return;
      state.variantError = error.message;
      renderSection();
    } finally {
      if (variantRequestKey === requestKey) variantRequestKey = null;
    }
  }
  
  /**
   * 将表格追加到横向滚动容器。
   *
   * @param {HTMLTableElement} table 资源表格
   * @returns {void} 无返回值
   */
  function appendScrollableTable(table) {
    const scrollContainer = document.createElement("div");
    scrollContainer.className = "table-scroll";
    scrollContainer.append(table);
    tableContainer.append(scrollContainer);
    const scope = getTableScrollScope();
    scrollContainer.scrollLeft = tableScrollPositions.get(scope) || 0;
    scrollContainer.addEventListener("scroll", () => {
      tableScrollPositions.set(scope, scrollContainer.scrollLeft);
    }, { passive: true });
  }

  function getTableScrollScope() {
    if (state.selectedModelId !== null) {
      return [
        "versions",
        state.selectedModelId,
        state.versionView,
        state.versionPage,
        state.versionPageSize,
        state.versionQuery,
        state.versionSort,
        state.versionOrder,
      ].join(":");
    }

    if (state.selectedExperimentId !== null) {
      return [
        "variants",
        state.selectedExperimentId,
        state.variantView,
        state.variantPage,
        state.variantPageSize,
        state.variantQuery,
        state.variantSort,
        state.variantOrder,
      ].join(":");
    }

    return [
      state.active,
      state.sectionView,
      state.sectionPage,
      state.sectionPageSize,
      state.sectionQuery,
      state.sectionSort,
      state.sectionOrder,
    ].join(":");
  }
  
  function getSelectionScope() {
    if (state.selectedModelId !== null) {
      return `versions:${state.selectedModelId}:${state.versionView}:${state.versionQuery}`;
    }
  
    if (state.selectedExperimentId !== null) {
      return `variants:${state.selectedExperimentId}:${state.variantView}:${state.variantQuery}`;
    }
  
    if (recyclableSections.has(state.active)) {
      const view = state.active === "versions"
        ? state.versionView
        : state.sectionView;
      return `${state.active}:${view}:${state.sectionQuery}`;
    }
  
    return `${state.active}:${state.sectionQuery}`;
  }
  
  function syncSelectionScope() {
    const scope = getSelectionScope();
  
    if (state.selectionScope === scope) return;
  
    state.selectionScope = scope;
    state.selectedRecordIds.clear();
  }
  
  function updateSelectionControls() {
    const count = state.selectedRecordIds.size;
    const formattedCount = formatInteger(count);
    selectedExportButton.disabled = isExportInProgress();
    selectedExportButton.hidden = (
      count === 0
      || !canExportData()
    );
    selectionCount.textContent = `已选择 ${formattedCount} 条`;
    selectionSummary.hidden = count === 0 || !canExportData();
  }
  
  function updateVisibleSelectionState() {
    const checkboxes = /** @type {HTMLInputElement[]} */ (Array.from(
      tableContainer.querySelectorAll(".record-select-checkbox"),
    ));
  
    for (const checkbox of checkboxes) {
      const selected = state.selectedRecordIds.has(checkbox.value);
      checkbox.checked = selected;
      checkbox.closest("tr")?.classList.toggle("selected-row", selected);
    }
  
    const selectedCount = checkboxes.filter((checkbox) => checkbox.checked).length;
    const selectAll = /** @type {HTMLInputElement | null} */ (
      tableContainer.querySelector(".select-all-checkbox")
    );
  
    if (selectAll !== null) {
      selectAll.checked = checkboxes.length > 0 && selectedCount === checkboxes.length;
      selectAll.indeterminate = selectedCount > 0 && selectedCount < checkboxes.length;
    }
  
    updateSelectionControls();
  }
  
  function appendSelectionHeader(row, records, idField) {
    if (!canExportData()) return;
  
    row.append(createSelectionHeader(
      records,
      idField,
    ));
  }
  
  function appendSelectionCell(row, record, idField) {
    if (!canExportData()) return;
  
    row.append(createSelectionCell(
      record,
      idField,
      row,
    ));
  }
  
  function createSelectionHeader(records, idField) {
    const cell = document.createElement("th");
    cell.className = "selection-column";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "select-all-checkbox";
    checkbox.setAttribute("aria-label", "选择当前页全部记录");
    checkbox.title = "选择当前页全部记录";
    checkbox.addEventListener("change", () => {
      for (const record of records) {
        const identifier = String(record[idField]);
        if (checkbox.checked) {
          state.selectedRecordIds.add(identifier);
        } else {
          state.selectedRecordIds.delete(identifier);
        }
      }
      updateVisibleSelectionState();
    });
    cell.append(checkbox);
    window.setTimeout(updateVisibleSelectionState, 0);
  
    return cell;
  }
  
  function createSelectionCell(record, idField, row) {
    const identifier = String(record[idField]);
    const cell = document.createElement("td");
    cell.className = "selection-column";
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.className = "record-select-checkbox";
    checkbox.value = identifier;
    checkbox.checked = state.selectedRecordIds.has(identifier);
    checkbox.setAttribute("aria-label", `选择记录 ${identifier}`);
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) {
        state.selectedRecordIds.add(identifier);
      } else {
        state.selectedRecordIds.delete(identifier);
      }
      row.classList.toggle("selected-row", checkbox.checked);
      updateVisibleSelectionState();
    });
    row.classList.toggle("selected-row", checkbox.checked);
    cell.append(checkbox);
  
    return cell;
  }
  
  /**
   * 渲染资源列表分页控件。
   *
   * @param {PageData | VersionPageData | VariantPageData} data 分页数据
   * @param {string} label 分页无障碍标签
   * @param {(page: number, pageSize: number) => void} navigate 分页导航方法
   * @returns {void} 无返回值
   */
  function renderPagination(data, label, navigate) {
    tableControls.renderPagination(data, label, navigate);
  }
  
  function canExportData() {
    const permissions = state.user?.permissions || [];
    return permissions.some((permission) => (
      permission === "*"
      || permission === "data.export"
      || permission === "data.*"
    ));
  }
  
  function buildExportPath() {
    const parameters = new URLSearchParams();
    let path;
  
    if (state.selectedModelId !== null) {
      path = `models/${encodeURIComponent(state.selectedModelId)}/versions/export`;
      parameters.set("deleted", String(state.versionView === "trash"));
      if (state.versionQuery) parameters.set("q", state.versionQuery);
      if (state.versionSort) {
        parameters.set("sort", state.versionSort);
        parameters.set("order", state.versionOrder);
      }
    } else if (state.selectedExperimentId !== null) {
      path = `experiments/${encodeURIComponent(state.selectedExperimentId)}/variants/export`;
      parameters.set("deleted", String(state.variantView === "trash"));
      if (state.variantQuery) parameters.set("q", state.variantQuery);
      if (state.variantSort) {
        parameters.set("sort", state.variantSort);
        parameters.set("order", state.variantOrder);
      }
    } else {
      path = `sections/${state.active}/export`;
      if (recyclableSections.has(state.active)) {
        parameters.set(
          "deleted",
          String(
            state.active === "versions"
              ? state.versionView === "trash"
              : state.sectionView === "trash",
          ),
        );
      }
      if (state.sectionQuery) parameters.set("q", state.sectionQuery);
      if (state.sectionSort) {
        parameters.set("sort", state.sectionSort);
        parameters.set("order", state.sectionOrder);
      }
    }
  
    const query = parameters.toString();
    return query ? `${path}?${query}` : path;
  }
  
  function buildPageQuery(
    page,
    pageSize,
    query,
    sortBy = "",
    sortOrder = "asc",
  ) {
    const parameters = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (query) parameters.set("q", query);
    if (sortBy) {
      parameters.set("sort", sortBy);
      parameters.set("order", sortOrder);
    }
    return parameters.toString();
  }
  
  function buildHashQuery(
    page,
    pageSize,
    query,
    sortBy = "",
    sortOrder = "asc",
  ) {
    const parameters = new URLSearchParams();
    if (page > 1) parameters.set("page", String(page));
    if (pageSize !== defaultPageSize) parameters.set("page_size", String(pageSize));
    if (query) parameters.set("q", query);
    if (sortBy) {
      parameters.set("sort", sortBy);
      parameters.set("order", sortOrder);
    }
    const value = parameters.toString();
    return value ? `?${value}` : "";
  }
  
  /**
   * 规范化多字段排序参数。
   *
   * @param {string | null | undefined} sortBy 排序字段
   * @param {string | null | undefined} sortOrder 排序方向
   * @returns {[string, string]} 规范化后的字段和方向
   */
  function normalizeSortParameters(sortBy, sortOrder) {
    const fields = (sortBy || "")
      .split(",")
      .map((field) => field.trim())
      .filter((field, index, values) => field && values.indexOf(field) === index)
      .slice(0, maxSortFields);
  
    if (!fields.length) return ["", "asc"];
  
    const directions = (sortOrder || "")
      .split(",")
      .map((direction) => (direction.trim().toLowerCase() === "desc" ? "desc" : "asc"));
    return [
      fields.join(","),
      fields.map((_field, index) => directions[index] || "asc").join(","),
    ];
  }
  
  /**
   * 解析多字段排序规则。
   *
   * @param {string} sortBy 排序字段
   * @param {string} sortOrder 排序方向
   * @returns {{field: string, order: string}[]} 排序规则列表
   */
  function parseSortRules(sortBy, sortOrder) {
    const [normalizedSort, normalizedOrder] = normalizeSortParameters(
      sortBy,
      sortOrder,
    );
    if (!normalizedSort) return [];
    const fields = normalizedSort.split(",");
    const directions = normalizedOrder.split(",");
    return fields.map((field, index) => ({
      field,
      order: directions[index],
    }));
  }
  
  function parsePageSize(value) {
    const pageSize = Number.parseInt(value || "", 10);
    return pageSizeOptions.includes(pageSize) ? pageSize : defaultPageSize;
  }

  return {
    buildExportPath,
    buildHashQuery,
    buildPageQuery,
    getSectionView,
    loadSectionPage,
    loadVariantPage,
    loadVersionPage,
    normalizeSortParameters,
    parseSortRules,
    parsePageSize,
    renderSection,
    syncDetailRoute,
    updateSelectionControls,
    updateVisibleSelectionState,
  };
}
