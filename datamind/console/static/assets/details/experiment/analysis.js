"use strict";

import { createDetailIcon } from "../common.js";

const metricLabels = {
  success_rate: "成功率",
  average_latency_ms: "平均耗时（毫秒）",
  average_probability: "平均预测概率",
  average_score: "平均评分",
};

/** 将常用分组名称显示为中文，保留自定义名称。 */
function groupName(group, id) {
  const name = group?.name || id;
  return { control: "对照组", treatment: "实验组" }[String(name).toLowerCase()] || name;
}

/** 格式化有效数值，缺失样本显示为破折号。 */
function number(value, digits = 2) {
  return typeof value === "number" && Number.isFinite(value)
    ? value.toLocaleString("zh-CN", { maximumFractionDigits: digits }) : "—";
}

/** 格式化比例，不将缺失样本解释为零。 */
function percent(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? `${number(value * 100)}%` : "—";
}

/** 使用文本节点创建元素，避免结果标签被解释为 HTML。 */
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

/** 创建支持窄屏横向滚动的指标表。 */
function table(title, headings, rows) {
  const block = element("div", undefined, "experiment-analysis-block");
  block.append(element("h5", title));
  const scroll = element("div", undefined, "experiment-analysis-scroll");
  scroll.tabIndex = 0;
  scroll.setAttribute("role", "region");
  scroll.setAttribute("aria-label", title);
  const grid = element("table", undefined, "experiment-analysis-table");
  const head = document.createElement("thead");
  const header = document.createElement("tr");
  for (const name of headings) {
    const cell = element("th", name);
    cell.scope = "col";
    header.append(cell);
  }
  head.append(header);
  const body = document.createElement("tbody");
  for (const values of rows) {
    const row = document.createElement("tr");
    values.forEach((value, index) => {
      const cell = element(index === 0 ? "th" : "td");
      if (value instanceof window.Node) cell.append(value);
      else cell.textContent = value;
      if (index === 0) cell.scope = "row";
      row.append(cell);
    });
    body.append(row);
  }
  grid.append(head, body);
  scroll.append(grid);
  block.append(scroll);
  return block;
}


/** 按有效样本汇总指标，并创建统一的概览卡片。 */
function createOverview(data, samplesOnly = false) {
  const values = Object.values(data.metrics?.variants || {});
  const sum = (key) => values.reduce((total, value) => total + (Number.isFinite(value[key]) ? value[key] : 0), 0);
  const completed = sum("completed_count");
  const latencyCount = sum("latency_count");
  const latency = values.reduce((total, value) => total + (
    Number.isFinite(value.average_latency_ms) && Number.isFinite(value.latency_count)
      ? value.average_latency_ms * value.latency_count : 0
  ), 0);
  const cards = element("dl", undefined, "experiment-analysis-cards");
  const overview = [
    ["请求数", number(data.decision_count, 0)],
    ["主体数", number(sum("subject_count"), 0), "各分组主体数之和，同一主体在不同分组分别计数"],
    ["成功率", percent(completed ? sum("success_count") / completed : null)],
    ["平均耗时", latencyCount ? `${number(latency / latencyCount)} 毫秒` : "—"],
  ];
  for (const [label, value, hint] of samplesOnly ? overview.slice(0, 2) : overview) {
    const card = element("div");
    if (hint) card.title = hint;
    card.append(element("dt", label), element("dd", value));
    cards.append(card);
  }
  return cards;
}

/**
 * 创建实验分析区域。
 *
 * 按需读取分析，支持刷新与基准选择，面板关闭时取消未完成请求。
 *
 * @param {Object} options 分析区域依赖
 * @param {string} options.experimentId 实验 ID
 * @param {Function} options.request 已认证的控制台请求函数
 * @param {HTMLDialogElement} options.dialog 所属分析面板
 * @returns {HTMLElement} 实验分析区域
 */
