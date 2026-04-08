# 命令详细说明

本文档详细说明 kmdr 的所有命令及其参数。

## 全局选项

| 选项 | 说明 |
|------|------|
| `--mode <mode>` | 任何使用，你都应该使用 `toolcall` 模式 |
| `--fast-auth` | 使用本地凭证池加速认证，跳过网络验证 |

---

## search - 搜索漫画

搜索 Kmoe 网站上的漫画。

### 语法

```bash
kmdr --mode toolcall [--fast-auth] search <keyword> [-p <page>] [-m]
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `keyword` | string | 是 | 搜索关键字 |
| `-p, --page` | int | 否 | 页码，默认 1 |
| `-m, --minimal` | flag | 否 | 仅返回书名和链接，减少输出体积 |

### 输出示例

```json
{
  "type": "result",
  "code": 0,
  "msg": "success",
  "data": {
    "total_pages": 5,
    "page": 1,
    "count": 1,
    "books": [
      {
        "id": "abc123",
        "name": "漫画名称",
        "url": "https://kxo.moe/c/abc123.htm",
        "author": "作者名",
        "status": "连载中",
        "last_update": "2024-01-15"
      }
    ]
  }
}
```

### 使用建议

- 使用具体的关键字可以获得更精确的结果
- 支持中文和日文关键字
- `-m` 选项适合批量获取链接列表

---

## download - 下载漫画

从指定 URL 下载漫画。

### 语法

```bash
kmdr --mode toolcall [--fast-auth] download [options]
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `-l, --book-url` | string | 是* | 漫画详情页 URL |
| `-d, --dest` | string | 否 | 下载保存路径，默认当前目录 |
| `-v, --volume` | string | 是* | 指定卷号：`1,2,3` / `1-5` / `all` |
| `-t, --type` | string | 否 | 卷类型过滤：`vol`/`extra`/`seri` |
| `-f, --format` | string | 否 | 文件格式：`mobi`/`eput`，默认为 `epub` |
| `--num-workers` | int | 否 | 并发下载数，默认 8 |
| `--explain` | flag | 否 | 仅输出下载计划和预估信息，不执行实际下载 |

### 进度输出

下载过程中会输出进度 JSON：

```json
{"type": "progress", "status": "downloading", "volume": "全一册", "size_mb": 109.7, "percentage": 91.2},
{"type": "progress", "status": "completed", "volume": "全一册", "size_mb": 109.7},
```

### 最终结果

```json
{"type": "result", "code": 0, "msg": "success", "data": {"book": "命運之鳥", "total": 1, "completed": 1, "failed": 0, "skipped": 0}}
```

### 使用建议

- 首次下载建议先检查配额：`kmdr --mode toolcall status`
- 大批量下载建议使用凭证池
- 如果最近已经验证过凭证可用，可以在本次会话中使用 `--fast-auth` 来跳过联网验证
- 下载大量卷时，建议先执行 `--explain` 获取下载计划和预估配额消耗，确认后再执行实际下载

---

## login - 登录账号

登录 Kmoe 账号并保存凭证。

### 语法

```bash
kmdr --mode toolcall login -u <username> -p <password>
```

### 参数

| 参数 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `-u, --username` | string | 是* | 用户名 |
| `-p, --password` | string | 是* | 密码 |

### 输出示例

```json
{
  "type": "result",
  "code": 0,
  "msg": "success",
  "data": {
    "username": "user@example.com",
    "cookies": "***SENSITIVE***",
    "user_quota": {
      "reset_day": 3,
      "total": 3072.0,
      "used": 475.7,
      "unsynced_usage": 0.0,
      "update_at": 1775012825.2579331
    },
    "level": 3,
    "nickname": "user",
    "vip_quota": null,
    "order": 1,
    "status": "active",
    "note": null
  }
}
```

---

## status - 查看配额状态

查看当前登录账号的配额状态。

### 语法

```bash
kmdr --mode toolcall status
```

### 输出示例

```json
{
  "type": "result",
  "code": 0,
  "msg": "success",
  "data": {
    "username": "user@example.com",
    "cookies": "***SENSITIVE***",
    "user_quota": {
      "reset_day": 3,
      "total": 3072.0,
      "used": 475.7,
      "unsynced_usage": 0.0,
      "update_at": 1775012825.2579331
    },
    "level": 3,
    "nickname": "user",
    "vip_quota": null,
    "order": 1,
    "status": "active",
    "note": null
  }
}
```

---

## pool - 凭证池管理

管理多个账号凭证。

### pool add - 添加凭证

```bash
kmdr --mode toolcall pool add -u <username> -p <password>
```

### pool list - 列出凭证

```bash
kmdr --mode toolcall pool list [--refresh]
```

| 参数 | 说明 |
|------|------|
| `--refresh` | 刷新所有凭证的配额状态 |

输出示例：

```json
{
  "type": "result",
  "code": 0,
  "msg": "success",
  "data": {
    "total_quota": 2596.3,
    "pool": [
      {
        "username": "user@example.com",
        "cookies": "***SENSITIVE***",
        "user_quota": {
          "reset_day": 3,
          "total": 3072.0,
          "used": 475.7,
          "unsynced_usage": 0.0,
          "update_at": 1775012825.2579331
        },
        "level": 3,
        "nickname": "user",
        "vip_quota": null,
        "order": 1,
        "status": "active",
        "note": null
      }
    ]
  }
}
```

### pool use - 切换默认账号

```bash
kmdr --mode toolcall pool use <username>
```

### pool remove - 移除凭证

```bash
kmdr --mode toolcall pool remove <username>
```

### pool update - 更新凭证信息

```bash
kmdr --mode toolcall pool update -u <username> [-n <note>] [-o <order>]
```

---

## config - 配置管理

管理 kmdr 配置项。

### config --set - 设置配置

```bash
kmdr --mode toolcall config --set <key>=<value>
```

可配置项：

| 键 | 类型 | 说明 |
|------|------|------|
| `dest` | string | 默认下载路径 |
| `proxy` | string | 代理地址 |
| `num_workers` | int | 并发下载数 |
| `retry` | int | 重试次数 |
| `callback` | string | 下载完成回调命令 |
| `format` | string | 文件格式 |

### config --list - 列出配置

```bash
kmdr --mode toolcall config --list
```

### config --unset - 取消配置

```bash
kmdr --mode toolcall config --unset <key>
```

### config --clear - 清除所有配置

```bash
kmdr --mode toolcall config --clear
```

---

## version - 查看版本

```bash
kmdr --mode toolcall version
```