"use strict";

import {
  appendDetailField as appendRequestDetail,
  createDetailBadge,
  createDetailDrawer,
  createDetailSection,
  createDetailSummary,
  mountDetailDrawer,
} from "./common.js";

/**
 * 创建用户与角色详情控制器。
 *
 * 详情以用户身份、角色分配和权限范围为核心。
 *
 * @param {Object.<string, *>} dependencies 页面基础能力
 * @returns {{
 *   showRoleDrawer: (record: Object) => void,
 *   showUserDrawer: (record: Object) => void
 * }} 用户与角色详情入口
 */
export function createAccessDetailController({
  createCopyableSectionNavigationLink,
  createStatusBadge,
  formatTime,
}) {
  function showUserDrawer(record) {
    /** @type {string[]} */
    const roles = [];
    if (Array.isArray(record.roles)) {
      for (const role of record.roles) roles.push(String(role));
    }
    const { dialog, body } = createDetailDrawer("用户详情");
    body.append(
      createDetailSummary({
        icon: "user",
        title: record.display_name || record.username,
        subtitle: record.username,
        status: record.status,
        badges: roles.slice(0, 3).map((role) => createDetailBadge(role)),
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["用户 ID", (drawer) => createCopyableSectionNavigationLink(
          record.user_id,
          "users",
          drawer,
          "用户 ID",
        )],
        ["用户名", record.username],
        ["显示名称", record.display_name],
        ["邮箱", record.email],
        ["状态", createStatusBadge(record.status)],
        ["角色", roles.length > 0 ? roles.join(", ") : null],
        ["最近登录", formatTime(record.last_login_at)],
        ["创建时间", formatTime(record.created_at)],
        ["更新时间", formatTime(record.updated_at)],
      ], dialog, "info", appendRequestDetail),
    );
    mountDetailDrawer(dialog, { section: "users", id: record.user_id });
  }

  function showRoleDrawer(record) {
    const { dialog, body } = createDetailDrawer("角色详情");
    body.append(
      createDetailSummary({
        icon: "role",
        title: record.name,
        subtitle: record.description || "角色",
        status: record.status,
        badges: Array.isArray(record.permissions)
          ? [createDetailBadge(`${record.permissions.length} 项权限`)]
          : [],
        createStatusBadge,
      }),
      createDetailSection("基本信息", [
        ["角色 ID", (drawer) => createCopyableSectionNavigationLink(
          record.role_id,
          "roles",
          drawer,
          "角色 ID",
        )],
        ["角色名称", record.name],
        ["状态", createStatusBadge(record.status)],
        ["描述", record.description],
        ["权限", Array.isArray(record.permissions)
          ? record.permissions.join(", ")
          : null],
        ["创建时间", formatTime(record.created_at)],
        ["更新时间", formatTime(record.updated_at)],
      ], dialog, "info", appendRequestDetail),
    );
    mountDetailDrawer(dialog, { section: "roles", id: record.role_id });
  }

  return { showRoleDrawer, showUserDrawer };
}
