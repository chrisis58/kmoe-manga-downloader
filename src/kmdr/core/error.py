from typing import Optional

"""
KMDR 异常定义与状态码

状态码 (code) 为两位数格式，按业务归类划分：

- [ 0] 成功：在 console 拦截器中自动组装，代表命令顺利完成。
- [1x] 基础/本地/参数解析错误：发生于工具初始化阶段，或者用户传入的命令参数有逻辑冲突（如 InitializationError, ArgsResolveError）。
- [2x] 身份/凭证/配额错误：发生于与账密相关的事务交互中（如 LoginError, QuotaExceededError, NoCandidateCredentialError）。
- [3x] 重定向/路由错误：遭遇站点强制重定向（如 RedirectError）。
- [4x] 用户输入/外部操作受限：因终端条件不足、查询的目标不存在、或内容被和谐（如 ValidationError, EmptyResultError, NotInteractableError, ContentBlockedError）。
- [5x] 服务端/网络传输异常：因源站点宕机网络不通畅，或者网站的资源本身不支持某下载范式（如 ResponseError, RangeNotSupportedError）。
- [50] (保留给 console.py)：用于抛出非 KmdrError 的预期外的原生系统崩溃信息（如底层的 KeyError、IndexError）。
"""


class KmdrError(RuntimeError):
    code: int = 10

    def __init__(
        self,
        message: str,
        solution: Optional[list[str]] = None,
        *args: object,
        **kwargs: object,
    ):
        super().__init__(message, *args, **kwargs)
        self.message = message

        self._solution = (
            "" if solution is None else "\n[bold cyan]推荐解决方法:[/bold cyan] \n" + "\n".join(f"[cyan]>>> {sol}[/cyan]" for sol in solution)
        )

    def __str__(self):
        return f"{self.message}\n{self._solution}"


class InitializationError(KmdrError):
    code: int = 11

    def __init__(self, message, solution: Optional[list[str]] = None):
        super().__init__(message, solution)

    def __str__(self):
        return f"{self.message}\n{self._solution}"


class ArgsResolveError(KmdrError):
    code: int = 12

    def __init__(self, message, solution: Optional[list[str]] = None):
        super().__init__(message, solution)

    def __str__(self):
        return f"{self.message}\n{self._solution}"


class LoginError(KmdrError):
    code: int = 21

    def __init__(self, message, solution: Optional[list[str]] = None):
        super().__init__(message, solution)

    def __str__(self):
        return f"{self.message}\n{self._solution}"


class RedirectError(KmdrError):
    code: int = 31

    def __init__(self, message, new_base_url: str):
        super().__init__(message)
        self.new_base_url = new_base_url

    def __str__(self):
        return f"{self.message} 新的地址: {self.new_base_url}"


class ValidationError(KmdrError):
    code: int = 41

    def __init__(self, message, field: str):
        super().__init__(message)
        self.field = field

    def __str__(self):
        return f"{self.message} (字段: {self.field})"


class EmptyResultError(KmdrError):
    code: int = 42

    def __init__(self, message):
        super().__init__(message)


class ResponseError(KmdrError):
    code: int = 51

    def __init__(self, message, status_code: int):
        super().__init__(message)
        self.status_code = status_code

    def __str__(self):
        return f"{self.message} (状态码: {self.status_code})"


class RangeNotSupportedError(KmdrError):
    code: int = 52

    def __init__(self, message, content_range: Optional[str] = None):
        super().__init__(message)
        self.content_range = content_range

    def __str__(self):
        return (
            f"不支持分片下载：{self.message} (Content-Range: {self.content_range})"
            if self.content_range is not None
            else f"不支持分片下载：{self.message}"
        )


class NotInteractableError(KmdrError):
    code: int = 43

    def __init__(self, message):
        super().__init__(message)

    def __str__(self):
        return f"当前环境不支持交互式输入：{self.message}"


class QuotaExceededError(KmdrError):
    code: int = 22

    def __init__(self, message):
        super().__init__(message)

    def __str__(self):
        return f"配额用尽：{self.message}"


class NoCandidateCredentialError(KmdrError):
    code: int = 23

    def __init__(self, message):
        super().__init__(message)

    def __str__(self):
        return f"没有可用的凭证：{self.message}"

class ContentBlockedError(KmdrError):
    """
    内容被屏蔽错误，可能是以下两种原因：
    1. 无法在当前网络环境访问，如 https://kxx.moe/c/13663.htm
    2. 需要登录后才能访问，如 https://kzo.moe/c/0f496f.htm
    """
    code: int = 44

    def __init__(self, message, solution: Optional[list[str]] = None):
        super().__init__(message, solution)
