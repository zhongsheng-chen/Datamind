import { beforeEach, describe, expect, it, vi } from "vitest";

import { createTableControls } from "../../datamind/console/static/assets/table.js";

function createControls() {
  document.body.innerHTML = `
    <main id="container"></main>
    <form id="query-form"><input id="query"><button id="collapse"></button></form>
    <button id="toggle"></button>
    <button id="clear"></button>
  `;
  const notify = vi.fn();
  const controls = createTableControls({
    container: document.querySelector("#container"),
    queryForm: document.querySelector("#query-form"),
    queryInput: document.querySelector("#query"),
    queryToggle: document.querySelector("#toggle"),
    queryCollapse: document.querySelector("#collapse"),
    queryClear: document.querySelector("#clear"),
    formatNumber: String,
    notify,
  });
  return { controls, notify, query: document.querySelector("#query") };
}

describe("table controls", () => {
  beforeEach(() => document.body.replaceChildren());

  it("preserves an active query draft during a refresh", () => {
    const { controls, query } = createControls();
    controls.setQueryAvailable(true);
    controls.updateQuery("", "查询子任务");
    query.focus();
    query.value = "322";
    query.dispatchEvent(new Event("input", { bubbles: true }));

    controls.updateQuery("", "查询子任务");

    expect(query.value).toBe("322");
    expect(controls.hasQueryDraft()).toBe(true);
  });

  it("replaces a draft when the list context changes", () => {
    const { controls, query } = createControls();
    controls.setQueryAvailable(true);
    controls.updateQuery("", "查询子任务");
    query.value = "draft";
    query.dispatchEvent(new Event("input", { bubbles: true }));

    controls.updateQuery("model-a", "查询模型");

    expect(query.value).toBe("model-a");
    expect(controls.hasQueryDraft()).toBe(false);
  });

  it("renders pagination and navigates from user actions", () => {
    const { controls } = createControls();
    const navigate = vi.fn();
    controls.renderPagination({
      page: 2,
      page_size: 20,
      total_pages: 4,
      has_previous: true,
      has_next: true,
    }, "资源分页", navigate);

    const buttons = [...document.querySelectorAll("nav.pagination > button")];
    buttons[0].click();
    buttons[1].click();
    expect(navigate).toHaveBeenNthCalledWith(1, 1, 20);
    expect(navigate).toHaveBeenNthCalledWith(2, 3, 20);
  });
});
