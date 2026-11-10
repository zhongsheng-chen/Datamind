"use strict";

import { enhanceOrganizationSelect } from "./select.js";

/**
 * 组织目录表单。
 *
 * 提供用户归属选择、机构维护及部门树维护，复用管理控制台的表单组件。
 */

/**
 * 返回所属机构内的部门选项，并排除当前部门及其下级部门。
 *
 * @param {Object[]} departments 部门目录
 * @param {string} organizationId 所属机构 ID
 * @param {string | null} [excludedId] 编辑中的部门 ID
 * @param {string | null} [selectedId] 保留已有归属，允许编辑停用部门中的用户
 * @returns {string[][]} 部门 ID 与完整路径
 */
export function departmentOptions(departments, organizationId, excludedId = null, selectedId = null) {
  return departments
    .filter(item => item.organization_id === organizationId)
    .filter(item => (item.is_available !== false && item.is_active !== false) || item.department_id === selectedId)
    .filter(item => (
      !excludedId || !item.path.some(node => node.department_id === excludedId)
    ))
    .map(item => [
      item.department_id,
      item.path.map(node => node.name).join(" / ")
        + (item.is_available === false || item.is_active === false ? "（已停用）" : ""),
    ]);
}

/**
 * 构建用户组织资料字段。
 *
 * @param {Object} directory 机构与部门目录
 * @param {Object} [record] 当前用户
 * @returns {Object[]} 管理表单字段
 */
export function userOrganizationFields(directory, record = {}) {
  return [
    {
      name: "employee_number",
      label: "工号",
      value: record.employee_number || "",
      maxLength: 64,
    },
    {
      name: "organization_id",
      label: "所属机构",
      type: "select",
      options: [
        ["", "未设置"],
        ...directory.organizations
          .filter(item => item.is_active !== false || item.organization_id === record.organization_id)
          .map(item => [item.organization_id, item.name + (item.is_active === false ? "（已停用）" : "")]),
      ],
      value: record.organization_id || "",
    },
    {
      name: "department_id",
      label: "所属部门",
      type: "select",
      options: [
        ["", "未设置"],
        ...departmentOptions(directory.departments, record.organization_id, null, record.department_id),
      ],
      value: record.department_id || "",
    },
  ];
}

/**
 * 机构切换后重新生成部门选项，清除原机构的选择。
 *
 * @param {HTMLDialogElement} dialog 管理表单
 * @param {Object} directory 机构与部门目录
 * @param {string} [fieldName] 部门选择字段名
 * @param {string | null} [excludedId] 不可作为上级的部门 ID
 */
export function bindDepartmentOptions(
  dialog,
  directory,
  fieldName = "department_id",
  excludedId = null,
) {
  const organization = dialog.querySelector('[name="organization_id"]');
  const department = dialog.querySelector(`[name="${fieldName}"]`);

  organization.addEventListener("change", () => {
    const options = [
      ["", fieldName === "parent_id" ? "无上级部门" : "未设置"],
      ...departmentOptions(directory.departments, organization.value, excludedId),
    ];

    department.replaceChildren(...options.map(
      ([value, label]) => Object.assign(document.createElement("option"), {
        textContent: label,
        value,
      }),
    ));
    department.value = "";
  });
}

