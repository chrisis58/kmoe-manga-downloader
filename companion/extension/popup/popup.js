// kmdr Companion — Popup logic

// ── Tab switching ──────────────────────────────────────────────

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");
    if (tab.dataset.tab === "downloads") refreshTasks();
    if (tab.dataset.tab === "logs") refreshLogs();
  });
});

// ── Downloads tab ──────────────────────────────────────────────

async function refreshTasks() {
  const list = document.getElementById("task-list");
  try {
    const result = await chrome.runtime.sendMessage({ type: "GET_TASKS" });
    const tasks = result?.data?.tasks || [];
    if (!tasks.length) {
      list.innerHTML = '<div class="empty">暂无下载任务</div>';
      return;
    }
    list.innerHTML = tasks
      .map((task) => {
        const icon =
          task.status === "completed" ? "✅" : task.status === "failed" ? "❌" : "⏳";
        const progressHtml =
          task.status === "running" && task.progress?.volumes
            ? Object.entries(task.progress.volumes)
                .map(
                  ([name, info]) => `
              <div class="progress-row">
                <span>${esc(name)}</span>
                <div class="progress-bar"><div class="progress-fill" style="width:${info.percentage || 0}%"></div></div>
                <span>${(info.percentage || 0).toFixed(0)}%</span>
              </div>`
                )
                .join("")
            : "";
        return `
          <div class="task-item">
            <div class="task-header">
              <span class="task-status">${icon}</span>
              <span class="task-book">${esc(task.book_name)}</span>
            </div>
            <div class="task-vols">${esc((task.volumes || []).join(", "))}</div>
            <div class="task-progress">${progressHtml}</div>
          </div>`;
      })
      .join("");
  } catch (e) {
    list.innerHTML = `<div class="empty">加载失败: ${esc(e.message)}</div>`;
  }
}

// ── Settings tab ───────────────────────────────────────────────

const connMode = document.getElementById("conn-mode");
const sshFields = document.getElementById("ssh-fields");

connMode.addEventListener("change", () => {
  sshFields.classList.toggle("show", connMode.value === "ssh");
});

// Load saved config
(async () => {
  const result = await chrome.runtime.sendMessage({ type: "GET_CONFIG" });
  const conn = result?.data?.connection || { mode: "local" };
  connMode.value = conn.mode;
  if (conn.mode === "ssh" && conn.ssh) {
    sshFields.classList.add("show");
    document.getElementById("ssh-host").value = conn.ssh.host || "";
    document.getElementById("ssh-user").value = conn.ssh.user || "";
    document.getElementById("ssh-port").value = conn.ssh.port || 22;
  }
  // Load hijack setting (default true)
  const hijackEl = document.getElementById("hijack-enabled");
  hijackEl.checked = result?.data?.hijackEnabled !== false;
})();

document.getElementById("btn-save").addEventListener("click", async () => {
  const msgEl = document.getElementById("status-msg");
  msgEl.textContent = "保存中...";
  msgEl.className = "status-msg";

  const connection = { mode: connMode.value };
  if (connection.mode === "ssh") {
    connection.ssh = {
      host: document.getElementById("ssh-host").value.trim(),
      user: document.getElementById("ssh-user").value.trim(),
      port: parseInt(document.getElementById("ssh-port").value, 10) || 22,
    };
  }
  const hijackEnabled = document.getElementById("hijack-enabled").checked;
  try {
    await chrome.runtime.sendMessage({
      type: "SAVE_CONFIG",
      payload: { connection, hijackEnabled },
    });

    // Notify active kxx.moe tabs about hijack toggle
    const tabs = await chrome.tabs.query({ url: ["https://kxx.moe/*", "https://mox.moe/*"] });
    for (const tab of tabs) {
      chrome.tabs.sendMessage(tab.id, {
        type: "SET_HIJACK",
        payload: { enabled: hijackEnabled },
      }).catch(() => {});
    }

    msgEl.textContent = "✓ 已保存";
  } catch (e) {
    msgEl.textContent = `保存失败: ${e.message}`;
    msgEl.className = "status-msg error";
  }
});

