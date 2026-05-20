---
name: kmdr
description: "Kmoe 漫画下载器。支持搜索漫画、下载漫画、管理凭证池等。当用户想要从 Kmoe 网站下载漫画、搜索漫画、管理下载账号配额时触发此 skill。"
compatibility: "Requires kmdr CLI installed and valid credentials configured"
user-invocable: true
---

# kmdr - Kmoe 漫画下载器

## 概述

kmdr 是一个用于从 [Kmoe](https://kxx.moe/) 网站下载漫画的命令行工具。此 skill 教导如何使用 kmdr 完成漫画搜索、下载、账号管理等任务。

## 环境准备

### 安装 kmdr

```bash
pip install --pre "kmoe-manga-downloader>=1.4.0.a1,<2.0.0"
```

验证安装：

```bash
kmdr --mode toolcall version
```

如果命令不存在，说明 kmdr 未安装或未添加到 PATH。

### 登录配置

#### 检测登录状态

```bash
kmdr --mode toolcall status
```

- 返回 `code: 0` → 已登录，可继续操作
- 返回 `code: 21` 或 `code: 23` → 未登录或凭证失效，需配置凭证

#### 配置凭证

**方式一（推荐）：用户自行登录**

在终端中执行：

```bash
kmdr login -u <username> [-p <password>]
```

如果不提供 `-p` 参数，将交互式提示输入密码。凭证将安全存储在本地配置文件中，不会暴露给智能体。

**方式二：智能体代为登录**

如果用户确认当前环境安全，可提供用户名和密码，由智能体执行登录命令。

⚠️ **风险提示**：凭证将出现在对话历史中，请确认环境安全后再选择此方式。

## 调用方式

你的所有命令都应使用 `--mode toolcall` 参数以获取结构化的 JSON 输出：

```bash
kmdr --mode toolcall <command> [options]
```

值得注意的是，当你向用户建议手动执行命令时，不要包含 `--mode toolcall` 参数，以便用户使用默认的交互式的输出格式。

## 主要命令

### 搜索漫画

```bash
kmdr --mode toolcall [--fast-auth] search <keyword> [-p <page>] [-m]
```

- `<keyword>`: 搜索关键字（必需）
- `-p, --page`: 页码，默认为 1
- `-m, --minimal`: 仅返回书名和链接

**使用场景**：用户想要搜索特定漫画、查找某作者的作品、发现新漫画。

### 下载漫画

```bash
kmdr --mode toolcall [--fast-auth] download [options]
```

关键选项：
- `-l, --book-url <url>`: 漫画详情页 URL
- `-d, --dest <path>`: 下载保存路径，默认从配置中读取，如果没有配置则是当前目录
- `-v, --volume`: 指定下载卷号（如 `1,2,3` 或 `1-5` 或 `all`）
- `-P, --use-pool`: 启用凭证池自动故障转移
- `-b, --background`: 后台下载，立即返回 task_id 和 PID，配合 `progress` 查询进度
- `--explain`: 仅输出下载计划，不执行实际下载

**使用场景**：用户想要下载指定漫画、批量下载多个卷。推荐使用 `--background` 后台启动，用户可随时通过 `progress` 查询进度。

### 登录和状态

```bash
kmdr --mode toolcall login -u <username> -p <password>
kmdr --mode toolcall status
```

**使用场景**：用户需要登录账号、查看剩余配额。

### 凭证池管理

```bash
kmdr --mode toolcall pool add -u <username> -p <password>
kmdr --mode toolcall pool list [--refresh]
kmdr --mode toolcall pool use <username>
kmdr --mode toolcall pool remove <username>
```

**使用场景**：用户需要管理多个账号、切换默认账号、查看所有账号配额。

### 配置管理

```bash
kmdr --mode toolcall config --set <key>=<value>
kmdr --mode toolcall config --list
kmdr --mode toolcall config --clear
```

可配置项：`dest`, `proxy`, `num_workers`, `retry`, `callback`, `format`

**使用场景**：用户需要设置下载路径、配置代理、调整并发数。在更新配置后，请使用 `config --list` 验证更改是否生效。

## 输出格式

详细输出格式请参阅 [./references/output-format.md](./references/output-format.md)。

### 结果类型

- `{"type": "result", "code": 0, ...}`: 最终结果
- `{"type": "progress", ...}`: 进度更新（仅下载命令）

### 错误处理

错误通过 `code` 字段表示，详细状态码请参阅 [./references/error-codes.md](./references/error-codes.md)。

## 示例场景

详细示例请参阅 [./assets/examples/](./assets/examples/) 目录。

### 典型工作流

1. **检查环境** → 确认已安装并登录（参见"环境准备"）
2. **搜索** → `kmdr --mode toolcall --fast-auth search "漫画名称"`
3. **获取详情** → 从搜索结果中获取 `url` 字段
4. **预估下载** → `kmdr --mode toolcall --fast-auth download -l <url> -v <volume> --explain`
5. **确认配额** → 根据预估消耗决定是否继续（若消耗较大需向用户确认）
6. **启动后台下载** → `kmdr --mode toolcall --fast-auth download -l <url> -v <volume> --background`
7. **响应用户查询** → 当用户询问下载进度（如"查询下载进度"）时，使用 `progress` 命令查询并报告
8. **完成确认** → 下载完成后向用户报告最终结果

## 后台下载模式

下载任务通常耗时 1-2 分钟（大批量下载可能更长），统一使用后台下载模式，这样可以跟踪进度并向用户报告。

### 工作流程

#### 步骤 1：预估下载计划

先用 `--explain` 获取下载计划：

```bash
kmdr --mode toolcall --fast-auth download -l <url> -v <volume> --explain
```

返回信息包括：
- `estimate_quota_usage_mb`: 预估配额消耗
- `avai_quota_mb`: 当前可用配额
- `to_download`: 待下载列表及各卷大小
- `skipped`: 已存在文件列表

#### 步骤 2：启动后台下载

使用 `--background` 参数启动后台下载：

```bash
kmdr --mode toolcall --fast-auth download -l <url> -v <volume> --background
```

立即返回：
- `task_id`: 任务 ID（如 `20260415_143000`）
- `pid`: 后台下载进程的 PID

**task_id 格式**：`YYYYMMDD_HHMMSS`（时间戳），用于查询任务状态。

将 `task_id` 返回给用户。告知用户："下载已启动，正在后台进行。您可以随时让我查询进度（例如'查询下载进度'或'查询进度 <task_id>'）。"

⚠️ **task_id 是后续查询进度的唯一凭证**。智能体必须在当前会话中牢记 task_id，以便用户后续发起查询时能直接使用，无需用户再次提供。

#### 步骤 3：响应用户的进度查询

**本步骤仅为用户主动询问时触发**，无需智能体主动轮询。当用户提出"查询下载进度""下载完了吗"或类似请求时，使用 `progress` 命令：

```bash
kmdr --mode toolcall progress <task_id> --wait 15
```

⚠️ **重要**：必须使用 `--wait` 参数，值至少为 15。`--wait` 的阻塞行为天然适配"用户提问 → 阻塞等待 → 立即回答"的交互模型。

参数：
- `<task_id>`: `download --background` 返回的任务 ID。如果智能体从上下文中找不到 task_id，可提醒用户提供
- `--wait`: 阻塞等待时间（秒），至少 15

**阻塞行为**：
- 命令会阻塞等待，任务完成则立即返回结果
- 如果任务未完成，等待指定时间后返回当前进度

**返回格式**：统一返回 `result` 类型：

```json
{"type": "result", "code": 0, "msg": "success", "data": {...}}
```

**判断方式**：通过 `data.is_finished` 判断任务状态：
- `is_finished: false` → 任务进行中，检查 `data.volumes` 字段获取各卷进度，告知用户当前进度
- `is_finished: true` → 任务完成，检查 `data` 字段获取最终结果（book、total、completed、failed、skipped）

#### 步骤 4：完成确认

当 `progress` 返回 `is_finished: true` 时：

1. 向用户报告下载完成
2. 展示 `data` 字段中的结果：
   - `book`: 漫画名称
   - `total`: 总卷数
   - `completed`: 成功下载数
   - `failed`: 失败数
   - `skipped`: 跳过数
3. 如果有失败，可读取日志文件查看详细错误信息

### 注意事项

- 后台下载进程独立运行，如果进程意外终止（崩溃、被系统杀掉），下载会中断
- 日志文件存放在系统临时目录，会被系统定期清理
- task_id 是关键信息，智能体应在会话上下文中始终保留；若丢失则提醒用户提供
- 如果下载失败，可以查看日志文件了解详细错误信息
- 智能体无需主动轮询进度，仅在用户询问时响应即可

## 注意事项

1. **认证要求**：大部分操作需要先登录或配置有效的 cookies
2. **配额限制**：下载会消耗账号配额，建议在下载前检查配额状态
3. **搜索结果过滤**：用户提供的关键词可能会多个相似结果（相同书名），请查看默认的下载路径
    - 如果本地有参考 → 自动选择匹配版本
    - 如果本地无参考 → 列出选项供用户选择
4. **代理配置**：如果遇到被屏蔽的内容，可以单独配置代理：`kmdr download -p <proxy_server> -l <url> -v <volume>`

## 快速参考

| 命令 | 用途 | 示例 |
|------|------|------|
| `search` | 搜索漫画 | `kmdr --mode toolcall [--fast-auth] search "fate"` |
| `download --explain` | 预估下载计划 | `kmdr --mode toolcall [--fast-auth] download -l <url> -v <volume> --explain` |
| `download --background` | 后台下载 | `kmdr --mode toolcall [--fast-auth] download -l <url> -v <volume> --background` |
| `progress` | 查询后台任务进度 | `kmdr --mode toolcall progress <task_id> --wait 15` |
| `login` | 登录账号 | `kmdr --mode toolcall login -u user -p pass` |
| `status` | 查看配额 | `kmdr --mode toolcall status` |
| `pool list` | 列出凭证 | `kmdr --mode toolcall pool list` |
| `config` | 配置设置 | `kmdr --mode toolcall config --set dest=/downloads` |