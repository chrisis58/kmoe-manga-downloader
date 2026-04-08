# JSON 输出格式规范

本文档说明 kmdr 在 toolcall 模式下的 JSON 输出格式。

## 输出类型

kmdr 输出两种类型的 JSON：

1. **result** - 最终结果，程序退出时输出
2. **progress** - 进度更新，执行过程中实时输出

---

## Result 格式

最终结果在程序退出时通过 `emit()` 输出：

```json
{
  "type": "result",
  "code": 0,
  "msg": "success",
  "data": { ... }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 固定为 `"result"` |
| `code` | int | 状态码，0 表示成功 |
| `msg` | string | 状态消息 |
| `data` | any | 返回数据，失败时为 `null` |

### 成功示例

```json
{
  "type": "result",
  "code": 0,
  "msg": "success",
  "data": {
    "total_pages": 5,
    "page": 1,
    "count": 20,
    "books": [...]
  }
}
```

### 失败示例

```json
{
  "type": "result",
  "code": 21,
  "msg": "登录失败：用户名或密码错误",
  "data": null
}
```

---

## Progress 格式

进度更新在下载过程中实时输出：

```json
{"type": "progress", "status": "downloading", "percentage": 45.2, "volume": "第1卷", "size_mb": 50.0}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 固定为 `"progress"` |
| `status` | string | 状态：`downloading`/`completed`/`failed`/`skipped` |
| `percentage` | float | 下载进度百分比（0-100） |
| `volume` | string | 当前卷名称 |
| `size_mb` | float | 文件大小（MB） |

### 状态说明

| 状态 | 说明 |
|------|------|
| `downloading` | 正在下载 |
| `completed` | 下载完成 |
| `failed` | 下载失败 |
| `skipped` | 跳过（文件已存在） |

### 进度流示例

```json
{"type": "progress", "status": "downloading", "percentage": 0.0, "volume": "第1卷", "size_mb": 50.0}
{"type": "progress", "status": "downloading", "percentage": 25.5, "volume": "第1卷", "size_mb": 50.0}
{"type": "progress", "status": "downloading", "percentage": 50.2, "volume": "第1卷", "size_mb": 50.0}
{"type": "progress", "status": "completed", "volume": "第1卷", "size_mb": 50.0}
{"type": "progress", "status": "downloading", "percentage": 0.0, "volume": "第2卷", "size_mb": 48.5}
...
```

**注意**：进度每 10MB 输出一次，避免输出过于频繁。

---

## 数据结构

### BookInfo

```json
{
  "id": "abc123",
  "name": "漫画名称",
  "url": "https://kxo.moe/c/abc123.htm",
  "author": "作者名",
  "status": "连载中",
  "last_update": "2024-01-15"
}
```

### Credential

```json
{
  "username": "user123",
  "nickname": "用户昵称",
  "cookies": "***SENSITIVE***",
  "user_quota": {
    "total": 500.0,
    "used": 100.0,
    "remaining": 400.0
  },
  "vip_quota": null,
  "level": 1,
  "status": "active",
  "order": 1
}
```

**注意**：`cookies` 字段会被自动脱敏为 `"***SENSITIVE***"`。

### QuotaInfo

```json
{
  "total": 500.0,
  "used": 100.0,
  "remaining": 400.0
}
```

### DownloadSummary

下载命令最终输出：

```json
{
  "book": "漫画名称",
  "total": 5,
  "completed": 4,
  "failed": 1,
  "skipped": 0
}
```

---

## 解析建议

### 处理进度流

进度 JSON 以 NDJSON (Newline-Delimited JSON) 格式输出，每行一个 JSON 对象：

```python
import json

for line in stdout:
    data = json.loads(line)
    if data["type"] == "progress":
        handle_progress(data)
    elif data["type"] == "result":
        handle_result(data)
```

### 错误处理

检查 `code` 字段判断是否成功：

```python
result = json.loads(last_line)
if result["code"] == 0:
    # 成功
    data = result["data"]
else:
    # 失败
    error_msg = result["msg"]
    error_code = result["code"]
```

### 敏感数据处理

`SafeJSONEncoder` 会自动脱敏标记为敏感的字段，无需额外处理。