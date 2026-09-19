import { createDetailIcon, showJsonDialog } from "../details/common.js";

/**
 * 管理控制台资源写入交互。
 *
 * 负责创建表单、可选项加载以及资源操作对话框，避免将写入逻辑继续
 * 堆叠在控制台主视图脚本中。
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

const createCapabilities = {
  models: "models.create",
  versions: "models.create",
  deployments: "deployments.create",
  routings: "routings.create",
  experiments: "experiments.create",
  variants: "variants.create",
  users: "users.create",
  roles: "roles.create",
};

const createLabels = {
  models: "注册模型",
  versions: "添加版本",
  deployments: "创建部署",
  routings: "创建路由",
  experiments: "创建实验",
  variants: "添加分组",
  users: "创建用户",
  roles: "创建角色",
};

const deploymentRolloutOptions = [
  ["full", "全量发布"],
  ["canary", "金丝雀发布"],
  ["shadow", "影子发布"],
];

const deploymentRoleOptionsByRollout = {
  full: [["champion", "Champion"]],
  canary: [["champion", "Champion"], ["challenger", "Challenger"]],
  shadow: [["shadow", "Shadow"]],
};

const standardFieldValidators = new WeakMap();

function createWizardCheckIcon() {
  const namespace = "http://www.w3.org/2000/svg";
  const icon = document.createElementNS(namespace, "svg");
  icon.classList.add("management-wizard-check-icon");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(namespace, "path");
  path.setAttribute("d", "M5 12.5 9.2 17 19 7");
  icon.append(path);
  return icon;
}

const modelTypeLabels = {
  logistic_regression: "逻辑回归",
  decision_tree: "决策树",
  random_forest: "随机森林",
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
};

const frameworkLabels = {
  sklearn: "scikit-learn",
  xgboost: "XGBoost",
  lightgbm: "LightGBM",
  catboost: "CatBoost",
};

const modelTypesByFramework = {
  sklearn: ["logistic_regression", "decision_tree", "random_forest"],
  xgboost: ["xgboost"],
  lightgbm: ["lightgbm"],
  catboost: ["catboost"],
};

const taskTypeOptionsByModelType = {
  logistic_regression: [["scoring", "评分"], ["classification", "分类"]],
  decision_tree: [["classification", "分类"]],
  random_forest: [["classification", "分类"]],
  xgboost: [["classification", "分类"]],
  lightgbm: [["classification", "分类"]],
  catboost: [["classification", "分类"]],
};

const maxModelUploadMegabytes = 200;
const maxModelUploadBytes = maxModelUploadMegabytes * 1024 * 1024;

function artifactExtensionsByFramework(options) {
  const capabilities = options?.artifact_extensions;
  if (!capabilities || typeof capabilities !== "object" || Array.isArray(capabilities)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(capabilities)
      .filter(([, extensions]) => Array.isArray(extensions))
      .map(([framework, extensions]) => [
        framework,
        extensions.map(String),
      ]),
  );
}

const permissionResourceLabels = {
  model: "模型",
  deployment: "部署",
  experiment: "实验",
  identity: "身份",
  routing: "路由",
  runtime: "运行时",
  outcome: "结果回流",
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

let multiselectId = 0;

function optionalValue(formData, name) {
  const value = String(formData.get(name) || "").trim();
  return value || null;
}

async function parseJsonFile(formData, name, label) {
  const file = formData.get(name);
  if (!(file instanceof File) || file.size === 0) return null;

  let value;
  try {
    value = JSON.parse(await file.text());
  } catch (_) {
    throw new Error(`${label}必须是有效的 JSON 文件`);
  }

  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new Error(`${label}的顶层内容必须是 JSON 对象`);
  }
  return value;
}

function datetimeLocalValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function normalizeChoice(optionConfig) {
  if (typeof optionConfig === "string") {
    return { value: optionConfig, label: optionConfig, description: "", group: "" };
  }

  if (Array.isArray(optionConfig)) {
    return {
      value: String(optionConfig[0]),
      label: String(optionConfig[1]),
      description: "",
      group: "",
    };
  }

  return {
    value: String(optionConfig.value),
    label: String(optionConfig.label || optionConfig.value),
    description: String(optionConfig.description || ""),
    group: String(optionConfig.group || ""),
  };
}

function appendFieldLabel(container, label, required = false) {
  container.append(document.createTextNode(label));

  if (!required) return;

  const marker = document.createElement("span");
  marker.className = "management-required-marker";
  marker.textContent = "*";
  marker.setAttribute("aria-hidden", "true");
  container.append(marker);
}

function appendChoiceField(body, field) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = `management-field choice-field${field.wide ? " wide" : ""}`;
  const legend = document.createElement("legend");
  appendFieldLabel(legend, field.label, field.required);
  fieldset.append(legend);

  if (field.help) {
    const help = document.createElement("small");
    help.textContent = field.help;
    fieldset.append(help);
  }

  const options = (field.options || []).map(normalizeChoice);

  if (!options.length) {
    const empty = document.createElement("p");
    empty.className = "choice-empty";
    empty.textContent = field.emptyText || "暂无可选项";
    fieldset.append(empty);
    body.append(fieldset);
    return;
  }

  const groups = new Map();
  for (const option of options) {
    const group = option.group || "";
    const groupOptions = groups.get(group);

    if (groupOptions === undefined) groups.set(group, [option]);
    else groupOptions.push(option);
  }

  const selectedValues = new Set(
    Array.isArray(field.value)
      ? field.value.map(String)
      : (field.value === undefined ? [] : [String(field.value)]),
  );
  const lockedValues = new Set(
    Array.isArray(field.lockedValues)
      ? field.lockedValues.map(String)
      : [],
  );

  for (const [groupName, groupOptions] of groups.entries()) {
    const group = document.createElement("section");
    group.className = "choice-group";

    if (groupName) {
      const heading = document.createElement("strong");
      heading.textContent = groupName;
      group.append(heading);
    }

    const choices = document.createElement("div");
    choices.className = field.compact ? "choice-grid compact" : "choice-grid";

    for (const option of groupOptions) {
      const label = document.createElement("label");
      label.className = "choice-option";
      const input = document.createElement("input");
      input.type = field.multiple ? "checkbox" : "radio";
      input.name = field.name;
      input.value = option.value;
      const locked = lockedValues.has(option.value);
      input.checked = selectedValues.has(option.value) || locked;
      input.disabled = locked;
      if (field.required && !field.multiple) input.required = true;
      const copy = document.createElement("span");
      const title = document.createElement("strong");
      title.textContent = option.label;
      copy.append(title);

      if (option.description) {
        const description = document.createElement("small");
        description.textContent = option.description;
        copy.append(description);
      }

      if (locked) {
        label.classList.add("locked");
        label.title = `${option.label} 是内置管理员账户的必选角色`;
        const fixedValue = document.createElement("input");
        fixedValue.type = "hidden";
        fixedValue.name = field.name;
        fixedValue.value = option.value;
        label.append(input, copy, fixedValue);
      } else {
        label.append(input, copy);
      }
      choices.append(label);
    }

    group.append(choices);
    fieldset.append(group);
  }

  body.append(fieldset);
}

function appendMultiSelectField(body, field) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = `management-field multiselect-field${field.wide ? " wide" : ""}`;
  const legend = document.createElement("legend");
  appendFieldLabel(legend, field.label, field.required);
  fieldset.append(legend);

  if (field.help) {
    const help = document.createElement("small");
    help.textContent = field.help;
    fieldset.append(help);
  }

  const options = (field.options || []).map(normalizeChoice);

  if (!options.length) {
    const empty = document.createElement("p");
    empty.className = "choice-empty";
    empty.textContent = field.emptyText || "暂无可选项";
    fieldset.append(empty);
    body.append(fieldset);
    return;
  }

  const selectedValues = new Set(
    Array.isArray(field.value)
      ? field.value.map(String)
      : (field.value === undefined ? [] : [String(field.value)]),
  );
  multiselectId += 1;
  const control = document.createElement("div");
  control.className = "multiselect";
  control.dataset.fieldName = field.name;
  const trigger = document.createElement("div");
  trigger.className = "multiselect-trigger";
  trigger.tabIndex = 0;
  trigger.setAttribute("role", "combobox");
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  trigger.setAttribute("aria-controls", `multiselect-menu-${multiselectId}`);
  const selection = document.createElement("div");
  selection.className = "multiselect-selection";
  const triggerIcon = document.createElement("span");
  triggerIcon.className = "multiselect-chevron";
  triggerIcon.setAttribute("aria-hidden", "true");
  trigger.append(selection, triggerIcon);
  const menu = document.createElement("div");
  menu.className = "multiselect-menu";
  menu.id = `multiselect-menu-${multiselectId}`;
  menu.setAttribute("role", "listbox");
  menu.setAttribute("aria-multiselectable", "true");
  menu.setAttribute("popover", "manual");
  const supportsPopover = typeof menu.showPopover === "function";
  if (!supportsPopover) menu.hidden = true;
  const menuHeader = document.createElement("div");
  menuHeader.className = "multiselect-menu-header";
  const search = document.createElement("input");
  search.type = "search";
  search.className = "multiselect-search";
  search.placeholder = "搜索权限";
  search.setAttribute("aria-label", "搜索权限");
  const menuSummary = document.createElement("span");
  menuSummary.className = "multiselect-summary";
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "multiselect-clear";
  clear.textContent = "清空";
  menuHeader.append(search, menuSummary, clear);
  const menuContent = document.createElement("div");
  menuContent.className = "multiselect-menu-content";
  const noResults = document.createElement("p");
  noResults.className = "multiselect-empty";
  noResults.textContent = "未找到匹配的权限";
  noResults.hidden = true;
  const groups = new Map();
  const groupElements = [];
  /** @type {HTMLInputElement[]} */
  const inputs = [];
  /** @type {HTMLButtonElement[]} */
  const optionButtons = [];
  let open = false;

  function isSelected(input) {
    return selectedValues.has(input.value);
  }

  function setSelected(input, selected) {
    if (selected) selectedValues.add(input.value);
    else selectedValues.delete(input.value);
    input.dataset.selected = String(selected);
    input.disabled = !selected;
  }

  for (const option of options) {
    const groupName = option.group || "其他";
    const groupOptions = groups.get(groupName);

    if (groupOptions === undefined) groups.set(groupName, [option]);
    else groupOptions.push(option);
  }

  function renderSelection() {
    const selected = inputs.filter(isSelected);
    control.classList.toggle("has-selection", selected.length > 0);
    selection.replaceChildren();

    if (!selected.length) {
      const placeholder = document.createElement("span");
      placeholder.className = "multiselect-placeholder";
      placeholder.textContent = field.placeholder || "请选择权限";
      selection.append(placeholder);
    } else {
      for (const input of selected.slice(0, 2)) {
        const tag = document.createElement("span");
        tag.className = "multiselect-tag";
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "multiselect-tag-remove";
        const removeNamespace = "http://www.w3.org/2000/svg";
        const removeIcon = document.createElementNS(removeNamespace, "svg");
        removeIcon.setAttribute("viewBox", "0 0 24 24");
        removeIcon.setAttribute("aria-hidden", "true");
        const removePath = document.createElementNS(removeNamespace, "path");
        removePath.setAttribute("d", "M7 7l10 10M17 7 7 17");
        removeIcon.append(removePath);
        remove.append(removeIcon);
        const label = input.dataset.label || input.value;
        remove.setAttribute("aria-label", `移除权限 ${label}`);
        const copy = document.createElement("span");
        copy.textContent = label;
        remove.addEventListener("click", (event) => {
          event.stopPropagation();
          setSelected(input, false);
          renderSelection();
        });
        tag.append(remove, copy);
        selection.append(tag);
      }

      if (selected.length > 2) {
        const overflow = document.createElement("span");
        overflow.className = "multiselect-overflow";
        overflow.textContent = `+${selected.length - 2}`;
        selection.append(overflow);
      }
    }

    menuSummary.textContent = `已选择 ${selected.length} 项`;
    clear.disabled = selected.length === 0;

    for (const button of optionButtons) {
      const input = inputs.find((item) => item.value === button.value);
      const selectedOption = input !== undefined && isSelected(input);
      button.classList.toggle("selected", selectedOption);
      button.setAttribute("aria-selected", String(selectedOption));
      const mark = button.querySelector(".multiselect-option-mark");
      if (mark instanceof HTMLElement) mark.hidden = !selectedOption;
    }
  }

  function positionMenu() {
    if (!open) return;

    const rect = trigger.getBoundingClientRect();
    const viewportPadding = 12;
    const gap = 6;
    const width = Math.min(
      Math.max(rect.width, 420),
      window.innerWidth - viewportPadding * 2,
    );
    const left = Math.min(
      Math.max(rect.left, viewportPadding),
      window.innerWidth - width - viewportPadding,
    );
    const spaceBelow = window.innerHeight - rect.bottom - viewportPadding - gap;
    const spaceAbove = rect.top - viewportPadding - gap;
    const placeAbove = spaceBelow < 260 && spaceAbove > spaceBelow;
    const availableHeight = Math.max(
      180,
      Math.min(380, placeAbove ? spaceAbove : spaceBelow),
    );

    menu.style.width = `${width}px`;
    menu.style.left = `${left}px`;
    menu.style.maxHeight = `${availableHeight}px`;
    menuContent.style.maxHeight = `${Math.max(120, availableHeight - 57)}px`;
    if (placeAbove) {
      menu.style.top = "auto";
      menu.style.bottom = `${window.innerHeight - rect.top + gap}px`;
    } else {
      menu.style.top = `${rect.bottom + gap}px`;
      menu.style.bottom = "auto";
    }
  }

  function setOpen(nextOpen) {
    if (open === nextOpen) return;

    open = nextOpen;
    control.classList.toggle("open", open);
    trigger.setAttribute("aria-expanded", String(open));

    if (open) {
      if (supportsPopover) menu.showPopover();
      else menu.hidden = false;
      positionMenu();
      search.focus();
    } else {
      if (supportsPopover && menu.matches(":popover-open")) menu.hidePopover();
      else if (!supportsPopover) menu.hidden = true;
      search.value = "";
      filterOptions();
    }
  }

  function filterOptions() {
    const query = search.value.trim().toLocaleLowerCase();
    let visibleCount = 0;

    for (const { group, buttons } of groupElements) {
      let groupVisible = false;
      for (const button of buttons) {
        const visible = !query || button.dataset.searchText.includes(query);
        button.hidden = !visible;
        if (visible) {
          visibleCount += 1;
          groupVisible = true;
        }
      }
      group.hidden = !groupVisible;
    }

    noResults.hidden = visibleCount !== 0;
  }

  function toggleInput(input) {
    const nextSelected = !isSelected(input);

    if (nextSelected && input.value === "*") {
      for (const item of inputs) setSelected(item, item === input);
    } else {
      setSelected(input, nextSelected);
      if (nextSelected) {
        const wildcard = inputs.find((item) => item.value === "*");
        if (wildcard !== undefined) setSelected(wildcard, false);
      }
    }

    renderSelection();
  }

  for (const [groupName, groupOptions] of groups.entries()) {
    const group = document.createElement("section");
    group.className = "multiselect-group";
    const heading = document.createElement("strong");
    heading.textContent = groupName;
    const choices = document.createElement("div");
    choices.className = "multiselect-options";
    const groupButtons = [];

    for (const option of groupOptions) {
      const input = document.createElement("input");
      input.type = "hidden";
      input.className = "multiselect-input";
      input.name = field.name;
      input.value = option.value;
      input.dataset.label = option.label;
      setSelected(input, selectedValues.has(option.value));
      const optionButton = document.createElement("button");
      optionButton.type = "button";
      optionButton.className = "multiselect-option";
      optionButton.value = option.value;
      optionButton.setAttribute("role", "option");
      optionButton.dataset.searchText = [
        option.value,
        option.label,
        option.description,
        groupName,
      ].join(" ").toLocaleLowerCase();
      const copy = document.createElement("span");
      const title = document.createElement("strong");
      title.textContent = option.label;
      copy.append(title);

      if (option.description) {
        const description = document.createElement("small");
        description.textContent = option.description;
        copy.append(description);
      }

      const mark = document.createElement("span");
      mark.className = "multiselect-option-mark";
      const markNamespace = "http://www.w3.org/2000/svg";
      const markIcon = document.createElementNS(markNamespace, "svg");
      markIcon.setAttribute("viewBox", "0 0 24 24");
      markIcon.setAttribute("aria-hidden", "true");
      const markPath = document.createElementNS(markNamespace, "path");
      markPath.setAttribute("d", "m5 12.5 4.2 4.2L19 7");
      markIcon.append(markPath);
      mark.append(markIcon);
      mark.hidden = true;
      optionButton.addEventListener("click", () => toggleInput(input));
      inputs.push(input);
      optionButtons.push(optionButton);
      groupButtons.push(optionButton);
      optionButton.append(copy, mark);
      choices.append(optionButton);
      control.append(input);
    }

    group.append(heading, choices);
    groupElements.push({ group, buttons: groupButtons });
    menuContent.append(group);
  }

  menuContent.append(noResults);
  menu.append(menuHeader, menuContent);

  trigger.addEventListener("click", () => setOpen(!open));
  trigger.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setOpen(!open);
    }
    if (event.key === "Escape") {
      setOpen(false);
      trigger.focus();
    }
  });
  control.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      setOpen(false);
      trigger.focus();
    }
  });
  control.addEventListener("management:close-multiselect", () => setOpen(false));
  search.addEventListener("input", filterOptions);
  search.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      trigger.focus();
    }
  });
  clear.addEventListener("click", () => {
    for (const input of inputs) setSelected(input, false);
    renderSelection();
    search.focus();
  });

  function handleOutsidePointerDown(event) {
    if (!open) return;
    if (
      event.target instanceof Node
      && (control.contains(event.target) || menu.contains(event.target))
    ) return;
    setOpen(false);
  }

  function handleViewportChange() {
    positionMenu();
  }

  document.addEventListener("pointerdown", handleOutsidePointerDown, true);
  window.addEventListener("resize", handleViewportChange);
  body.addEventListener("scroll", handleViewportChange, { passive: true });
  control.append(trigger, menu);
  fieldset.append(control);
  body.append(fieldset);
  renderSelection();
  filterOptions();

  return () => {
    setOpen(false);
    document.removeEventListener("pointerdown", handleOutsidePointerDown, true);
    window.removeEventListener("resize", handleViewportChange);
    body.removeEventListener("scroll", handleViewportChange);
  };
}

