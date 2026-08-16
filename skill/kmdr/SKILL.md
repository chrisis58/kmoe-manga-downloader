---
name: kmdr
description: "Kmoe 漫画下载器。支持搜索漫画、下载漫画、管理凭证池等。当用户想要从 Kmoe 网站下载漫画、搜索漫画、管理下载账号配额时触发此 skill。"
compatibility: "Requires kmdr CLI installed and valid credentials configured"
user-invocable: true
---

# kmdr - Kmoe 漫画下载器

## 概述

kmdr 是一个用于从 [Kmoe](https://kxx.moe/) 网站下载漫画的命令行工具。

## 环境准备

安装：

```bash
pip install --pre "kmoe-manga-downloader>=1.4.0.a3,<2.0.0"
```

验证安装：

```bash
kmdr --mode toolcall version
```

登录（二选一）：
- **推荐**：让用户在终端执行 `kmdr login -u <username> [-p <password>]`，凭证不会暴露给智能体
- **备选**：用户提供凭证，智能体执行 `kmdr --mode toolcall login -u <username> -p <password>`（凭证会出现在对话历史中）

检测登录状态：

```bash
kmdr --mode toolcall status
```

## 调用方式

**所有命令必须使用 `--mode toolcall`** 以获取结构化 JSON 输出。向用户建议手动执行命令时不要包含此参数。

`--fast-auth` 原则：**会话首次命令联网同步凭证，后续只读操作可跳过，写操作不要跳过以确保配额准确。**

- 会话首次命令（无论 search / download --explain）→ 不加 `--fast-auth`
- 后续只读（search、download --explain、progress、config --list、pool list）→ 加 `--fast-auth`
- 写操作（download、pool add/remove/use、config --set）→ 不加 `--fast-auth`
- status、login → `--fast-auth` 对其无效

## 命令速览

| 命令 | 语法 | 用途 |
|------|------|------|
| `search` | `kmdr --mode toolcall search <keyword> [-p N] [-m]` | 搜索漫画 |
| `download` | `kmdr --mode toolcall download -l <url> -v <vol> [--explain\|--background]` | 下载漫画 |
| `progress` | `kmdr --mode toolcall progress <task_id> [--wait N]` | 查询后台下载进度 |
| `login` | `kmdr --mode toolcall login -u <user> -p <pass>` | 登录账号 |
| `status` | `kmdr --mode toolcall status` | 查看配额 |
| `pool` | `kmdr --mode toolcall pool <add\|list\|use\|remove>` | 管理凭证池 |
| `config` | `kmdr --mode toolcall config <--set\|--list\|--clear>` | 管理配置 |

> 完整选项见 `kmdr --mode toolcall <command> --help`。输出格式详见 [./references/output-format.md](./references/output-format.md)。

## 典型工作流

```
搜索 → 获取详情 → 预估下载计划 → 确认配额 → 启动后台下载 → 响应用户进度查询 → 完成确认
```

| 步骤 | 命令 |
|------|------|
| 1. 检查环境 | 确认安装并登录（见「环境准备」） |
| 2. 搜索漫画 | `kmdr --mode toolcall search "漫画名称"` |
| 3. 获取详情 | 从搜索结果中取 `url` 字段（结合 `tags` 区分语言版本） |
| 4. 预估下载 | `kmdr --mode toolcall --fast-auth download -l <url> -v <volume> --explain` |
| 5. 确认配额 | `kmdr --mode toolcall --fast-auth status`，对比预估消耗决定是否继续 |
| 6. 启动后台下载 | `kmdr --mode toolcall download -l <url> -v <volume> --background`（返回 `task_id`） |
| 7. 响应用户查询 | 用户询问进度时执行 `kmdr --mode toolcall progress <task_id> [--wait N]` |
| 8. 完成确认 | 下载完成后报告结果（成功/失败/跳过数） |

> 实际顺序可能不同，遵循 `--fast-auth` 原则即可。

## 后台下载要点

- **预估**：先用 `--explain` 获取下载计划和配额预估（`estimate_quota_usage_mb`、`avai_quota_mb`）
- **启动**：`--background` 立即返回 `task_id`（格式 `YYYYMMDD_HHMMSS`）和 `pid`
- **查询**：`progress <task_id> [--wait N]`。用户随口一问用 `--wait 0`（即时返回），要求等完成用 `--wait 60`（阻塞等待，完成即返回）
- **判断**：通过 `data.is_finished` 判断——`false` 进行中（看 `data.volumes`），`true` 已完成（看 `completed/failed/skipped`）
- **task_id 是查询进度的唯一凭证**，智能体应在会话中记住它；无需主动轮询，仅在用户询问时响应

## 错误处理

命令通过 `code` 字段表示状态（0 = 成功）。**遇到非 0 的 code 时，必须查阅 [错误码文档](./references/error-codes.md) 获取恢复策略，不可自行猜测处理方式。**

## 注意事项

- 搜索结果中可能存在同名但语言/版本不同的条目。`BookInfo.tags` 字段包含语言标签（`日語`/`英文`，无标签则为中文翻译版）和状态标签（`完結`/`停更`），可用于区分和选择
- 下载前检查 `dest` 配置（`kmdr config --list`），若未设置则需要向用户确认保存路径
