"use strict";

/**
 * 创建页面导航控制器。
 *
 * 控制器统一管理资源列表、模型版本和实验分组的路由状态。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   applyRoute: (available: string[]) => void,
 *   navigateToExperimentVariants: (experiment: ExperimentReference, page?: number, query?: string, sortBy?: string, sortOrder?: string, pageSize?: number, view?: string) => void,
 *   navigateToModelVersions: (model: ConsoleModel, page?: number, query?: string, sortBy?: string, sortOrder?: string, pageSize?: number, view?: string) => void,
 *   navigateToOverview: () => void,
 *   navigateToSection: (section: string, page?: number, query?: string, sortBy?: string, sortOrder?: string, pageSize?: number, view?: string) => void,
 *   updateSearchForm: (query: string, placeholder: string) => void
 * }} 页面导航入口
 */
export function createNavigationController({
  applyDefaultRoute,
  buildHashQuery,
  canViewOverview,
  defaultPageSize,
  getAvailableSections,
  loadOverview,
  normalizeSortParameters,
  parsePageSize,
  recyclableSections,
  renderNavigation,
  renderSection,
  resetDetailRoute,
  state,
  tableControls,
}) {
  function updateSearchForm(query, placeholder) {
    tableControls.updateQuery(query, placeholder);
  }
  
  function navigateToOverview() {
    const snapshot = state.snapshot;
  
    if (snapshot === null) return;
  
    if (!canViewOverview(snapshot)) {
      const available = getAvailableSections(snapshot);
  
      if (available.length) navigateToSection(available[0]);
  
      return;
    }
  
    state.active = "overview";
    resetDetailRoute();
    state.sectionData = null;
    state.sectionError = null;
    state.versionData = null;
    state.versionError = null;
    state.variantData = null;
    state.variantError = null;
    window.history.pushState(null, "", "#overview");
    renderNavigation();
    renderSection();
    void loadOverview({ silent: true });
  }
  
  function navigateToSection(
    section,
    page = 1,
    query = "",
    sortBy = "",
    sortOrder = "asc",
    pageSize = defaultPageSize,
    view = "active",
  ) {
    state.active = section;
    state.selectedModelId = null;
    state.selectedModel = null;
    state.selectedExperimentId = null;
    state.selectedExperiment = null;
    state.sectionPage = page;
    state.sectionPageSize = pageSize;
    state.sectionQuery = query;
    state.sectionSort = sortBy;
    state.sectionOrder = sortOrder;
    state.sectionData = null;
    state.sectionError = null;
    state.versionQuery = "";
    state.versionSort = "";
    state.versionOrder = "asc";
    state.versionView = section === "versions" && view === "trash"
      ? "trash"
      : "versions";
    state.sectionView = recyclableSections.has(section) && view === "trash"
      ? "trash"
      : "active";
    state.versionData = null;
    state.versionError = null;
    state.variantQuery = "";
    state.variantSort = "";
    state.variantOrder = "asc";
    state.variantView = "active";
    state.variantData = null;
    state.variantError = null;
    const pageQuery = buildHashQuery(page, pageSize, query, sortBy, sortOrder);
    const hasAlternateView = recyclableSections.has(section) && view === "trash";
    const viewQuery = hasAlternateView
      ? `${pageQuery ? `${pageQuery}&` : "?"}view=${view}`
      : pageQuery;
    window.history.pushState(null, "", `#${section}${viewQuery}`);
    renderNavigation();
    renderSection();
  }
  
  /**
   * 跳转到指定模型的版本列表。
   *
   * @param {ConsoleModel} model 目标模型
   * @param {number} page 页码
   * @param {string} query 查询条件
   * @param {string} sortBy 排序字段
   * @param {string} sortOrder 排序方向
   * @param {number} pageSize 每页数量
   * @param {string} view 列表视图
   * @returns {void} 无返回值
   */
  function navigateToModelVersions(
    model,
    page = 1,
    query = "",
    sortBy = "",
    sortOrder = "asc",
    pageSize = defaultPageSize,
    view = state.versionView,
  ) {
    const modelId = model.model_id;
    state.active = "models";
    state.selectedModelId = modelId;
    state.selectedModel = model;
    state.selectedExperimentId = null;
    state.selectedExperiment = null;
    state.versionPage = page;
    state.versionPageSize = pageSize;
    state.versionQuery = query;
    state.versionSort = sortBy;
    state.versionOrder = sortOrder;
    state.versionView = view;
    state.versionData = null;
    state.versionError = null;
    const pageQuery = buildHashQuery(page, pageSize, query, sortBy, sortOrder);
    const viewQuery = view === "trash"
      ? `${pageQuery ? `${pageQuery}&` : "?"}view=trash`
      : pageQuery;
    window.history.pushState(
      null,
      "",
      `#models/${encodeURIComponent(modelId)}/versions${viewQuery}`,
    );
    renderNavigation();
    renderSection();
  }
  
  /**
   * 跳转到指定实验的分组列表。
   *
   * @param {ExperimentReference} experiment 目标实验
   * @param {number} page 页码
   * @param {string} query 查询条件
   * @param {string} sortBy 排序字段
   * @param {string} sortOrder 排序方向
   * @param {number} pageSize 每页数量
   * @param {string} view 列表视图
   * @returns {void} 无返回值
   */
  function navigateToExperimentVariants(
    experiment,
    page = 1,
    query = "",
    sortBy = "",
    sortOrder = "asc",
    pageSize = defaultPageSize,
    view = state.variantView,
  ) {
    const experimentId = experiment.experiment_id;
    state.active = "experiments";
    state.selectedModelId = null;
    state.selectedModel = null;
    state.selectedExperimentId = experimentId;
    state.selectedExperiment = experiment;
    state.variantPage = page;
    state.variantPageSize = pageSize;
    state.variantQuery = query;
    state.variantSort = sortBy;
    state.variantOrder = sortOrder;
    state.variantView = view;
    state.variantData = null;
    state.variantError = null;
    const pageQuery = buildHashQuery(page, pageSize, query, sortBy, sortOrder);
    const viewQuery = view === "trash"
      ? `${pageQuery ? `${pageQuery}&` : "?"}view=trash`
      : pageQuery;
    window.history.pushState(
      null,
      "",
      `#experiments/${encodeURIComponent(experimentId)}/variants${viewQuery}`,
    );
    renderNavigation();
    renderSection();
  }
  
  function applyRoute(available) {
    const route = window.location.hash.slice(1);
  
    if (!route || /^overview(?:\?.*)?$/.test(route)) {
      const snapshot = state.snapshot;
  
      if (snapshot === null || !canViewOverview(snapshot)) {
        applyDefaultRoute(available);
        return;
      }
  
      state.active = "overview";
      resetDetailRoute();
      return;
    }
  
    const versionRoute = route.match(/^models\/([^/]+)\/versions(?:\?(.+))?$/);
  
    if (versionRoute && available.includes("models")) {
      const parameters = new URLSearchParams(versionRoute[2] || "");
      const parsedPage = Number.parseInt(parameters.get("page") || "1", 10);
      const modelId = decodeURIComponent(versionRoute[1]);
      const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
      const pageSize = parsePageSize(parameters.get("page_size"));
      const query = parameters.get("q") || "";
      const [sortBy, sortOrder] = normalizeSortParameters(
        parameters.get("sort"),
        parameters.get("order"),
      );
      const view = parameters.get("view") === "trash" ? "trash" : "versions";
  
      if (
        state.selectedModelId !== modelId
        || state.versionPage !== page
        || state.versionPageSize !== pageSize
        || state.versionQuery !== query
        || state.versionSort !== sortBy
        || state.versionOrder !== sortOrder
        || state.versionView !== view
      ) {
        state.versionData = null;
        state.versionError = null;
      }
  
      state.active = "models";
      state.selectedModelId = modelId;
      state.selectedExperimentId = null;
      state.selectedExperiment = null;
      state.versionPage = page;
      state.versionPageSize = pageSize;
      state.versionQuery = query;
      state.versionSort = sortBy;
      state.versionOrder = sortOrder;
      state.versionView = view;
      return;
    }
  
    const variantRoute = route.match(/^experiments\/([^/]+)\/variants(?:\?(.+))?$/);
  
    if (variantRoute && available.includes("experiments")) {
      const parameters = new URLSearchParams(variantRoute[2] || "");
      const parsedPage = Number.parseInt(parameters.get("page") || "1", 10);
      const experimentId = decodeURIComponent(variantRoute[1]);
      const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
      const pageSize = parsePageSize(parameters.get("page_size"));
      const query = parameters.get("q") || "";
      const [sortBy, sortOrder] = normalizeSortParameters(
        parameters.get("sort"),
        parameters.get("order"),
      );
      const view = parameters.get("view") === "trash" ? "trash" : "active";
  
      if (
        state.selectedExperimentId !== experimentId
        || state.variantPage !== page
        || state.variantPageSize !== pageSize
        || state.variantQuery !== query
        || state.variantSort !== sortBy
        || state.variantOrder !== sortOrder
        || state.variantView !== view
      ) {
        state.variantData = null;
        state.variantError = null;
      }
  
      state.active = "experiments";
      state.selectedModelId = null;
      state.selectedModel = null;
      state.selectedExperimentId = experimentId;
      state.variantPage = page;
      state.variantPageSize = pageSize;
      state.variantQuery = query;
      state.variantSort = sortBy;
      state.variantOrder = sortOrder;
      state.variantView = view;
      return;
    }
  
    const sectionRoute = route.match(/^([^?]+)(?:\?(.+))?$/);
    const section = sectionRoute ? sectionRoute[1] : "";
    const parameters = new URLSearchParams(sectionRoute ? sectionRoute[2] || "" : "");
    const parsedPage = Number.parseInt(parameters.get("page") || "1", 10);
    const page = Number.isInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1;
    const pageSize = parsePageSize(parameters.get("page_size"));
    const query = parameters.get("q") || "";
    const [sortBy, sortOrder] = normalizeSortParameters(
      parameters.get("sort"),
      parameters.get("order"),
    );
    const view = recyclableSections.has(section) && parameters.get("view") === "trash"
      ? "trash"
      : "active";
  
    if (!available.includes(section)) {
      applyDefaultRoute(available);
      return;
    }
  
    if (
      state.sectionPage !== page
      || state.sectionPageSize !== pageSize
      || state.active !== section
      || state.sectionQuery !== query
      || state.sectionSort !== sortBy
      || state.sectionOrder !== sortOrder
      || (
        recyclableSections.has(section)
        && (section === "versions"
          ? (state.versionView === "trash" ? "trash" : "active")
          : state.sectionView) !== view
      )
    ) {
      state.sectionData = null;
      state.sectionError = null;
    }
    state.active = section;
    state.sectionPage = page;
    state.sectionPageSize = pageSize;
    state.sectionQuery = query;
    state.sectionSort = sortBy;
    state.sectionOrder = sortOrder;
    state.versionView = section === "versions" && view === "trash"
      ? "trash"
      : "versions";
    state.sectionView = recyclableSections.has(section) && view === "trash"
      ? "trash"
      : "active";
    state.selectedModelId = null;
    state.selectedModel = null;
    state.selectedExperimentId = null;
    state.selectedExperiment = null;
    state.versionData = null;
    state.versionError = null;
    state.variantData = null;
    state.variantError = null;
  }

  return {
    applyRoute,
    navigateToExperimentVariants,
    navigateToModelVersions,
    navigateToOverview,
    navigateToSection,
    updateSearchForm,
  };
}