function buildManagementFormData(form) {
  const formData = new FormData(form);

  for (const control of form.querySelectorAll(".multiselect[data-field-name]")) {
    const fieldName = control.dataset.fieldName;
    if (!fieldName) continue;

    formData.delete(fieldName);
    for (const input of control.querySelectorAll(".multiselect-input")) {
      if (
        input instanceof HTMLInputElement
        && input.dataset.selected === "true"
      ) {
        formData.append(fieldName, input.value);
      }
    }
  }

  return formData;
}

function closeManagementMultiselects(form) {
  for (const control of form.querySelectorAll(".multiselect.open")) {
    control.dispatchEvent(new Event("management:close-multiselect"));
  }
}

function createNumberStepper(input, field) {
  const control = document.createElement("div");
  control.className = "management-number-stepper";
  const valueControl = document.createElement("div");
  valueControl.className = "management-input-affix";
  const suffix = document.createElement("span");
  suffix.className = "management-input-suffix";
  suffix.textContent = field.suffix || "";
  const decrease = document.createElement("button");
  const increase = document.createElement("button");

  for (const [button, symbol, action] of [
    [decrease, "−", "减少"],
    [increase, "+", "增加"],
  ]) {
    button.type = "button";
    button.className = "management-number-stepper-button";
    button.textContent = symbol;
    button.setAttribute("aria-label", `${action}${field.label}`);
    button.title = `${action}${field.label}`;
  }

  const minimum = Number(input.min);
  const maximum = Number(input.max);
  const hasMinimum = input.min !== "" && Number.isFinite(minimum);
  const hasMaximum = input.max !== "" && Number.isFinite(maximum);
  const numericStep = Number(input.step);
  const step = Number.isFinite(numericStep) && numericStep > 0
    ? numericStep
    : 1;
  const stepText = String(step);
  const precision = stepText.includes(".")
    ? stepText.split(".")[1].length
    : 0;

  function syncButtons() {
    const current = Number(input.value);
    const hasValue = input.value !== "" && Number.isFinite(current);
    decrease.disabled = hasValue && hasMinimum && current <= minimum;
    increase.disabled = hasValue && hasMaximum && current >= maximum;
  }

  function adjust(direction) {
    const current = Number(input.value);
    let base = input.value !== "" && Number.isFinite(current)
      ? current
      : (direction > 0 ? (hasMinimum ? minimum : 0) : (hasMaximum ? maximum : 0));
    if (direction < 0 && hasMaximum && base > maximum) base = maximum + step;
    if (direction > 0 && hasMinimum && base < minimum) base = minimum - step;
    let next = base + direction * step;
    if (hasMinimum) next = Math.max(minimum, next);
    if (hasMaximum) next = Math.min(maximum, next);
    input.value = String(Number(next.toFixed(precision)));
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.focus();
    syncButtons();
  }

  decrease.addEventListener("click", () => adjust(-1));
  increase.addEventListener("click", () => adjust(1));
  input.addEventListener("input", syncButtons);
  valueControl.append(input, suffix);
  control.append(decrease, valueControl, increase);
  syncButtons();
  return control;
}

