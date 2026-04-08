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
pip install kmoe-manga-downloader
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

所有命令都应使用 `--mode toolcall` 参数以获取结构化的 JSON 输出：

```bash
kmdr --mode toolcall <command> [options]
```

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

**使用场景**：用户想要下载指定漫画、批量下载多个卷。

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
6. **下载** → `kmdr --mode toolcall --fast-auth download -l <url> -v <volume> [-d <path>]`

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
| `download` | 下载漫画 | `kmdr --mode toolcall [--fast-auth] download -l <url>` |
| `login` | 登录账号 | `kmdr --mode toolcall login -u user -p pass` |
| `status` | 查看配额 | `kmdr --mode toolcall status` |
| `pool list` | 列出凭证 | `kmdr --mode toolcall pool list` |
| `config` | 配置设置 | `kmdr --mode toolcall config --set dest=/downloads` |