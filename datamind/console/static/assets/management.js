import {
  appendChoiceField,
  appendFormSection,
  appendMultiSelectField,
  appendStandardField,
  artifactExtensionsByFramework,
  buildManagementFormData,
  closeManagementMultiselects,
  createCapabilities,
  createLabels,
  createWizardCheckIcon,
  datetimeLocalValue,
  deploymentRoleOptionsByRollout,
  deploymentRolloutOptions,
  frameworkLabels,
  filterModelTypes,
  maxModelUploadBytes,
  maxModelUploadMegabytes,
  modelTypeOptions,
  modelTypesByFramework,
  optionalValue,
  permissionOptions,
  readJsonConfig,
  replaceSelectOptions,
  roleOptions,
  standardFieldValidators,
  taskTypeOptionsByModelType,
} from "./management/forms.js";

/**
 * 管理控制台资源写入交互。
 *
 * 负责资源创建、编辑、删除和批量操作的业务编排。
 */

/**
 * @typedef {Object} ManagementRoleOption
 * @property {string} name
 * @property {string | null} description
 */

/**
 * @typedef {Object} ManagementOptions
 * @property {string[]} model_types
 * @property {Object.<string, string[]>} artifact_extensions
 * @property {string[]} permissions
 * @property {ManagementRoleOption[]} roles
 * @property {{schema: Object, example: Object}} routing_rules
 */

/**
 * @typedef {Object} ManagementDialogConfig
 * @property {string} title
 * @property {string} [description]
 * @property {Object[]} fields
 * @property {string} submitLabel
 * @property {(formData: FormData) => Promise<any>} onSubmit
 * @property {((result: any) => (any | Promise<any>)) | null} [onSuccess]
 * @property {boolean} [refreshAfterSubmit]
 * @property {string} [successMessage]
 * @property {boolean} [wizard]
 */

/**
 * @typedef {Object} RecordAction
 * @property {string} label
 * @property {string} resource
 * @property {string} identifier
 * @property {string} action
 * @property {string} tone
 * @property {boolean} [dividerBefore]
 * @property {boolean} [disabled]
 * @property {string} [disabledReason]
 */