document.getElementById("btn-test").addEventListener("click", async () => {
  const msgEl = document.getElementById("status-msg");
  msgEl.textContent = "测试中...";
  msgEl.className = "status-msg";

  const results = [];

  // Test 1: sendNativeMessage (one-shot)
  try {
    const result = await new Promise((resolve, reject) => {
      chrome.runtime.sendNativeMessage("com.kmdr.host", {
        action: "status",
        params: {},
        target: "local",
      }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(response);
      });
    });
    results.push(`sendNativeMessage: ✓ code=${result.code}`);
  } catch (e) {
    results.push(`sendNativeMessage: ✗ ${e.message}`);
  }

  // Test 2: connectNative (persistent port — keepassxc-browser style)
  try {
    const result = await new Promise((resolve, reject) => {
      let settled = false;
      try {
        const port = chrome.runtime.connectNative("com.kmdr.host");
        port.onMessage.addListener((msg) => {
          if (!settled) {
            settled = true;
            port.disconnect();
            resolve(msg);
          }
        });
        port.onDisconnect.addListener(() => {
          if (!settled) {
            settled = true;
            const err = chrome.runtime.lastError?.message || "port disconnected";
            reject(new Error(err));
          }
        });
        port.postMessage({ action: "status", params: {}, target: "local" });
      } catch (e) {
        if (!settled) {
          settled = true;
          reject(e);
        }
      }
    });
    results.push(`connectNative: ✓ code=${result.code}`);
  } catch (e) {
    results.push(`connectNative: ✗ ${e.message}`);
  }

  // Test 3: echo host (sendNativeMessage)
  try {
    const result = await new Promise((resolve, reject) => {
      chrome.runtime.sendNativeMessage("com.kmdr.echo_test", {
        action: "ping",
        params: {},
        target: "local",
      }, (response) => {
        if (chrome.runtime.lastError) {
          reject(new Error(chrome.runtime.lastError.message));
          return;
        }
        resolve(response);
      });
    });
    results.push(`echo(send): ✓ msg="${result.msg}"`);
  } catch (e) {
    results.push(`echo(send): ✗ ${e.message}`);
  }

  // Test 4: echo host (connectNative)
  try {
    const result = await new Promise((resolve, reject) => {
      let settled = false;
      try {
        const port = chrome.runtime.connectNative("com.kmdr.echo_test");
        port.onMessage.addListener((msg) => {
          if (!settled) {
            settled = true;
            port.disconnect();
            resolve(msg);
          }
        });
        port.onDisconnect.addListener(() => {
          if (!settled) {
            settled = true;
            const err = chrome.runtime.lastError?.message || "port disconnected";
            reject(new Error(err));
          }
        });
        port.postMessage({ action: "ping", params: {}, target: "local" });
      } catch (e) {
        if (!settled) {
          settled = true;
          reject(e);
        }
      }
    });
    results.push(`echo(connect): ✓ msg="${result.msg}"`);
  } catch (e) {
    results.push(`echo(connect): ✗ ${e.message}`);
  }

  const allOk = results.every((r) => r.includes("✓"));
  msgEl.innerHTML = results.join("<br>");
  msgEl.className = allOk ? "status-msg" : "status-msg error";
});

// ── Logs tab ──────────────────────────────────────────────────

async function refreshLogs() {
  const list = document.getElementById("log-list");
  try {
    const result = await chrome.runtime.sendMessage({ type: "GET_LOGS" });
    const logs = result?.data?.logs || [];
    if (!logs.length) {
      list.innerHTML = '<div class="empty">暂无日志</div>';
      return;
    }
    list.innerHTML = logs
      .map(
        (l) => `
      <div class="log-entry ${logEntryClass(l)}">
        <span class="log-time">${formatLogTime(l.time)}</span>
        <span class="log-msg">${esc(l.message)}</span>
      </div>`
      )
      .join("");
  } catch (e) {
    list.innerHTML = `<div class="empty">加载失败: ${esc(e.message)}</div>`;
  }
}

// ── Helpers ────────────────────────────────────────────────────

function esc(str) {
  const div = document.createElement("div");
  div.textContent = String(str);
  return div.innerHTML;
}

function formatLogTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function logLevelClass(msg) {
  if (msg.startsWith("→")) return "info";
  if (msg.startsWith("←")) return "info";
  if (msg.startsWith("✗")) return "error";
  if (msg.startsWith("✓")) return "info";
  return "";
}

function logEntryClass(entry) {
  if (entry.level === "error") return "log-error";
  const msg = entry.message || "";
  if (msg.startsWith("✗")) return "log-error";
  if (msg.startsWith("←")) return "log-response";
  if (msg.startsWith("→")) return "log-request";
  return "";
}

// ── Init ───────────────────────────────────────────────────────

refreshTasks();