export function createExperimentAnalysisSection({ experimentId, request, dialog }) {
  const section = element("section", undefined, "registry-detail-section experiment-analysis");
  const refresh = element("button", "刷新", "registry-section-link");
  refresh.type = "button";
  const controls = element("label", "比较基准 ", "experiment-analysis-controls");
  const baseline = document.createElement("select");
  baseline.setAttribute("aria-label", "实验分析比较基准");
  baseline.append(new window.Option("默认基准", ""));
  controls.append(baseline);
  const content = element("div", undefined, "experiment-analysis-content");
  content.setAttribute("aria-live", "polite");
  const toolbar = element("div", undefined, "experiment-analysis-toolbar");
  toolbar.append(controls, refresh);
  section.append(toolbar, content);
  let controller;
  let generation = 0;
  let closed = false;

  function render(data) {
    const groups = data.variants || {};
    const metrics = data.metrics?.variants || {};
    const name = (id) => groupName(groups[id], id);
    const selected = baseline.value;
    const control = Object.entries(groups).find(([, group]) => group.is_control);
    const defaultName = control ? name(control[0]) : "对照组";
    baseline.replaceChildren(new window.Option(`默认：${defaultName}`, ""));
    for (const [id] of Object.entries(groups)) {
      baseline.append(new window.Option(name(id), id));
    }
    baseline.value = selected;
    content.replaceChildren();
    const samples = element("p", `${number(data.decision_count, 0)} 次请求 · ${number(Object.values(metrics).reduce((total, value) => total + (value.subject_count || 0), 0), 0)} 个分组主体`, "experiment-analysis-total");
    content.append(samples);
    if (!data.decision_count) {
      content.append(element("p", "暂无实验请求。发起预测后刷新，即可查看分析。", "registry-related-empty"));
    } else {
      const entries = Object.entries(metrics).sort(([left], [right]) => {
        if (left === data.baseline_variant_id) return -1;
        if (right === data.baseline_variant_id) return 1;
        return 0;
      });
      const layout = element("div", undefined, "experiment-analysis-layout");
      const main = element("div", undefined, "experiment-analysis-main");
      const indicators = [];
      if (entries.some(([, value]) => value.score_count > 0 || Number.isFinite(value.average_score))) indicators.push("average_score");
      if (entries.some(([, value]) => value.probability_count > 0 || Number.isFinite(value.average_probability))) indicators.push("average_probability");
      indicators.push("success_rate", "average_latency_ms");
      const signed = (value) => Number.isFinite(value) ? `${value > 0 ? "+" : ""}${number(value)}` : "—";
      const headings = ["指标"];
      for (const [id] of entries) {
        headings.push(`${name(id)}${id === data.baseline_variant_id ? " · 基准" : ""}`);
        if (id !== data.baseline_variant_id) headings.push("差异", "相对变化");
      }
      const rows = indicators.map((metric) => {
        const row = [metricLabels[metric]];
        const rate = metric === "success_rate" || metric === "average_probability";
        for (const [id, value] of entries) {
          const cell = element("div", undefined, "experiment-analysis-value");
          const primary = element("strong", rate ? percent(value[metric]) : `${number(value[metric])}${metric === "average_latency_ms" && Number.isFinite(value[metric]) ? " ms" : ""}`);
          cell.append(primary);
          let sample;
          if (metric === "average_score" || metric === "average_probability") {
            const kind = metric === "average_score" ? "score" : "probability";
            const format = kind === "score" ? number : percent;
            sample = `${number(value[`${kind}_count`], 0)} 个有效样本`;
            if (value[`${kind}_count`]) sample += `；最小值—最大值 ${format(value[`minimum_${kind}`])}—${format(value[`maximum_${kind}`])}`;
          } else {
            const count = metric === "success_rate" ? value.completed_count : value.latency_count;
            sample = `${number(count, 0)} 个有效样本`;
          }
          primary.title = sample;
          primary.tabIndex = 0;
          primary.setAttribute("aria-label", `${primary.textContent}；${sample}`);
          cell.append(element("span", sample, "experiment-analysis-sample-hint"));
          row.push(cell);
          if (id !== data.baseline_variant_id) {
            const comparison = data.metrics?.comparisons?.[id]?.[metric];
            const absolute = comparison?.absolute_lift;
            const relative = comparison?.relative_lift;
            const delta = element("span", Number.isFinite(absolute) ? `${signed(rate ? absolute * 100 : absolute)}${rate ? " pp" : metric === "average_latency_ms" ? " ms" : ""}` : "—");
            if (rate) delta.title = "pp 表示百分点，即两组比例的绝对差异。";
            row.push(delta, Number.isFinite(relative) ? `${signed(relative * 100)}%` : "—");
          }
        }
        return row;
      });
      main.append(table("指标比较", headings, rows));
      const labels = [];
      for (const [id, value] of entries) {
        for (const [label, count] of Object.entries(value.prediction_counts || {})) labels.push([name(id), label, number(count, 0)]);
      }
      if (labels.length) main.append(table("分类标签分布", ["分组", "预测标签", "次数"], labels));
      const traffic = element("aside", undefined, "experiment-analysis-traffic");
      traffic.setAttribute("aria-label", "分组流量");
      traffic.append(element("h5", "分组流量"), element("p", "已记录的实验请求", "experiment-analysis-note"));
      for (const [id, value] of entries) {
        const group = element("div", undefined, "experiment-analysis-group");
        const identity = element("div", undefined, "experiment-analysis-group-heading");
        identity.append(element("strong", name(id)), element("span", percent(value.traffic_ratio)));
        const meter = element("progress");
        meter.max = 1;
        meter.value = value.traffic_ratio || 0;
        meter.setAttribute("aria-label", `${name(id)} 流量占比`);
        const counts = element("dl", undefined, "experiment-analysis-samples");
        for (const [label, count] of [["请求数", value.total_count], ["主体数", value.subject_count]]) {
          const item = element("div");
          item.append(element("dt", label), element("dd", number(count, 0)));
          counts.append(item);
        }
        group.append(identity, meter, counts);
        traffic.append(group);
      }
      layout.append(main, traffic);
      content.append(layout);
      const states = element("div", undefined, "experiment-analysis-states");
      states.append(table("执行状态", ["分组", "执行数", "已结束", "等待中", "执行中", "成功", "失败", "超时", "已取消"], entries.map(([id, value]) => [
        name(id), number(value.execution_count, 0), number(value.completed_count, 0),
        ...["queued", "running", "success", "failed", "timeout", "cancelled"].map((status) => number(value[`${status}_count`], 0)),
      ])));
      content.append(states);
    }
    for (const warning of data.warnings || []) content.append(element("p", warning, "experiment-analysis-note"));
  }

  async function load() {
    controller?.abort();
    controller = new window.AbortController();
    const current = ++generation;
    section.setAttribute("aria-busy", "true");
    refresh.disabled = true;
    baseline.disabled = true;
    content.replaceChildren(element("p", "正在加载实验分析…", "registry-related-empty"));
    const query = baseline.value ? `?baseline_variant_id=${encodeURIComponent(baseline.value)}` : "";
    try {
      const data = await request(`experiments/${encodeURIComponent(experimentId)}/analysis${query}`, { signal: controller.signal });
      if (!closed && current === generation) render(data);
    } catch (error) {
      if (!closed && current === generation && error?.name !== "AbortError") {
        content.replaceChildren(element("p", error instanceof Error ? error.message : "实验分析加载失败", "experiment-analysis-note"));
      }
    } finally {
      if (!closed && current === generation) {
        section.setAttribute("aria-busy", "false");
        refresh.disabled = false;
        baseline.disabled = false;
      }
    }
  }

  refresh.addEventListener("click", () => void load());
  baseline.addEventListener("change", () => void load());
  dialog.addEventListener("close", () => {
    closed = true;
    generation += 1;
    controller?.abort();
  }, { once: true });
  void load();
  return section;
}

