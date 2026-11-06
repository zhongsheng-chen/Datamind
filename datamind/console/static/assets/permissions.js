"use strict";

/** 权限标识及资源分组的展示信息，供授权表单和详情共用。 */

const permissionResourceLabels = {
  model: "模型",
  deployment: "部署",
  experiment: "实验",
  identity: "身份",
  routing: "路由",
  runtime: "运行时",
  prediction: "预测",
  request: "API 调用",
  audit: "审计",
  data: "数据",
};

const permissionActionLabels = {
  read: "查看",
  write: "管理",
  delete: "删除",
  manage: "管理",
  invoke: "调用",
  export: "导出",
};

export function permissionOptions(permissions) {
  return permissions.map((permission) => {
    if (permission === "*") {
      return {
        value: permission,
        label: permission,
        description: "授予当前及后续新增的全部权限",
        group: "全局权限",
      };
    }

    const [resource, action] = permission.split(".");
    const resourceLabel = permissionResourceLabels[resource] || resource;
    const actionLabel = permissionActionLabels[action] || action;
    return {
      value: permission,
      label: permission,
      description: `${resourceLabel}${actionLabel}`,
      group: resourceLabel,
    };
  });
}
