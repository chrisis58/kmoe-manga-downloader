// kmdr Companion — Content Script
// Injects kmdr download UI into kxx.moe manga detail pages

(async function () {
  "use strict";
  console.log("[kmdr] content script starting...");

  // ── Extract book info ──────────────────────────────────────────

  function extractBookInfo() {
    const nameEl = document.querySelector("font.text_bglight_big");
    const bookName = nameEl?.textContent?.trim()
      || document.title?.split(" -")[0]?.trim()
      || "Unknown";
    // bookid appears in multiple hidden inputs on the page
    const idEl = document.querySelector("input[name='bookid']");
    const bookId = idEl?.value || "";
    return {
      name: bookName,
      id: bookId,
      url: window.location.href,
    };
  }

  const bookInfo = extractBookInfo();
  console.log("[kmdr] book info:", bookInfo);

  // ── Extract volumes from the rendered DOM table ────────────────

  function extractVolumesFromDOM() {
    const volumes = [];
    const table = document.getElementById("div_tabdata");
    if (!table) {
      console.log("[kmdr] #div_tabdata not found");
      return volumes;
    }

    const rows = table.querySelectorAll("tr");
    for (const row of rows) {
      const checkbox = row.querySelector("input[name='checkbox_vol']");
      if (!checkbox?.value) continue;

      const volId = checkbox.value.trim();

      // Volume name from <b> tag
      const bTag = row.querySelector("b");
      const rawName = bTag ? bTag.textContent.replace(/\s+/g, " ").trim() : `ID:${volId}`;
      // Strip leading dots/spaces (e.g. "  卷 01" → "卷 01")
      const name = rawName.replace(/^[.\s]+/, "");

      // Determine vol_type from the section header row
      let volType = "unknown";
      let current = row;
      for (let i = 0; i < 30; i++) {
        current = current.previousElementSibling;
        if (!current) break;
        const headerText = (current.textContent || "").trim();
        if (headerText.includes("單行本")) { volType = "tankoubon"; break; }
        if (headerText.includes("連載話") || headerText.includes("连载话")) { volType = "serial"; break; }
      }

      // Size from <font class="filesize">
      const sizeEl = row.querySelector("font.filesize");
      let size = 0;
      if (sizeEl) {
        const sizeMatch = sizeEl.textContent.match(/([\d.]+)\s*M/);
        if (sizeMatch) size = parseFloat(sizeMatch[1]);
      }

      // Page count from <font class="filesize"> (e.g. "179.3M (203頁)")
      let pages = 0;
      if (sizeEl) {
        const pageMatch = sizeEl.textContent.match(/(\d+)\s*頁/);
        if (pageMatch) pages = parseInt(pageMatch[1], 10);
      }

      volumes.push({ id: volId, name, vol_type: volType, size, pages, index: 0 });
    }
    return volumes;
  }

  // ── Reliable messaging to background ────────────────────────────

  async function sendToBackground(message, retries = 2) {
    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        return await chrome.runtime.sendMessage(message);
      } catch (e) {
        const isContextInvalidated =
          e.message?.includes("context invalidated") ||
          e.message?.includes("Extension context invalidated");
        if (isContextInvalidated && attempt < retries) {
          // Service worker may have been terminated — wait and retry
          console.log("[kmdr] context invalidated, retrying in 500ms...");
          await new Promise((r) => setTimeout(r, 500));
          continue;
        }
        throw e;
      }
    }
  }

  // ── Toast notification ──────────────────────────────────────────

  function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `kmdr-toast kmdr-toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add("kmdr-toast-show"));
    setTimeout(() => {
      toast.classList.remove("kmdr-toast-show");
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  // ── Floating ball (always visible) ─────────────────────────────

  const floatingBall = document.createElement("div");
  floatingBall.id = "kmdr-floating-ball";
  floatingBall.innerHTML = `<span id="kmdr-ball-badge">0</span>`;
  floatingBall.title = "kmdr Companion — 下载任务";
  document.body.appendChild(floatingBall);
  console.log("[kmdr] floating ball appended to body");

  function updateBallBadge(count) {
    const badge = document.getElementById("kmdr-ball-badge");
    if (badge) {
      badge.textContent = count;
      badge.style.display = count > 0 ? "flex" : "none";
    }
  }

  // ── Download panel (always visible) ────────────────────────────

  const panel = document.createElement("div");
  panel.id = "kmdr-panel";
  panel.innerHTML = `
    <div id="kmdr-panel-header">
      <span>kmdr 下载</span>
      <button id="kmdr-panel-close">&times;</button>
    </div>
    <div id="kmdr-panel-list"></div>
  `;
  document.body.appendChild(panel);

  floatingBall.addEventListener("click", () => {
    panel.classList.toggle("kmdr-panel-open");
  });
  document.getElementById("kmdr-panel-close").addEventListener("click", () => {
    panel.classList.remove("kmdr-panel-open");
  });

  // ── Panel rendering ─────────────────────────────────────────────

  async function refreshPanel() {
    const list = document.getElementById("kmdr-panel-list");
    let tasks = [];
    try {
      const result = await sendToBackground({ type: "GET_TASKS" });
      tasks = result?.data?.tasks || [];
    } catch (e) {
      // Background may not be ready yet
    }

    if (!tasks.length) {
      list.innerHTML = '<div class="kmdr-panel-empty">暂无下载任务</div>';
      updateBallBadge(0);
      return;
    }

    const active = tasks.filter((t) => t.status === "running").length;
    updateBallBadge(active);

    list.innerHTML = tasks
      .map((task) => {
        const statusIcon =
          task.status === "completed"
            ? "✅"
            : task.status === "failed"
              ? "❌"
              : "⏳";
        const progressHtml = buildProgressHtml(task);
        return `
          <div class="kmdr-task-item" data-task-id="${task.task_id}">
            <div class="kmdr-task-main">
              <span class="kmdr-task-status">${statusIcon}</span>
              <div class="kmdr-task-info">
                <div class="kmdr-task-book">${escapeHtml(task.book_name)}</div>
                <div class="kmdr-task-vols">${escapeHtml((task.volumes || []).join(", "))}</div>
                ${progressHtml}
              </div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  function buildProgressHtml(task) {
    if (task.status === "running" && task.progress?.volumes) {
      return Object.entries(task.progress.volumes)
        .map(([name, info]) => {
          const pct = info.percentage || 0;
          return `<div class="kmdr-progress">
            <span class="kmdr-progress-name">${escapeHtml(name)}</span>
            <div class="kmdr-progress-bar"><div class="kmdr-progress-fill" style="width:${pct}%"></div></div>
            <span class="kmdr-progress-pct">${pct.toFixed(0)}%</span>
          </div>`;
        })
        .join("");
    }
    if (task.status === "completed") {
      const completed = task.progress?.completed || task.volumes?.length || 0;
      const total = task.progress?.total || task.volumes?.length || 0;
      return `<div class="kmdr-task-status-text">已完成 ${completed}/${total}</div>`;
    }
    if (task.status === "failed") {
      return `<div class="kmdr-task-status-text kmdr-failed">${task.progress?.msg || "下载失败"}</div>`;
    }
    return '<div class="kmdr-task-status-text">排队中...</div>';
  }

  function formatTime(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = String(str);
    return div.innerHTML;
  }

  // ── Poll panel periodically ─────────────────────────────────────

  setInterval(refreshPanel, 10000);
  refreshPanel();

  // ── Listen for task updates ─────────────────────────────────────

  chrome.runtime.onMessage.addListener((request) => {
    if (request.type === "TASKS_UPDATED") {
      refreshPanel();
    }
    if (request.type === "SET_HIJACK") {
      hijackEnabled = request.payload.enabled;
      console.log("[kmdr] hijack toggled:", hijackEnabled);
      if (hijackEnabled && !hijackDone) {
        const vols = extractVolumesFromDOM();
        hijackDownloadButtons(vols);
      } else if (!hijackEnabled) {
        // Hide kmdr buttons, restore originals
        document.querySelectorAll("a.kmdr-btn-hijacked").forEach((btn) => btn.remove());
        document.querySelectorAll("a[onclick*='down_geturl'], a[onclick*='captcha_show']").forEach((link) => {
          link.style.display = "";
        });
        hijackDone = false;
      }
    }
  });

  // ── Detect active format tab on kxx.moe page ──────────────────

  let activeFormat = null; // "epub", "mobi", or null

  function detectActiveFormat() {
    // kxx.moe format tabs: #nav_mobi, #nav_epub
    // Active tab has class "tab_check", inactive has "tab_unchk"
    const formatTabs = [
      { id: "nav_mobi", format: "mobi" },
      { id: "nav_epub", format: "epub" },
    ];
    for (const { id, format } of formatTabs) {
      const tab = document.getElementById(id);
      if (tab && tab.classList.contains("tab_check")) {
        if (activeFormat !== format) {
          console.log("[kmdr] detected active format:", format);
          activeFormat = format;
        }
        return format;
      }
    }
    // No tab_check found — format tab may not be visible
    // Keep the last known activeFormat
    return activeFormat;
  }

  // ── Button hijacking ───────────────────────────────────────────

  let hijackDone = false;
  let hijackEnabled = true; // default on, will be updated from storage

  // Load hijack setting from storage
  try {
    const config = await sendToBackground({ type: "GET_CONFIG" });
    if (config?.data?.hijackEnabled !== undefined) {
      hijackEnabled = config.data.hijackEnabled;
    }
    console.log("[kmdr] hijack enabled:", hijackEnabled);
  } catch (e) {
    // use default
  }

  function hijackDownloadButtons(pageVolumes) {
    if (hijackDone) return 0;
    if (!hijackEnabled) {
      console.log("[kmdr] hijack disabled by user setting");
      return 0;
    }
    if (!pageVolumes.length) {
      console.log("[kmdr] No volumes to hijack");
      return 0;
    }

    // Find all <a> tags with onclick containing 'down_geturl'
    const allLinks = document.querySelectorAll("a[onclick*='down_geturl']");
    console.log("[kmdr] found download links:", allLinks.length);

    const processedRows = new Set();
    let hijackCount = 0;

    for (const link of allLinks) {
      const row = link.closest("tr");
      if (!row || processedRows.has(row)) continue;

      const volId = extractVolIdFromRow(row, pageVolumes);
      if (!volId) {
        console.log("[kmdr] could not extract vol_id from row");
        continue;
      }

      processedRows.add(row);

      // Find all download links in this row
      const downloadLinks = row.querySelectorAll("a[onclick*='down_geturl'], a[onclick*='captcha_show']");
      for (const dlLink of downloadLinks) {
        const kmdrBtn = document.createElement("a");
        kmdrBtn.href = "#";
        kmdrBtn.className = dlLink.className;
        kmdrBtn.textContent = "📥 kmdr 下载";
        kmdrBtn.title = "通过 kmdr 下载";
        kmdrBtn.style.cssText = dlLink.style.cssText;
        kmdrBtn.classList.add("kmdr-btn-hijacked");
        kmdrBtn.style.cursor = "pointer";
        kmdrBtn.style.color = "#4CAF50";
        kmdrBtn.style.fontWeight = "bold";
        kmdrBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          handleDownloadClick(volId, pageVolumes, row);
        });

        dlLink.style.display = "none";
        dlLink.insertAdjacentElement("afterend", kmdrBtn);
        hijackCount++;
      }
    }

    if (hijackCount > 0) {
      hijackDone = true;
    }
    console.log("[kmdr] hijacked", hijackCount, "links in", processedRows.size, "rows");
    return hijackCount;
  }

  // ── Batch download button (top of format table) ────────────────

  let batchBtnTableId = null; // track which format table has the batch button

  function hijackBatchButtons(pageVolumes) {
    if (!hijackEnabled || pageVolumes.length === 0) return;

    // Find the currently visible format-specific table
    const formatTables = [
      { tableId: "div_epub" },
      { tableId: "div_mobi" },
    ];

    let visibleTable = null;
    for (const { tableId } of formatTables) {
      const table = document.getElementById(tableId);
      if (table && table.offsetParent !== null) { // visible
        visibleTable = { table, tableId };
        break;
      }
    }

    // Already added to the correct table
    if (visibleTable && batchBtnTableId === visibleTable.tableId) return;

    // Remove any existing batch buttons (from hidden tables)
    document.querySelectorAll(".kmdr-batch-btn, .kmdr-batch-sep").forEach((el) => el.remove());
    if (!visibleTable) {
      batchBtnTableId = null;
      return;
    }

    // Find container with existing batch download buttons
    const existingBatchBtn = visibleTable.table.querySelector("button[id*='bt_down_all']");
    if (!existingBatchBtn) {
      console.log("[kmdr] no batch download buttons found in", visibleTable.tableId);
      return;
    }

    const container = existingBatchBtn.parentElement;

    // Add separator
    const sep = document.createElement("span");
    sep.className = "kmdr-batch-sep";
    sep.innerHTML = "&nbsp;|&nbsp;";
    container.appendChild(sep);

    // Create kmdr batch download button
    const kmdrBatchBtn = document.createElement("button");
    kmdrBatchBtn.type = "button";
    kmdrBatchBtn.className = existingBatchBtn.className + " kmdr-batch-btn";
    kmdrBatchBtn.textContent = "📥 kmdr 批量下载";
    kmdrBatchBtn.style.cssText = existingBatchBtn.style.cssText;
    kmdrBatchBtn.style.color = "#4CAF50";
    kmdrBatchBtn.style.fontWeight = "bold";
    kmdrBatchBtn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      handleBatchDownloadClick(pageVolumes);
    });

    container.appendChild(kmdrBatchBtn);
    batchBtnTableId = visibleTable.tableId;
    console.log("[kmdr] batch download button added to", visibleTable.tableId);
  }

  function getCheckedVolIds() {
    const ids = new Set();
    const table = document.getElementById("div_tabdata");
    if (!table) return ids;
    const checkboxes = table.querySelectorAll("input[name='checkbox_vol']:checked");
    for (const cb of checkboxes) {
      if (cb.value) ids.add(cb.value.trim());
    }
    return ids;
  }

  async function handleBatchDownloadClick(pageVolumes) {
    // Only include volumes with checked checkboxes
    const checkedIds = getCheckedVolIds();
    const selected = pageVolumes.filter((v) => checkedIds.has(v.id));

    if (selected.length === 0) {
      showToast("请先勾选要下载的卷", "error");
      return;
    }

    // Remove any existing config panels
    document.querySelectorAll(".kmdr-inline-config").forEach((el) => el.remove());

    const batchBtn = document.querySelector(".kmdr-batch-btn");
    const defaultFormat = activeFormat || "";
    const volIds = selected.map((v) => v.id).join(",");
    const volNames = selected.map((v) => v.name);

    const fmtOptions = [
      { value: "", label: "默认" },
      { value: "epub", label: "EPUB" },
      { value: "mobi", label: "MOBI" },
    ].map((opt) => `<option value="${opt.value}"${opt.value === defaultFormat ? " selected" : ""}>${opt.label}</option>`).join("");

    const panel = document.createElement("div");
    panel.className = "kmdr-inline-config kmdr-batch-config";
    panel.innerHTML = `
      <div class="kmdr-inline-config-title">批量下载: ${selected.length} / ${pageVolumes.length} 卷${defaultFormat ? ` (格式: ${defaultFormat.toUpperCase()})` : ""}</div>
      <label>格式: <select class="kmdr-cfg-format">${fmtOptions}</select></label>
      <label>路径: <input type="text" class="kmdr-cfg-dest" placeholder="留空=kmdr默认" /></label>
      <div class="kmdr-inline-config-actions">
        <button class="kmdr-btn-cancel">取消</button>
        <button class="kmdr-btn-confirm">提交已选 ${selected.length} 卷</button>
      </div>
    `;

    document.body.appendChild(panel);

    if (batchBtn) {
      const rect = batchBtn.getBoundingClientRect();
      panel.style.top = Math.min(rect.bottom + window.scrollY + 4, window.innerHeight + window.scrollY - 200) + "px";
      panel.style.left = Math.min(rect.left + window.scrollX, window.innerWidth - 260) + "px";
    }
    panel.classList.add("kmdr-config-show");

    panel.querySelector(".kmdr-btn-cancel").addEventListener("click", () => panel.remove());

    panel.querySelector(".kmdr-btn-confirm").addEventListener("click", async () => {
      const fmt = panel.querySelector(".kmdr-cfg-format").value || undefined;
      const dest = panel.querySelector(".kmdr-cfg-dest").value || undefined;

      const btn = panel.querySelector(".kmdr-btn-confirm");
      btn.textContent = "提交中...";
      btn.disabled = true;

      try {
        const result = await sendToBackground({
          type: "DOWNLOAD",
          payload: {
            book_url: bookInfo.url,
            book_name: bookInfo.name,
            vol_ids: volIds,
            volume_names: volNames,
            format: fmt,
            dest: dest,
          },
        });

        if (result.code === 0) {
          showToast(`${bookInfo.name} — 批量下载 ${selected.length} 卷已提交`, "success");
          refreshPanel();
        } else {
          showToast(`下载提交失败: ${result.msg}`, "error");
        }
      } catch (e) {
        if (e.message?.includes("context invalidated")) {
          showToast("扩展已更新，请刷新页面后重试", "error");
        } else {
          showToast(`通信失败: ${e.message}`, "error");
        }
      }

      panel.remove();
    });

    // Click outside to close
    const closeHandler = (e) => {
      if (!panel.contains(e.target) && !e.target.classList.contains("kmdr-batch-btn")) {
        panel.remove();
        document.removeEventListener("click", closeHandler);
      }
    };
    setTimeout(() => document.addEventListener("click", closeHandler), 0);
  }

  function extractVolIdFromRow(row, pageVolumes) {
    // Method 1: checkbox value (most reliable)
    const checkbox = row.querySelector("input[name='checkbox_vol']");
    if (checkbox?.value) {
      const val = checkbox.value.trim();
      if (pageVolumes.some((v) => v.id === val)) return val;
    }

    // Method 2: parse down_geturl(bookid, volid, ...) from onclick
    const links = row.querySelectorAll("a[onclick*='down_geturl']");
    for (const link of links) {
      const onclick = link.getAttribute("onclick") || "";
      const match = onclick.match(/down_geturl\(\s*\d+\s*,\s*(\d+)/);
      if (match) {
        const candidate = match[1];
        if (pageVolumes.some((v) => v.id === candidate)) return candidate;
      }
    }

    // Method 3: extract from hidden input name (size_down_1001 → 1001)
    const hiddenInputs = row.querySelectorAll("input[type='hidden']");
    for (const input of hiddenInputs) {
      const name = input.getAttribute("name") || "";
      const m = name.match(/size_(?:down|push)_(\d+)/);
      if (m) {
        const candidate = m[1];
        if (pageVolumes.some((v) => v.id === candidate)) return candidate;
      }
    }

    // Method 4: match volume name from <b> tag
    if (pageVolumes.length > 0) {
      const bTag = row.querySelector("b");
      const rowText = bTag ? bTag.textContent.replace(/\s+/g, " ").trim() : "";
      for (const vol of pageVolumes) {
        if (vol.name && rowText.includes(vol.name)) return vol.id;
      }
    }

    return null;
  }

  async function handleDownloadClick(volId, pageVolumes, row) {
    const vol = pageVolumes.find((v) => v.id === volId);
    const volName = vol ? vol.name : volId;

    // Remove any existing config panels
    document.querySelectorAll(".kmdr-inline-config").forEach((el) => el.remove());

    const configPanel = createInlineConfig(row, volId, volName);
    document.body.appendChild(configPanel);

    const rowRect = row.getBoundingClientRect();
    configPanel.style.top = Math.min(rowRect.bottom + window.scrollY + 4, window.innerHeight + window.scrollY - 200) + "px";
    configPanel.style.left = Math.min(rowRect.left + window.scrollX, window.innerWidth - 260) + "px";
    configPanel.classList.add("kmdr-config-show");
  }

  function createInlineConfig(row, volId, volName) {
    const defaultFormat = activeFormat || ""; // auto-detect from kxx.moe tab
    const panel = document.createElement("div");
    panel.className = "kmdr-inline-config";
    const fmtOptions = [
      { value: "", label: "默认" },
      { value: "epub", label: "EPUB" },
      { value: "mobi", label: "MOBI" },
    ];
    const fmtSelectHtml = fmtOptions
      .map((opt) => `<option value="${opt.value}"${opt.value === defaultFormat ? " selected" : ""}>${opt.label}</option>`)
      .join("");
    panel.innerHTML = `
      <div class="kmdr-inline-config-title">下载: ${escapeHtml(volName)}${defaultFormat ? ` (格式: ${defaultFormat.toUpperCase()})` : ""}</div>
      <label>格式: <select class="kmdr-cfg-format">
        ${fmtSelectHtml}
      </select></label>
      <label>路径: <input type="text" class="kmdr-cfg-dest" placeholder="留空=kmdr默认" /></label>
      <div class="kmdr-inline-config-actions">
        <button class="kmdr-btn-cancel">取消</button>
        <button class="kmdr-btn-confirm">提交下载</button>
      </div>
    `;

    panel.querySelector(".kmdr-btn-cancel").addEventListener("click", () => panel.remove());

    panel.querySelector(".kmdr-btn-confirm").addEventListener("click", async () => {
      const fmt = panel.querySelector(".kmdr-cfg-format").value || undefined;
      const dest = panel.querySelector(".kmdr-cfg-dest").value || undefined;

      const btn = panel.querySelector(".kmdr-btn-confirm");
      btn.textContent = "提交中...";
      btn.disabled = true;

      try {
        const result = await sendToBackground({
          type: "DOWNLOAD",
          payload: {
            book_url: bookInfo.url,
            book_name: bookInfo.name,
            vol_ids: volId,
            volume_names: [volName],
            format: fmt,
            dest: dest,
          },
        });

        if (result.code === 0) {
          showToast(`${bookInfo.name} — ${volName} 已提交下载`, "success");
          refreshPanel();
        } else {
          showToast(`下载提交失败: ${result.msg}`, "error");
        }
      } catch (e) {
        if (e.message?.includes("context invalidated")) {
          showToast("扩展已更新，请刷新页面后重试", "error");
        } else {
          showToast(`通信失败: ${e.message}`, "error");
        }
      }

      panel.remove();
    });

    // Click outside to close
    const closeHandler = (e) => {
      if (!panel.contains(e.target)) {
        panel.remove();
        document.removeEventListener("click", closeHandler);
      }
    };
    setTimeout(() => document.addEventListener("click", closeHandler), 0);

    return panel;
  }

  // ── Wait for download table to appear, then hijack ──────────────

  function tryHijack() {
    // Detect active format from kxx.moe format tabs
    detectActiveFormat();

    // Detect table replacement (e.g. switching format tabs)
    // If our buttons are gone but the table has content, re-hijack
    if (hijackDone && !document.querySelector(".kmdr-btn-hijacked")) {
      console.log("[kmdr] hijacked buttons gone — table was replaced, re-hijacking");
      hijackDone = false;
    }

    const pageVolumes = extractVolumesFromDOM();
    console.log("[kmdr] tryHijack — volumes:", pageVolumes.length, "hijackDone:", hijackDone);
    if (pageVolumes.length > 0) {
      hijackDownloadButtons(pageVolumes);
      hijackBatchButtons(pageVolumes);
      return true;
    }
    return false;
  }

  // Try immediately (in case the table is already rendered, e.g. from cache)
  tryHijack();

  // Watch for the table being populated/changed via AJAX (tab switches, etc.)
  const tabdata = document.getElementById("div_tabdata");
  if (tabdata) {
    console.log("[kmdr] watching #div_tabdata for changes...");
    const observer = new MutationObserver(() => tryHijack());
    observer.observe(tabdata, { childList: true, subtree: true });
  } else {
    console.log("[kmdr] #div_tabdata not found — page may not be a manga detail page");
  }

  // Watch format tables for visibility changes (tab switches)
  for (const tableId of ["div_mobi", "div_epub"]) {
    const table = document.getElementById(tableId);
    if (table) {
      console.log("[kmdr] watching #" + tableId + " for visibility changes...");
      const fmtObserver = new MutationObserver(() => {
        const pageVolumes = extractVolumesFromDOM();
        if (pageVolumes.length > 0) {
          detectActiveFormat();
          hijackBatchButtons(pageVolumes);
        }
      });
      fmtObserver.observe(table, { attributes: true, attributeFilter: ["style", "class"] });
    }
  }

  console.log("[kmdr] content script ready — floating ball injected");
})().catch((err) => {
  console.error("[kmdr] content script error:", err);
});