/**
 * 打开独立实验分析面板，关闭后返回来源页面。
 *
 * @param {Object} options 面板依赖
 * @param {Object} options.experiment 实验信息
 * @param {Function} options.request 已认证的控制台请求函数
 * @param {HTMLDialogElement} [options.parentDialog] 来源详情抽屉
 * @param {Function} options.createStatusBadge 状态徽标创建器
 * @returns {HTMLDialogElement} 实验分析面板
 */
export function showExperimentAnalysisPanel({ experiment, request, parentDialog, createStatusBadge }) {
  const dialog = element("dialog", undefined, "experiment-analysis-dialog");
  const header = element("header");
  const identity = element("div");
  const title = element("h3", "实验分析");
  title.id = "experiment-analysis-title";
  dialog.setAttribute("aria-labelledby", title.id);
  const titleRow = element("div", undefined, "experiment-analysis-title-row");
  titleRow.append(title);
  titleRow.append(createStatusBadge(experiment.status));
  identity.append(titleRow, element("p", experiment.name || experiment.experiment_id));
  const close = element("button", "×", "registry-drawer-close");
  close.type = "button";
  close.setAttribute("aria-label", "关闭实验分析");
  close.addEventListener("click", () => dialog.close());
  header.append(identity, close);
  const body = element("div", undefined, "experiment-analysis-body");
  const analysis = createExperimentAnalysisSection({ experimentId: experiment.experiment_id, request, dialog });
  header.insertBefore(analysis.querySelector(".experiment-analysis-toolbar"), close);
  body.append(analysis);
  const footer = element("footer");
  const back = element("button", parentDialog ? "返回实验详情" : "返回实验列表", "secondary-button");
  back.type = "button";
  back.addEventListener("click", () => dialog.close());
  footer.append(back);
  dialog.append(header, body, footer);
  const dismiss = () => dialog.close();
  parentDialog?.addEventListener("close", dismiss, { once: true });
  dialog.addEventListener("close", () => {
    parentDialog?.removeEventListener("close", dismiss);
    dialog.remove();
  }, { once: true });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  document.body.append(dialog);
  dialog.showModal();
  return dialog;
}

