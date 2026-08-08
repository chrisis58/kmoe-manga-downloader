// kmdr Companion — Background Service Worker
// Bridges content script ↔ native host, manages tasks + polling

const NATIVE_HOST = "com.kmdr.host";

// ── Native Host communication ──────────────────────────────────────

async function sendToHost(message) {
  const extId = chrome.runtime.id;
  const startTime = Date.now();

  // Log the outgoing call
  // Log full command for diagnostics
  if (message.action === "download") {
    const cmdParts = [
      "kmdr", "--mode", "toolcall", "download",
      "-l", message.params.book_url || "?",
      "--vol-ids", message.params.vol_ids || "?",
      "--background",
    ];
    if (message.params.format) cmdParts.push("-f", message.params.format);
    if (message.params.dest) cmdParts.push("-d", message.params.dest);
    const fullCmd = cmdParts.join(" ");
    console.log("[kmdr bg] →", fullCmd);
    addLog("info", `→ ${fullCmd}`);
  } else {
    console.log("[kmdr bg] →", message.action, summarizeParams(message));
    addLog("info", `→ ${message.action} ${summarizeParams(message)}`);
  }

  return new Promise((resolve, reject) => {
    chrome.runtime.sendNativeMessage(NATIVE_HOST, message, (response) => {
      const elapsed = Date.now() - startTime;

      if (chrome.runtime.lastError) {
        const err = chrome.runtime.lastError.message;
        console.error("[kmdr bg] ✗", message.action, `(${elapsed}ms)`, err);
        addLog("error", `✗ ${message.action} 失败 (${elapsed}ms): ${err}`);
        reject(new Error(err));
        return;
      }

      // Log the response
      const respSummary = response.code === 0
        ? `code=${response.code} data=${JSON.stringify(response.data).substring(0, 200)}`
        : `code=${response.code} msg=${response.msg}`;
      console.log("[kmdr bg] ←", message.action, `(${elapsed}ms)`, respSummary);
      addLog("info", `← ${message.action} (${elapsed}ms) ${respSummary}`);

      resolve(response);
    });
  });
}

function summarizeParams(msg) {
  const p = msg.params || {};
  if (msg.action === "download") {
    return `vols=${p.vol_ids || "?"} fmt=${p.format || "default"}`;
  }
  if (msg.action === "progress") {
    return `task=${p.task_id}`;
  }
  if (msg.action === "status") {
    return `target=${JSON.stringify(msg.target)}`;
  }
  return "";
}

// ── Storage helpers ────────────────────────────────────────────────

async function getStored(key) {
  const result = await chrome.storage.local.get(key);
  return result[key];
}

async function setStored(key, value) {
  await chrome.storage.local.set({ [key]: value });
}

// ── Task management ────────────────────────────────────────────────

async function getTasks() {
  return (await getStored("tasks")) || [];
}

async function addTask(task) {
  const tasks = await getTasks();
  tasks.unshift(task);
  await setStored("tasks", tasks);
  updateBadge(tasks);
}

async function updateTask(taskId, updates) {
  const tasks = await getTasks();
  const idx = tasks.findIndex((t) => t.task_id === taskId);
  if (idx >= 0) {
    Object.assign(tasks[idx], updates);
    await setStored("tasks", tasks);
    updateBadge(tasks);
  }
}

function updateBadge(tasks) {
  const active = tasks.filter((t) => t.status === "running").length;
  if (active > 0) {
    chrome.action.setBadgeText({ text: String(active) });
    chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
  } else {
    chrome.action.setBadgeText({ text: "" });
  }
}

// ── Logging ────────────────────────────────────────────────────────

async function addLog(level, message) {
  const logs = (await getStored("logs")) || [];
  logs.unshift({ time: new Date().toISOString(), level, message });
  // Keep last 200 entries
  if (logs.length > 200) logs.length = 200;
  await setStored("logs", logs);
}

// ── Message handlers from content script ───────────────────────────

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  handleRequest(request).then(sendResponse);
  return true; // async
});

