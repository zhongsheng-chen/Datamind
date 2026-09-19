"use strict";

import {
  appendDetailField as appendRequestDetail,
  appendDetailFooter,
  createDetailAction,
  createDetailDrawer,
  createDetailSection,
  createDetailSummary,
  createErrorDetailSection,
  createJsonDetailSection,
  formatBadgeValue,
  formatStatusValue,
  mountDetailDrawer,
} from "./common.js";

/**
 * 创建运行实例详情控制器。
 *
 * 详情展示实例生命周期、健康信息、模型上下文和错误信息。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {(record: Object) => void} 打开运行实例详情抽屉
 */
export function createRuntimeDetailController({
  createCopyableNavigationLink,
  createDeploymentRoleBadge,
  createStatusBadge,
  formatTime,
  navigateToSection,
}) {
  function showRuntimeDrawer(record) {
    if (!record) return;
    const { dialog, body } = createDetailDrawer(
      "运行实例详情",
      "runtime-detail-drawer",
    );
    body.append(
      createDetailSummary({
        icon: "runtime",
        title: record.model_name || "未命名模型",
        subtitle: [record.model_version, record.worker_id]
          .filter(Boolean)
          .join(" · "),
        status: record.status,
        badges: [
          createDeploymentRoleBadge(record.role),
          createStatusBadge(record.health_status),
        ],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["实例 ID", () => createCopyableNavigationLink(
          record.runtime_id,
          () => {
            dialog.close();
            navigateToSection(
              "runtimes",
              1,
              `runtime_id:${record.runtime_id}`,
              "last_heartbeat_at",
              "desc",
            );
          },
          "实例 ID",
        )],
        ["模型名称", record.model_name],
        ["版本", record.model_version],
        ["角色", formatBadgeValue(record.role, createDeploymentRoleBadge)],
        ["框架", record.framework],
        ["运行节点", record.worker_id],
        ["创建时间", formatTime(record.created_at)],
        ["更新时间", formatTime(record.updated_at)],
      ], dialog, "info", appendRequestDetail),
      createDetailSection("运行状态", [
        ["状态", formatStatusValue(record.status, createStatusBadge)],
        ["健康状态", formatStatusValue(
          record.health_status,
          createStatusBadge,
        )],
        ["Generation", record.applied_generation],
        ["加载时间", formatTime(record.loaded_at)],
        ["卸载时间", formatTime(record.unloaded_at)],
        ["最近心跳", formatTime(record.last_heartbeat_at)],
      ], dialog, "activity", appendRequestDetail),
    );
    if (record.error) body.append(createErrorDetailSection(record.error));
    if (record.context !== null && record.context !== undefined) {
      body.append(createJsonDetailSection(
        "运行上下文",
        record.context,
        "metadata",
      ));
    }

    const buttons = [];
    if (record.deployment_id) {
      const viewDeployment = createDetailAction("查看部署", "view");
      viewDeployment.addEventListener("click", () => {
        dialog.close();
        navigateToSection(
          "deployments",
          1,
          `deployment_id:${record.deployment_id}`,
        );
      });
      buttons.push(viewDeployment);
    }
    appendDetailFooter(dialog, buttons);
    mountDetailDrawer(dialog, { section: "runtimes", id: record.runtime_id });
  }

  return showRuntimeDrawer;
}