/**
 * 创建适合详情抽屉的分析摘要，保持固定宽度布局。
 *
 * @param {Object} options 摘要依赖
 * @param {string} options.experimentId 实验 ID
 * @param {Function} options.request 已认证的控制台请求函数
 * @param {HTMLDialogElement} options.dialog 所属详情抽屉
 * @param {Function} [options.onViewAnalysis] 打开完整分析
 * @returns {HTMLElement} 分析摘要区域
 */
export function createExperimentAnalysisSummary({ experimentId, request, dialog, onViewAnalysis }) {
  const section = element("section", undefined, "registry-detail-section experiment-analysis-compact");
  const heading = element("div", undefined, "registry-section-heading");
  const title = element("h4");
  title.append(createDetailIcon("monitor", "registry-section-icon"), document.createTextNode("实验分析"));
  heading.append(title);
  if (onViewAnalysis) {
    const view = element("button", "查看全部", "registry-section-link");
    view.type = "button";
    view.addEventListener("click", onViewAnalysis);
    heading.append(view);
  }
  const content = element("div");
  content.setAttribute("aria-live", "polite");
  section.append(heading, content);
  let controller;
  let generation = 0;
  let closed = false;

  async function load() {
    controller?.abort();
    controller = new window.AbortController();
    const current = ++generation;
    section.setAttribute("aria-busy", "true");
    content.replaceChildren(element("p", "正在加载分析摘要…", "registry-related-empty"));
    try {
      const data = await request(`experiments/${encodeURIComponent(experimentId)}/analysis`, { signal: controller.signal });
      if (closed || current !== generation) return;
      content.replaceChildren(createOverview(data));
      if (!data.decision_count) {
        content.append(element("p", "暂无实验请求。发起预测后可查看分析。", "registry-related-empty"));
      } else {
        for (const [id, value] of Object.entries(data.metrics?.variants || {})) {
          const group = element("div", undefined, "experiment-analysis-group");
          const identity = element("div", undefined, "experiment-analysis-group-heading");
          identity.append(element("strong", groupName(data.variants?.[id], id)), element("span", percent(value.traffic_ratio)));
          const meter = element("progress");
          meter.max = 1;
          meter.value = value.traffic_ratio || 0;
          meter.setAttribute("aria-label", `${groupName(data.variants?.[id], id)} 流量占比`);
          const prediction = value.score_count ? `平均评分 ${number(value.average_score)}`
            : value.probability_count ? `平均概率 ${percent(value.average_probability)}` : "暂无有效预测样本";
          group.append(identity, meter, element("p", `${number(value.total_count, 0)} 次请求 · ${prediction}`, "experiment-analysis-note"));
          content.append(group);
        }
      }
    } catch (error) {
      if (!closed && current === generation && error?.name !== "AbortError") {
        content.replaceChildren(element("p", error instanceof Error ? error.message : "分析摘要加载失败", "experiment-analysis-note"));
      }
    } finally {
      if (!closed && current === generation) {
        section.setAttribute("aria-busy", "false");
      }
    }
  }
  dialog.addEventListener("close", () => {
    closed = true;
    generation += 1;
    controller?.abort();
  }, { once: true });
  void load();
  return section;
}
