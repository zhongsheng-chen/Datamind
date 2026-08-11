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
  createErrorDetailSection,
  createJsonCode,
  createJsonDetailSection,
  mountDetailDrawer,
} from "./common.js?v=20260902-6";

/**
 * 创建审计记录详情控制器。
 *
 * 详情呈现审计主体、变更内容、请求上下文和目标资源。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {(record: Object) => void} 打开审计记录详情抽屉
 */
export function createAuditDetailController({
  createCopyableNavigationLink,
  createSectionNavigationLink,
  createStatusBadge,
  formatTime,
  navigateToSection,
  sectionIdFields,
}) {
  const targetSections = {
    model: "models",
    version: "versions",
    deployment: "deployments",
    routing: "routings",
    experiment: "experiments",
    variant: "variants",
    runtime: "runtimes",
    request: "requests",
    decision: "decisions",
    execution: "executions",
    user: "users",
    role: "roles",
  };

  function createChangeSection(before, after) {
    const section = document.createElement("section");
    section.className = "registry-detail-section registry-change-section";
    const heading = document.createElement("h4");
    heading.append(
      createDetailIcon("change", "registry-section-icon"),
      document.createTextNode("变更内容"),
    );
    const comparison = document.createElement("div");
    comparison.className = "registry-change-comparison";
    for (const [label, value] of [["变更前", before], ["变更后", after]]) {
      const panel = document.createElement("section");
      const title = document.createElement("h5");
      title.textContent = label;
      const content = createJsonCode(value, label);
      panel.append(title, content);
      comparison.append(panel);
    }
    section.append(heading, comparison);
    return section;
  }

  function showAuditDrawer(record) {
    if (!record) return;
    const { dialog, body } = createDetailDrawer(
      "审计记录详情",
      "audit-detail-drawer",
    );
    const targetSection = targetSections[
      String(record.target_type || "").toLowerCase()
    ];
    body.append(
      createDetailSummary({
        icon: "audit",
        title: record.action || record.operation || "审计操作",
        subtitle: [record.target_type, record.target_id]
          .filter(Boolean)
          .join(" · "),
        status: record.status,
        badges: [
          createDetailBadge(record.user || "系统"),
          createDetailBadge(record.source || "未知来源", "blue"),
        ],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["审计 ID", () => createCopyableNavigationLink(
          record.audit_id,
          () => {
            dialog.close();
            navigateToSection(
              "audits",
              1,
              `audit_id:${record.audit_id}`,
            );
          },
          "审计 ID",
        )],
        ["操作", record.action],
        ["操作名称", record.operation],
        ["资源", record.resource],
        ["目标类型", record.target_type],
        ["目标资源", () => createSectionNavigationLink(
          record.target_id,
          targetSection,
          dialog,
          record.target_id,
        )],
        ["状态", createStatusBadge(record.status)],
        ["来源", record.source],
        ["操作人", record.user],
        ["发生时间", formatTime(record.occurred_at)],
      ], dialog, "info", appendRequestDetail),
    );
    if (record.error) body.append(createErrorDetailSection(record.error));
    if (record.before !== null || record.after !== null) {
      body.append(createChangeSection(record.before, record.after));
    }
    body.append(
      createDetailSection("请求上下文", [
        ["请求 ID", record.request_id],
        ["追踪 ID", record.trace_id],
        ["客户端 IP", record.ip],
        ["主机名", record.hostname],
      ], dialog, "request", appendRequestDetail),
    );
    if (record.context !== null && record.context !== undefined) {
      body.append(createJsonDetailSection("审计上下文", record.context, "metadata"));
    }
    if (targetSection && record.target_id) {
      const target = createDetailAction("查看目标资源", "external", "primary");
      target.addEventListener("click", () => {
        dialog.close();
        navigateToSection(
          targetSection,
          1,
          `${sectionIdFields[targetSection]}:${record.target_id}`,
        );
      });
      appendDetailFooter(dialog, [target]);
    }
    mountDetailDrawer(dialog, { section: "audits", id: record.audit_id });
  }

  return showAuditDrawer;
}