async function handleRequest(request) {
  const { type, payload } = request;

  try {
    if (type === "DOWNLOAD") {
      return await handleDownload(payload);
    } else if (type === "STATUS") {
      return await handleStatus(payload);
    } else if (type === "PROGRESS") {
      return await handleProgress(payload);
    } else if (type === "GET_TASKS") {
      return { code: 0, data: { tasks: await getTasks() } };
    } else if (type === "GET_LOGS") {
      return { code: 0, data: { logs: (await getStored("logs")) || [] } };
    } else if (type === "GET_CONFIG") {
      const connection = (await getStored("connection")) || { mode: "local" };
      const hijackEnabled = (await getStored("hijackEnabled"));
      return {
        code: 0,
        data: {
          connection,
          hijackEnabled: hijackEnabled !== false, // default true
        },
      };
    } else if (type === "SAVE_CONFIG") {
      await setStored("connection", payload.connection);
      if (payload.hijackEnabled !== undefined) {
        await setStored("hijackEnabled", payload.hijackEnabled);
      }
      addLog("info", `连接配置已更新: ${payload.connection.mode}`);
      return { code: 0, msg: "ok" };
    }
  } catch (e) {
    addLog("error", `${type} 处理失败: ${e.message}`);
    return { code: 500, msg: e.message };
  }
}

// ── Action handlers ────────────────────────────────────────────────

async function handleDownload(payload) {
  const connection = (await getStored("connection")) || { mode: "local" };
  const target = connection.mode === "ssh" ? connection.ssh : "local";

  const params = {
    book_url: payload.book_url,
    vol_ids: payload.vol_ids,
    format: payload.format || undefined,
    dest: payload.dest || undefined,
    vol_type: payload.vol_type || undefined,
  };

  // Clean undefined values
  Object.keys(params).forEach((k) => {
    if (params[k] === undefined) delete params[k];
  });

  const result = await sendToHost({
    action: "download",
    params,
    target,
  });

  if (result.code === 0 && result.data?.task_id) {
    await addTask({
      task_id: result.data.task_id,
      book_name: payload.book_name,
      book_url: payload.book_url,
      volumes: payload.volume_names || [],
      created_at: new Date().toISOString(),
      status: "running",
      progress: {},
    });
    addLog("info", `下载已启动: ${payload.book_name} (${payload.volume_names?.join(", ")}) — task_id: ${result.data.task_id}`);

    // Start polling for this task
    await chrome.alarms.create(`poll_${result.data.task_id}`, { periodInMinutes: 0.17 }); // ~10s
  } else {
    addLog("error", `下载提交失败: ${result.msg}`);
  }

  return result;
}

async function handleStatus(payload) {
  const connection = (await getStored("connection")) || { mode: "local" };
  const target = connection.mode === "ssh" ? connection.ssh : "local";

  return await sendToHost({ action: "status", params: {}, target });
}

async function handleProgress(payload) {
  const connection = (await getStored("connection")) || { mode: "local" };
  const target = connection.mode === "ssh" ? connection.ssh : "local";

  return await sendToHost({
    action: "progress",
    params: { task_id: payload.task_id, wait: payload.wait || 0 },
    target,
  });
}

// ── Alarm: poll progress ───────────────────────────────────────────

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (!alarm.name.startsWith("poll_")) return;
  const taskId = alarm.name.slice(5); // remove "poll_" prefix

  try {
    const result = await handleProgress({ task_id: taskId, wait: 0 });

    if (result.code === 0 && result.data) {
      if (result.data.is_finished) {
        await updateTask(taskId, {
          status: "completed",
          progress: result.data,
        });
        await chrome.alarms.clear(alarm.name);
        addLog("info", `下载完成: task_id ${taskId}`);
      } else {
        await updateTask(taskId, {
          status: "running",
          progress: result.data,
        });
      }
    }
  } catch (e) {
    // Silently retry next poll
    console.warn(`Poll failed for ${taskId}: ${e.message}`);
  }
});

// ── Init: restore badge ────────────────────────────────────────────

(async () => {
  const tasks = await getTasks();
  updateBadge(tasks);

  // Re-arm alarms for active tasks
  for (const task of tasks) {
    if (task.status === "running") {
      await chrome.alarms.create(`poll_${task.task_id}`, { periodInMinutes: 0.17 });
    }
  }
})();
