"use strict";

let nextId = 0;

/**
 * 为组织归属字段提供可键盘操作的单选菜单，保留原字段用于表单提交。
 *
 * @param {HTMLSelectElement} select 原始选择字段
 * @param {HTMLDialogElement} dialog 所属表单
 * @returns {{sync: () => void}} 同步选项与选中状态
 */
export function enhanceOrganizationSelect(select, dialog) {
  const control = document.createElement("div");
  control.className = "organization-select";
  const trigger = document.createElement("button");
  trigger.type = "button";
  trigger.className = "organization-select-trigger";
  const label = select.closest(".management-field")?.querySelector("span")?.textContent
    || (select.name === "organization_id" ? "所属机构" : "所属部门");
  trigger.setAttribute("aria-label", label);
  trigger.setAttribute("aria-haspopup", "listbox");
  trigger.setAttribute("aria-expanded", "false");
  const value = document.createElement("span");
  const chevron = document.createElement("span");
  chevron.className = "multiselect-chevron";
  chevron.setAttribute("aria-hidden", "true");
  trigger.append(value, chevron);
  const menu = document.createElement("div");
  menu.className = "organization-select-menu";
  menu.setAttribute("popover", "manual");
  menu.hidden = true;
  const options = document.createElement("div");
  options.id = `organization-options-${++nextId}`;
  options.className = "organization-select-options";
  options.setAttribute("role", "listbox");
  options.setAttribute("aria-label", label);
  trigger.setAttribute("aria-controls", options.id);
  menu.append(options);
  control.append(trigger, menu);
  select.hidden = true;
  select.after(control);

  const close = (restoreFocus = false) => {
    if (menu.hidden) return;
    if (typeof menu.hidePopover === "function") menu.hidePopover();
    menu.hidden = true;
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) trigger.focus();
  };
  const buttons = () => [...menu.querySelectorAll("button:not(:disabled)")];
  const open = (last = false) => {
    const bounds = trigger.getBoundingClientRect();
    menu.hidden = false;
    menu.style.width = `${bounds.width}px`;
    menu.style.left = `${bounds.left}px`;
    menu.style.top = `${bounds.bottom + 6}px`;
    if (typeof menu.showPopover === "function") menu.showPopover();
    const height = menu.getBoundingClientRect().height;
    if (bounds.bottom + 6 + height > window.innerHeight) {
      menu.style.top = `${Math.max(8, bounds.top - height - 6)}px`;
    }
    trigger.setAttribute("aria-expanded", "true");
    const choices = buttons();
    const selected = options.querySelector('[aria-selected="true"]');
    (last ? choices.at(-1) : selected || choices[0])?.focus();
  };
  const sync = () => {
    close();
    value.textContent = select.selectedOptions[0]?.textContent || "未设置";
    trigger.disabled = select.disabled;
    options.replaceChildren();
    menu.querySelector(".organization-select-create")?.remove();
    for (const option of select.options) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "organization-select-option";
      button.disabled = option.disabled;
      button.textContent = option.textContent;
      if (option.value === "__create__") {
        button.classList.add("organization-select-create");
        menu.append(button);
      } else {
        button.setAttribute("role", "option");
        button.setAttribute("aria-selected", String(option.selected));
        if (option.selected) {
          const mark = document.createElement("span");
          mark.className = "organization-select-check";
          mark.textContent = "✓";
          mark.setAttribute("aria-hidden", "true");
          button.append(mark);
        }
        options.append(button);
      }
      button.addEventListener("click", () => {
        close(true);
        select.value = option.value;
        select.dispatchEvent(new Event("change", { bubbles: true }));
        sync();
      });
    }
  };
  trigger.addEventListener("click", () => menu.hidden ? open() : close());
  trigger.addEventListener("keydown", event => {
    if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
    event.preventDefault();
    open(event.key === "ArrowUp");
  });
  menu.addEventListener("keydown", event => {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      close(true);
    } else if (event.key === "Tab") {
      close(true);
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const choices = buttons();
      const current = choices.indexOf(document.activeElement);
      const index = event.key === "Home" ? 0 : event.key === "End" ? choices.length - 1
        : (current + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
      choices[index]?.focus();
    }
  });
  const outsideClick = event => {
    if (!control.contains(event.target)) close();
  };
  const onScroll = event => {
    if (!menu.contains(event.target)) close();
  };
  const onResize = () => close();
  document.addEventListener("click", outsideClick);
  dialog.addEventListener("scroll", onScroll, true);
  window.addEventListener("resize", onResize);
  dialog.addEventListener("close", () => {
    close();
    document.removeEventListener("click", outsideClick);
    dialog.removeEventListener("scroll", onScroll, true);
    window.removeEventListener("resize", onResize);
  }, { once: true });
  sync();
  return { sync };
}
