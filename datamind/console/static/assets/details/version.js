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
  showJsonDialog,
} from "./common.js?v=20260902-4";

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

  function schemaFieldCount(schema) {
    if (!schema || typeof schema !== "object") return null;
    if (Array.isArray(schema.feature_names)) return schema.feature_names.length;
    if (Array.isArray(schema.fields)) return schema.fields.length;
    if (Array.isArray(schema.columns)) return schema.columns.length;
    if (schema.properties && typeof schema.properties === "object") {
      return Object.keys(schema.properties).length;
    }
    if (schema.data_types && typeof schema.data_types === "object") {
      return Object.keys(schema.data_types).length;
    }
    return null;
  }

  function createSchemaFileValue(label, storageKey, schema) {
    if (!storageKey && !schema) return "未配置";
    const value = document.createElement("span");
    value.className = "registry-version-schema-value";
    const count = schemaFieldCount(schema);
    const summary = document.createElement("span");
    summary.textContent = count === null ? "已配置" : `${count} 个字段`;
    value.append(summary);
    if (schema) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "registry-json-view-button";
      button.textContent = "查看";
      button.addEventListener("click", () => showJsonDialog(label, schema));
      value.append(button);
    }
    return value;
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
        ["输入 Schema", createSchemaFileValue(
          "输入 Schema",
          version.input_schema_key,
          version.input_schema,
        )],
        ["输出 Schema", createSchemaFileValue(
          "输出 Schema",
          version.output_schema_key,
          version.output_schema,
        )],
      ],
      dialog,
      "artifact",
      appendRequestDetail,
    );
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
