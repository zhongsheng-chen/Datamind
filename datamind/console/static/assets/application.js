/** 绑定关于窗口，使用浏览器原生弹窗管理焦点和 Escape 关闭。 */
export function bindAboutDialog() {
  const button = document.querySelector("#about-button");
  const dialog = document.querySelector("#about-dialog");
  button.addEventListener("click", () => dialog.showModal());
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (
      event.clientX < bounds.left || event.clientX > bounds.right
      || event.clientY < bounds.top || event.clientY > bounds.bottom
    ) {
      dialog.close();
    }
  });
}

/** 加载当前应用版本，供关于窗口展示。 */
export async function loadApplicationInfo(request) {
  try {
    const info = await request("info", { retry: false });
    if (typeof info?.version !== "string" || !info.version) {
      document.querySelector("#about-dialog [data-app-version]").textContent = "暂不可用";
      return;
    }

    for (const element of document.querySelectorAll("[data-app-version]")) {
      element.textContent = `v${info.version}`;
      element.hidden = false;
    }
    document.querySelector("[data-release-notes]").href = (
      `https://github.com/zhongsheng-chen/Datamind/releases/tag/v${encodeURIComponent(info.version)}`
    );
  } catch {
    // 版本信息暂不可用时，继续正常登录和使用控制台。
    document.querySelector("#about-dialog [data-app-version]").textContent = "暂不可用";
  }
}
