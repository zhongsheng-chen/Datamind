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
  mountDetailDrawer,
} from "./common.js";

/**
 * @typedef {Object} ScorecardScalingParameters
 * @property {number} [scorecard_points] 基准分
 * @property {number} [pdo] 好坏比翻倍对应的分差
 * @property {number} [odds] 基准赔率
 * @property {number} [min] 目标最低分
 * @property {number} [max] 目标最高分
 */

/**
 * @typedef {Object} ScorecardScaling
 * @property {string|null} method 刻度方法
 * @property {ScorecardScalingParameters} parameters 刻度参数
 * @property {number} minimum_score 理论最低分
 * @property {number} maximum_score 理论最高分
 * @property {boolean} intercept_based 是否基于截距
 * @property {boolean} reverse_scorecard 是否反向评分
 * @property {boolean} rounding 是否对分值取整
 */

/**
 * @typedef {Object} ScorecardEstimator
 * @property {string} class_name 估计器类名
 */

/**
 * @typedef {Object} ScorecardVariable
 * @property {string} name 变量名称
 * @property {string} dtype 变量类型
 * @property {string} status 分箱状态
 * @property {boolean} selected 是否入模
 * @property {number} n_bins 分箱数量
 * @property {number|null} iv 信息值
 * @property {number|null} js JS 散度
 * @property {number|null} gini 基尼系数
 * @property {number|null} quality_score 分箱质量分
 * @property {Array.<Object.<string, *>>} bins 分箱明细
 */

/**
 * @typedef {Object} ScorecardDetails
 * @property {ScorecardScaling} scaling 评分刻度
 * @property {ScorecardEstimator} estimator 估计器信息
 * @property {number} variable_count 变量数量
 * @property {number} selected_variable_count 入模变量数量
 * @property {ScorecardVariable[]} variables 变量分箱信息
 */

/**
 * 创建版本详情控制器。
 *
 * 版本详情以版本身份、文件信息和关联资源为核心。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {(record: Object) => void} 打开版本详情抽屉
 */
