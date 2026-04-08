# 错误状态码说明

本文档说明 kmdr 在 toolcall 模式下返回的错误状态码。

## 状态码分类

状态码为两位数格式，按业务归类划分：

| 范围 | 分类 | 说明 |
|------|------|------|
| 0 | 成功 | 命令顺利完成 |
| 1x | 基础/参数错误 | 工具初始化或参数解析问题 |
| 2x | 身份/凭证错误 | 账号登录或配额相关问题 |
| 3x | 重定向错误 | 站点强制重定向 |
| 4x | 用户输入受限 | 终端条件不足或内容不可用 |
| 5x | 服务端/网络异常 | 网络问题或服务器错误 |

---

## 详细状态码

### 0 - 成功

```json
{"code": 0, "msg": "success", "data": {...}}
```

---

### 1x - 基础/参数错误

| 状态码 | 名称 | 说明 |
|--------|------|------|
| 10 | KmdrError | 通用错误 |
| 11 | InitializationError | 初始化失败 |
| 12 | ArgsResolveError | 参数解析错误 |
| 13 | ArgparseError | 命令行参数无效 |

**常见原因**：
- 配置文件损坏
- 参数格式不正确
- 缺少必需参数

**处理建议**：
- 检查命令语法
- 查看错误消息中的具体原因
- 尝试 `kmdr config --clear` 重置配置

---

### 2x - 身份/凭证错误

| 状态码 | 名称 | 说明 |
|--------|------|------|
| 21 | LoginError | 登录失败 |
| 22 | QuotaExceededError | 配额不足 |
| 23 | NoCandidateCredentialError | 无可用凭证 |

**常见原因**：
- 用户名或密码错误
- 账号被禁用
- 配额已用完
- 凭证池为空或所有凭证不可用

**处理建议**：
- 检查用户名密码
- 使用 `kmdr status` 查看配额
- 添加更多凭证到凭证池
- 等待配额重置（每月重置）

---

### 3x - 重定向错误

| 状态码 | 名称 | 说明 |
|--------|------|------|
| 31 | RedirectError | 站点重定向到新地址 |

**常见原因**：
- Kmoe 更换了域名
- 镜像站点切换

**处理建议**：
- 按照错误消息中的提示更新 base_url
- 运行 `kmdr config --set base_url=<new_url>`

---

### 4x - 用户输入受限

| 状态码 | 名称 | 说明 |
|--------|------|------|
| 41 | ValidationError | 输入验证失败 |
| 42 | EmptyResultError | 查询结果为空 |
| 43 | NotInteractableError | 无法交互操作 |
| 44 | ContentBlockedError | 内容被屏蔽 |

**常见原因**：
- 配置值无效（如目录不存在）
- 搜索无结果
- 非交互模式下需要用户输入
- 内容需要特定网络环境访问

**处理建议**：
- 检查输入参数
- 尝试不同的搜索关键字
- 配置代理：`kmdr config --set proxy=<proxy_url>`
- 在交互模式下操作

---

### 5x - 服务端/网络异常

| 状态码 | 名称 | 说明 |
|--------|------|------|
| 51 | ResponseError | 服务器响应错误 |
| 52 | RangeNotSupportedError | 服务器不支持分片下载 |

**常见原因**：
- 服务器维护或宕机
- 网络连接不稳定
- 代理配置问题

**处理建议**：
- 检查网络连接
- 稍后重试
- 配置或更换代理
- 使用 `--retry` 增加重试次数

---

### 50 - 未知错误

非 KmdrError 的预期外错误，如 Python 运行时异常：

```json
{"code": 50, "msg": "division by zero", "data": null}
```

**处理建议**：
- 检查错误消息
- 使用 `--verbose` 获取详细日志
- 提交 issue 到项目仓库

---

## 错误处理示例

### Python 示例

```python
import subprocess
import json

def run_kmdr(args):
    result = subprocess.run(
        ["kmdr", "--mode", "toolcall"] + args,
        capture_output=True,
        text=True
    )
    
    # 获取最后一行作为结果
    lines = result.stdout.strip().split("\n")
    final_result = json.loads(lines[-1])
    
    if final_result["code"] == 0:
        return final_result["data"]
    elif final_result["code"] == 22:
        raise QuotaExceededError("配额不足，请更换账号或等待重置")
    elif final_result["code"] == 21:
        raise AuthenticationError("登录失败，请检查凭证")
    else:
        raise KmdrError(final_result["msg"])
```

### Shell 示例

```bash
# 检查状态码
output=$(kmdr --mode toolcall search "test")
code=$(echo "$output" | tail -1 | jq -r '.code')

if [ "$code" -eq 0 ]; then
    echo "成功"
else
    echo "失败: $(echo "$output" | tail -1 | jq -r '.msg')"
fi
```

---

## 错误恢复策略

| 状态码范围 | 恢复策略 |
|------------|----------|
| 1x | 检查命令和参数，重置配置 |
| 2x | 检查凭证，使用凭证池切换账号 |
| 3x | 更新 base_url |
| 4x | 检查输入，配置代理，使用交互模式 |
| 5x | 检查网络，配置代理，增加重试 |