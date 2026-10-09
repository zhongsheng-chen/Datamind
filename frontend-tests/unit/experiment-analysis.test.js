import { describe, expect, it, vi } from "vitest";
import { createExperimentAnalysisSection, createExperimentAnalysisSummary } from "../../datamind/console/static/assets/details/experiment/analysis.js";

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

function setup(request) {
  const dialog = document.createElement("dialog");
  const section = createExperimentAnalysisSection({ experimentId: "exp/demo", request, dialog });
  dialog.append(section);
  return { dialog, section };
}

describe("experiment analysis", () => {
  it("opens full analysis from the summary without the obsolete guidance", async () => {
    const onViewAnalysis = vi.fn();
    const section = createExperimentAnalysisSummary({
      experimentId: "demo", request: vi.fn().mockResolvedValue({ decision_count: 0 }),
      dialog: document.createElement("dialog"), onViewAnalysis,
    });
    await settle();
    [...section.querySelectorAll("button")].find((button) => button.textContent === "查看全部").click();
    expect(onViewAnalysis).toHaveBeenCalledOnce();
    expect(section.textContent).not.toContain("成功率与耗时仅统计");
    expect(section.textContent).not.toContain("完整指标可从实验列表");
  });

  it("renders missing metrics, zero rates and escaped labels, and switches baseline", async () => {
    const markupLabel = "<mark>高风险</mark>";
    const request = vi.fn().mockResolvedValue({
      decision_count: 2, baseline_variant_id: "v/1",
      variants: { "v/1": { name: "对照组", is_control: true } },
      metrics: { variants: { "v/1": { total_count: 2, success_rate: 0, average_score: null, prediction_counts: { [markupLabel]: 2 } } } },
    });
    const { section } = setup(request);
    await settle();
    expect(section.textContent).toContain("0%");
    expect(section.textContent).toContain("—");
    expect(section.textContent).toContain(markupLabel);
    expect(section.querySelector("mark")).toBeNull();
    const select = section.querySelector("select");
    select.value = "v/1";
    select.dispatchEvent(new Event("change"));
    await settle();
    expect(request.mock.calls[1][0]).toBe("experiments/exp%2Fdemo/analysis?baseline_variant_id=v%2F1");
  });

  it("weights aggregate rates and latency by valid sample counts", async () => {
    const request = vi.fn().mockResolvedValue({
      decision_count: 11,
      metrics: { variants: {
        control: { subject_count: 3, completed_count: 2, success_count: 1, latency_count: 2, average_latency_ms: 10 },
        treatment: { subject_count: 7, completed_count: 8, success_count: 7, latency_count: 8, average_latency_ms: 20 },
      } },
    });
    const section = createExperimentAnalysisSummary({ experimentId: "demo", request, dialog: document.createElement("dialog") });
    await settle();
    const cards = section.querySelector(".experiment-analysis-cards");
    expect([...cards.querySelectorAll("dd")].map((value) => value.textContent))
      .toEqual(["11", "10", "80%", "18 毫秒"]);
    expect(section.querySelector("details")).toBeNull();
  });

  it("compares metrics across groups with the baseline first and neutral differences", async () => {
    const request = vi.fn().mockResolvedValue({
      decision_count: 2, baseline_variant_id: "control",
      variants: { control: { name: "对照组" }, treatment: { name: "实验组" } },
      metrics: { variants: {
        treatment: { total_count: 1, score_count: 1, average_score: 650, minimum_score: 650, maximum_score: 650, probability_count: 1, average_probability: 0.1 },
        control: { total_count: 1, score_count: 1, average_score: 600, minimum_score: 600, maximum_score: 600, probability_count: 1, average_probability: 0 },
      }, comparisons: { treatment: {
        average_score: { absolute_lift: 50, relative_lift: 0.083333 },
        average_probability: { absolute_lift: 0.1, relative_lift: null },
      } } },
    });
    const { section } = setup(request);
    await settle();
    const matrix = section.querySelector(".experiment-analysis-main table");
    expect([...matrix.querySelectorAll("thead th")].map((cell) => cell.textContent))
      .toEqual(["指标", "对照组 · 基准", "实验组", "差异", "相对变化"]);
    expect(matrix.querySelectorAll("tbody tr")).toHaveLength(4);
    expect(matrix.querySelector("tbody tr").textContent).toContain("+50+8.33%");
    expect(matrix.querySelectorAll("tbody tr")[1].textContent).toContain("+10 pp—");
    expect(matrix.textContent).toContain("最小值—最大值 600—600");
    expect(section.querySelector(".experiment-analysis-traffic")).not.toBeNull();
    expect(section.querySelector("details")).toBeNull();
  });

  it("keeps difference columns associated with each variant in a multi-group experiment", async () => {
    const { section } = setup(vi.fn().mockResolvedValue({
      decision_count: 3, baseline_variant_id: "control",
      variants: { control: { name: "control", is_control: true }, a: { name: "方案甲" }, b: { name: "方案乙" } },
      metrics: { variants: { control: {}, a: {}, b: {} }, comparisons: {} },
    }));
    await settle();
    const matrix = section.querySelector(".experiment-analysis-main table");
    expect([...matrix.querySelectorAll("thead th")].map((cell) => cell.textContent))
      .toEqual(["指标", "对照组 · 基准", "方案甲", "差异", "相对变化", "方案乙", "差异", "相对变化"]);
    expect(matrix.querySelector("tbody tr").children).toHaveLength(8);
    expect([...matrix.querySelector("tbody tr").children].slice(1).map((cell) => cell.querySelector("strong")?.textContent || cell.textContent))
      .toEqual(["—", "—", "—", "—", "—", "—", "—"]);
  });

  it("allows retry after failure and displays the empty state", async () => {
    const request = vi.fn().mockRejectedValueOnce(new Error("暂不可用"))
      .mockResolvedValue({ decision_count: 0, variants: {}, metrics: {} });
    const { section } = setup(request);
    await settle();
    expect(section.textContent).toContain("暂不可用");
    section.querySelector("button").click();
    await settle();
    expect(section.textContent).toContain("暂无实验请求");
    expect(section.getAttribute("aria-busy")).toBe("false");
  });

  it("cancels pending requests when the drawer closes", () => {
    const request = vi.fn(() => new Promise(() => {}));
    const { dialog } = setup(request);
    const signal = request.mock.calls[0][1].signal;
    dialog.dispatchEvent(new Event("close"));
    expect(signal.aborted).toBe(true);
  });
});

