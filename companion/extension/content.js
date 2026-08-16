// kmdr Companion — page integration and floating control center

(async function () {
  "use strict";

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const state = { view: "tasks", tasks: [], config: null, hijackEnabled: true, batchTableId: null };

  function escapeHtml(value) {
    const el = document.createElement("div");
    el.textContent = String(value ?? "");
    return el.innerHTML;
  }

  function formatTime(value) {
    if (!value) return "";
    const date = new Date(value);
    return new Intl.DateTimeFormat("zh-CN", {
      month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    }).format(date);
  }

  async function send(message, retries = 2) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        return await chrome.runtime.sendMessage(message);
      } catch (error) {
        const invalidated = error.message?.toLowerCase().includes("context invalidated");
        if (!invalidated || attempt === retries) throw error;
        await new Promise((resolve) => setTimeout(resolve, 400));
      }
    }
  }

  function toast(message, type = "info") {
    const el = document.createElement("div");
    el.className = `kmdr-toast kmdr-toast-${type}`;
    el.textContent = message;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add("kmdr-toast-show"));
    setTimeout(() => {
      el.classList.remove("kmdr-toast-show");
      setTimeout(() => el.remove(), 200);
    }, 3200);
  }

  function extractBook() {
    return {
      name: $("font.text_bglight_big")?.textContent?.trim() || document.title.split(" -")[0].trim() || "Unknown",
      url: window.location.href,
    };
  }

  function extractVolumes() {
    const volumes = [];
    $$("#div_tabdata input[name='checkbox_vol']").forEach((checkbox) => {
      if (!checkbox.value) return;
      const controls = checkbox.closest("td");
      const nameCell = controls?.previousElementSibling;
      const rawName = nameCell?.querySelector("b")?.textContent?.replace(/\s+/g, " ").trim();
      volumes.push({ id: checkbox.value.trim(), name: rawName?.replace(/^[.\s]+/, "") || `ID:${checkbox.value}` });
    });
    return volumes;
  }

  function activeFormat() {
    const formats = [
      { format: "epub", tab: "#nav_epub", table: "#div_epub" },
      { format: "mobi", tab: "#nav_mobi", table: "#div_mobi" },
    ];
    return formats.find(({ tab }) => $(tab)?.classList.contains("tab_check"))?.format
      || formats.find(({ table }) => { const el = $(table); return el && el.offsetParent !== null; })?.format
      || undefined;
  }

  // ── Floating control center ────────────────────────────────────

  const launcher = document.createElement("button");
  launcher.id = "kmdr-launcher";
  launcher.type = "button";
  launcher.title = "打开 kmdr Companion";
  launcher.innerHTML = '<span class="kmdr-launcher-icon">↓</span><span id="kmdr-badge"></span>';

  const panel = document.createElement("section");
  panel.id = "kmdr-panel";
  panel.setAttribute("aria-label", "kmdr Companion");
  panel.innerHTML = `
    <header class="kmdr-panel-header">
      <button class="kmdr-back" type="button" aria-label="返回">‹</button>
      <div class="kmdr-title"><span class="kmdr-logo">k</span><div><strong>kmdr</strong><small id="kmdr-subtitle">最近任务</small></div></div>
      <div class="kmdr-header-actions">
        <button class="kmdr-icon-button kmdr-open-settings" type="button" title="设置">⚙</button>
        <button class="kmdr-icon-button kmdr-close" type="button" title="关闭">×</button>
      </div>
    </header>
    <div class="kmdr-panel-body">
      <div class="kmdr-view kmdr-view-tasks" data-view="tasks"><div class="kmdr-loading">正在读取任务…</div></div>
      <div class="kmdr-view kmdr-view-settings" data-view="settings"></div>
      <div class="kmdr-view kmdr-view-logs" data-view="logs"></div>
    </div>`;
  document.body.append(launcher, panel);

  function setOpen(open) {
    panel.classList.toggle("kmdr-panel-open", open);
    launcher.classList.toggle("kmdr-launcher-hidden", open);
    if (open) showView("tasks");
  }

  function showView(view) {
    state.view = view;
    $$(".kmdr-view", panel).forEach((el) => el.classList.toggle("kmdr-view-active", el.dataset.view === view));
    $(".kmdr-back", panel).classList.toggle("kmdr-visible", view !== "tasks");
    $(".kmdr-open-settings", panel).style.visibility = view === "tasks" ? "visible" : "hidden";
    $("#kmdr-subtitle", panel).textContent = { tasks: "最近任务", settings: "连接与偏好", logs: "诊断日志" }[view];
    if (view === "tasks") refreshTasks();
    if (view === "settings") renderSettings();
    if (view === "logs") refreshLogs();
  }

  launcher.addEventListener("click", () => setOpen(true));
  $(".kmdr-close", panel).addEventListener("click", () => setOpen(false));
  $(".kmdr-back", panel).addEventListener("click", () => showView("tasks"));
  $(".kmdr-open-settings", panel).addEventListener("click", () => showView("settings"));

  function taskSummary(task) {
    const volumes = Object.entries(task.progress?.volumes || {}).map(([name, info]) => ({ name, ...info }));
    const total = task.progress?.total || task.volumes?.length || volumes.length;
    const completed = task.progress?.completed ?? volumes.filter((v) => v.status === "completed").length;
    const active = volumes.filter((v) => ["downloading", "retrying"].includes(v.status));
    const pct = active.length
      ? active.reduce((sum, item) => sum + Number(item.percentage || 0), 0) / active.length
      : total ? (completed / total) * 100 : 0;
    return { total, completed, active, pct: Math.max(0, Math.min(100, pct)) };
  }

  function renderTasks() {
    const root = $(".kmdr-view-tasks", panel);
    const recent = state.tasks.slice(0, 8);
    const running = state.tasks.filter((task) => task.status === "running").length;
    const badge = $("#kmdr-badge");
    badge.textContent = running || "";
    badge.classList.toggle("kmdr-badge-visible", running > 0);

    if (!recent.length) {
      root.innerHTML = `<div class="kmdr-empty"><span>↓</span><strong>还没有下载任务</strong><p>在页面中勾选卷，然后点击“kmdr 批量下载”。</p></div>`;
      return;
    }

    root.innerHTML = `<div class="kmdr-task-overview"><span>${running ? `${running} 个任务进行中` : "最近下载"}</span><small>显示最近 ${recent.length} 项</small></div>
      <div class="kmdr-task-list">${recent.map((task) => {
        const summary = taskSummary(task);
        const status = task.status === "completed" ? "completed" : task.status === "failed" ? "failed" : "running";
        const label = status === "completed" ? "已完成" : status === "failed" ? "失败" : `${summary.completed}/${summary.total} 卷`;
        const volumeDetail = summary.active.slice(0, 2).map((info) =>
          `<div class="kmdr-volume-row"><span>${escapeHtml(info.volume || info.name || "正在下载")}</span><b>${Number(info.percentage || 0).toFixed(0)}%</b></div>`
        ).join("");
        return `<article class="kmdr-task kmdr-task-${status}">
          <div class="kmdr-task-top"><span class="kmdr-status-dot"></span><strong title="${escapeHtml(task.book_name)}">${escapeHtml(task.book_name)}</strong><time>${formatTime(task.created_at)}</time></div>
          <div class="kmdr-task-meta"><span>${label}</span><span>${escapeHtml((task.volumes || []).slice(0, 2).join("、"))}${task.volumes?.length > 2 ? ` 等 ${task.volumes.length} 卷` : ""}</span></div>
          ${status === "running" ? `<div class="kmdr-progress-track"><i style="width:${summary.pct}%"></i></div>${volumeDetail}` : ""}
          ${status === "failed" ? `<p class="kmdr-task-error">${escapeHtml(task.progress?.msg || "下载任务失败")}</p>` : ""}
        </article>`;
      }).join("")}</div>`;
  }

  async function refreshTasks() {
    try {
      const result = await send({ type: "GET_TASKS" });
      state.tasks = result?.data?.tasks || [];
      renderTasks();
    } catch (error) {
      $(".kmdr-view-tasks", panel).innerHTML = `<div class="kmdr-empty"><strong>任务读取失败</strong><p>${escapeHtml(error.message)}</p></div>`;
    }
  }

  function readConnectionForm() {
    const mode = $("#kmdr-connection-mode", panel).value;
    const connection = { mode };
    if (mode === "ssh") {
      connection.ssh = {
        host: $("#kmdr-ssh-host", panel).value.trim(),
        user: $("#kmdr-ssh-user", panel).value.trim(),
        port: parseInt($("#kmdr-ssh-port", panel).value, 10) || 22,
        keyFile: $("#kmdr-ssh-key", panel).value.trim() || undefined,
        kmdrPath: $("#kmdr-ssh-path", panel).value.trim() || undefined,
      };
    }
    return connection;
  }

  async function renderSettings() {
    const root = $(".kmdr-view-settings", panel);
    root.innerHTML = '<div class="kmdr-loading">正在读取设置…</div>';
    try {
      const result = await send({ type: "GET_CONFIG" });
      state.config = result?.data || { connection: { mode: "local" }, hijackEnabled: true };
      const connection = state.config.connection || { mode: "local" };
      const ssh = connection.ssh || {};
      root.innerHTML = `<div class="kmdr-settings-section">
        <h3>运行位置</h3>
        <div class="kmdr-segmented">
          <label><input type="radio" name="kmdr-mode" value="local" ${connection.mode !== "ssh" ? "checked" : ""}><span>本机</span></label>
          <label><input type="radio" name="kmdr-mode" value="ssh" ${connection.mode === "ssh" ? "checked" : ""}><span>SSH</span></label>
        </div>
        <select id="kmdr-connection-mode" hidden><option value="local">local</option><option value="ssh">ssh</option></select>
        <div class="kmdr-ssh-fields ${connection.mode === "ssh" ? "kmdr-visible" : ""}">
          <div class="kmdr-field-row"><label>主机<input id="kmdr-ssh-host" value="${escapeHtml(ssh.host)}" placeholder="example.com"></label><label class="kmdr-port">端口<input id="kmdr-ssh-port" type="number" value="${ssh.port || 22}"></label></div>
          <label>用户名<input id="kmdr-ssh-user" value="${escapeHtml(ssh.user)}" placeholder="可选"></label>
          <label>密钥文件<input id="kmdr-ssh-key" value="${escapeHtml(ssh.keyFile)}" placeholder="可选，建议配合 ssh-agent"></label>
          <label>kmdr 路径<input id="kmdr-ssh-path" value="${escapeHtml(ssh.kmdrPath)}" placeholder="留空时使用 PATH"></label>
        </div>
      </div>
      <div class="kmdr-settings-section"><h3>页面集成</h3><label class="kmdr-switch-row"><span><strong>批量下载按钮</strong><small>显示在网站原生批量按钮旁</small></span><input id="kmdr-hijack-enabled" type="checkbox" ${state.config.hijackEnabled !== false ? "checked" : ""}><i></i></label></div>
      <div class="kmdr-settings-actions"><button class="kmdr-button kmdr-button-secondary" id="kmdr-test">测试连接</button><button class="kmdr-button kmdr-button-primary" id="kmdr-save">保存设置</button></div>
      <div class="kmdr-setting-status" id="kmdr-setting-status"></div>
      <button class="kmdr-diagnostics-link" type="button">查看诊断日志 <span>›</span></button>`;

      $("#kmdr-connection-mode", panel).value = connection.mode;
      $$("input[name='kmdr-mode']", panel).forEach((radio) => radio.addEventListener("change", () => {
        $("#kmdr-connection-mode", panel).value = radio.value;
        $(".kmdr-ssh-fields", panel).classList.toggle("kmdr-visible", radio.value === "ssh");
      }));
      $(".kmdr-diagnostics-link", panel).addEventListener("click", () => showView("logs"));
      $("#kmdr-save", panel).addEventListener("click", saveSettings);
      $("#kmdr-test", panel).addEventListener("click", testConnection);
    } catch (error) {
      root.innerHTML = `<div class="kmdr-empty"><strong>设置读取失败</strong><p>${escapeHtml(error.message)}</p></div>`;
    }
  }

  async function saveSettings() {
    const status = $("#kmdr-setting-status", panel);
    const connection = readConnectionForm();
    const hijackEnabled = $("#kmdr-hijack-enabled", panel).checked;
    status.textContent = "保存中…";
    try {
      const result = await send({ type: "SAVE_CONFIG", payload: { connection, hijackEnabled } });
      if (result?.code !== 0) throw new Error(result?.msg || "保存失败");
      state.hijackEnabled = hijackEnabled;
      applyHijackSetting();
      status.textContent = "设置已保存";
      status.className = "kmdr-setting-status kmdr-success";
    } catch (error) {
      status.textContent = `保存失败：${error.message}`;
      status.className = "kmdr-setting-status kmdr-error";
    }
  }

  async function testConnection() {
    const status = $("#kmdr-setting-status", panel);
    const button = $("#kmdr-test", panel);
    status.textContent = "正在连接…";
    button.disabled = true;
    const started = performance.now();
    try {
      const result = await send({ type: "TEST_CONNECTION", payload: { connection: readConnectionForm() } });
      if (result?.code !== 0) throw new Error(result?.msg || `错误码 ${result?.code}`);
      status.textContent = `连接正常 · ${Math.round(performance.now() - started)} ms`;
      status.className = "kmdr-setting-status kmdr-success";
    } catch (error) {
      status.textContent = `连接失败：${error.message}`;
      status.className = "kmdr-setting-status kmdr-error";
    } finally {
      button.disabled = false;
    }
  }

  async function refreshLogs() {
    const root = $(".kmdr-view-logs", panel);
    root.innerHTML = '<div class="kmdr-loading">正在读取日志…</div>';
    try {
      const result = await send({ type: "GET_LOGS" });
      const logs = result?.data?.logs || [];
      root.innerHTML = `<div class="kmdr-log-toolbar"><span>最近 ${logs.length} 条</span><button type="button" class="kmdr-clear-logs">清空</button></div>
        <div class="kmdr-log-list">${logs.length ? logs.map((entry) => `<div class="kmdr-log kmdr-log-${entry.level}"><time>${formatTime(entry.time)}</time><p>${escapeHtml(entry.message)}</p></div>`).join("") : '<div class="kmdr-empty"><strong>没有诊断日志</strong></div>'}</div>`;
      $(".kmdr-clear-logs", panel).addEventListener("click", async () => {
        await send({ type: "CLEAR_LOGS" });
        refreshLogs();
      });
    } catch (error) {
      root.innerHTML = `<div class="kmdr-empty"><strong>日志读取失败</strong><p>${escapeHtml(error.message)}</p></div>`;
    }
  }

  // ── Page batch download integration ───────────────────────────

  function applyHijackSetting() {
    if (!state.hijackEnabled) {
      $$(".kmdr-batch-btn, .kmdr-batch-sep").forEach((el) => el.remove());
      state.batchTableId = null;
      return;
    }
    injectBatchButton(extractVolumes());
  }

  function injectBatchButton(volumes) {
    if (!state.hijackEnabled || !volumes.length) return;
    const visible = ["div_epub", "div_mobi"].map((id) => ({ id, el: document.getElementById(id) })).find(({ el }) => el && el.offsetParent !== null);
    if (!visible || state.batchTableId === visible.id) return;
    $$(".kmdr-batch-btn, .kmdr-batch-sep").forEach((el) => el.remove());
    const original = $("button[id*='bt_down_all']", visible.el);
    if (!original) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `${original.className} kmdr-batch-btn`;
    button.style.cssText = original.style.cssText;
    button.textContent = "↓ kmdr 批量下载";
    button.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      openBatchConfirm(extractVolumes());
    });
    const separator = document.createElement("span");
    separator.className = "kmdr-batch-sep";
    separator.textContent = " | ";
    original.parentElement.insertBefore(separator, original);
    original.parentElement.insertBefore(button, separator);
    state.batchTableId = visible.id;
  }

  function openBatchConfirm(volumes) {
    const checked = new Set($$("#div_tabdata input[name='checkbox_vol']:checked").map((el) => el.value.trim()));
    const selected = volumes.filter((volume) => checked.has(volume.id));
    if (!selected.length) return toast("请先勾选要下载的卷", "error");
    const format = activeFormat();
    $$(".kmdr-batch-confirm").forEach((el) => el.remove());
    const confirm = document.createElement("div");
    confirm.className = "kmdr-batch-confirm";
    confirm.innerHTML = `<div class="kmdr-confirm-icon">↓</div><div class="kmdr-confirm-content"><strong>下载 ${selected.length} 卷</strong><p>${format ? format.toUpperCase() : "默认格式"} · ${escapeHtml(selected.slice(0, 2).map((v) => v.name).join("、"))}${selected.length > 2 ? "…" : ""}</p></div><button class="kmdr-confirm-cancel" type="button">取消</button><button class="kmdr-confirm-submit" type="button">提交</button>`;
    document.body.appendChild(confirm);
    requestAnimationFrame(() => confirm.classList.add("kmdr-confirm-visible"));
    $(".kmdr-confirm-cancel", confirm).addEventListener("click", () => confirm.remove());
    $(".kmdr-confirm-submit", confirm).addEventListener("click", async () => {
      const button = $(".kmdr-confirm-submit", confirm);
      button.disabled = true;
      button.textContent = "提交中…";
      try {
        const book = extractBook();
        const result = await send({ type: "DOWNLOAD", payload: {
          book_url: book.url, book_name: book.name,
          vol_ids: selected.map((v) => v.id).join(","), volume_names: selected.map((v) => v.name), format,
        }});
        if (result?.code !== 0) throw new Error(result?.msg || "下载提交失败");
        toast(`${selected.length} 卷已加入下载`, "success");
        setOpen(true);
      } catch (error) {
        toast(`提交失败：${error.message}`, "error");
      } finally {
        confirm.remove();
      }
    });
  }

  chrome.runtime.onMessage.addListener((request) => {
    if (request.type === "TASKS_UPDATED") refreshTasks();
    if (request.type === "SET_HIJACK") {
      state.hijackEnabled = request.payload.enabled;
      applyHijackSetting();
    }
  });

  try {
    const result = await send({ type: "GET_CONFIG" });
    state.hijackEnabled = result?.data?.hijackEnabled !== false;
  } catch (error) {
    console.warn("[kmdr] config unavailable:", error);
  }

  const refreshIntegration = () => injectBatchButton(extractVolumes());
  refreshIntegration();
  const target = $("#div_tabdata");
  if (target) new MutationObserver(refreshIntegration).observe(target, { childList: true, subtree: true });
  ["#div_epub", "#div_mobi"].forEach((selector) => {
    const el = $(selector);
    if (el) new MutationObserver(() => {
      state.batchTableId = null;
      refreshIntegration();
    }).observe(el, { attributes: true, attributeFilter: ["style", "class"] });
  });
  setInterval(refreshTasks, 30000);
  refreshTasks();
})().catch((error) => console.error("[kmdr] content script failed:", error));
