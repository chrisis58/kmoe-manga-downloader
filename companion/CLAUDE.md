# CLAUDE.md

本文件为 Claude Code（claude.ai/code）在此仓库中工作时提供指导。

## 项目概述

kmdr Companion 是一个**浏览器扩展 + Native Messaging Host**，在 kxx.moe 漫画详情页注入下载 UI。用户可以直接在页面上勾选卷，提交到 `kmdr` CLI（本地或 SSH 远程），无需离开浏览器。

```
kxx.moe 页面  ──content.js──▶  background.js  ──stdin/stdout──▶  native_host.exe  ──subprocess──▶  kmdr CLI
     │            (DOM 注入)        │ (Service Worker)            │ (Go 编译的 NMH)              │
     │                              │                             │                              │
     └── popup (任务/设置) ◀────────┘                             │                              │
                                                                  ├── 本地: os/exec             │
                                                                  └── SSH:   ssh user@host cmd  │
```

## 关键文件与职责

| 文件 | 职责 |
|---|---|
| `extension/content.js` | 注入到 kxx.moe `/c/*.htm` 页面的内容脚本。从 DOM 中提取书籍信息与卷列表，添加悬浮球 + 下载任务面板，在原生批量下载按钮左侧注入 kmdr 批量下载按钮。 |
| `extension/background.js` | Service Worker。桥接 `chrome.runtime.sendMessage` ↔ `chrome.runtime.sendNativeMessage("com.kmdr.host", …)`。管理 `chrome.storage.local` 中的下载任务，通过 `chrome.alarms` 轮询进度，更新扩展角标。 |
| `extension/popup/popup.html` + `popup.js` | 扩展弹窗，3 个标签页：下载（任务列表）、设置（本地/SSH 连接、批量按钮开关）、日志。 |
| `extension/content.css` | 注入元素的样式：悬浮球、任务面板、toast 通知。 |
| `native_host.go` | Native Messaging Host（Go，纯标准库）。从 stdin 读取长度前缀的 JSON，校验输入，构建 `kmdr` CLI 命令，通过 `os/exec`（本地）或 `ssh`（远程）执行，将结果以 JSON 写入 stdout。编译为独立 `.exe`，零运行时依赖。 |
| `go.mod` | Go module 定义（`kmdr-native-host`），仅依赖标准库。 |
| `install.ps1` / `install.sh` | 用户安装脚本。从 GitHub Releases 下载预编译的 `native_host` 二进制，写入 manifest 并注册到浏览器。零依赖（仅需 curl/wget）。 |
| `install-dev.ps1` / `install-dev.sh` | 开发安装脚本。从本地源码 `go build`，然后委托 install 脚本完成 manifest + 注册。需要 Go。 |
| `manifest-template.json` | NMH manifest 模板（供手动安装参考）。 |
| `../.github/workflows/release-companion.yml` | CI 发布工作流。推送 `companion-v*` 标签时自动构建多平台 Go 二进制文件并创建 GitHub Release。 |

## 扩展通信机制

1. **content.js → background.js**：`chrome.runtime.sendMessage({type, payload})`。异步，带 "context invalidated"（Service Worker 被终止后重启）重试。
2. **background.js → native_host.exe**：`chrome.runtime.sendNativeMessage("com.kmdr.host", {action, params, target})`。每次调用启动一个新的 Go 进程。
3. **native_host.exe → kmdr CLI**：`exec.CommandContext` 执行本地或 SSH 命令。kmdr 输出 NDJSON 到 stdout；host 解析最后一行 `{"type":"result",...}`。

流经的消息类型：`DOWNLOAD`、`STATUS`、`PROGRESS`、`GET_TASKS`、`GET_LOGS`、`GET_CONFIG`、`SAVE_CONFIG`。

## 如何修改扩展