export function createOrganizationEditors({
  directory, request, createDialog, toast, onSuccess, selectedOrganizationId = null,
}) {
  const editOrganization = (record = null) => createDialog({
    title: record ? "编辑机构" : "创建机构",
    submitLabel: "保存",
    fields: [
      {
        name: "code",
        label: "机构编码（可选）",
        value: record?.code || "",
      },
      {
        name: "name",
        label: "机构名称",
        required: true,
        value: record?.name || "",
      },
    ],
    onSubmit: data => request(
      record ? `organizations/${record.organization_id}` : "organizations",
      {
        method: record ? "PATCH" : "POST",
        body: JSON.stringify({
          code: data.get("code"),
          name: data.get("name"),
        }),
      },
    ),
    onSuccess,
    refreshAfterSubmit: false,
  });

  const editDepartment = (record = null, context = {}) => {
    const organizations = directory.organizations.filter(
      item => item.is_active !== false || item.organization_id === record?.organization_id,
    );
    if (!organizations.length) {
      toast("请先新增或启用所属机构");
      return;
    }

    const organizationId = record?.organization_id
      || context.organizationId
      || selectedOrganizationId
      || organizations[0].organization_id;
    const form = createDialog({
      title: record ? "编辑部门" : context.parentId ? "创建子部门" : "创建部门",
      submitLabel: "保存",
      fields: [
        {
          name: "organization_id",
          label: "所属机构",
          type: "select",
          required: true,
          options: organizations
            .filter(item => !record || item.organization_id === organizationId)
            .map(item => [item.organization_id, item.name]),
          value: organizationId,
        },
        {
          name: "code",
          label: "部门编码（可选）",
          value: record?.code || "",
        },
        {
          name: "name",
          label: "部门名称",
          required: true,
          value: record?.name || "",
        },
        {
          name: "parent_id",
          label: "上级部门",
          type: "select",
          options: [
            ["", "无上级部门"],
            ...departmentOptions(
              directory.departments,
              organizationId,
              record?.department_id,
              record?.parent_id,
            ),
          ],
          value: record?.parent_id || context.parentId || "",
        },
      ],
      onSubmit: data => request(
        record ? `departments/${record.department_id}` : "departments",
        {
          method: record ? "PATCH" : "POST",
          body: JSON.stringify({
            organization_id: data.get("organization_id"),
            code: data.get("code"),
            name: data.get("name"),
            parent_id: data.get("parent_id") || null,
          }),
        },
      ),
      onSuccess,
      refreshAfterSubmit: false,
    });

    bindDepartmentOptions(form, directory, "parent_id", record?.department_id);
  };

  return { editOrganization, editDepartment };
}

/**
 * 在用户归属下拉框中提供新增操作，保存后选中新建项。
 *
 * @param {HTMLDialogElement} dialog 用户表单
 * @param {Object} directory 机构与部门目录
 * @param {Object.<string, *>} dependencies 请求、表单及提示组件
 */
export function bindUserOrganizationOptions(dialog, directory, { request, createDialog, toast }) {
  const organization = dialog.querySelector('[name="organization_id"]');
  const department = dialog.querySelector('[name="department_id"]');
  const createValue = "__create__";
  let organizationId = organization.value;
  let departmentId = department.value;
  const controls = [organization, department].map(select => enhanceOrganizationSelect(select, dialog));

  const render = () => {
    for (const field of userOrganizationFields(directory, {
      organization_id: organizationId, department_id: departmentId,
    }).filter(field => field.type === "select")) {
      const select = field.name === "organization_id" ? organization : department;
      select.replaceChildren(...field.options.map(([value, label]) => new window.Option(label, value)));
      const action = new window.Option(field.name === "organization_id" ? "＋ 创建机构" : "＋ 创建部门", createValue);
      action.disabled = select === department && !organizationId;
      select.append(action);
      select.value = field.value;
    }
    for (const control of controls) control.sync();
  };

  const openCreate = (kind) => {
    const editors = createOrganizationEditors({
      directory, request, createDialog, toast,
      selectedOrganizationId: organizationId,
      onSuccess: async (result) => {
        Object.assign(directory, await request("directory"));
        if (kind === "organization") {
          organizationId = result.organization_id;
          departmentId = "";
        } else {
          organizationId = result.organization_id;
          departmentId = result.department_id;
        }
        render();
      },
    });
    if (kind === "organization") editors.editOrganization();
    else editors.editDepartment();
  };

  organization.addEventListener("change", () => {
    if (organization.value === createValue) {
      organization.value = organizationId;
      openCreate("organization");
      return;
    }
    organizationId = organization.value;
    departmentId = "";
    render();
  });
  department.addEventListener("change", () => {
    if (department.value === createValue) {
      department.value = departmentId;
      if (organizationId) openCreate("department");
      else toast("请先选择所属机构");
      return;
    }
    departmentId = department.value;
  });
  render();
}