export function createVersionDetailController({
  buildPageQuery,
  createCopyableNavigationLink,
  createStatusBadge,
  formatTime,
  getRecordActions,
  hasCapability,
  navigateToModelVersions,
  navigateToSection,
  openDeploymentCreateDialog,
  request,
  runRecordAction,
  showModelDrawer,
  toast,
}) {
  function createFileIdentifier(value, label, truncate = false) {
    if (!value) return "—";
    const identifier = createCopyableNavigationLink(value, null, label);
    if (identifier instanceof HTMLElement) {
      identifier.classList.add("registry-version-file-identifier");
      identifier.classList.toggle(
        "registry-version-file-identifier-truncated",
        truncate,
      );
      identifier.title = value;
    }
    return identifier;
  }

  function createFileInformationSection(version, dialog) {
    return createDetailSection(
      "文件信息",
      [
        ["制品 ID", () => createFileIdentifier(
          version.current_artifact_id,
          "制品 ID",
        )],
        ["Bento Tag", () => createFileIdentifier(
          version.bento_tag,
          "Bento Tag",
        )],
        ["文件路径", () => createFileIdentifier(
          version.model_key,
          "文件路径",
          true,
        )],
        ["SHA-256 校验值", () => createFileIdentifier(
          version.artifact_sha256,
          "SHA-256 校验值",
          true,
        )],
      ],
      dialog,
      "artifact",
      appendRequestDetail,
    );
  }

  function formatScorecardNumber(value, digits = 4) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return number.toFixed(digits).replace(/\.?0+$/, "");
  }

  function formatScorecardPercentage(value) {
    if (value === null || value === undefined || value === "") return "—";
    const number = Number(value);
    return Number.isFinite(number) ? `${(number * 100).toFixed(2)}%` : "—";
  }

  /**
   * 创建评分卡参数区块。
   *
   * @param {ScorecardDetails} scorecardDetails 评分卡详情
   * @param {HTMLDialogElement} dialog 版本详情抽屉
   * @returns {HTMLElement} 评分卡参数区块
   */
  function createScorecardParameters(scorecardDetails, dialog) {
    const scaling = scorecardDetails.scaling;
    const parameters = scaling.parameters;
    const methodLabels = {
      pdo_odds: "PDO 与赔率",
      min_max: "最小值与最大值",
    };
    const fields = [
      ["评分刻度", methodLabels[scaling.method] || scaling.method],
    ];
    if (scaling.method === "pdo_odds") {
      fields.push(
        ["基准分", parameters.scorecard_points],
        ["PDO", parameters.pdo],
        ["基准赔率", parameters.odds],
      );
    } else if (scaling.method === "min_max") {
      fields.push(
        ["目标最低分", parameters.min],
        ["目标最高分", parameters.max],
      );
    }
    fields.push(
      ["理论最低分", formatScorecardNumber(scaling.minimum_score, 2)],
      ["理论最高分", formatScorecardNumber(scaling.maximum_score, 2)],
      ["变量数", scorecardDetails.variable_count],
      ["入模变量数", scorecardDetails.selected_variable_count],
      ["估计器", scorecardDetails.estimator.class_name],
      ["基于截距", scaling.intercept_based ? "是" : "否"],
      ["反向评分", scaling.reverse_scorecard ? "是" : "否"],
      ["分值取整", scaling.rounding ? "是" : "否"],
    );
    return createDetailSection(
      "评分卡参数",
      fields,
      dialog,
      "prediction",
      appendRequestDetail,
    );
  }

  /**
   * 创建变量分箱明细表。
   *
   * @param {ScorecardVariable} variable 变量分箱信息
   * @returns {HTMLDivElement} 分箱明细表容器
   */
  function createBinningTable(variable) {
    const wrapper = document.createElement("div");
    wrapper.className = "scorecard-binning-table-scroll";
    wrapper.tabIndex = 0;
    wrapper.setAttribute("role", "region");
    const label = `${variable.name} 分箱明细`;
    wrapper.setAttribute("aria-label", `${label}，可横向滚动`);
    const table = document.createElement("table");
    table.className = "scorecard-binning-table";
    table.setAttribute("aria-label", label);
    const columns = [
      ["Bin", "分箱"],
      ["Count", "样本数"],
      ["Count (%)", "样本占比"],
      ["Non-event", "非事件数"],
      ["Event", "事件数"],
      ["Event rate", "事件率"],
      ["WoE", "WoE"],
      ["IV", "分箱 IV"],
      ["JS", "分箱 JS"],
      ["Points", "分值"],
    ];
    const head = document.createElement("thead");
    const heading = document.createElement("tr");
    for (const [, label] of columns) {
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.textContent = label;
      heading.append(cell);
    }
    head.append(heading);
    const body = document.createElement("tbody");
    for (const bin of variable.bins) {
      const row = document.createElement("tr");
      for (const [key] of columns) {
        const cell = document.createElement("td");
        const value = bin[key];
        cell.textContent = key === "Bin"
          ? String(value ?? "—")
          : ["Count (%)", "Event rate"].includes(key)
            ? formatScorecardPercentage(value)
            : formatScorecardNumber(value);
        row.append(cell);
      }
      body.append(row);
    }
    table.append(head, body);
    wrapper.append(table);
    return wrapper;
  }

  /**
   * 创建变量统计指标。
   *
   * 集中展示模型保存的变量级系数与统计值。
   *
   * @param {ScorecardVariable} variable 变量分箱信息
   * @returns {HTMLDListElement} 变量统计指标
   */
  function createVariableStatistics(variable) {
    const list = document.createElement("dl");
    list.className = "scorecard-variable-statistics";
    list.setAttribute("aria-label", `${variable.name} 变量统计`);
    const coefficientBin = variable.bins.find((bin) => (
      bin["Coefficient"] !== null && bin["Coefficient"] !== undefined
    ));
    const fields = [
      ["回归系数", formatScorecardNumber(coefficientBin?.["Coefficient"])],
      ["IV", formatScorecardNumber(variable.iv)],
      ["Gini", formatScorecardNumber(variable.gini)],
      ["JS", formatScorecardNumber(variable.js)],
      ["质量分", formatScorecardNumber(variable.quality_score)],
      ["分箱状态", variable.status],
    ];
    for (const [label, value] of fields) appendRequestDetail(list, label, value);
    return list;
  }

  /**
   * 排列变量分箱的展示顺序。
   *
   * 已入模变量优先，同组按 IV 降序排列，缺少有效 IV 的变量置后。
   * IV 相同时保留原顺序，不修改模型保存的变量数组。
   *
   * @param {ScorecardVariable[]} variables 变量分箱信息
   * @returns {ScorecardVariable[]} 排序后的变量分箱信息
   */
  function sortScorecardVariables(variables) {
    return [...variables].sort((left, right) => {
      const selectedOrder = Number(right.selected) - Number(left.selected);
      if (selectedOrder !== 0) return selectedOrder;
      if (!Number.isFinite(left.iv)) return Number.isFinite(right.iv) ? 1 : 0;
      if (!Number.isFinite(right.iv)) return -1;
      return right.iv - left.iv;
    });
  }

  /**
   * 创建变量分箱区块。
   *
   * @param {ScorecardDetails} scorecardDetails 评分卡详情
   * @returns {HTMLElement} 变量分箱区块
   */
  function createBinningSection(scorecardDetails) {
    const section = document.createElement("section");
    section.className = "registry-detail-section scorecard-binning-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("config", "registry-section-icon"),
      document.createTextNode("变量分箱"),
    );
    section.append(heading);
    for (const variable of sortScorecardVariables(scorecardDetails.variables)) {
      const details = document.createElement("details");
      details.className = "scorecard-variable";
      const summary = document.createElement("summary");
      const identity = document.createElement("span");
      identity.className = "scorecard-variable-identity";
      const name = document.createElement("strong");
      name.textContent = variable.name;
      const type = document.createElement("span");
      const typeLabels = { numerical: "数值型", categorical: "类别型" };
      type.textContent = typeLabels[variable.dtype] || variable.dtype;
      identity.append(name, type);
      const metrics = document.createElement("span");
      metrics.className = "scorecard-variable-metrics";
      const metricValues = [
        variable.selected ? "已入模" : "未入模",
        `分箱数 ${variable.n_bins}`,
      ];
      for (const value of metricValues) {
        const metric = document.createElement("span");
        metric.textContent = value;
        metrics.append(metric);
      }
      summary.append(
        identity,
        createDetailIcon("arrow", "scorecard-variable-toggle"),
        metrics,
      );
      details.append(
        summary,
        createVariableStatistics(variable),
        createBinningTable(variable),
      );
      section.append(details);
    }
    return section;
  }

  async function loadRelatedVersionData(version) {
    const query = `version_id:${version.version_id}`;
    const sections = ["deployments", "routings", "runtimes"];
    const results = await Promise.allSettled(sections.map((section) => request(
      `sections/${section}?${buildPageQuery(
        1,
        1,
        query,
        "updated_at",
        "desc",
      )}`,
    )));
    return Object.fromEntries(sections.map((section, index) => {
      const result = results[index];
      return [section, result.status === "fulfilled" ? result.value : null];
    }));
  }

  function createRelatedResourceCard({
    icon,
    label,
    total,
    onClick,
  }) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "registry-model-usage-item";
    button.setAttribute("aria-label", `查看${label}，共 ${total} 个`);
    const iconContainer = createDetailIcon(icon, "registry-model-usage-icon");
    iconContainer.classList.add(icon);
    const content = document.createElement("span");
    const name = document.createElement("span");
    name.className = "registry-model-usage-label";
    name.textContent = label;
    const value = document.createElement("strong");
    value.textContent = String(total);
    content.append(name, value);
    button.append(iconContainer, content);
    button.addEventListener("click", onClick);
    return button;
  }

  function createRelatedResourcesSection(version, related, dialog) {
    const section = document.createElement("section");
    section.className = [
      "registry-detail-section",
      "registry-version-related-section",
    ].join(" ");
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("link", "registry-section-icon"),
      document.createTextNode("关联资源"),
    );
    const grid = document.createElement("div");
    grid.className = "registry-model-usage-grid registry-version-related-grid";
    const definitions = [
      ["deployments", "model", "部署"],
      ["routings", "routing", "路由"],
      ["runtimes", "runtime", "运行实例"],
    ];
    for (const [key, icon, label] of definitions) {
      const data = related[key];
      if (data === null) continue;
      grid.append(createRelatedResourceCard({
        icon,
        label,
        total: Number(data.total || 0),
        onClick: () => {
          dialog.close();
          navigateToSection(
            key,
            1,
            `version_id:${version.version_id}`,
          );
        },
      }));
    }
    if (grid.childElementCount === 0) {
      const empty = document.createElement("p");
      empty.className = "registry-related-empty";
      empty.textContent = "暂时无法获取关联资源";
      section.append(heading, empty);
      return section;
    }
    section.append(heading, grid);
    return section;
  }

  function appendVersionFooter(dialog, version, related) {
    const buttons = [];
    const actions = getRecordActions("versions", version);
    const deploymentTotal = Number(related.deployments?.total || 0);
    if (deploymentTotal > 0) {
      const button = createDetailAction("查看部署", "model");
      button.addEventListener("click", () => {
        dialog.close();
        navigateToSection(
          "deployments",
          1,
          `version_id:${version.version_id}`,
        );
      });
      buttons.push(button);
    } else if (
      !version.deleted_at
      && String(version.status || "").toLowerCase() === "active"
      && hasCapability("deployments.create")
    ) {
      const button = createDetailAction("部署版本", "deploy", "primary");
      button.addEventListener("click", () => {
        dialog.close();
        Promise.resolve(openDeploymentCreateDialog(version)).catch(
          (error) => toast(error.message),
        );
      });
      buttons.push(button);
    }
    const lifecycle = actions.find((action) => (
      action.action === "deactivate" || action.action === "activate"
    ));
    if (lifecycle) {
      const activating = lifecycle.action === "activate";
      const button = createDetailAction(
        activating ? "激活版本" : "停用版本",
        activating ? "start" : "deactivate",
        activating ? "primary" : "danger",
      );
      button.addEventListener("click", () => {
        dialog.close();
        runRecordAction(lifecycle, version);
      });
      buttons.push(button);
    }
    appendDetailFooter(dialog, buttons);
  }

  async function loadVersionDrawer(record) {
    const versionId = String(record.version_id || "");
    if (!versionId) {
      toast("版本 ID 不存在");
      return;
    }
    try {
      const version = await request(
        `versions/${encodeURIComponent(versionId)}/detail`,
      );
      const related = await loadRelatedVersionData(version);
      const { dialog, body } = createDetailDrawer(
        "版本详情",
        "version-detail-drawer",
      );
      const modelLink = document.createElement("button");
      modelLink.type = "button";
      modelLink.className = "request-link";
      modelLink.textContent = version.model_name || version.model_id || "—";
      modelLink.addEventListener("click", () => {
        dialog.close();
        showModelDrawer({ model_id: version.model_id });
      });
      body.append(
        createDetailSummary({
          icon: "model",
          title: version.model_name || "未命名模型",
          subtitle: version.version || "—",
          status: version.status,
          badges: [
            createDetailBadge(version.framework, "framework"),
            createDetailBadge(version.model_type, "type"),
            createDetailBadge(version.task_type, "task"),
          ],
          createStatusBadge,
        }),
        createDetailSection(
          "基本信息",
          [
            ["版本 ID", () => createCopyableNavigationLink(
              version.version_id,
              () => {
                dialog.close();
                navigateToModelVersions({
                  model_id: version.model_id,
                  name: version.model_name || version.model_id,
                }, 1, `version_id:${version.version_id}`);
              },
              "版本 ID",
            )],
            ["模型名称", modelLink],
            ["显示名称", version.display_name],
            ["状态", createStatusBadge(version.status)],
            ["框架", version.framework],
            ["类型", version.model_type],
            ["任务类型", version.task_type],
            ["描述", version.description],
            ["创建时间", formatTime(version.created_at)],
            ["更新时间", formatTime(version.updated_at)],
          ],
          dialog,
          "info",
          appendRequestDetail,
        ),
        createFileInformationSection(version, dialog),
        ...(version.task_type === "scoring" && version.scorecard?.details
          ? [
              createScorecardParameters(version.scorecard.details, dialog),
              createBinningSection(version.scorecard.details),
            ]
          : []),
        createRelatedResourcesSection(version, related, dialog),
      );
      appendVersionFooter(dialog, version, related);
      mountDetailDrawer(dialog, { section: "versions", id: version.version_id });
    } catch (error) {
      toast(error instanceof Error ? error.message : "版本详情加载失败");
    }
  }

  return (record) => {
    void loadVersionDrawer(record);
  };
}
