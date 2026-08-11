"use strict";

/**
 * 创建概览页控制器。
 *
 * 控制器负责导航、指标摘要、请求趋势和模型调用排行的展示。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   renderModelUsage: () => void,
 *   renderNavigation: () => void,
 *   renderRequestTrend: () => void,
 *   renderSummary: () => void,
 *   renderTrendRangeSelector: () => void
 * }} 概览页渲染入口
 */
export function createDashboardController({
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
  navigateToOverview,
  navigateToSection,
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
}) {
  function renderNavigation() {
    const snapshot = state.snapshot;
  
    if (snapshot === null) return;
  
    navigation.replaceChildren();
    renderAccountManagement();
  
    if (canViewOverview(snapshot)) {
      const overviewButton = document.createElement("button");
      overviewButton.type = "button";
      overviewButton.className = `nav-button${state.active === "overview" ? " active" : ""}`;
      const overviewLabel = document.createElement("span");
      overviewLabel.textContent = "概览";
      overviewButton.append(overviewLabel);
      overviewButton.addEventListener("click", () => {
        navigateToOverview();
        sidebar.classList.remove("open");
      });
      navigation.append(overviewButton);
    }
  
    for (const [key, config] of Object.entries(sections)) {
      if (!snapshot.access[key] || accountSectionKeys.has(key)) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = `nav-button${state.active === key ? " active" : ""}`;
      const label = document.createElement("span");
      label.textContent = config.label;
      const count = document.createElement("span");
      count.className = "nav-count";
      const total = snapshot.counts[key];
      count.textContent = formatNavigationCount(total);
  
      if (Number.isInteger(total)) {
        const exactCount = formatInteger(total);
        count.title = exactCount;
        count.setAttribute(
          "aria-label",
          `${config.label}共 ${exactCount} 条`,
        );
      }
      button.append(label, count);
      button.addEventListener("click", () => {
        navigateToSection(key);
        sidebar.classList.remove("open");
      });
      navigation.append(button);
    }
  }
  
  function renderSummary() {
    const snapshot = state.snapshot;
  
    if (snapshot === null) return;
  
    summaryGrid.replaceChildren();
    const canViewRequests = Boolean(snapshot.access.requests);
    const visible = state.active === "overview" && canViewRequests;
    const summary = snapshot.request_summary;
    summaryGrid.hidden = !visible;
  
    if (!visible) return;
  
    const requestCount = summary?.request_count ?? null;
    const previousCount = summary?.previous_request_count ?? null;
    const changeRate = summary?.change_rate ?? null;
    const modelUsage = Array.isArray(snapshot.model_usage)
      ? snapshot.model_usage
      : [];
    const totalRequestCount = modelUsage.reduce((total, record) => {
      const count = Number(record.total_count);
      return total + (Number.isFinite(count) ? count : 0);
    }, 0);
    let changeDescription = "暂无调用数据";
  
    if (requestCount !== null && previousCount !== null) {
      if (previousCount > 0 && changeRate !== null) {
        changeDescription = `较前 24 小时 ${formatSignedPercentage(changeRate)}`;
      } else if (requestCount > 0) {
        changeDescription = "前 24 小时暂无调用";
      }
    }
  
    const metrics = [
      {
        icon: "activity",
        tone: "primary",
        label: "近 24 小时 API 调用",
        value: requestCount === null ? "—" : formatInteger(requestCount),
        detail: changeDescription,
      },
      {
        icon: "check",
        tone: "success",
        label: "近 24 小时成功率",
        value: formatCompactPercentage(summary?.success_rate ?? null),
        detail: summary === null || summary === undefined
          ? "暂无调用数据"
          : `成功 ${formatInteger(summary.success_count)} · 失败 ${formatInteger(summary.failed_count)}`,
      },
      {
        icon: "latency",
        tone: "warning",
        label: "近 24 小时 P95 耗时",
        value: formatOptionalDuration(summary?.p95_latency_ms ?? null),
        detail: `平均耗时 ${formatOptionalDuration(summary?.average_latency_ms ?? null)}`,
      },
      {
        icon: "total",
        tone: "neutral",
        label: "累计 API 调用",
        value: formatInteger(totalRequestCount),
        detail: "所有模型历史累计",
      },
    ];
  
    for (const metric of metrics) {
      const card = document.createElement("article");
      card.className = `overview-metric-card ${metric.tone}`;
      const header = document.createElement("div");
      header.className = "overview-metric-heading";
      header.append(createOverviewMetricIcon(metric.icon));
      const label = document.createElement("span");
      label.textContent = metric.label;
      header.append(label);
      const value = document.createElement("strong");
      value.textContent = metric.value;
      const detail = document.createElement("small");
      detail.textContent = metric.detail;
      card.append(header, value, detail);
      summaryGrid.append(card);
    }
  }
  
  function createOverviewMetricIcon(kind) {
    const namespace = "http://www.w3.org/2000/svg";
    const container = document.createElement("span");
    container.className = "overview-metric-icon";
    container.setAttribute("aria-hidden", "true");
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
  
    const paths = {
      activity: [
        "M4 16.5 9 11l4 4 7-8",
        "M15 7h5v5",
      ],
      check: [
        "M5 12.5 9.2 17 19 7",
      ],
      latency: [
        "M12 4a8 8 0 1 1-8 8",
        "M12 7v5l3 2",
        "M4 4v5h5",
      ],
      total: [
        "M5 19V9",
        "M12 19V5",
        "M19 19v-7",
      ],
    };
  
    for (const data of paths[kind] || paths.activity) {
      const path = document.createElementNS(namespace, "path");
      path.setAttribute("d", data);
      svg.append(path);
    }
  
    container.append(svg);
    return container;
  }
  
  function renderRequestTrend() {
    const snapshot = state.snapshot;
  
    if (snapshot === null) return;
  
    const records = Array.isArray(snapshot.request_trend)
      ? snapshot.request_trend
      : [];
    const canViewRequests = Boolean(snapshot.access.requests);
    const visible = state.active === "overview" && canViewRequests;
    renderTrendRangeSelector();
    trendPanel.hidden = !visible;
    trendChart.replaceChildren();
  
    if (!visible) return;
  
    const normalizeCount = (value) => {
      const count = Number(value);
      return Number.isFinite(count) && count > 0 ? count : 0;
    };
    const counts = records.map((record) => normalizeCount(record.count));
    const successCounts = records.map((record) => normalizeCount(record.success_count));
    const failedCounts = records.map((record) => normalizeCount(record.failed_count));
    const failureRates = records.map((record, index) => (
      counts[index] > 0
        ? failedCounts[index] / counts[index]
        : 0
    ));
    const total = counts.reduce((sum, count) => sum + count, 0);
    const successTotal = successCounts.reduce((sum, count) => sum + count, 0);
    const failedTotal = failedCounts.reduce((sum, count) => sum + count, 0);
    const aggregateFailureRate = total > 0 ? failedTotal / total : 0;
    trendVolumeTotal.textContent = formatInteger(total);
    trendFailureRate.textContent = total > 0
      ? formatPercentage(aggregateFailureRate)
      : "—";
  
    if (!records.length) {
      const empty = document.createElement("div");
      empty.className = "trend-empty";
      empty.textContent = "暂无 API 调用趋势数据";
      trendChart.append(empty);
      return;
    }
  
    const namespace = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(namespace, "svg");
    svg.setAttribute("viewBox", "0 0 1440 330");
    svg.setAttribute("role", "img");
    svg.setAttribute(
      "aria-label",
      `${trendRangeDescriptions[state.trendRange]}，共 ${total} 次 API 调用，成功 ${successTotal} 次，失败 ${failedTotal} 次`,
    );
  
    const left = 58;
    const right = 1388;
    const volumeTop = 26;
    const volumeBottom = 186;
    const errorTop = 232;
    const errorBottom = 276;
    const volumeScale = getNiceVolumeScale(
      Math.max(0, ...counts),
    );
    const volumeMaximum = volumeScale.maximum;
    const failureMaximum = Math.max(0.01, ...failureRates);
    const x = (index) => left + ((right - left) * index) / Math.max(records.length - 1, 1);
    const volumeY = (count) => (
      volumeBottom
      - ((volumeBottom - volumeTop) * count) / volumeMaximum
    );
    const failureY = (rate) => (
      errorBottom
      - ((errorBottom - errorTop) * rate) / failureMaximum
    );
  
    for (const [top, bottom, kind] of [
      [volumeTop, volumeBottom, "volume"],
      [errorTop, errorBottom, "error-rate"],
    ]) {
      const background = document.createElementNS(namespace, "rect");
      background.setAttribute("class", `trend-plot-background ${kind}`);
      background.setAttribute("x", String(left));
      background.setAttribute("y", String(top));
      background.setAttribute("width", String(right - left));
      background.setAttribute("height", String(bottom - top));
      background.setAttribute("rx", "8");
      svg.append(background);
    }
  
    const currentLine = document.createElementNS(namespace, "line");
    currentLine.setAttribute("class", "trend-current-line");
    currentLine.setAttribute("x1", String(right));
    currentLine.setAttribute("x2", String(right));
    currentLine.setAttribute("y1", String(volumeTop));
    currentLine.setAttribute("y2", String(errorBottom));
    svg.append(currentLine);
  
    for (let index = 0; index <= volumeScale.tickCount; index += 1) {
      const position = (
        volumeTop
        + ((volumeBottom - volumeTop) * index)
        / volumeScale.tickCount
      );
      const line = document.createElementNS(namespace, "line");
      line.setAttribute("class", "trend-grid-line");
      line.setAttribute("x1", String(left));
      line.setAttribute("x2", String(right));
      line.setAttribute("y1", String(position));
      line.setAttribute("y2", String(position));
      svg.append(line);
  
      const label = document.createElementNS(namespace, "text");
      label.setAttribute("class", "trend-axis-label");
      label.setAttribute("x", "46");
      label.setAttribute("y", String(position + 4));
      label.setAttribute("text-anchor", "end");
      label.textContent = formatInteger(
        volumeMaximum
        - volumeScale.step * index,
      );
      svg.append(label);
    }
  
    const volumeTitle = document.createElementNS(namespace, "text");
    volumeTitle.setAttribute("class", "trend-axis-title");
    volumeTitle.setAttribute("x", String(left));
    volumeTitle.setAttribute("y", "17");
    volumeTitle.textContent = "调用量";
    svg.append(volumeTitle);
  
    const errorTitle = document.createElementNS(namespace, "text");
    errorTitle.setAttribute("class", "trend-axis-title");
    errorTitle.setAttribute("x", String(left));
    errorTitle.setAttribute("y", "222");
    errorTitle.textContent = "失败率";
    svg.append(errorTitle);
  
    for (const [position, value] of [
      [errorTop, failureMaximum],
      [errorBottom, 0],
    ]) {
      const line = document.createElementNS(namespace, "line");
      line.setAttribute("class", "trend-grid-line");
      line.setAttribute("x1", String(left));
      line.setAttribute("x2", String(right));
      line.setAttribute("y1", String(position));
      line.setAttribute("y2", String(position));
      svg.append(line);
  
      const label = document.createElementNS(namespace, "text");
      label.setAttribute("class", "trend-axis-label");
      label.setAttribute("x", "46");
      label.setAttribute("y", String(position + 4));
      label.setAttribute("text-anchor", "end");
      label.textContent = formatPercentage(value);
      svg.append(label);
    }
  
    const volumePoints = counts.map((count, index) => `${x(index)},${volumeY(count)}`);
    const failurePoints = failureRates.map((rate, index) => `${x(index)},${failureY(rate)}`);
    const defs = document.createElementNS(namespace, "defs");
    const gradient = document.createElementNS(namespace, "linearGradient");
    gradient.setAttribute("id", "trend-volume-gradient");
    gradient.setAttribute("x1", "0");
    gradient.setAttribute("x2", "0");
    gradient.setAttribute("y1", "0");
    gradient.setAttribute("y2", "1");
    const gradientStart = document.createElementNS(namespace, "stop");
    gradientStart.setAttribute("offset", "0%");
    gradientStart.setAttribute("stop-color", "#3b82f6");
    gradientStart.setAttribute("stop-opacity", ".18");
    const gradientEnd = document.createElementNS(namespace, "stop");
    gradientEnd.setAttribute("offset", "100%");
    gradientEnd.setAttribute("stop-color", "#3b82f6");
    gradientEnd.setAttribute("stop-opacity", "0");
    gradient.append(gradientStart, gradientEnd);
    defs.append(gradient);
    svg.append(defs);
  
    const area = document.createElementNS(namespace, "polygon");
    area.setAttribute("class", "trend-area");
    area.setAttribute(
      "points",
      `${left},${volumeBottom} ${volumePoints.join(" ")} ${right},${volumeBottom}`,
    );
    svg.append(area);
  
    for (const [points, kind] of [
      [volumePoints, "volume"],
      [failurePoints, "error-rate"],
    ]) {
      const line = document.createElementNS(namespace, "polyline");
      line.setAttribute("class", `trend-line ${kind}`);
      line.setAttribute("points", points.join(" "));
      svg.append(line);
    }
  
    const labelCount = Math.min(7, records.length);
    const labelIndexes = new Set(Array.from(
      { length: labelCount },
      (_, index) => Math.round(
        ((records.length - 1) * index)
        / Math.max(labelCount - 1, 1),
      ),
    ));
    const tooltip = document.createElement("div");
    tooltip.className = "trend-tooltip";
    tooltip.hidden = true;
    const tooltipTime = document.createElement("strong");
    const tooltipGrid = document.createElement("div");
    tooltipGrid.className = "trend-tooltip-grid";
    const tooltipTotal = document.createElement("span");
    const tooltipSuccess = document.createElement("span");
    const tooltipFailed = document.createElement("span");
    const tooltipFailureRate = document.createElement("span");
  
    for (const [label, value] of [
      ["调用量", tooltipTotal],
      ["成功", tooltipSuccess],
      ["失败", tooltipFailed],
      ["失败率", tooltipFailureRate],
    ]) {
      const name = document.createElement("span");
      name.textContent = label;
      tooltipGrid.append(name, value);
    }
  
    tooltip.append(tooltipTime, tooltipGrid);
  
    /** @param {PointerEvent} event */
    const positionTooltip = (event) => {
      const bounds = trendChart.getBoundingClientRect();
      const tooltipWidth = 210;
      const pointerX = event.clientX - bounds.left;
      const pointerY = event.clientY - bounds.top;
      const leftPosition = pointerX + tooltipWidth + 24 > bounds.width
        ? pointerX - tooltipWidth - 12
        : pointerX + 12;
      tooltip.style.left = `${Math.max(8, leftPosition)}px`;
      tooltip.style.top = `${Math.max(68, Math.min(bounds.height - 42, pointerY))}px`;
    };
  
    records.forEach((record, index) => {
      if (labelIndexes.has(index)) {
        const label = document.createElementNS(namespace, "text");
        label.setAttribute(
          "class",
          index === records.length - 1
            ? "trend-axis-label current"
            : "trend-axis-label",
        );
        label.setAttribute("x", String(x(index)));
        label.setAttribute("y", "320");
        label.setAttribute("text-anchor", index === 0 ? "start" : (index === records.length - 1 ? "end" : "middle"));
        const timeLabel = formatTrendAxisTime(
          record.time,
          index,
          records.length,
        );
        label.textContent = index === records.length - 1
          ? `${timeLabel} · 当前`
          : timeLabel;
        svg.append(label);
      }
  
      const previousX = index === 0 ? left : x(index - 1);
      const nextX = index === records.length - 1 ? right : x(index + 1);
      const hitLeft = index === 0 ? left : (previousX + x(index)) / 2;
      const hitRight = index === records.length - 1 ? right : (x(index) + nextX) / 2;
      const group = document.createElementNS(namespace, "g");
      group.setAttribute("class", "trend-hover-target");
  
      const guide = document.createElementNS(namespace, "line");
      guide.setAttribute("class", "trend-hover-line");
      guide.setAttribute("x1", String(x(index)));
      guide.setAttribute("x2", String(x(index)));
      guide.setAttribute("y1", String(volumeTop));
      guide.setAttribute("y2", String(errorBottom));
  
      const volumeDot = document.createElementNS(namespace, "circle");
      volumeDot.setAttribute("class", "trend-hover-dot volume");
      volumeDot.setAttribute("cx", String(x(index)));
      volumeDot.setAttribute("cy", String(volumeY(counts[index])));
      volumeDot.setAttribute("r", "4");
  
      const errorDot = document.createElementNS(namespace, "circle");
      errorDot.setAttribute("class", "trend-hover-dot error-rate");
      errorDot.setAttribute("cx", String(x(index)));
      errorDot.setAttribute("cy", String(failureY(failureRates[index])));
      errorDot.setAttribute("r", "4");
  
      const hit = document.createElementNS(namespace, "rect");
      hit.setAttribute("class", "trend-hover-hit");
      hit.setAttribute("x", String(hitLeft));
      hit.setAttribute("y", String(volumeTop));
      hit.setAttribute("width", String(Math.max(1, hitRight - hitLeft)));
      hit.setAttribute("height", String(errorBottom - volumeTop));
      hit.addEventListener("pointerenter", (event) => {
        tooltipTime.textContent = formatTrendTime(record.time, true);
        tooltipTotal.textContent = `${formatInteger(counts[index])} 次`;
        tooltipSuccess.textContent = `${formatInteger(successCounts[index])} 次`;
        tooltipFailed.textContent = `${formatInteger(failedCounts[index])} 次`;
        tooltipFailureRate.textContent = formatPercentage(failureRates[index]);
        tooltip.hidden = false;
        positionTooltip(event);
      });
      hit.addEventListener("pointermove", positionTooltip);
      hit.addEventListener("pointerleave", () => {
        tooltip.hidden = true;
      });
      group.append(guide, volumeDot, errorDot, hit);
      svg.append(group);
    });
  
    trendChart.append(svg, tooltip);
  }
  
  function renderTrendRangeSelector() {
    for (const button of trendRangeSelector.querySelectorAll("[data-trend-range]")) {
      if (!(button instanceof HTMLButtonElement)) continue;
  
      const active = button.dataset.trendRange === state.trendRange;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
  
    trendRangeDescription.textContent = (
      trendRangeDescriptions[state.trendRange]
      || trendRangeDescriptions["24h"]
    );
  }
  
  /**
   * 计算请求量坐标轴的易读刻度。
   *
   * @param {number} value 请求量最大值
   * @returns {{tickCount: number, step: number, maximum: number}} 坐标轴刻度配置
   */
  function getNiceVolumeScale(value) {
    const maximumValue = Number.isFinite(value) && value > 0
      ? value
      : 1;
    const tickCount = 5;
    const rawStep = maximumValue / tickCount;
    const magnitude = 10 ** Math.floor(Math.log10(rawStep));
    const fraction = rawStep / magnitude;
    let niceFraction;
  
    if (fraction <= 1) niceFraction = 1;
    else if (fraction <= 2) niceFraction = 2;
    else if (fraction <= 2.5) niceFraction = 2.5;
    else if (fraction <= 5) niceFraction = 5;
    else niceFraction = 10;
  
    const step = Math.max(
      1,
      Math.ceil(niceFraction * magnitude),
    );
  
    return {
      tickCount,
      step,
      maximum: step * tickCount,
    };
  }
  
  /**
   * 格式化趋势图时间轴标签。
   *
   * @param {string} value 时间值
   * @param {number} index 数据点索引
   * @param {number} total 数据点总数
   * @returns {string} 时间轴标签
   */
  function formatTrendAxisTime(value, index, total) {
    if (
      state.trendRange === "24h"
      && (index === 0 || index === total - 1)
    ) {
      const date = new Date(value);
  
      if (Number.isNaN(date.getTime())) return "—";
  
      return new Intl.DateTimeFormat("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(date);
    }
  
    return formatTrendTime(value);
  }
  
  function formatTrendTime(value, detailed = false) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
  
    /** @type {Intl.DateTimeFormatOptions} */
    let options;
  
    if (state.trendRange === "30d") {
      options = detailed
        ? { year: "numeric", month: "2-digit", day: "2-digit" }
        : { month: "2-digit", day: "2-digit" };
    } else if (state.trendRange === "7d" || detailed) {
      options = {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      };
    } else {
      options = {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      };
    }
  
    return new Intl.DateTimeFormat("zh-CN", options).format(date);
  }
  
  function renderModelUsage() {
    const snapshot = state.snapshot;
  
    if (snapshot === null) return;
  
    const canViewRequests = Boolean(snapshot.access.requests);
    const visible = state.active === "overview" && canViewRequests;
    const records = Array.isArray(snapshot.model_usage)
      ? snapshot.model_usage
      : [];
    modelUsagePanel.hidden = !visible;
    recentModelUsageContent.replaceChildren();
    totalModelUsageContent.replaceChildren();
  
    if (!visible) return;
  
    if (!records.length) {
      for (const container of [
        recentModelUsageContent,
        totalModelUsageContent,
      ]) {
        const empty = document.createElement("div");
        empty.className = "model-usage-empty";
        empty.textContent = "暂无模型调用数据";
        container.append(empty);
      }
      return;
    }
  
    const elements = createModelUsageTable([
      "模型",
      "近 24 小时调用",
      "成功率",
      "平均耗时",
      "调用占比",
    ]);
    const sortedRecords = [...records].sort((left, right) => (
      right.recent_count - left.recent_count
      || right.total_count - left.total_count
      || compareModelUsageNames(left, right)
    ));
  
    for (const record of sortedRecords) {
      const row = document.createElement("tr");
      const recentCell = document.createElement("td");
      recentCell.textContent = formatInteger(record.recent_count);
      const successCell = document.createElement("td");
      successCell.textContent = formatOptionalPercentage(record.success_rate);
      const latencyCell = document.createElement("td");
      latencyCell.textContent = record.average_latency_ms === null
        ? "—"
        : `${formatDuration(record.average_latency_ms)} ms`;
      const shareCell = document.createElement("td");
      shareCell.className = "model-usage-share";
      const share = Number(record.request_share);
  
      if (record.request_share === null || !Number.isFinite(share)) {
        shareCell.textContent = "—";
      } else {
        const shareContent = document.createElement("div");
        shareContent.className = "model-usage-share-content";
        const bar = document.createElement("span");
        bar.className = "model-usage-share-bar";
        const fill = document.createElement("span");
        fill.style.width = `${Math.min(100, Math.max(0, share * 100))}%`;
        bar.append(fill);
        const value = document.createElement("span");
        value.textContent = formatOptionalPercentage(share);
        shareContent.append(bar, value);
        shareCell.append(shareContent);
      }
  
      row.append(
        createModelUsageNameCell(record, snapshot.access.models),
        recentCell,
        successCell,
        latencyCell,
        shareCell,
      );
      elements.body.append(row);
    }
  
    recentModelUsageContent.append(elements.table);
    renderModelUsageRanking(
      records,
      Boolean(snapshot.access.models),
    );
  }
  
  /**
   * 渲染模型调用排行。
   *
   * @param {ModelUsageItem[]} records 模型调用记录
   * @param {boolean} canViewModels 是否允许查看模型
   * @returns {void} 无返回值
   */
  function renderModelUsageRanking(records, canViewModels) {
    const sortedRecords = [...records].sort((left, right) => (
      right.total_count - left.total_count
      || compareModelUsageNames(left, right)
    ));
    const maximum = Math.max(
      1,
      ...sortedRecords.map((record) => Number(record.total_count) || 0),
    );
    const list = document.createElement("ol");
    list.className = "model-ranking-list";
  
    sortedRecords.forEach((record, index) => {
      const item = document.createElement("li");
      const rank = document.createElement("span");
      rank.className = "model-ranking-position";
      rank.textContent = String(index + 1).padStart(2, "0");
      const content = document.createElement("div");
      content.className = "model-ranking-content";
      const heading = document.createElement("div");
      heading.className = "model-ranking-heading";
      heading.append(createModelUsageLink(record, canViewModels));
      const count = document.createElement("strong");
      count.textContent = formatInteger(record.total_count);
      heading.append(count);
      const track = document.createElement("span");
      track.className = "model-ranking-track";
      const fill = document.createElement("span");
      fill.style.width = `${Math.max(0, Number(record.total_count) || 0) / maximum * 100}%`;
      track.append(fill);
      content.append(heading, track);
      item.append(rank, content);
      list.append(item);
    });
  
    totalModelUsageContent.append(list);
  }
  
  /**
   * 按模型名称比较调用记录。
   *
   * @param {ModelUsageItem} left 左侧记录
   * @param {ModelUsageItem} right 右侧记录
   * @returns {number} 排序比较结果
   */
  function compareModelUsageNames(left, right) {
    const leftName = left.model_name || left.model_id;
    const rightName = right.model_name || right.model_id;
  
    return leftName.localeCompare(
      rightName,
      "zh-CN",
      {
        numeric: true,
        sensitivity: "base",
      },
    ) || left.model_id.localeCompare(right.model_id);
  }
  
  /**
   * 创建模型调用排行表格。
   *
   * @param {string[]} labels 表头文本
   * @returns {{table: HTMLTableElement, body: HTMLTableSectionElement}} 表格及表体
   */
  function createModelUsageTable(labels) {
    const table = document.createElement("table");
    table.className = "model-usage-table";
    const thead = document.createElement("thead");
    const heading = document.createElement("tr");
  
    for (const label of labels) {
      const cell = document.createElement("th");
      cell.textContent = label;
      heading.append(cell);
    }
  
    const tbody = document.createElement("tbody");
    thead.append(heading);
    table.append(thead, tbody);
    return {
      table,
      body: tbody,
    };
  }
  
  /**
   * 创建模型调用排行名称单元格。
   *
   * @param {ModelUsageItem} record 模型调用记录
   * @param {boolean} canViewModels 是否允许查看模型
   * @returns {HTMLTableCellElement} 模型名称单元格
   */
  function createModelUsageNameCell(record, canViewModels) {
    const cell = document.createElement("td");
    const content = document.createElement("div");
    content.className = "model-usage-name";
    content.append(createModelUsageLink(record, canViewModels));
    cell.append(content);
    return cell;
  }
  
  /**
   * 创建模型调用排行名称内容。
   *
   * @param {ModelUsageItem} record 模型调用记录
   * @param {boolean} canViewModels 是否允许查看模型
   * @returns {HTMLElement} 可跳转按钮或静态名称
   */
  function createModelUsageLink(record, canViewModels) {
    const name = record.model_name || record.model_id;
  
    if (canViewModels) {
      const link = document.createElement("button");
      link.type = "button";
      link.className = "model-usage-link";
      link.textContent = name;
      link.title = `查看模型 ${record.model_id}`;
      link.addEventListener("click", () => {
        navigateToSection(
          "models",
          1,
          `model_id:${record.model_id}`,
        );
      });
      return link;
    }
  
    const label = document.createElement("strong");
    label.textContent = name;
    return label;
  }

  return {
    renderModelUsage,
    renderNavigation,
    renderRequestTrend,
    renderSummary,
    renderTrendRangeSelector,
  };
}