- **修改 Native Host（Go）**：编辑 `native_host.go`。本地开发用 `install-dev.ps1`（Windows）或 `./install-dev.sh`（Linux/macOS）编译并安装。普通用户直接运行 `install.ps1` / `install.sh` 从 GitHub Releases 下载预编译二进制。
- **测试更改**：打开 `edge://extensions`，点击已加载扩展的"重新加载"，然后刷新 kxx.moe 页面。内容脚本在 `document_end` 时运行。
- **调试 content.js**：在 kxx.moe 页面打开 DevTools（F12）——content.js 的 `console.log` 输出会出现在这里。
- **调试 background.js**：在 `edge://extensions` 中点击 kmdr Companion 旁的 "Service Worker" 打开其 DevTools。
- **调试 native_host.go**：Go 端的错误会出现在 background.js 的控制台中（通过 `chrome.runtime.lastError`）。如需深入调试，由于 stdout 被 NMH 协议占用，可临时写入文件来排查。
- **页面是动态渲染的**：`#div_tabdata` 由 JS 在页面加载后填充。内容脚本使用 `MutationObserver` 检测卷表格的出现或变化（格式标签切换时会替换 `innerHTML`）。
- **格式标签**：页面有 `#div_epub` 和 `#div_mobi` 两个格式表格，同一时间只有一个可见。批量下载按钮注入到可见的那个表格中。切换标签时会移除旧按钮并在新可见表格中重建。
- **复选框交互**：复用页面原生的 `checkbox_vol` 复选框（位于 `#div_tabdata`）——kmdr 批量按钮点击时读取 `:checked` 复选框，无需自定义复选框逻辑。

## native_host.go 的输入校验

Go host 在构建 CLI 命令前对所有输入进行校验（函数 `validate()`）：
- `action`：必须是 `download`/`status`/`progress` 之一
- `book_url`：scheme 必须是 http/https，且必须有 host
- `vol_ids`：必须匹配 `^[\d,]+$`
- `dest`：不能以 `-` 开头，不能包含 `..`
- `task_id`：必须匹配 `^[\w.-]+$`
- `wait`：仅用于 progress，由 kmdr argparse 校验

这是安全层面的校验（防止命令注入）；`format`/`vol_type` 的类型和选项校验交由 kmdr 自身的 argparse 处理。

Go 版本编译为独立二进制文件，仅依赖标准库（`net/url`、`os/exec`、`regexp`、`encoding/json` 等），无需 Python 运行时或虚拟环境。

## SSH 密钥有密码怎么办

Native Host 使用 `BatchMode=yes` 执行 SSH，不会弹出密码提示。密钥有密码时需要通过以下方式之一处理：

### 方法一：ssh-agent（推荐）

先将密钥加载到 ssh-agent，之后 SSH 连接由 agent 自动提供密码：

**Windows**：
```powershell
# 启动 OpenSSH Authentication Agent 服务（只需一次）
Set-Service ssh-agent -StartupType Automatic
Start-Service ssh-agent
# 加载密钥
ssh-add C:\Users\用户名\.ssh\id_rsa
```

**macOS**：
```bash
ssh-add --apple-use-keychain ~/.ssh/id_rsa
```

**Linux**：
```bash
ssh-add ~/.ssh/id_rsa
```

### 方法二：在扩展设置中指定密钥文件

在弹窗的「设置」→ SSH 模式下，填写「密钥文件」路径（如 `~/.ssh/id_rsa` 或 `C:\Users\...\.ssh\id_rsa`）。Native Host 会通过 `ssh -i` 使用指定密钥。

> 注意：即使指定密钥文件，如果密钥本身有密码且未加入 ssh-agent，连接仍会失败。`BatchMode=yes` 禁止交互式输入密码。

## background.js 使用的 Storage Key

`chrome.storage.local` 键：`tasks`（下载任务数组）、`logs`（日志环形缓冲区，最多 200 条）、`connection`（本地/SSH 配置，含 `ssh.keyFile`）、`hijackEnabled`（批量按钮开关，默认 true）。

## 如何发布 Companion

1. 修改 `native_host.go` 后提交 PR
2. 合并到 main 后打 tag：`git tag companion-v1.0.0 && git push origin companion-v1.0.0`
3. GitHub Actions 自动构建 4 个平台的二进制文件并创建 Release：
   - `native_host-windows-amd64.exe`
   - `native_host-linux-amd64`
   - `native_host-darwin-amd64`
   - `native_host-darwin-arm64`
4. 用户运行 `install.ps1` / `install.sh` 时自动下载对应平台的二进制

安装脚本使用 `https://github.com/chrisis58/kmoe-manga-downloader/releases/latest/download/native_host-{os}-{arch}{ext}` 获取最新版本，用户无需安装任何编译工具。