describe("experiment analysis summary", () => {
  it("shows compact group scores and traffic without wide tables", async () => {
    const dialog = document.createElement("dialog");
    const request = vi.fn().mockResolvedValue({
      decision_count: 2, variants: { control: { name: "对照组" } },
      metrics: { variants: { control: { total_count: 2, subject_count: 1, traffic_ratio: 1,
        completed_count: 2, success_count: 2, latency_count: 2, average_latency_ms: 10,
        score_count: 2, average_score: 600 } } },
    });
    const section = createExperimentAnalysisSummary({ experimentId: "demo", request, dialog });
    await settle();
    expect(section.querySelector("table")).toBeNull();
    expect(section.textContent).toContain("平均评分 600");
    expect(section.querySelector("progress").value).toBe(1);
    expect(section.querySelector("progress").getAttribute("aria-label")).toBe("对照组 流量占比");
    expect([...section.querySelectorAll("dd")].map((value) => value.textContent)).toEqual(["2", "1", "100%", "10 毫秒"]);
  });

  it("keeps missing samples distinct from zero without a refresh action", async () => {
    const request = vi.fn().mockResolvedValue({ decision_count: 0, metrics: {} });
    const section = createExperimentAnalysisSummary({ experimentId: "demo", request, dialog: document.createElement("dialog") });
    await settle();
    expect([...section.querySelectorAll("dd")].map((value) => value.textContent)).toEqual(["0", "0", "—", "—"]);
    expect(section.querySelector("button")).toBeNull();
    expect(request).toHaveBeenCalledOnce();
  });

  it("cancels the pending summary request on close", async () => {
    const dialog = document.createElement("dialog");
    let resolve;
    const request = vi.fn(() => new Promise((complete) => { resolve = complete; }));
    const section = createExperimentAnalysisSummary({ experimentId: "demo", request, dialog });
    const signal = request.mock.calls[0][1].signal;
    dialog.dispatchEvent(new Event("close"));
    resolve({ decision_count: 100, metrics: {} });
    await settle();
    expect(signal.aborted).toBe(true);
    expect(section.textContent).not.toContain("100");
  });
});