export function createResourceManager({
  state,
  createButton,
  changePasswordButton,
  closeAccountMenu,
  hasCapability,
  request,
  refresh,
  toast,
  sectionIdFields,
  onCurrentUserUpdated,
  onAccessChanged,
  onSessionEnded,
  onShowBatch,
  onShowModel,
  onShowModelVersions,
  onShowVersion,
}) {
  /** @type {Promise<ManagementOptions> | null} */
  let managementOptionsRequest = null;
  /** @type {(() => void) | null} */
  let closeActiveActionMenu = null;

  function getCreateResource() {
    if (state.selectedExperimentId !== null) return "variants";
    return state.active;
  }

  function updateCreateButton() {
    const resource = getCreateResource();
    const capability = createCapabilities[resource];
    const visible = Boolean(capability && hasCapability(capability));
    createButton.hidden = !visible;

    if (!visible) return;

    const label = (
      resource === "models" && state.selectedModelId !== null
        ? "注册版本"
        : createLabels[resource]
    );
    const iconOnly = Boolean(createLabels[resource]);
    createButton.classList.toggle("create-icon-button", iconOnly);
    createButton.textContent = iconOnly ? "+" : label;
    createButton.title = label;
    createButton.setAttribute("aria-label", label);
  }

  /**
   * 获取资源管理可选项。
   *
   * @returns {Promise<ManagementOptions>} 模型类型、权限和角色选项
   */
  async function getManagementOptions() {
    if (managementOptionsRequest === null) {
      managementOptionsRequest = /** @type {Promise<ManagementOptions>} */ (
        request("management/options")
      )
        .catch((error) => {
          managementOptionsRequest = null;
          throw error;
        });
    }

    return managementOptionsRequest;
  }

  /**
   * 创建资源管理表单对话框。
   *
   * 对话框统一处理字段渲染、分步校验、提交反馈和资源刷新。
   *
   * @param {ManagementDialogConfig} config 对话框配置
   * @returns {HTMLDialogElement} 已打开的管理对话框
   */
  function createManagementDialog({
    title,
    description = "",
    fields,
    submitLabel,
    onSubmit,
    onSuccess = null,
    refreshAfterSubmit = true,
    successMessage = `${title}成功`,
    wizard = false,
  }) {
    const dialog = document.createElement("dialog");
    dialog.className = "management-dialog";
    const form = document.createElement("form");
    form.className = "management-form";
    form.noValidate = wizard;

    const header = document.createElement("header");
    const headingCopy = document.createElement("div");
    const heading = document.createElement("h3");
    heading.textContent = title;
    headingCopy.append(heading);
    if (description) {
      const copy = document.createElement("p");
      copy.textContent = description;
      headingCopy.append(copy);
    }
    const close = document.createElement("button");
    close.type = "button";
    close.className = "dialog-close-button";
    close.textContent = "关闭";
    close.addEventListener("click", () => dialog.close());
    header.append(headingCopy, close);

    const stepFields = fields.filter((field) => field.type === "section");
    const stepNavigation = document.createElement("ol");
    stepNavigation.className = "management-wizard-steps";
    stepNavigation.hidden = !wizard;
    for (const [index, field] of stepFields.entries()) {
      const item = document.createElement("li");
      const marker = document.createElement("span");
      marker.className = "management-wizard-step-marker";
      marker.append(
        document.createTextNode(String(index + 1)),
        createWizardCheckIcon(),
      );
      const label = document.createElement("strong");
      label.textContent = field.label;
      item.append(marker, label);
      stepNavigation.append(item);
    }

    const body = document.createElement("div");
    body.className = "management-form-body";
    const fieldCleanups = [];
    let fieldStep = -1;
    for (const field of fields) {
      if (field.type === "section") fieldStep += 1;
      const firstNewChild = body.children.length;
      if (field.type === "section") appendFormSection(body, field);
      else if (field.type === "choices") appendChoiceField(body, field);
      else if (field.type === "multiselect") {
        fieldCleanups.push(appendMultiSelectField(body, field));
      }
      else appendStandardField(body, field);

      if (wizard) {
        for (let index = firstNewChild; index < body.children.length; index += 1) {
          body.children[index].dataset.formStep = String(Math.max(fieldStep, 0));
        }
      }
    }

    for (const field of fields) {
      if (!field.optionsByField || !field.optionsByValue) continue;
      const source = body.querySelector(
        `[name="${field.optionsByField}"]`,
      );
      const target = body.querySelector(
        `[name="${field.name}"]`,
      );
      if (!(source instanceof HTMLSelectElement) || !(target instanceof HTMLSelectElement)) continue;
      const updateOptions = () => {
        replaceSelectOptions(target, field.optionsByValue[source.value] || []);
      };
      source.addEventListener("change", updateOptions);
      updateOptions();
    }

    for (const field of fields) {
      if (!field.lockByField || !Array.isArray(field.lockValues)) continue;
      const source = body.querySelector(
        `[name="${field.lockByField}"]`,
      );
      const target = body.querySelector(
        `[name="${field.name}"]`,
      );
      if (
        !(source instanceof HTMLSelectElement)
        || !(target instanceof HTMLInputElement)
      ) continue;
      const updateLock = () => {
        const locked = field.lockValues.includes(source.value);
        target.readOnly = locked;
        target.setAttribute("aria-readonly", String(locked));
        const stepper = target.closest(".management-number-stepper");
        if (stepper instanceof HTMLElement) {
          if (locked) stepper.classList.add("locked");
          else stepper.classList.remove("locked");
        }
        if (locked && field.lockValue !== undefined) {
          target.value = String(field.lockValue);
          target.dispatchEvent(new Event("input", { bubbles: true }));
        }
      };
      source.addEventListener("change", updateLock);
      updateLock();
    }

    for (const field of fields) {
      if (!field.acceptByField || !field.acceptByValue) continue;
      const source = body.querySelector(
        `[name="${field.acceptByField}"]`,
      );
      const target = body.querySelector(
        `[name="${field.name}"]`,
      );
      if (
        !(source instanceof HTMLSelectElement)
        || !(target instanceof HTMLInputElement)
      ) continue;

      const updateAccept = () => {
        target.accept = (field.acceptByValue[source.value] || []).join(",");
        target.closest(".management-field")
          ?.querySelector(".management-file-upload")
          ?.dispatchEvent(
          new Event("management:accept-change"),
        );
      };
      source.addEventListener("change", updateAccept);
      updateAccept();
    }

    for (const field of fields) {
      if (!field.helpByField || !field.helpByValue) continue;
      const source = body.querySelector(
        `[name="${field.helpByField}"]`,
      );
      const target = body.querySelector(
        `[name="${field.name}"]`,
      );
      if (
        !(source instanceof HTMLSelectElement)
        || !(target instanceof HTMLInputElement || target instanceof HTMLSelectElement)
      ) continue;
      const help = target.closest("label")?.querySelector("small");
      if (!(help instanceof HTMLElement)) continue;
      const updateHelp = () => {
        help.textContent = field.helpByValue[source.value] || "";
        help.hidden = !help.textContent;
      };
      source.addEventListener("change", updateHelp);
      updateHelp();
    }

    for (const field of fields) {
      if (!field.visibleByField || !Array.isArray(field.visibleValues)) continue;
      const source = body.querySelector(
        `[name="${field.visibleByField}"]`,
      );
      const target = body.querySelector(
        `[name="${field.name}"]`,
      );
      if (
        !(source instanceof HTMLSelectElement)
        || !(target instanceof HTMLInputElement)
      ) continue;
      const container = target.closest(".management-field");
      if (!(container instanceof HTMLElement)) continue;
      const updateVisibility = () => {
        const visible = field.visibleValues.includes(source.value);
        container.hidden = !visible;
        container.dataset.conditionallyHidden = String(!visible);
        target.disabled = !visible;
        if (field.type === "manual-assignments") {
          for (const control of container.querySelectorAll("input, select, button")) control.disabled = !visible;
        }
      };
      source.addEventListener("change", updateVisibility);
      updateVisibility();
    }

    const error = document.createElement("p");
    error.className = "management-form-error";
    error.hidden = true;
    body.append(error);

    const footer = document.createElement("footer");
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "secondary-button";
    cancel.textContent = "取消";
    cancel.addEventListener("click", () => dialog.close());
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "secondary-button";
    previous.textContent = "上一步";
    const next = document.createElement("button");
    next.type = "button";
    next.className = "primary-button";
    next.textContent = "下一步";
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "primary-button";
    submit.textContent = submitLabel;
    footer.append(cancel);
    if (wizard) footer.append(previous, next);
    footer.append(submit);

    let activeStep = 0;
    const visibleSteps = () => stepFields.flatMap((field, index) => {
      const source = field.visibleByField && body.querySelector(`[name="${field.visibleByField}"]`);
      return !source || field.visibleValues.includes(source.value) ? [index] : [];
    });
    const updateWizard = () => {
      if (!wizard) return;
      const steps = visibleSteps();
      if (!steps.includes(activeStep)) activeStep = steps[steps.length - 1];
      for (const element of body.querySelectorAll("[data-form-step]")) {
        element.hidden = (
          Number(element.dataset.formStep) !== activeStep
          || element.dataset.conditionallyHidden === "true"
        );
      }
      for (const [index, item] of [...stepNavigation.children].entries()) {
        item.hidden = !steps.includes(index);
        item.classList.toggle("last-visible", index === steps.at(-1));
        item.classList.toggle("active", index === activeStep);
        item.classList.toggle("complete", index < activeStep);
      }
      previous.hidden = activeStep === steps[0];
      next.hidden = activeStep === steps[steps.length - 1];
      submit.hidden = !next.hidden;
      body.scrollTop = 0;
    };
    form.addEventListener("management:update-wizard", updateWizard);
    body.addEventListener("change", (event) => {
      if (fields.some((field) => field.visibleByField === event.target.name)) {
        updateWizard();
      }
    });
    const validateStep = () => {
      const controls = body.querySelectorAll(
        `[data-form-step="${activeStep}"] input, [data-form-step="${activeStep}"] select, [data-form-step="${activeStep}"] textarea`,
      );
      for (const control of controls) {
        const validate = standardFieldValidators.get(control);
        if (validate) validate();
        if (!control.checkValidity()) {
          control.focus();
          control.reportValidity();
          return false;
        }
      }
      return true;
    };
    previous.addEventListener("click", () => {
      const steps = visibleSteps();
      activeStep = steps[Math.max(0, steps.indexOf(activeStep) - 1)];
      updateWizard();
    });
    const advanceWizard = () => {
      if (!validateStep()) return;
      const steps = visibleSteps();
      activeStep = steps[Math.min(steps.length - 1, steps.indexOf(activeStep) + 1)];
      updateWizard();
    };
    next.addEventListener("click", advanceWizard);
    form.append(header, stepNavigation, body, footer);
    dialog.append(form);

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (wizard && activeStep !== visibleSteps().at(-1)) {
        advanceWizard();
        return;
      }
      error.hidden = true;
      if (wizard) {
        for (const step of visibleSteps()) {
          activeStep = step;
          updateWizard();
          if (!validateStep()) return;
        }
      }
      submit.disabled = true;
      submit.textContent = "正在提交…";
      try {
        const formData = buildManagementFormData(form);
        closeManagementMultiselects(form);
        const result = await onSubmit(formData);
        if (typeof onSuccess === "function") await onSuccess(result);
        managementOptionsRequest = null;
        dialog.close();
        if (successMessage) toast(successMessage);
        if (refreshAfterSubmit) await refresh({ silent: true });
      } catch (requestError) {
        error.textContent = requestError.message;
        error.hidden = false;
      } finally {
        submit.disabled = false;
        submit.textContent = submitLabel;
      }
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", () => {
      for (const cleanup of fieldCleanups) cleanup();
      dialog.remove();
    });
    document.body.append(dialog);
    updateWizard();
    dialog.showModal();
    return dialog;
  }

  async function openCreateDialog() {
    const resource = getCreateResource();
    createButton.disabled = true;

    try {
      if (resource === "models") {
        await openModelRegistrationDialog();
      } else if (resource === "versions") {
        await openVersionRegistrationDialog();
      } else if (resource === "deployments") {
        await openDeploymentCreateDialog();
      } else if (resource === "routings") {
        await openRoutingCreateDialog();
      } else if (resource === "experiments") {
        await openExperimentCreateDialog();
      } else if (resource === "variants") {
        await openVariantCreateDialog();
      } else if (resource === "users") {
        await openUserCreateDialog();
      } else if (resource === "roles") {
        await openRoleCreateDialog();
      }
    } catch (error) {
      toast(error.message);
    } finally {
      createButton.disabled = false;
    }
  }

  async function openVersionRegistrationDialog() {
    let selectedModel = (
      state.selectedModel?.model_id === state.selectedModelId
        ? state.selectedModel
        : null
    );

    if (state.selectedModelId !== null) {
      if (selectedModel === null) {
        selectedModel = await request(
          `models/${encodeURIComponent(state.selectedModelId)}/detail`,
        );
      }
      await openModelRegistrationDialog(selectedModel);
      return;
    }

    const response = await request(
      "sections/models?page=1&page_size=100&sort_by=name&sort_order=asc",
    );
    const models = Array.isArray(response?.items)
      ? response.items
      : [];

    if (models.length === 0) {
      throw new Error("暂无可添加版本的模型");
    }

    await openModelRegistrationDialog(null, models);
  }

  /**
   * 打开模型注册或版本添加对话框。
   *
   * @param {ConsoleModel | null} [targetModel=null] 目标模型
   * @param {ConsoleModel[] | null} [availableModels=null] 向导内可选模型
   * @returns {Promise<void>} 对话框关闭后完成
   */
  async function openModelRegistrationDialog(
    targetModel = null,
    availableModels = null,
  ) {
    const modelCandidates = Array.isArray(availableModels)
      ? availableModels
      : null;
    const selectedModel = modelCandidates
      ? modelCandidates[0]
      : (targetModel ?? state.selectedModel);
    const options = await getManagementOptions();
    const artifactExtensions = artifactExtensionsByFramework(options);
    const selectedName = selectedModel?.name || "";
    const addingVersion = Boolean(selectedName || modelCandidates);
    let registrationTarget = selectedName
      ? {
        exists: true,
        description: selectedModel?.description || null,
        version_exists: false,
      }
      : { exists: false, description: null, version_exists: false };
    const dialog = createManagementDialog({
      title: addingVersion ? "添加版本" : "注册模型",
      description: "上传模型文件并配置版本信息。",
      submitLabel: "确认注册",
      wizard: true,
      fields: [
        ...(modelCandidates ? [
          {
            type: "section",
            label: "选择模型",
            help: "选择要添加版本的模型。",
          },
          {
            name: "name",
            label: "模型名称",
            type: "select",
            required: true,
            value: selectedName,
            options: modelCandidates.map((model) => ({
              value: model.name,
              label: model.display_name
                ? `${model.display_name} (${model.name})`
                : model.name,
            })),
          },
        ] : []),
        {
          type: "section",
          label: addingVersion ? "版本信息" : "基本信息",
          help: addingVersion
            ? "填写版本和类型信息。"
            : "填写模型标识、版本和类型信息。",
        },
        ...(!modelCandidates ? [{
          name: "name",
          label: "模型名称",
          required: true,
          value: selectedName,
          readonly: Boolean(selectedName),
          validationPattern: "[a-z0-9](?:[a-z0-9._-]{0,61}[a-z0-9])?",
          invalidMessage: "请使用小写字母、数字、点、下划线或连字符",
        }] : []),
        ...(!modelCandidates ? [{
          name: "display_name",
          label: "显示名称",
          value: selectedModel?.display_name || "",
          readonly: Boolean(selectedName),
        }] : []),
        {
          name: "version",
          label: "版本",
          required: true,
          validationPattern: "(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-(?:0|[1-9]\\d*|\\d*[A-Za-z-][0-9A-Za-z-]*)(?:\\.(?:0|[1-9]\\d*|\\d*[A-Za-z-][0-9A-Za-z-]*))*)?(?:\\+[0-9A-Za-z-]+(?:\\.[0-9A-Za-z-]+)*)?",
          invalidMessage: "请输入主版本.次版本.修订版本，例如 1.0.0",
        },
        {
          name: "framework",
          label: "框架",
          type: "select",
          options: ["sklearn", "xgboost", "lightgbm", "catboost"],
          value: selectedModel?.framework || "sklearn",
          required: true,
        },
        {
          name: "model_type",
          label: "类型",
          type: "select",
          options: modelTypeOptions(
            filterModelTypes(
              modelTypesByFramework[selectedModel?.framework || "sklearn"] || [],
              options.model_types || [],
            ),
          ),
          value: selectedModel?.model_type || "",
          optionsByField: "framework",
          optionsByValue: Object.fromEntries(
            Object.entries(modelTypesByFramework).map(([framework, modelTypes]) => [
              framework,
              modelTypeOptions(filterModelTypes(
                modelTypes,
                options.model_types || [],
              )),
            ]),
          ),
          required: true,
        },
        {
          name: "task_type",
          label: "任务类型",
          type: "select",
          options: taskTypeOptionsByModelType[
            selectedModel?.model_type || "logistic_regression"
          ],
          value: selectedModel?.task_type
            || ((selectedModel?.model_type || "logistic_regression") === "logistic_regression"
              ? "scoring"
              : "classification"),
          optionsByField: "model_type",
          optionsByValue: taskTypeOptionsByModelType,
          required: true,
        },
        {
          type: "section",
          label: "文件上传",
          help: "上传模型文件。",
        },
        {
          name: "file",
          label: "模型文件",
          type: "file-dropzone",
          required: true,
          wide: true,
          acceptByField: "framework",
          acceptByValue: artifactExtensions,
          maxFileSize: maxModelUploadBytes,
        },
        {
          type: "section",
          label: "说明与选项",
          help: addingVersion
            ? "填写版本说明，并确认版本注册选项。"
            : "填写模型和版本说明，并确认注册选项。",
        },
        ...(!addingVersion ? [{
          name: "description",
          label: "模型描述",
          type: "textarea",
          rows: 3,
          wide: true,
          value: registrationTarget.description || "",
          readonly: registrationTarget.exists,
          help: registrationTarget.exists ? "模型描述由已有模型维护。" : "",
        }] : []),
        { name: "version_description", label: "版本描述", type: "textarea", rows: 3, wide: true },
        {
          name: "force",
          label: "强制重新注册已有版本",
          type: "checkbox",
          wide: true,
          help: "强制重新注册要求版本处于停用状态，并且当前没有部署。",
        },
      ],
      onSubmit: async (formData) => {
        const file = formData.get("file");
        if (!(file instanceof File) || file.size === 0) throw new Error("请选择模型文件");
        if (file.size > maxModelUploadBytes) {
          throw new Error(`模型文件不能超过 ${maxModelUploadMegabytes} MB`);
        }
        const framework = String(formData.get("framework") || "");
        const allowedExtensions = artifactExtensions[framework] || [];
        const filename = file.name.toLowerCase();
        if (!allowedExtensions.some((extension) => filename.endsWith(extension))) {
          const supportedFormats = allowedExtensions.join("、");
          throw new Error(
            `${frameworkLabels[framework] || framework} 模型文件支持 ${supportedFormats}`,
          );
        }
        const name = optionalValue(formData, "name");
        const selectedCandidate = modelCandidates?.find(
          (model) => model.name === name,
        );
        registrationTarget = await request(
          `models/registration-target?name=${encodeURIComponent(name || "")}&version=${encodeURIComponent(optionalValue(formData, "version") || "")}`,
        );
        const metadata = {
          name,
          display_name: selectedCandidate?.display_name
            || optionalValue(formData, "display_name"),
          version: optionalValue(formData, "version"),
          framework: optionalValue(formData, "framework"),
          model_type: optionalValue(formData, "model_type"),
          task_type: optionalValue(formData, "task_type"),
          description: registrationTarget.exists
            ? registrationTarget.description
            : optionalValue(formData, "description"),
          version_description: optionalValue(formData, "version_description"),
          force: formData.get("force") === "on",
        };
        const body = new FormData();
        body.append("metadata", JSON.stringify(metadata));
        body.append("file", file);
        await request("models", { method: "POST", body });
      },
    });

    const nameInput = dialog.querySelector('[name="name"]');
    const versionInput = dialog.querySelector('[name="version"]');
    const descriptionInput = dialog.querySelector('[name="description"]');
    const forceInput = dialog.querySelector('[name="force"]');
    const frameworkInput = dialog.querySelector('[name="framework"]');
    const modelTypeInput = dialog.querySelector('[name="model_type"]');
    const taskTypeInput = dialog.querySelector('[name="task_type"]');
    const forceField = forceInput?.closest(".management-field");
    if (
      frameworkInput instanceof HTMLSelectElement
      && modelTypeInput instanceof HTMLSelectElement
    ) {
      frameworkInput.addEventListener("change", () => {
        modelTypeInput.dispatchEvent(new Event("change", { bubbles: true }));
      });
    }
    const updateForceVisibility = () => {
      if (!(forceField instanceof HTMLElement)) return;
      const conditionallyHidden = !registrationTarget.version_exists;
      forceField.dataset.conditionallyHidden = String(conditionallyHidden);
      if (conditionallyHidden && forceInput instanceof HTMLInputElement) {
        forceInput.checked = false;
      }
      forceInput?.form?.dispatchEvent(
        new Event("management:update-wizard"),
      );
    };
    updateForceVisibility();
    if (
      nameInput instanceof HTMLInputElement
      && versionInput instanceof HTMLInputElement
      && descriptionInput instanceof HTMLTextAreaElement
      && !nameInput.readOnly
    ) {
      let draftDescription = descriptionInput.value;
      let lookupSequence = 0;
      const synchronizeDescription = async () => {
        const sequence = ++lookupSequence;
        const name = nameInput.value.trim();
        const version = versionInput.value.trim();
        if (!descriptionInput.readOnly) {
          draftDescription = descriptionInput.value;
        }
        const target = await request(
          `models/registration-target?name=${encodeURIComponent(name)}&version=${encodeURIComponent(version)}`,
        );
        if (
          sequence !== lookupSequence
          || name !== nameInput.value.trim()
          || version !== versionInput.value.trim()
        ) return;

        registrationTarget = target;
        descriptionInput.readOnly = target.exists;
        descriptionInput.value = target.exists
          ? (target.description || "")
          : draftDescription;
        updateForceVisibility();
      };
      nameInput.addEventListener("blur", () => {
        synchronizeDescription().catch((lookupError) => toast(lookupError.message));
      });
      versionInput.addEventListener("blur", () => {
        synchronizeDescription().catch((lookupError) => toast(lookupError.message));
      });
    } else if (
      (
        nameInput instanceof HTMLInputElement
        || nameInput instanceof HTMLSelectElement
      )
      && versionInput instanceof HTMLInputElement
    ) {
      const synchronizeExistingVersion = () => {
        request(
          `models/registration-target?name=${encodeURIComponent(nameInput.value.trim())}&version=${encodeURIComponent(versionInput.value.trim())}`,
        ).then((target) => {
          registrationTarget = target;
          if (descriptionInput instanceof HTMLTextAreaElement) {
            descriptionInput.value = target.description || "";
          }
          updateForceVisibility();
        }).catch((lookupError) => toast(lookupError.message));
      };
      versionInput.addEventListener("blur", synchronizeExistingVersion);
      if (nameInput instanceof HTMLSelectElement) {
        nameInput.addEventListener("change", () => {
          const candidate = modelCandidates?.find(
            (model) => model.name === nameInput.value,
          );
          registrationTarget = {
            exists: true,
            description: candidate?.description || null,
            version_exists: false,
          };
          if (descriptionInput instanceof HTMLTextAreaElement) {
            descriptionInput.value = registrationTarget.description || "";
          }
          if (
            candidate
            && frameworkInput instanceof HTMLSelectElement
            && modelTypeInput instanceof HTMLSelectElement
            && taskTypeInput instanceof HTMLSelectElement
          ) {
            frameworkInput.value = candidate.framework || "sklearn";
            frameworkInput.dispatchEvent(new Event("change", { bubbles: true }));
            modelTypeInput.value = candidate.model_type || modelTypeInput.value;
            taskTypeInput.value = candidate.task_type
              || (candidate.model_type === "logistic_regression"
                ? "scoring"
                : "classification");
          }
          updateForceVisibility();
          if (versionInput.value.trim()) synchronizeExistingVersion();
        });
      }
    }
  }

  async function openDeploymentCreateDialog(targetVersion = null) {
    const response = await request(
      "sections/models?page=1&page_size=100&sort_by=name&sort_order=asc",
    );
    const models = (Array.isArray(response?.items) ? response.items : [])
      .filter((model) => model.status === "active");
    const versionsByModel = Object.fromEntries(await Promise.all(
      models.map(async (model) => {
        const versionResponse = await request(
          `models/${encodeURIComponent(model.model_id)}/versions?page=1&page_size=100&sort=version&order=desc`,
        );
        const versions = (Array.isArray(versionResponse?.items)
          ? versionResponse.items
          : []
        ).filter((version) => version.status === "active");
        return [model.model_id, versions];
      }),
    ));
    const deployableModels = models.filter(
      (model) => versionsByModel[model.model_id].length > 0,
    );

    if (deployableModels.length === 0) {
      throw new Error("暂无已激活且包含可部署版本的模型");
    }
    if (targetVersion) {
      const targetVersions = versionsByModel[targetVersion.model_id] || [];
      if (!targetVersions.some(
        (version) => version.version_id === targetVersion.version_id,
      )) {
        throw new Error("该版本当前不可部署");
      }
    }

    createManagementDialog({
      title: "创建部署",
      description: "选择模型版本并定义发布方式。",
      submitLabel: "创建部署",
      fields: [
        {
          name: "model_id",
          label: "模型",
          type: "select",
          required: true,
          value: targetVersion?.model_id,
          options: deployableModels.map((model) => ({
            value: model.model_id,
            label: model.display_name
              ? `${model.display_name} (${model.name})`
              : model.name,
          })),
        },
        {
          name: "version_id",
          label: "版本",
          type: "select",
          required: true,
          value: targetVersion?.version_id,
          optionsByField: "model_id",
          optionsByValue: Object.fromEntries(deployableModels.map((model) => [
            model.model_id,
            versionsByModel[model.model_id].map((version) => ({
              value: version.version_id,
              label: version.version,
            })),
          ])),
        },
        { name: "rollout_type", label: "发布类型", type: "select", options: deploymentRolloutOptions },
        {
          name: "role",
          label: "部署角色",
          type: "select",
          options: deploymentRoleOptionsByRollout.full,
          optionsByField: "rollout_type",
          optionsByValue: deploymentRoleOptionsByRollout,
        },
        { name: "description", label: "描述", type: "textarea", rows: 3, wide: true },
        {
          name: "threshold",
          label: "决策阈值",
          type: "number",
          step: "any",
          help: "可选；默认 0.5。",
          helpByField: "model_id",
          helpByValue: Object.fromEntries(deployableModels.map(
            (model) => [
              model.model_id,
              model.task_type === "scoring"
                ? "可选；默认 600。"
                : "可选；默认 0.5。",
            ],
          )),
          visibleByField: "rollout_type",
          visibleValues: ["full", "canary"],
          wide: true,
        },
      ],
      onSubmit: async (formData) => {
        return request("deployments", {
          method: "POST",
          body: JSON.stringify({
          model_id: optionalValue(formData, "model_id"),
          version_id: optionalValue(formData, "version_id"),
          rollout_type: optionalValue(formData, "rollout_type"),
          role: optionalValue(formData, "role"),
          threshold: optionalValue(formData, "threshold"),
          description: optionalValue(formData, "description"),
          }),
        });
      },
    });
  }

  async function openRoutingCreateDialog() {
    const [deploymentResponse, modelResponse, routingResponse, options] = await Promise.all([
      request(
        "sections/deployments?page=1&page_size=100&sort_by=updated_at&sort_order=desc",
      ),
      request(
        "sections/models?page=1&page_size=100&sort_by=name&sort_order=asc",
      ),
      request(
        "sections/routings?page=1&page_size=100&sort_by=updated_at&sort_order=desc",
      ),
      getManagementOptions(),
    ]);
    const routedDeploymentIds = new Set(
      (Array.isArray(routingResponse?.items) ? routingResponse.items : [])
        .map((routing) => routing.deployment_id)
        .filter(Boolean),
    );
    const deployments = (
      Array.isArray(deploymentResponse?.items) ? deploymentResponse.items : []
    )
      .filter((deployment) => (
        deployment.status === "active"
        && deployment.environment === state.user?.environment
        && !routedDeploymentIds.has(deployment.deployment_id)
      ));
    const modelsById = new Map(
      (Array.isArray(modelResponse?.items) ? modelResponse.items : [])
        .map((model) => [model.model_id, model]),
    );

    if (deployments.length === 0) {
      throw new Error("暂无可用部署，请先启用未配置路由的部署");
    }
    const fullDeploymentIds = deployments
      .filter((deployment) => String(deployment.rollout_type).toLowerCase() === "full")
      .map((deployment) => deployment.deployment_id);
    const roleLabels = {
      champion: "Champion",
      challenger: "Challenger",
      shadow: "Shadow",
    };

    createManagementDialog({
      title: "创建路由",
      description: "选择部署并配置流量规则。",
      submitLabel: "创建路由",
      fields: [
        {
          name: "name",
          label: "路由名称",
          required: true,
          wide: true,
        },
        {
          name: "deployment_id",
          label: "模型名称",
          type: "select",
          required: true,
          wide: true,
          options: deployments.map((deployment) => {
            const model = modelsById.get(deployment.model_id);
            const modelName = model?.name || deployment.model_name || "未命名模型";
            const modelLabel = model?.display_name
              ? `${model.display_name} (${modelName})`
              : modelName;
            const roleLabel = roleLabels[
              String(deployment.role).toLowerCase()
            ] || deployment.role || "未标注角色";
            return {
              value: deployment.deployment_id,
              label: `${modelLabel} · ${deployment.model_version || "未标注版本"} · ${roleLabel}`,
            };
          }),
        },
        {
          name: "traffic_ratio",
          label: "流量比例",
          type: "number",
          min: 0,
          max: 100,
          step: 0.1,
          value: 100,
          suffix: "%",
          stepper: true,
          lockByField: "deployment_id",
          lockValues: fullDeploymentIds,
          lockValue: 100,
          required: true,
        },
        {
          name: "rules",
          label: "规则配置",
          type: "json-config",
          mode: "create",
          template: options.routing_rules?.example || {},
          wide: true,
        },
        {
          name: "effective_from",
          label: "生效时间",
          type: "datetime-local",
        },
        {
          name: "effective_to",
          label: "失效时间",
          type: "datetime-local",
        },
        { name: "description", label: "描述", type: "textarea", rows: 3, wide: true },
      ],
      onSubmit: async (formData) => {
        const rules = readJsonConfig(formData, "rules");
        return request("routings", {
          method: "POST",
          body: JSON.stringify({
            name: optionalValue(formData, "name"),
            deployment_id: optionalValue(formData, "deployment_id"),
            traffic_ratio: Number(formData.get("traffic_ratio")) / 100,
            rules,
            rules_metadata: readJsonConfig(formData, "rules_metadata"),
            effective_from: optionalValue(formData, "effective_from"),
            effective_to: optionalValue(formData, "effective_to"),
            description: optionalValue(formData, "description"),
          }),
        });
      },
    });
  }

  async function openExperimentCreateDialog() {
    async function loadAll(resource) {
      const items = [];
      for (let page = 1; ; page += 1) {
        const response = await request(`sections/${resource}?page=${page}&page_size=100&deleted=false`);
        const batch = response.items || [];
        items.push(...batch);
        if (batch.length < 100) return items;
      }
    }
    const [allModels, allDeployments] = await Promise.all([loadAll("models"), loadAll("deployments")]);
    const response = { items: allModels };
    const models = (Array.isArray(response?.items) ? response.items : [])
      .filter((model) => model.status === "active");

    if (models.length === 0) {
      throw new Error("暂无已激活的模型");
    }

    createManagementDialog({
      title: "创建实验",
      description: "配置实验信息、分组和客户分配，保存为草稿。",
      submitLabel: "保存",
      wizard: true,
      fields: [
        { type: "section", label: "基本信息" },
        { name: "name", label: "实验名称", required: true },
        {
          name: "model_id",
          label: "模型",
          type: "select",
          required: true,
          options: models.map((model) => ({
            value: model.model_id,
            label: model.display_name
              ? `${model.display_name} (${model.name})`
              : model.name,
          })),
        },
        {
          name: "strategy", label: "分配策略", type: "select",
          options: [["hash", "稳定哈希"], ["manual", "手动分配"]],
        },
        {
          name: "traffic_ratio",
          label: "流量比例",
          type: "number",
          min: 1,
          max: 100,
          step: 1,
          value: 100,
          suffix: "%",
          stepper: true,
          required: true,
          visibleByField: "strategy",
          visibleValues: ["hash"],
        },
        {
          name: "bucket_key",
          label: "主体标识字段",
          required: true,
          placeholder: "例如 customer_id",
          wide: true,
        },
        { name: "effective_from", label: "生效时间", type: "datetime-local" },
        { name: "effective_to", label: "失效时间", type: "datetime-local" },
        { name: "description", label: "描述", type: "textarea", rows: 3, wide: true },
        { type: "section", label: "配置分组" },
        {
          name: "groups", type: "experiment-groups",
          models,
          deployments: allDeployments.filter((item) => item.status === "active"
            && item.role !== "shadow" && item.rollout_type !== "shadow"),
        },
        { type: "section", label: "指定客户", visibleByField: "strategy", visibleValues: ["manual"] },
        {
          name: "manual_assignments", type: "manual-assignments", sourceGroups: "groups",
          visibleByField: "strategy", visibleValues: ["manual"],
        },
      ],
      onSubmit: async (formData) => request("experiments", {
        method: "POST",
        body: JSON.stringify({
          name: optionalValue(formData, "name"),
          model_id: optionalValue(formData, "model_id"),
          strategy: optionalValue(formData, "strategy"),
          traffic_ratio: formData.has("traffic_ratio")
            ? Number(formData.get("traffic_ratio")) / 100 : undefined,
          bucket_key: optionalValue(formData, "bucket_key"),
          groups: readJsonConfig(formData, "groups"),
          manual_assignments: readJsonConfig(formData, "manual_assignments"),
          effective_from: optionalValue(formData, "effective_from"),
          effective_to: optionalValue(formData, "effective_to"),
          description: optionalValue(formData, "description"),
        }),
      }),
    });
  }

  async function openVariantCreateDialog() {
    const selectedExperimentId = state.selectedExperimentId;

    const [experimentResponse, deploymentResponse, modelResponse, variantResponse] = (
      await Promise.all([
        request(
          "sections/experiments?page=1&page_size=100&sort_by=updated_at&sort_order=desc",
        ),
        request(
          "sections/deployments?page=1&page_size=100&sort_by=updated_at&sort_order=desc",
        ),
        request(
          "sections/models?page=1&page_size=100&sort_by=name&sort_order=asc",
        ),
        request(
          selectedExperimentId === null
            ? "sections/variants?page=1&page_size=100&sort_by=updated_at&sort_order=desc"
            : `experiments/${encodeURIComponent(selectedExperimentId)}/variants?page=1&page_size=100`,
        ),
      ])
    );
    const experiments = (
      Array.isArray(experimentResponse?.items) ? experimentResponse.items : []
    );
    const experiment = selectedExperimentId === null
      ? null
      : experiments.find((item) => item.experiment_id === selectedExperimentId);

    if (selectedExperimentId !== null && !experiment) {
      throw new Error("无法读取当前实验信息");
    }

    const variants = Array.isArray(variantResponse?.items) ? variantResponse.items : [];
    const allDeployments = Array.isArray(deploymentResponse?.items)
      ? deploymentResponse.items
      : [];
    const modelsById = new Map(
      (Array.isArray(modelResponse?.items) ? modelResponse.items : [])
        .map((model) => [model.model_id, model]),
    );
    const roleLabels = {
      champion: "Champion",
      challenger: "Challenger",
    };
    const deploymentOptionsByExperiment = Object.fromEntries(experiments.map((item) => {
      const existingDeploymentIds = new Set(
        variants
          .filter((variant) => variant.experiment_id === item.experiment_id)
          .map((variant) => variant.deployment_id)
          .filter(Boolean),
      );
      const options = allDeployments.filter((deployment) => (
        deployment.model_id === item.model_id
        && deployment.environment === item.environment
        && deployment.status === "active"
        && String(deployment.rollout_type).toLowerCase() !== "shadow"
        && String(deployment.role).toLowerCase() !== "shadow"
        && !existingDeploymentIds.has(deployment.deployment_id)
      )).map((deployment) => {
        const model = modelsById.get(deployment.model_id);
        const modelName = model?.name || deployment.model_name || "未命名模型";
        const modelLabel = model?.display_name
          ? `${model.display_name} (${modelName})`
          : modelName;
        const roleLabel = roleLabels[
          String(deployment.role).toLowerCase()
        ] || deployment.role || "未标注角色";
        return {
          value: deployment.deployment_id,
          label: `${modelLabel} · ${deployment.model_version || "未标注版本"} · ${roleLabel}`,
        };
      });
      return [item.experiment_id, options];
    }));
    const availableExperiments = experiments.filter((item) => (
      (deploymentOptionsByExperiment[item.experiment_id] || []).length > 0
    ));

    if (selectedExperimentId !== null && (
      deploymentOptionsByExperiment[selectedExperimentId] || []
    ).length === 0) {
      throw new Error("当前实验暂无可添加的部署");
    }
    if (selectedExperimentId === null && availableExperiments.length === 0) {
      throw new Error("暂无可添加分组的实验");
    }

    const experimentField = experiment
      ? { name: "experiment", label: "实验名称", type: "display", value: experiment.name }
      : {
          name: "experiment_id",
          label: "实验",
          type: "select",
          required: true,
          options: availableExperiments.map((item) => ({
            value: item.experiment_id,
            label: item.name,
          })),
        };
    const initialExperimentId = selectedExperimentId || availableExperiments[0].experiment_id;

    createManagementDialog({
      title: "添加分组",
      description: "选择部署并配置分组权重。",
      submitLabel: "添加分组",
      fields: [
        experimentField,
        { name: "name", label: "分组名称", required: true },
        {
          name: "deployment_id",
          label: "部署",
          type: "select",
          required: true,
          options: deploymentOptionsByExperiment[initialExperimentId],
          optionsByField: experiment ? undefined : "experiment_id",
          optionsByValue: deploymentOptionsByExperiment,
        },
        { name: "weight", label: "权重", type: "number", min: 0.01, max: 1, step: 0.01, value: 0.5, required: true },
        { name: "is_control", label: "设为对照组", type: "checkbox" },
        { name: "description", label: "描述", type: "textarea", rows: 3, wide: true },
      ],
      onSubmit: async (formData) => {
        const experimentId = selectedExperimentId
          || optionalValue(formData, "experiment_id");
        return request(`experiments/${encodeURIComponent(experimentId)}/variants`, {
          method: "POST",
          body: JSON.stringify({
            name: optionalValue(formData, "name"),
            deployment_id: optionalValue(formData, "deployment_id"),
            weight: Number(formData.get("weight")),
            is_control: formData.get("is_control") === "on",
            description: optionalValue(formData, "description"),
          }),
        });
      },
    });
  }

  async function openUserCreateDialog() {
    const options = await getManagementOptions();
    createManagementDialog({
      title: "创建用户",
      description: "创建本地用户并分配角色。",
      submitLabel: "创建用户",
      fields: [
        { name: "username", label: "用户名", required: true },
        { name: "display_name", label: "显示名称" },
        { name: "email", label: "邮箱", type: "email" },
        { name: "password", label: "初始密码", type: "password", required: true },
        {
          name: "roles",
          label: "角色",
          type: "choices",
          options: roleOptions(options.roles || []),
          multiple: true,
          wide: true,
          emptyText: "暂无可分配的有效角色",
        },
      ],
      onSubmit: async (formData) => request("users", {
        method: "POST",
        body: JSON.stringify({
          username: optionalValue(formData, "username"),
          display_name: optionalValue(formData, "display_name"),
          email: optionalValue(formData, "email"),
          password: optionalValue(formData, "password"),
          roles: formData.getAll("roles").map(String),
        }),
      }),
    });
  }

  async function openRoleCreateDialog() {
    const options = await getManagementOptions();
    createManagementDialog({
      title: "创建角色",
      description: "创建角色并从权限目录中分配权限。",
      submitLabel: "创建角色",
      fields: [
        { name: "name", label: "角色名称", required: true },
        { name: "description", label: "描述", type: "textarea", rows: 3, wide: true },
        {
          name: "permissions",
          label: "权限",
          type: "multiselect",
          options: permissionOptions(options.permissions || []),
          multiple: true,
          wide: true,
          required: true,
          emptyText: "暂无可分配权限",
        },
      ],
      onSubmit: async (formData) => {
        const permissions = formData.getAll("permissions").map(String);
        if (!permissions.length) throw new Error("请至少选择一项权限");
        if (permissions.includes("*") && permissions.length > 1) {
          throw new Error("选择全部权限时无需再选择其他权限");
        }
        return request("roles", {
          method: "POST",
          body: JSON.stringify({
            name: optionalValue(formData, "name"),
            description: optionalValue(formData, "description"),
            permissions,
          }),
        });
      },
    });
  }

  function canManageSection(section) {
    if (["batches", "models", "versions", "experiments"].includes(section)) return true;

    const capabilities = {
      deployments: ["deployments.manage", "deployments.delete"],
      routings: ["routings.manage", "routings.delete"],
      experiments: ["experiments.manage", "experiments.delete"],
      variants: ["variants.manage", "variants.delete"],
      users: ["users.manage"],
      roles: ["roles.manage"],
    };
    return (capabilities[section] || []).some(hasCapability);
  }

  function getRecordActions(section, record) {
    const status = String(record.status || "").toLowerCase();
    const actions = /** @type {RecordAction[]} */ ([]);
    const add = (
      label,
      resource,
      identifier,
      action,
      capability,
      tone = "",
    ) => {
      if (hasCapability(capability)) {
        actions.push({ label, resource, identifier, action, tone });
      }
    };

    if (section === "batches") {
      actions.push({
        label: "查看详情",
        resource: "batches",
        identifier: record.batch_id,
        action: "view",
        tone: "",
      });
      if (["queued", "running", "retrying"].includes(status)) {
        add("取消", "batches", record.batch_id, "cancel", "batches.manage", "danger");
      } else if (["partially_succeeded", "failed", "cancelled"].includes(status)) {
        add("重试", "batches", record.batch_id, "retry", "batches.manage");
      }
      if (actions.length > 1) actions[1].dividerBefore = true;
    } else if (section === "models") {
      if (record.deleted_at) {
        add("恢复", "models", record.model_id, "restore", "models.create");
        add("永久清理", "models", record.model_id, "purge", "models.create", "danger");
        return actions;
      }
      add(
        "编辑",
        "models",
        record.model_id,
        "edit",
        "models.create",
      );
      const lifecycleStart = actions.length;
      if (status === "active") {
        add("停用", "models", record.model_id, "deactivate", "models.create");
      } else if (status === "inactive") {
        add("激活", "models", record.model_id, "activate", "models.create");
      }
      if (status === "active" || status === "inactive") {
        add("弃用", "models", record.model_id, "deprecate", "models.create");
      }
      if (status === "inactive" || status === "deprecated") {
        add("归档", "models", record.model_id, "archive", "models.create");
      }
      if (actions.length > lifecycleStart) {
        actions[lifecycleStart].dividerBefore = true;
      }
      add("删除", "models", record.model_id, "delete", "models.create", "danger");
    } else if (section === "versions") {
      if (record.deleted_at) {
        add("恢复", "versions", record.version_id, "restore", "versions.manage");
        add("永久清理", "versions", record.version_id, "purge", "versions.manage", "danger");
        return actions;
      }
      add(
        "编辑",
        "versions",
        record.version_id,
        "edit",
        "versions.manage",
      );
      const lifecycleStart = actions.length;
      if (status === "active") {
        add("停用", "versions", record.version_id, "deactivate", "versions.manage");
      } else if (status === "inactive") {
        add("激活", "versions", record.version_id, "activate", "versions.manage");
      }
      if (status === "active" || status === "inactive") {
        add("弃用", "versions", record.version_id, "deprecate", "versions.manage");
      }
      if (status === "inactive" || status === "deprecated") {
        add("归档", "versions", record.version_id, "archive", "versions.manage");
      }
      if (actions.length > lifecycleStart) {
        actions[lifecycleStart].dividerBefore = true;
      }
      add("删除", "versions", record.version_id, "delete", "versions.manage", "danger");
    } else if (section === "deployments") {
      if (record.deleted_at) {
        add("恢复", "deployments", record.deployment_id, "restore", "deployments.manage");
        return actions;
      }
      if (status === "inactive") {
        add("编辑", "deployments", record.deployment_id, "edit", "deployments.manage");
      }
      const lifecycleStart = actions.length;
      add(status === "active" ? "停用" : "启用", "deployments", record.deployment_id, status === "active" ? "disable" : "enable", "deployments.manage");
      if (lifecycleStart > 0 && actions.length > lifecycleStart) {
        actions[lifecycleStart].dividerBefore = true;
      }
      if (status === "inactive") {
        add("删除", "deployments", record.deployment_id, "delete", "deployments.delete", "danger");
      }
    } else if (section === "routings") {
      if (record.deleted_at) {
        add("恢复", "routings", record.routing_id, "restore", "routings.manage");
        return actions;
      }
      add("编辑", "routings", record.routing_id, "edit", "routings.manage");
      const lifecycleStart = actions.length;
      add(status === "enabled" ? "禁用" : "启用", "routings", record.routing_id, status === "enabled" ? "disable" : "enable", "routings.manage");
      if (lifecycleStart > 0 && actions.length > lifecycleStart) {
        actions[lifecycleStart].dividerBefore = true;
      }
      if (status === "disabled") {
        add("删除", "routings", record.routing_id, "delete", "routings.delete", "danger");
      }
    } else if (section === "experiments") {
      if (record.deleted_at) {
        add("恢复", "experiments", record.experiment_id, "restore", "experiments.manage");
        return actions;
      }
      if (status === "draft") {
        add("编辑", "experiments", record.experiment_id, "edit", "experiments.manage");
      }
      const transitions = {
        draft: [["启动", "start"]],
        running: [["暂停", "pause"], ["停止", "stop"], ["完成", "complete"]],
        paused: [["继续", "start"], ["停止", "stop"], ["完成", "complete"]],
        stopped: [["归档", "archive"]],
        completed: [["归档", "archive"]],
      };
      const lifecycleStart = actions.length;
      for (const [label, action, tone = ""] of transitions[status] || []) {
        add(label, "experiments", record.experiment_id, action, action === "delete" ? "experiments.delete" : "experiments.manage", tone);
      }
      if (lifecycleStart > 0 && actions.length > lifecycleStart) {
        actions[lifecycleStart].dividerBefore = true;
      }
      if (status === "draft" || status === "archived") {
        add("删除", "experiments", record.experiment_id, "delete", "experiments.delete", "danger");
      }
    } else if (section === "variants") {
      if (record.deleted_at) {
        add("恢复", "variants", record.variant_id, "restore", "variants.manage");
        return actions;
      }
      const experimentStatus = String(record.experiment_status || "").toLowerCase();
      if (!experimentStatus || experimentStatus === "draft") {
        add("编辑", "variants", record.variant_id, "edit", "variants.manage");
      }
      const lifecycleStart = actions.length;
      add(status === "active" ? "停用" : "启用", "variants", record.variant_id, status === "active" ? "disable" : "enable", "variants.manage");
      if (lifecycleStart > 0 && actions.length > lifecycleStart) {
        actions[lifecycleStart].dividerBefore = true;
      }
      if (!experimentStatus || experimentStatus === "draft") {
        add("删除", "variants", record.variant_id, "delete", "variants.delete", "danger");
      }
    } else if (section === "users") {
      add("编辑", "users", record.username, "edit", "users.manage");
      if (!record.is_builtin) {
        add(status === "active" ? "停用" : "启用", "users", record.username, status === "active" ? "disable" : "enable", "users.manage");
      } else if (status !== "active") {
        add("启用", "users", record.username, "enable", "users.manage");
      }
      add("重置密码", "users", record.username, "reset-password", "users.manage");
      if (!record.is_builtin) {
        add("删除", "users", record.username, "delete", "users.manage", "danger");
      }
    } else if (section === "roles") {
      if (!record.is_builtin) {
        add("编辑", "roles", record.name, "edit", "roles.manage");
        add(status === "active" ? "停用" : "启用", "roles", record.name, status === "active" ? "disable" : "enable", "roles.manage");
        add("删除", "roles", record.name, "delete", "roles.manage", "danger");
      } else if (status !== "active") {
        add("启用", "roles", record.name, "enable", "roles.manage");
      } else {
        actions.push({
          label: "内置角色不可修改",
          resource: "roles",
          identifier: record.name,
          action: "readonly",
          tone: "",
          disabled: true,
        });
      }
    }

    return actions;
  }

  function appendManagementHeader(row, section) {
    if (!canManageSection(section)) return;
    const cell = document.createElement("th");
    cell.scope = "col";
    cell.className = "management-column";
    cell.textContent = "操作";
    row.append(cell);
  }

  function appendManagementCell(row, section, record) {
    if (!canManageSection(section)) return;
    const cell = document.createElement("td");
    cell.className = "management-column";
    const actions = getRecordActions(section, record);

    if (!actions.length) {
      cell.textContent = "—";
      row.append(cell);
      return;
    }

    const button = document.createElement("button");
    const identifier = record[sectionIdFields[section]] || record.username || record.name || "";
    const icon = document.createElement("span");
    button.type = "button";
    button.className = "row-action-button";
    button.title = "更多操作";
    button.setAttribute("aria-label", identifier ? `${identifier} 的更多操作` : "更多操作");
    button.setAttribute("aria-haspopup", "menu");
    button.setAttribute("aria-expanded", "false");
    button.addEventListener("click", () => openRecordActionsMenu(button, record, actions));
    icon.className = "row-action-icon";
    icon.setAttribute("aria-hidden", "true");
    button.append(icon);
    cell.append(button);
    row.append(cell);
  }

  /**
   * 打开资源记录操作菜单。
   *
   * @param {HTMLButtonElement} anchor 菜单锚点按钮
   * @param {Object} record 资源记录
   * @param {RecordAction[]} actions 可用操作
   * @returns {void} 无返回值
   */
  function openRecordActionsMenu(anchor, record, actions) {
    const isCurrentMenu = anchor.getAttribute("aria-expanded") === "true";
    closeActiveActionMenu?.();

    if (isCurrentMenu) return;

    const menu = document.createElement("div");
    menu.className = "row-action-menu";
    menu.setAttribute("role", "menu");
    menu.setAttribute("aria-label", "资源操作");

    for (const actionConfig of actions) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = [
        "row-action-menu-button",
        actionConfig.dividerBefore ? "group-start" : "",
        actionConfig.tone,
      ].filter(Boolean).join(" ");
      button.textContent = actionConfig.label;
      button.setAttribute("role", "menuitem");
      button.disabled = Boolean(actionConfig.disabled);
      if (actionConfig.disabledReason) button.title = actionConfig.disabledReason;
      if (!actionConfig.disabled) {
        button.addEventListener("click", () => {
          closeMenu();
          runRecordAction(actionConfig, record);
        });
      }
      menu.append(button);
    }

    function closeMenu() {
      document.removeEventListener("pointerdown", handleOutsideClick);
      document.removeEventListener("keydown", handleKeydown);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      menu.remove();
      anchor.setAttribute("aria-expanded", "false");

      if (closeActiveActionMenu === closeMenu) {
        closeActiveActionMenu = null;
      }
    }

    function handleOutsideClick(event) {
      if (!menu.contains(event.target) && event.target !== anchor) closeMenu();
    }

    function handleKeydown(event) {
      if (event.key !== "Escape") return;
      closeMenu();
      anchor.focus();
    }

    menu.style.visibility = "hidden";
    document.body.append(menu);
    const anchorBounds = anchor.getBoundingClientRect();
    const menuBounds = menu.getBoundingClientRect();
    const viewportPadding = 12;
    const left = Math.min(
      window.innerWidth - menuBounds.width - viewportPadding,
      Math.max(viewportPadding, anchorBounds.right - menuBounds.width),
    );
    const spaceBelow = window.innerHeight - anchorBounds.bottom;
    const top = spaceBelow >= menuBounds.height + 8
      ? anchorBounds.bottom + 6
      : Math.max(viewportPadding, anchorBounds.top - menuBounds.height - 6);
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
    menu.style.visibility = "visible";
    anchor.setAttribute("aria-expanded", "true");
    closeActiveActionMenu = closeMenu;

    document.addEventListener("pointerdown", handleOutsideClick);
    document.addEventListener("keydown", handleKeydown);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    menu.querySelector("button")?.focus();
  }

  function runRecordAction(actionConfig, record) {
    if (actionConfig.resource === "batches" && actionConfig.action === "view") {
      onShowBatch(record);
    }
    else if (actionConfig.resource === "batches") openBatchActionDialog(actionConfig);
    else if (actionConfig.action === "delete") openDeleteDialog(actionConfig);
    else if (actionConfig.action === "purge") openPurgeDialog(actionConfig);
    else if (actionConfig.action === "reset-password") openPasswordResetDialog(actionConfig.identifier);
    else if (actionConfig.action === "edit" && actionConfig.resource === "users") {
      void openUserEditDialog(record).catch((error) => toast(error.message));
    }
    else if (actionConfig.action === "edit" && actionConfig.resource === "roles") {
      void openRoleEditDialog(record).catch((error) => toast(error.message));
    }
    else if (actionConfig.action === "view" && actionConfig.resource === "models") {
      onShowModel(record);
    }
    else if (actionConfig.action === "versions" && actionConfig.resource === "models") {
      onShowModelVersions(record);
    }
    else if (actionConfig.action === "edit" && actionConfig.resource === "models") {
      openModelEditDialog(record);
    }
    else if (actionConfig.action === "view" && actionConfig.resource === "versions") {
      onShowVersion(record);
    }
    else if (actionConfig.action === "edit" && actionConfig.resource === "versions") {
      openVersionEditDialog(record);
    }
    else if (actionConfig.action === "edit" && actionConfig.resource === "deployments") {
      openDeploymentEditDialog(record);
    }
    else if (actionConfig.action === "edit" && actionConfig.resource === "routings") {
      void openRoutingEditDialog(record).catch((error) => toast(error.message));
    }
    else if (actionConfig.action === "edit" && actionConfig.resource === "experiments") {
      void openExperimentEditDialog(record).catch((error) => toast(error.message, "error"));
    }
    else if (actionConfig.action === "edit" && actionConfig.resource === "variants") {
      openVariantEditDialog(record);
    }
    else void executeRecordAction(actionConfig);
  }

  function openBatchActionDialog(actionConfig) {
    const isCancel = actionConfig.action === "cancel";
    createManagementDialog({
      title: isCancel
        ? "取消批量任务"
        : "重试批量任务",
      description: isCancel
        ? "系统会停止尚未开始的执行；正在处理的执行将在安全检查点结束。"
        : "系统会为未成功的请求创建新的执行，并保留已有的成功结果。",
      submitLabel: isCancel
        ? "确认取消"
        : "确认重试",
      fields: [],
      onSubmit: async () => executeRecordAction(
        actionConfig,
        null,
        false,
        false,
      ),
    });
  }

  function openDeleteDialog(actionConfig) {
    const resourceLabel = {
      models: "模型",
      versions: "版本",
      deployments: "部署",
      routings: "路由",
      experiments: "实验",
      variants: "分组",
    }[actionConfig.resource] || "资源";
    createManagementDialog({
      title: `删除${resourceLabel}`,
      description: "该操作会逻辑删除资源。请确认资源已停止使用。",
      submitLabel: "确认删除",
      fields: [
        { name: "reason", label: "删除原因", type: "textarea", rows: 3, wide: true },
      ],
      onSubmit: async (formData) => executeRecordAction(actionConfig, optionalValue(formData, "reason"), false, false),
    });
  }

  function openPurgeDialog(actionConfig) {
    const isModel = actionConfig.resource === "models";
    const resourceLabel = isModel ? "模型" : "版本";
    createManagementDialog({
      title: `永久清理${resourceLabel}`,
      description: isModel
        ? "将永久清理该模型各版本的文件。此后无法恢复该模型。"
        : "将永久清理该版本的文件。此后无法恢复该版本。",
      submitLabel: "永久清理",
      fields: [
        { name: "reason", label: "清理原因", type: "textarea", rows: 3, wide: true },
        { name: "confirmation", label: "我了解该操作无法撤销", type: "checkbox", required: true, wide: true },
      ],
      onSubmit: async (formData) => {
        if (formData.get("confirmation") !== "on") {
          throw new Error("请确认永久清理风险");
        }
        return executeRecordAction(
          actionConfig,
          optionalValue(formData, "reason"),
          false,
          false,
        );
      },
    });
  }

  function openModelEditDialog(record) {
    createManagementDialog({
      title: "编辑模型信息",
      description: "修改模型显示名称和描述。",
      submitLabel: "保存修改",
      fields: [
        {
          name: "display_name",
          label: "显示名称",
          value: record.display_name || "",
          wide: true,
        },
        {
          name: "description",
          label: "模型描述",
          type: "textarea",
          rows: 4,
          value: record.description || "",
          wide: true,
        },
      ],
      onSubmit: async (formData) => request(
        `models/${encodeURIComponent(record.model_id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            display_name: optionalValue(formData, "display_name"),
            description: optionalValue(formData, "description"),
          }),
        },
      ),
    });
  }

  function openVersionEditDialog(record) {
    createManagementDialog({
      title: "编辑版本信息",
      description: `修改 ${record.model_name || record.model_id || "模型"} ${record.version} 的版本说明。`,
      submitLabel: "保存修改",
      fields: [
        {
          name: "version",
          label: "版本",
          type: "display",
          value: record.version,
        },
        {
          name: "description",
          label: "版本说明",
          type: "textarea",
          rows: 4,
          value: record.description || "",
          wide: true,
        },
      ],
      onSubmit: async (formData) => request(
        `versions/${encodeURIComponent(record.version_id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            description: optionalValue(formData, "description"),
          }),
        },
      ),
    });
  }

  function openDeploymentEditDialog(record) {
    createManagementDialog({
      title: "编辑部署",
      description: "修改已停用部署的发布方式、决策阈值和说明。",
      submitLabel: "保存修改",
      fields: [
        { name: "rollout_type", label: "发布类型", type: "select", options: deploymentRolloutOptions, value: record.rollout_type },
        {
          name: "role",
          label: "部署角色",
          type: "select",
          options: deploymentRoleOptionsByRollout[record.rollout_type]
            || deploymentRoleOptionsByRollout.full,
          optionsByField: "rollout_type",
          optionsByValue: deploymentRoleOptionsByRollout,
          value: record.role,
        },
        { name: "description", label: "描述", type: "textarea", rows: 3, value: record.description || "", wide: true },
        {
          name: "threshold",
          label: "决策阈值",
          type: "number",
          step: "any",
          value: record.threshold,
          visibleByField: "rollout_type",
          visibleValues: ["full", "canary"],
          wide: true,
        },
      ],
      onSubmit: async (formData) => {
        return request(`deployments/${encodeURIComponent(record.deployment_id)}`, {
          method: "PATCH",
          body: JSON.stringify({
            rollout_type: optionalValue(formData, "rollout_type"),
            role: optionalValue(formData, "role"),
            threshold: optionalValue(formData, "threshold"),
            description: optionalValue(formData, "description"),
          }),
        });
      },
    });
  }

  async function openRoutingEditDialog(record) {
    const options = await getManagementOptions();
    createManagementDialog({
      title: "编辑路由",
      description: "修改路由名称、流量比例、生效时间和规则配置。",
      submitLabel: "保存修改",
      fields: [
        {
          name: "name",
          label: "路由名称",
          value: record.name || "",
          required: true,
          wide: true,
        },
        {
          name: "traffic_ratio",
          label: "流量比例",
          type: "number",
          min: 0,
          max: 100,
          step: 0.1,
          value: record.rollout_type === "full"
            ? 100
            : Number(record.traffic_ratio) * 100,
          suffix: "%",
          stepper: record.rollout_type !== "full",
          readonly: record.rollout_type === "full",
          required: true,
        },
        {
          name: "rules",
          label: "规则配置",
          type: "json-config",
          value: record.rules,
          file: record.rules_metadata,
          template: options.routing_rules?.example || {},
          wide: true,
        },
        {
          name: "effective_from",
          label: "生效时间",
          type: "datetime-local",
          value: datetimeLocalValue(record.effective_from),
        },
        {
          name: "effective_to",
          label: "失效时间",
          type: "datetime-local",
          value: datetimeLocalValue(record.effective_to),
        },
        { name: "description", label: "描述", type: "textarea", rows: 3, value: record.description || "", wide: true },
      ],
      onSubmit: async (formData) => {
        const rules = readJsonConfig(formData, "rules");
        return request(
          `routings/${encodeURIComponent(record.routing_id)}`,
          {
            method: "PATCH",
            body: JSON.stringify({
              name: optionalValue(formData, "name"),
              traffic_ratio: Number(formData.get("traffic_ratio")) / 100,
              rules,
              rules_metadata: readJsonConfig(formData, "rules_metadata"),
              effective_from: optionalValue(formData, "effective_from"),
              effective_to: optionalValue(formData, "effective_to"),
              description: optionalValue(formData, "description"),
            }),
          },
        );
      },
    });
  }

  async function openExperimentEditDialog(record) {
    const config = record.config || {};
    const variants = [];
    for (let page = 1; ; page += 1) {
      const response = await request(`experiments/${encodeURIComponent(record.experiment_id)}/variants?page=${page}&page_size=100&deleted=false`);
      const items = response.items || [];
      variants.push(...items.filter((item) => item.status === "active"));
      if (items.length < 100) break;
    }
    createManagementDialog({
      title: "编辑实验",
      description: "修改草稿实验的基本信息和分流配置。",
      submitLabel: "保存修改",
      fields: [
        { name: "name", label: "实验名称", value: record.name, required: true },
        { name: "strategy", label: "分配策略", type: "select", options: [["hash", "稳定哈希"], ["manual", "手动分配"]], value: config.strategy || "hash" },
        {
          name: "traffic_ratio",
          label: "流量比例",
          type: "number",
          min: 1,
          max: 100,
          step: 1,
          value: Number(config.traffic_ratio ?? 1) * 100,
          suffix: "%",
          stepper: true,
          required: true,
          visibleByField: "strategy",
          visibleValues: ["hash"],
        },
        {
          name: "bucket_key",
          label: "主体标识字段",
          value: config.bucket_key || "",
          required: true,
          placeholder: "例如 customer_id",
          wide: true,
        },
        { name: "manual_assignments", type: "manual-assignments", variants, value: config.manual_assignments || {}, visibleByField: "strategy", visibleValues: ["manual"] },
        { name: "effective_from", label: "生效时间", type: "datetime-local", value: datetimeLocalValue(record.effective_from) },
        { name: "effective_to", label: "失效时间", type: "datetime-local", value: datetimeLocalValue(record.effective_to) },
        { name: "description", label: "描述", type: "textarea", rows: 3, value: record.description || "", wide: true },
      ],
      onSubmit: async (formData) => request(
        `experiments/${encodeURIComponent(record.experiment_id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            name: optionalValue(formData, "name"),
            strategy: optionalValue(formData, "strategy"),
            manual_assignments: readJsonConfig(formData, "manual_assignments"),
            traffic_ratio: formData.has("traffic_ratio")
              ? Number(formData.get("traffic_ratio")) / 100 : undefined,
            bucket_key: optionalValue(formData, "bucket_key"),
            effective_from: optionalValue(formData, "effective_from"),
            effective_to: optionalValue(formData, "effective_to"),
            description: optionalValue(formData, "description"),
          }),
        },
      ),
    });
  }

  function openVariantEditDialog(record) {
    createManagementDialog({
      title: "编辑分组",
      description: "修改草稿实验中的分组配置。",
      submitLabel: "保存修改",
      fields: [
        { name: "name", label: "分组名称", value: record.name, required: true },
        { name: "weight", label: "权重", type: "number", min: 0.01, max: 1, step: 0.01, value: record.weight, required: true },
        { name: "is_control", label: "设为对照组", type: "checkbox", value: record.is_control },
        { name: "description", label: "描述", type: "textarea", rows: 3, value: record.description || "", wide: true },
        {
          name: "config",
          label: "分组配置",
          type: "json-config",
          value: record.config,
          help: "配置变更将在保存修改后生效。",
          wide: true,
        },
      ],
      onSubmit: async (formData) => {
        const config = readJsonConfig(formData, "config");
        return request(
          `variants/${encodeURIComponent(record.variant_id)}`,
          {
            method: "PATCH",
            body: JSON.stringify({
              name: optionalValue(formData, "name"),
              weight: Number(formData.get("weight")),
              is_control: formData.get("is_control") === "on",
              description: optionalValue(formData, "description"),
              config,
            }),
          },
        );
      },
    });
  }

  async function openUserEditDialog(record) {
    const options = await getManagementOptions();
    const builtin = Boolean(record.is_builtin);
    const assignedRoles = Array.isArray(record.roles)
      ? record.roles.map(String)
      : [];
    const effectiveRoles = builtin && !assignedRoles.includes("administrator")
      ? ["administrator", ...assignedRoles]
      : assignedRoles;
    createManagementDialog({
      title: "编辑用户资料",
      description: "修改用户资料及角色分配。",
      submitLabel: "保存修改",
      fields: [
        { name: "username", label: "用户名", required: true, value: record.username, readonly: builtin },
        { name: "display_name", label: "显示名称", value: record.display_name || "", readonly: builtin },
        { name: "email", label: "邮箱", type: "email", value: record.email || "" },
        {
          name: "roles",
          label: "角色",
          type: "choices",
          options: roleOptions(options.roles || []),
          value: effectiveRoles,
          lockedValues: builtin ? ["administrator"] : [],
          multiple: true,
          wide: true,
          emptyText: "暂无可分配的有效角色",
        },
      ],
      onSubmit: async (formData) => request(
        `users/${encodeURIComponent(record.username)}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            username: optionalValue(formData, "username"),
            display_name: optionalValue(formData, "display_name"),
            email: optionalValue(formData, "email"),
            roles: formData.getAll("roles").map(String),
          }),
        },
      ),
      onSuccess: async (result) => {
        if (state.user?.username === record.username) {
          onCurrentUserUpdated(result);
          await onAccessChanged();
        }
      },
    });
  }

  async function openRoleEditDialog(record) {
    const options = await getManagementOptions();
    createManagementDialog({
      title: "编辑角色",
      description: `修改 ${record.name} 的描述与权限配置。变更将在保存后生效。`,
      submitLabel: "保存修改",
      fields: [
        { name: "name", label: "角色名称", value: record.name, readonly: true },
        { name: "description", label: "描述", type: "textarea", rows: 3, value: record.description || "", wide: true },
        {
          name: "permissions",
          label: "权限",
          type: "multiselect",
          options: permissionOptions(options.permissions || []),
          value: Array.isArray(record.permissions) ? record.permissions : [],
          multiple: true,
          wide: true,
          required: true,
          emptyText: "暂无可分配权限",
        },
      ],
      onSubmit: async (formData) => {
        const permissions = formData.getAll("permissions").map(String);
        if (!permissions.length) throw new Error("请至少选择一项权限");
        if (permissions.includes("*") && permissions.length > 1) {
          throw new Error("选择全部权限时无需再选择其他权限");
        }
        return request(`roles/${encodeURIComponent(record.name)}`, {
          method: "PATCH",
          body: JSON.stringify({
            description: optionalValue(formData, "description"),
            permissions,
          }),
        });
      },
      onSuccess: async () => onAccessChanged(),
    });
  }

  function openPasswordChangeDialog() {
    createManagementDialog({
      title: "修改密码",
      description: "验证当前密码后设置新密码。修改成功后需要重新登录。",
      submitLabel: "修改密码",
      fields: [
        { name: "current_password", label: "当前密码", type: "password", required: true, wide: true },
        { name: "new_password", label: "新密码", type: "password", required: true, wide: true },
        { name: "confirmation", label: "确认新密码", type: "password", required: true, wide: true },
      ],
      onSubmit: async (formData) => {
        const newPassword = optionalValue(formData, "new_password");
        if (newPassword !== optionalValue(formData, "confirmation")) {
          throw new Error("两次输入的新密码不一致");
        }
        return request("account/password", {
          method: "POST",
          body: JSON.stringify({
            current_password: optionalValue(formData, "current_password"),
            new_password: newPassword,
          }),
        });
      },
      onSuccess: async () => onSessionEnded("密码已修改，请重新登录。"),
      refreshAfterSubmit: false,
      successMessage: "",
    });
  }

  function openPasswordResetDialog(username) {
    createManagementDialog({
      title: "重置用户密码",
      description: `为用户 ${username} 设置新密码。现有登录会话将被撤销。`,
      submitLabel: "重置密码",
      fields: [
        { name: "password", label: "新密码", type: "password", required: true, wide: true },
        { name: "confirmation", label: "确认新密码", type: "password", required: true, wide: true },
      ],
      onSubmit: async (formData) => {
        const password = optionalValue(formData, "password");
        if (password !== optionalValue(formData, "confirmation")) {
          throw new Error("两次输入的密码不一致");
        }
        await request(`users/${encodeURIComponent(username)}/reset-password`, {
          method: "POST",
          body: JSON.stringify({ password }),
        });
      },
    });
  }

  async function executeRecordAction(actionConfig, reason = null, shouldRefresh = true, report = true) {
    try {
      await request(
        `actions/${encodeURIComponent(actionConfig.resource)}/${encodeURIComponent(actionConfig.identifier)}/${encodeURIComponent(actionConfig.action)}`,
        { method: "POST", body: JSON.stringify({ reason }) },
      );
      if (report) {
        toast(`${actionConfig.label}成功`);
      }
      if (shouldRefresh) await refresh({ silent: true });
    } catch (error) {
      if (report) {
        toast(error.message);
        return;
      }
      throw error;
    }
  }

  createButton.addEventListener("click", () => {
    void openCreateDialog();
  });
  changePasswordButton.addEventListener("click", () => {
    closeAccountMenu();
    openPasswordChangeDialog();
  });

  return {
    appendManagementCell,
    appendManagementHeader,
    getRecordActions,
    openDeploymentCreateDialog,
    openVersionCreateDialog: (model) => openModelRegistrationDialog(model),
    runRecordAction,
    updateCreateButton,
  };
}