function createDateTimePickerButton(label, pathData) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "management-datetime-picker-button";
  button.setAttribute("aria-label", label);
  const namespace = "http://www.w3.org/2000/svg";
  const icon = document.createElementNS(namespace, "svg");
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(namespace, "path");
  path.setAttribute("d", pathData);
  icon.append(path);
  button.append(icon);
  return button;
}

function openNativePicker(input) {
  if (typeof input.showPicker === "function") {
    try {
      input.showPicker();
      return;
    } catch {
      // 旧版浏览器不支持时，继续使用点击回退方案。
    }
  }
  input.focus();
  input.click();
}

function createDateTimeControl(field) {
  const control = document.createElement("div");
  control.className = "management-datetime-control";
  const dateSegment = document.createElement("div");
  dateSegment.className = "management-datetime-segment";
  const dateCaption = document.createElement("span");
  dateCaption.textContent = "日期";
  const dateInputShell = document.createElement("div");
  dateInputShell.className = "management-datetime-input-shell";
  const dateTextInput = document.createElement("input");
  dateTextInput.type = "text";
  dateTextInput.placeholder = "yyyy/mm/dd";
  dateTextInput.inputMode = "numeric";
  dateTextInput.autocomplete = "off";
  dateTextInput.spellcheck = false;
  dateTextInput.maxLength = 10;
  dateTextInput.setAttribute(
    "aria-label",
    `${field.label}日期，格式为 yyyy/mm/dd`,
  );
  const datePickerInput = document.createElement("input");
  datePickerInput.type = "date";
  datePickerInput.className = "management-datetime-picker-input";
  datePickerInput.tabIndex = -1;
  datePickerInput.setAttribute("aria-hidden", "true");
  const datePickerButton = createDateTimePickerButton(
    `选择${field.label}日期`,
    "M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z",
  );
  const timeSegment = document.createElement("div");
  timeSegment.className = "management-datetime-segment time";
  const timeCaption = document.createElement("span");
  timeCaption.textContent = "时间";
  const timeInputShell = document.createElement("div");
  timeInputShell.className = "management-datetime-input-shell";
  const timeTextInput = document.createElement("input");
  timeTextInput.type = "text";
  timeTextInput.placeholder = "hh:mm:ss";
  timeTextInput.inputMode = "numeric";
  timeTextInput.autocomplete = "off";
  timeTextInput.spellcheck = false;
  timeTextInput.maxLength = 8;
  timeTextInput.setAttribute(
    "aria-label",
    `${field.label}时间，格式为 hh:mm:ss`,
  );
  const timePickerInput = document.createElement("input");
  timePickerInput.type = "time";
  timePickerInput.step = "1";
  timePickerInput.className = "management-datetime-picker-input";
  timePickerInput.tabIndex = -1;
  timePickerInput.setAttribute("aria-hidden", "true");
  const timePickerButton = createDateTimePickerButton(
    `选择${field.label}时间`,
    "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20ZM12 6v6l4 2",
  );
  const valueInput = document.createElement("input");
  valueInput.type = "hidden";
  valueInput.name = field.name;

  const initialValue = String(field.value || "");
  const initialMatch = initialValue.match(
    /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}(?::\d{2})?)/,
  );
  if (initialMatch) {
    datePickerInput.value = initialMatch[1];
    dateTextInput.value = initialMatch[1].replaceAll("-", "/");
    const initialTime = initialMatch[2].length === 5
      ? `${initialMatch[2]}:00`
      : initialMatch[2];
    timePickerInput.value = initialTime;
    timeTextInput.value = initialTime;
  }

  const maskDateText = (value) => {
    const rawValue = String(value || "");
    const digits = rawValue.replace(/\D/g, "").slice(0, 8);
    const slashCount = (rawValue.match(/\//g) || []).length;
    let maskedValue = digits.slice(0, 4);
    if (digits.length > 4 || slashCount > 0) {
      maskedValue += `/${digits.slice(4, 6)}`;
    }
    if (digits.length > 6 || slashCount > 1) {
      maskedValue += `/${digits.slice(6, 8)}`;
    }
    return maskedValue;
  };

  const resolveDateValue = (value) => {
    const match = String(value || "").match(
      /^(\d{4})\/(\d{2})\/(\d{2})$/,
    );
    if (!match) return "";
    const dateValue = `${match[1]}-${match[2]}-${match[3]}`;
    datePickerInput.value = dateValue;
    return datePickerInput.value === dateValue ? dateValue : "";
  };

  const maskTimeText = (value) => {
    const rawValue = String(value || "");
    const digits = rawValue.replace(/\D/g, "").slice(0, 6);
    const colonCount = (rawValue.match(/:/g) || []).length;
    let maskedValue = digits.slice(0, 2);
    if (digits.length > 2 || colonCount > 0) {
      maskedValue += `:${digits.slice(2, 4)}`;
    }
    if (digits.length > 4 || colonCount > 1) {
      maskedValue += `:${digits.slice(4, 6)}`;
    }
    return maskedValue;
  };

  const resolveTimeValue = (value) => {
    const match = String(value || "").match(
      /^(\d{2}):(\d{2}):(\d{2})$/,
    );
    if (!match) return "";
    const timeValue = `${match[1]}:${match[2]}:${match[3]}`;
    timePickerInput.value = timeValue;
    return timePickerInput.value === timeValue ? timeValue : "";
  };

  const syncValue = () => {
    const dateValue = resolveDateValue(dateTextInput.value);
    const timeValue = resolveTimeValue(timeTextInput.value);
    const hasDateText = dateTextInput.value !== "";
    const hasTimeText = timeTextInput.value !== "";
    const hasDate = dateValue !== "";
    const hasTime = timeValue !== "";
    datePickerInput.value = dateValue;
    timePickerInput.value = timeValue;
    dateTextInput.required = Boolean(field.required) || hasTimeText;
    dateTextInput.setCustomValidity(
      hasDateText && !hasDate ? "请输入有效日期，格式为 yyyy/mm/dd。" : "",
    );
    timeTextInput.required = Boolean(field.required) || hasDateText;
    timeTextInput.setCustomValidity(
      hasTimeText && !hasTime ? "请输入有效时间，格式为 hh:mm:ss。" : "",
    );
    valueInput.value = hasDate && hasTime
      ? `${dateValue}T${timeValue}`
      : "";
    control.classList.toggle(
      "incomplete",
      (hasDateText || hasTimeText) && !(hasDate && hasTime),
    );
  };

  dateTextInput.addEventListener("input", () => {
    dateTextInput.value = maskDateText(dateTextInput.value);
    syncValue();
  });
  const syncDatePicker = () => {
    dateTextInput.value = datePickerInput.value.replaceAll("-", "/");
    syncValue();
  };
  datePickerButton.addEventListener("click", () => openNativePicker(datePickerInput));
  datePickerInput.addEventListener("input", syncDatePicker);
  datePickerInput.addEventListener("change", syncDatePicker);
  timeTextInput.addEventListener("input", () => {
    timeTextInput.value = maskTimeText(timeTextInput.value);
    syncValue();
  });
  const syncTimePicker = () => {
    timeTextInput.value = timePickerInput.value.length === 5
      ? `${timePickerInput.value}:00`
      : timePickerInput.value;
    syncValue();
  };
  timePickerButton.addEventListener("click", () => openNativePicker(timePickerInput));
  timePickerInput.addEventListener("input", syncTimePicker);
  timePickerInput.addEventListener("change", syncTimePicker);
  dateInputShell.append(dateTextInput, datePickerButton, datePickerInput);
  dateSegment.append(dateCaption, dateInputShell);
  timeInputShell.append(timeTextInput, timePickerButton, timePickerInput);
  timeSegment.append(timeCaption, timeInputShell);
  control.append(dateSegment, timeSegment, valueInput);
  syncValue();
  return control;
}

/**
 * @typedef {Object} RulesMetadata
 * @property {string} name 文件名
 * @property {number} size 文件大小（字节）
 * @property {string | null} [uploaded_at] 服务端记录的上传时间
 */

function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

/**
 * 创建统一的文件选择空状态和已选文件状态。
 *
 * @param {HTMLInputElement} input 原生文件输入框
 * @param {number} [maxFileSize] 文件大小上限（字节）
 */
function createFileUploadView(input, maxFileSize = 0) {
  const dropzone = document.createElement("button");
  dropzone.type = "button";
  dropzone.className = "management-json-dropzone";
  dropzone.append(createDetailIcon("upload", "management-file-dropzone-icon"));
  const prompt = document.createElement("strong");
  prompt.append("拖拽文件到这里，或 ");
  const choose = document.createElement("span");
  choose.textContent = "点击选择文件";
  prompt.append(choose);
  const formats = document.createElement("small");
  formats.className = "management-file-formats";
  const limit = document.createElement("small");
  limit.textContent = maxFileSize
    ? `单个文件不超过 ${Math.round(maxFileSize / 1024 / 1024)} MB`
    : "";
  limit.hidden = !maxFileSize;
  dropzone.append(prompt, formats, limit);
  dropzone.addEventListener("click", () => input.click());

  const fileInfo = document.createElement("div");
  fileInfo.className = "management-upload-file";
  fileInfo.append(createDetailIcon("payload", "management-upload-file-icon"));
  const fileCopy = document.createElement("div");
  const filename = document.createElement("span");
  const metadata = document.createElement("small");
  fileCopy.append(filename, metadata);
  fileInfo.append(fileCopy);

  function renderFormats() {
    const extensions = input.accept
      .split(",")
      .map((value) => value.trim())
      .filter((value) => value.startsWith("."));
    formats.textContent = extensions.length
      ? `支持格式：${extensions.join("、")}`
      : "";
    formats.hidden = extensions.length === 0;
  }

  function showFile(name, details = "") {
    const selected = Boolean(name);
    dropzone.hidden = selected;
    fileInfo.hidden = !selected;
    filename.textContent = name;
    metadata.textContent = details;
  }

  renderFormats();
  showFile("");
  return { dropzone, fileInfo, renderFormats, showFile };
}

/**
 * 创建 JSON 配置上传控件。
 *
 * @param {HTMLElement} body 表单容器
 * @param {Object} field 字段配置
 * @param {string} field.name 字段名称
 * @param {string} field.label 显示名称
 * @param {Object | null} [field.value] 当前配置
 * @param {RulesMetadata | null} [field.file] 文件元信息
 * @param {string} [field.mode] 表单模式
 * @param {string} [field.help] 辅助说明
 * @param {Object.<string, *>} [field.template] 后端提供的配置示例
 */
function appendJsonConfigField(body, field) {
  const container = document.createElement("div");
  container.className = "management-field wide";
  const title = document.createElement("span");
  title.textContent = field.label;
  const heading = document.createElement("div");
  heading.className = "management-json-heading";
  heading.append(title);
  const panel = document.createElement("div");
  panel.className = "management-json-config";
  const status = document.createElement("span");
  status.setAttribute("aria-live", "polite");
  const actions = document.createElement("div");
  actions.className = "management-json-actions";
  const input = document.createElement("input");
  input.type = "file";
  input.accept = ".json,application/json";
  input.hidden = true;
  const value = document.createElement("input");
  value.type = "hidden";
  value.name = field.name;
  value.disabled = true;
  const fileValue = document.createElement("input");
  fileValue.type = "hidden";
  fileValue.name = `${field.name}_metadata`;
  fileValue.disabled = true;
  const preview = document.createElement("pre");
  preview.className = "management-json-preview";
  preview.hidden = true;
  const error = document.createElement("small");
  error.setAttribute("role", "alert");
  let current = field.value ?? null;
  const creating = field.mode === "create";
  let filename = field.file?.name || "";
  let fileSize = field.file?.size || 0;
  let previous = null;
  let revision = 0;

  function button(label, handler) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = "secondary-button";
    element.textContent = label;
    element.addEventListener("click", handler);
    actions.append(element);
    return element;
  }

  if (field.name === "rules") {
    const template = field.template || {};
    const links = document.createElement("div");
    links.className = "management-json-actions";
    const example = button(
      "查看配置示例",
      () => showJsonDialog("规则配置示例", template),
    );
    const download = button("下载模板", () => {
      const blob = new Blob([JSON.stringify(template, null, 2) + "\n"], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "route_rules.json";
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    example.prepend(createDetailIcon("rules", "management-json-action-icon"));
    download.prepend(createDetailIcon("download", "management-json-action-icon"));
    links.append(example, download);
    heading.append(links);
  }
  const uploadView = createFileUploadView(input);
  const { dropzone, fileInfo } = uploadView;
  const view = button("预览", () => {
    preview.hidden = !preview.hidden;
    view.textContent = preview.hidden ? "预览" : "收起";
    view.setAttribute("aria-expanded", String(!preview.hidden));
  });
  view.title = "查看 JSON 配置";
  const upload = button("导入 JSON", () => input.click());
  const remove = button("清除", () => {
    revision += 1;
    if (creating) previous = { current, filename, fileSize, unchanged: value.disabled };
    current = null;
    filename = "";
    value.disabled = false;
    render();
  });
  remove.classList.add("management-json-clear");
  const undo = button("撤销", () => {
    revision += 1;
    if (creating && previous) {
      ({ current, filename, fileSize } = previous);
      value.disabled = previous.unchanged;
      previous = null;
    } else {
      current = field.value ?? null;
      filename = field.file?.name || "";
      fileSize = field.file?.size || 0;
      value.disabled = true;
    }
    render();
  });

  function render() {
    const configured = current !== null;
    status.textContent = configured
      ? (value.disabled ? "已配置" : "已替换，保存后生效")
      : (value.disabled ? "未指定配置" : "保存后将移除配置");
    if (creating) status.textContent = configured ? filename : "未指定规则";
    status.hidden = configured || creating || value.disabled;
    upload.textContent = "重新选择";
    upload.hidden = !configured;
    view.hidden = !configured;
    remove.hidden = !configured;
    undo.hidden = configured || (creating ? previous === null : value.disabled);
    preview.hidden = true;
    view.textContent = "预览";
    let fileDetails = filename
      ? `${formatFileSize(fileSize)} · JSON 解析成功`
      : "";
    if (value.disabled && field.file?.uploaded_at) {
      fileDetails += ` · 上传时间：${new Date(field.file.uploaded_at).toLocaleString("zh-CN", { hour12: false })}`;
    }
    uploadView.showFile(configured ? filename || "规则 JSON" : "", fileDetails);
    fileValue.disabled = value.disabled || !filename || !configured;
    fileValue.value = JSON.stringify({ name: filename, size: fileSize });
    view.setAttribute("aria-expanded", "false");
    preview.textContent = configured ? JSON.stringify(current, null, 2) : "";
    value.value = JSON.stringify(current);
    input.value = "";
    error.textContent = "";
  }

  async function selectFile(file) {
    if (!file) return;
    const selectedRevision = ++revision;
    if (creating && value.value !== "") {
      previous = { current, filename, fileSize, unchanged: value.disabled };
    }
    value.disabled = false;
    value.value = "";
    status.textContent = "正在读取配置…";
    status.hidden = false;
    view.hidden = true;
    fileInfo.hidden = true;
    undo.hidden = false;
    error.textContent = "";
    const data = new FormData();
    data.set("file", file);
    let parsed;
    try {
      parsed = await parseJsonFile(data, "file", field.label);
    } catch (cause) {
      if (selectedRevision !== revision) return;
      error.textContent = cause.message;
    }
    if (selectedRevision !== revision) return;
    if (parsed == null) {
      status.textContent = "配置文件无效，请重新选择或撤销";
      if (!error.textContent) error.textContent = "请选择非空的 JSON 配置文件";
      input.value = "";
      return;
    }
    current = parsed;
    filename = file.name;
    fileSize = file.size;
    value.disabled = false;
    render();
  }
  input.addEventListener("change", () => selectFile(input.files?.[0]));
  panel.addEventListener("dragover", (event) => {
    event.preventDefault();
    panel.classList.add("dragging");
  });
  panel.addEventListener("dragleave", (event) => {
    if (!panel.contains(event.relatedTarget)) panel.classList.remove("dragging");
  });
  panel.addEventListener("drop", (event) => {
    event.preventDefault();
    panel.classList.remove("dragging");
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    if (files.length !== 1) {
      error.textContent = "请一次选择一个 JSON 文件";
      return;
    }
    void selectFile(files[0]);
  });

  render();
  panel.append(dropzone, fileInfo, status, actions, preview);
  container.append(heading, panel, input, value, fileValue, error);
  if (field.help) {
    const help = document.createElement("small");
    help.textContent = field.help;
    container.append(help);
  }
  body.append(container);
}

/**
 * 添加支持点击选择和拖放的文件上传字段。
 *
 * @param {HTMLElement} body 表单容器
 * @param {Object} field 字段配置
 * @param {string} field.name 字段名称
 * @param {string} field.label 显示名称
 * @param {boolean} [field.required] 是否必填
 * @param {boolean} [field.wide] 是否占满表单宽度
 * @param {string} [field.accept] 接受的文件类型
 * @param {number} [field.maxFileSize] 文件大小上限（字节）
 * @param {string} [field.help] 辅助说明
 */
function appendFileDropzoneField(body, field) {
  const container = document.createElement("div");
  container.className = field.wide ? "management-field wide" : "management-field";
  const title = document.createElement("span");
  appendFieldLabel(title, field.label, field.required);
  const panel = document.createElement("div");
  panel.className = "management-json-config management-file-upload";
  const input = document.createElement("input");
  input.type = "file";
  input.name = field.name;
  input.hidden = true;
  input.required = Boolean(field.required);
  if (field.accept) input.accept = field.accept;
  const uploadView = createFileUploadView(input, field.maxFileSize);
  const { dropzone, fileInfo } = uploadView;

  const actions = document.createElement("div");
  actions.className = "management-json-actions";
  const replace = document.createElement("button");
  replace.type = "button";
  replace.className = "secondary-button";
  replace.textContent = "重新选择";
  replace.addEventListener("click", () => input.click());
  const clear = document.createElement("button");
  clear.type = "button";
  clear.className = "secondary-button management-json-clear";
  clear.textContent = "清除";
  clear.addEventListener("click", () => {
    input.value = "";
    render();
  });
  actions.append(replace, clear);

  const error = document.createElement("small");
  error.setAttribute("role", "alert");

  function render() {
    const file = input.files?.[0];
    uploadView.showFile(file?.name || "", file ? formatFileSize(file.size) : "");
    actions.hidden = !file;
    error.textContent = file && field.maxFileSize && file.size > field.maxFileSize
      ? `模型文件不能超过 ${Math.round(field.maxFileSize / 1024 / 1024)} MB`
      : "";
  }

  input.addEventListener("change", render);
  panel.addEventListener("management:accept-change", uploadView.renderFormats);
  panel.addEventListener("dragover", (event) => {
    event.preventDefault();
    panel.classList.add("dragging");
  });
  panel.addEventListener("dragleave", (event) => {
    if (!panel.contains(event.relatedTarget)) panel.classList.remove("dragging");
  });
  panel.addEventListener("drop", (event) => {
    event.preventDefault();
    panel.classList.remove("dragging");
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    if (files.length !== 1) {
      error.textContent = "请一次选择一个模型文件";
      return;
    }
    input.files = files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });

  render();
  panel.append(dropzone, fileInfo, actions);
  container.append(title, panel, input, error);
  if (field.help) {
    const help = document.createElement("small");
    help.textContent = field.help;
    container.append(help);
  }
  body.append(container);
}

function readJsonConfig(formData, name) {
  if (!formData.has(name)) return undefined;
  const value = formData.get(name);
  if (!value) throw new Error("配置文件尚未解析成功，请重新选择或撤销后再保存");
  return JSON.parse(value);
}

function appendExperimentGroupsField(body, field) {
  const container = document.createElement("div");
  container.className = "management-field wide";
  const header = document.createElement("div");
  header.className = "management-assignment-header";
  const title = document.createElement("span");
  title.textContent = "实验分组";
  const add = document.createElement("button");
  add.type = "button";
  add.className = "management-assignment-add";
  add.textContent = "＋ 添加分组";
  header.append(title, add);
  const list = document.createElement("div");
  list.className = "management-group-list";
  const value = document.createElement("input");
  value.type = "hidden";
  value.name = field.name;
  container.append(header, list, value);
  body.append(container);
  const model = body.querySelector('[name="model_id"]');
  const strategy = body.querySelector('[name="strategy"]');
  const rows = [];
  let sequence = 0;

  function sync() {
    const hash = strategy.value === "hash";
    const names = new Set();
    const deployments = new Set();
    const total = rows.reduce(
      (sum, row) => sum + Number(row.weight.value),
      0,
    );

    for (const row of rows) {
      const name = row.name.value.trim();
      row.name.setCustomValidity(
        !name ? "请输入分组名称" : names.has(name) ? "分组名称不能重复" : "",
      );
      names.add(name);
      row.deployment.setCustomValidity(
        deployments.has(row.deployment.value) ? "不能重复选择同一部署" : "",
      );
      deployments.add(row.deployment.value);
      row.weight.disabled = !hash;
      row.weight.closest("label").hidden = !hash;
      row.weight.setCustomValidity(
        hash && Math.abs(total - 100) > 0.000001
          ? "分组权重合计必须为 100%"
          : "",
      );
      row.remove.disabled = rows.length <= 1;
    }
    value.value = JSON.stringify(rows.map((row) => ({
      key: row.key,
      name: row.name.value.trim(),
      deployment_id: row.deployment.value,
      weight: hash ? Number(row.weight.value) / 100 : 1 / rows.length,
      is_control: row.control.checked,
    })));
    body.dispatchEvent(new Event("management:groups-change"));
  }

  function updateDeployments() {
    const available = field.deployments.filter(
      (item) => item.model_id === model.value,
    );

    for (const row of rows) {
      const selected = row.deployment.value;
      row.deployment.replaceChildren();
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = available.length ? "选择部署" : "暂无可用部署";
      row.deployment.append(placeholder);
      for (const deployment of available) {
        const option = document.createElement("option");
        option.value = deployment.deployment_id;
        const modelInfo = field.models.find(
          (item) => item.model_id === deployment.model_id,
        );
        const modelName = modelInfo?.name || deployment.model_name || "未命名模型";
        const modelLabel = modelInfo?.display_name
          ? `${modelInfo.display_name} (${modelName})`
          : modelName;
        const roleLabels = {
          champion: "Champion",
          challenger: "Challenger",
        };
        const roleLabel = roleLabels[String(deployment.role).toLowerCase()]
          || deployment.role || "未标注角色";
        option.textContent = `${modelLabel} · ${deployment.model_version || "未标注版本"} · ${roleLabel}`;
        row.deployment.append(option);
      }
      row.deployment.value = available.some(
        (item) => item.deployment_id === selected,
      ) ? selected : "";
    }
    sync();
  }

  function addRow(isControl = false) {
    const key = `group_${++sequence}`;
    const card = document.createElement("div");
    card.className = "management-group-card";
    appendStandardField(card, {
      name: `${key}_name`,
      label: "分组名称",
      required: true,
      maxLength: 128,
      value: isControl ? "对照组" : "",
    });
    appendStandardField(card, {
      name: `${key}_deployment`,
      label: "部署",
      type: "select",
      required: true,
      options: [],
    });
    appendStandardField(card, {
      name: `${key}_weight`,
      label: "权重（%）",
      type: "number",
      min: 0.01,
      max: 100,
      step: 0.01,
      required: true,
      value: 50,
    });
    const actions = document.createElement("div");
    actions.className = "management-group-actions";
    const controlLabel = document.createElement("label");
    const control = document.createElement("input");
    control.type = "radio";
    control.name = "experiment_control_group";
    control.value = key;
    control.required = true;
    control.checked = isControl;
    controlLabel.append(control, document.createTextNode("设为对照组"));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "management-assignment-remove";
    remove.title = "移除分组";
    remove.setAttribute("aria-label", "移除分组");
    remove.append(createDetailIcon("delete"));
    actions.append(controlLabel, remove);
    card.append(actions);
    const row = {
      key,
      name: card.querySelector(`[name="${key}_name"]`),
      deployment: card.querySelector("select"),
      weight: card.querySelector('[type="number"]'),
      control,
      remove,
    };
    rows.push(row);
    remove.addEventListener("click", () => {
      rows.splice(rows.indexOf(row), 1);
      card.remove();
      sync();
    });
    card.addEventListener("input", sync);
    card.addEventListener("change", sync);
    list.append(card);
    updateDeployments();
    return row;
  }

  add.addEventListener("click", () => addRow().name.focus());
  model.addEventListener("change", updateDeployments);
  strategy.addEventListener("change", sync);
  addRow(true);
  addRow();
}

function appendManualAssignmentsField(body, field) {
  const container = document.createElement("div");
  container.className = "management-field wide";
  const title = document.createElement("span");
  title.textContent = "指定客户";
  const header = document.createElement("div");
  header.className = "management-assignment-header";
  const columns = document.createElement("div");
  columns.className = "management-assignment-columns";
  columns.setAttribute("aria-hidden", "true");
  for (const text of ["客户标识", "目标分组"]) {
    const label = document.createElement("span");
    label.textContent = text;
    columns.append(label);
  }
  const list = document.createElement("div");
  list.className = "management-assignment-list";
  const value = document.createElement("input");
  value.type = "hidden";
  value.name = field.name;
  const rows = [];
  function availableVariants() {
    if (!field.sourceGroups) return field.variants;
    return JSON.parse(body.querySelector(`[name="${field.sourceGroups}"]`).value || "[]")
      .map((group) => ({ variant_id: group.key, name: group.name || "未命名分组" }));
  }
  function sync() {
    const mapping = Object.create(null);
    for (const { subject, target } of rows) {
      const key = subject.value.trim();
      subject.setCustomValidity(!key ? "请输入客户标识" : Object.hasOwn(mapping, key) ? "客户标识不能重复" : "");
      if (key) mapping[key] = target.value;
    }
    value.value = JSON.stringify(mapping);
    columns.hidden = rows.length === 0;
  }
  function addRow(key = "", selected = "") {
    const row = document.createElement("div");
    row.className = "management-assignment-row";
    const subject = document.createElement("input");
    subject.placeholder = "请输入客户标识";
    subject.setAttribute("aria-label", "客户标识");
    subject.required = true;
    subject.maxLength = 128;
    subject.value = key;
    const target = document.createElement("select");
    target.setAttribute("aria-label", "目标分组");
    target.required = true;
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "选择目标分组";
    target.append(placeholder);
    for (const variant of availableVariants()) {
      const option = document.createElement("option");
      option.value = variant.variant_id;
      option.textContent = variant.name;
      target.append(option);
    }
    target.value = selected;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "management-assignment-remove";
    remove.title = "移除客户";
    remove.setAttribute("aria-label", "移除客户");
    remove.append(createDetailIcon("delete"));
    const entry = { subject, target };
    remove.addEventListener("click", () => {
      rows.splice(rows.indexOf(entry), 1);
      row.remove();
      sync();
    });
    subject.addEventListener("input", sync);
    target.addEventListener("change", sync);
    rows.push(entry);
    row.append(subject, target, remove);
    list.append(row);
    sync();
    return subject;
  }
  const add = document.createElement("button");
  add.type = "button";
  add.className = "management-assignment-add";
  add.textContent = "＋ 添加客户";
  add.hidden = availableVariants().length === 0;
  add.addEventListener("click", () => addRow().focus());
  header.append(title, add);
  container.append(header, columns, list, value);
  if (!availableVariants().length) {
    const empty = document.createElement("small");
    empty.textContent = "暂无可用分组";
    container.append(empty);
  }
  body.append(container);
  for (const [key, target] of Object.entries(field.value || {})) addRow(key, target);
  if (field.sourceGroups) {
    body.addEventListener("management:groups-change", () => {
      const variants = availableVariants();
      add.hidden = variants.length === 0;
      for (const { target } of rows) {
        const selected = target.value;
        target.replaceChildren();
        for (const variant of [{ variant_id: "", name: "选择目标分组" }, ...variants]) {
          const option = document.createElement("option");
          option.value = variant.variant_id;
          option.textContent = variant.name;
          target.append(option);
        }
        target.value = variants.some((item) => item.variant_id === selected) ? selected : "";
      }
      sync();
    });
  }
  sync();
}

function appendStandardField(body, field) {
  if (field.type === "experiment-groups") {
    appendExperimentGroupsField(body, field);
    return;
  }
  if (field.type === "manual-assignments") {
    appendManualAssignmentsField(body, field);
    return;
  }
  if (field.type === "json-config") {
    appendJsonConfigField(body, field);
    return;
  }
  if (field.type === "file-dropzone") {
    appendFileDropzoneField(body, field);
    return;
  }
  const label = document.createElement("label");
  label.className = field.wide ? "management-field wide" : "management-field";
  if (field.compact) label.classList.add("compact");
  const name = document.createElement("span");
  appendFieldLabel(name, field.label, field.required);

  if (field.type === "display") {
    const value = document.createElement("div");
    value.className = "management-readonly-value";
    value.textContent = String(field.value ?? "—");
    value.setAttribute("aria-readonly", "true");
    label.append(name, value);
    if (field.help) {
      const help = document.createElement("small");
      help.textContent = field.help;
      label.append(help);
    }
    body.append(label);
    return;
  }

  if (field.type === "datetime-local") {
    label.append(name, createDateTimeControl(field));
    if (field.help) {
      const help = document.createElement("small");
      help.textContent = field.help;
      label.append(help);
    }
    body.append(label);
    return;
  }

  let input;

  if (field.type === "select") {
    input = document.createElement("select");
    for (const optionConfig of field.options || []) {
      const option = document.createElement("option");
      const normalized = normalizeChoice(optionConfig);
      option.value = normalized.value;
      option.textContent = normalized.label;
      input.append(option);
    }
  } else if (field.type === "textarea") {
    input = document.createElement("textarea");
    input.rows = field.rows || 4;
  } else {
    input = document.createElement("input");
    input.type = field.type || "text";
  }

  input.name = field.name;
  if (field.required) input.required = true;
  if (field.readonly) {
    input.readOnly = true;
    input.setAttribute("aria-readonly", "true");
    label.classList.add("readonly");
  }
  if (field.placeholder) input.placeholder = field.placeholder;
  if (field.maxLength !== undefined) input.maxLength = field.maxLength;
  if (field.pattern) input.pattern = field.pattern;
  if (field.title) input.title = field.title;
  if (field.validationPattern && field.invalidMessage) {
    const expression = new RegExp(
      `^(?:${field.validationPattern})$`,
    );
    const validate = () => {
      const valid = input.value === "" || expression.test(input.value);
      input.setCustomValidity(valid ? "" : field.invalidMessage);
    };
    standardFieldValidators.set(input, validate);
    input.addEventListener("input", validate);
  }
  if (field.accept) input.accept = field.accept;
  if (field.min !== undefined) input.min = String(field.min);
  if (field.max !== undefined) input.max = String(field.max);
  if (field.step !== undefined) input.step = String(field.step);
  if (field.value !== undefined && field.type !== "checkbox") {
    input.value = String(field.value);
  }
  if (field.type === "checkbox") input.checked = Boolean(field.value);

  if (field.type === "checkbox") {
    label.classList.add("checkbox-field");
    label.append(input, name);
  } else {
    label.append(name);
    if (field.stepper && field.type === "number") {
      label.append(createNumberStepper(input, field));
    } else if (field.suffix) {
      const control = document.createElement("div");
      control.className = "management-input-affix";
      const suffix = document.createElement("span");
      suffix.className = "management-input-suffix";
      suffix.textContent = field.suffix;
      control.append(input, suffix);
      label.append(control);
    } else {
      label.append(input);
    }
  }

  if (field.help) {
    const help = document.createElement("small");
    help.textContent = field.help;
    label.append(help);
  }
  body.append(label);
}

function replaceSelectOptions(select, options) {
  const previousValue = select.value;
  select.replaceChildren();
  for (const optionConfig of options) {
    const option = document.createElement("option");
    const normalized = normalizeChoice(optionConfig);
    option.value = normalized.value;
    option.textContent = normalized.label;
    select.append(option);
  }
  if ([...select.options].some((option) => option.value === previousValue)) {
    select.value = previousValue;
  }
}

function appendFormSection(body, field) {
  const section = document.createElement("section");
  section.className = "management-form-section";
  const heading = document.createElement("h4");
  heading.textContent = field.label;
  section.append(heading);

  if (field.help) {
    const help = document.createElement("p");
    help.textContent = field.help;
    section.append(help);
  }

  body.append(section);
}

function permissionOptions(permissions) {
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

/**
 * @param {string[]} modelTypes 模型类型
 * @returns {{value: string, label: string, description: string}[]}
 */
function modelTypeOptions(modelTypes) {
  return modelTypes.map((modelType) => ({
    value: modelType,
    label: modelTypeLabels[modelType] || modelType,
    description: modelType,
  }));
}

/**
 * 过滤后端当前允许注册的模型类型。
 *
 * @param {string[]} modelTypes 框架支持的模型类型
 * @param {string[]} availableModelTypes 后端允许的模型类型
 * @returns {string[]}
 */
function filterModelTypes(modelTypes, availableModelTypes) {
  const available = new Set(availableModelTypes);
  const filtered = [];
  for (const modelType of modelTypes) {
    if (available.has(modelType)) filtered.push(modelType);
  }
  return filtered;
}

/**
 * @param {ManagementRoleOption[]} roles 角色选项
 */
function roleOptions(roles) {
  return roles.map((role) => ({
    value: role.name,
    label: role.name,
    description: role.description || "未提供角色描述",
  }));
}

export {
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
  normalizeChoice,
  optionalValue,
  permissionOptions,
  readJsonConfig,
  replaceSelectOptions,
  roleOptions,
  standardFieldValidators,
  taskTypeOptionsByModelType,
};
