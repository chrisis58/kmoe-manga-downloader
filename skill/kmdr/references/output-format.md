# JSON 输出格式

kmdr 在 toolcall 模式下输出 NDJSON（每行一个 JSON 对象）。

## 输出类型

| 类型 | 含义 | 出现场景 |
|------|------|----------|
| `result` | 最终结果 | 所有命令退出时 |
| `progress` | 进度更新 | 仅 download 命令执行过程中实时输出 |

## result 格式

```json
{"type": "result", "code": 0, "msg": "success", "data": {...}}
```

- `code`: 0 = 成功，非 0 = 错误（查阅 [error-codes.md](./error-codes.md)）
- `data`: 成功时包含返回数据，失败时为 `null`

## progress 格式

```json
{"type": "progress", "status": "downloading", "percentage": 45.2, "volume": "第1卷", "size_mb": 50.0}
```

- `status`: `downloading` | `completed` | `failed` | `skipped`
- 每 10MB 输出一次，进度流以 `status: "completed"` 或 `"failed"` 结束

## 关键数据结构

### download --background 返回

```json
{"type": "result", "code": 0, "data": {"task_id": "20260415_143000", "pid": 12345}}
```

- `task_id` 格式 `YYYYMMDD_HHMMSS`，是查询进度的唯一凭证

### progress <task_id> 返回

统一返回 `result` 类型，通过 `data.is_finished` 区分：

- **进行中**：`"is_finished": false`，查看 `data.volumes` 获取各卷进度
- **已完成**：`"is_finished": true`，查看 `data.book`, `data.total`, `data.completed`, `data.failed`, `data.skipped`，以及 `data.volumes` 各卷最终状态
- **不存在**：`code: 45`（查阅 error-codes.md）

### --explain 返回

`data` 关键字段：`estimate_quota_usage_mb`, `avai_quota_mb`, `to_download[]`（含 `name` 和 `size`）, `skipped[]`

### BookInfo（搜索/详情）

```json
{"id": "...", "name": "漫画名称", "url": "https://kxo.moe/c/abc123.htm", "author": "...", "status": "连载中", "tags": ["日語", "完結"], ...}
```

- `tags`：字符串数组。语言标签（`日語`/`英文`，无则为中文翻译版）；状态标签（`完結`/`停更`）。用于区分同名条目的语言版本。
