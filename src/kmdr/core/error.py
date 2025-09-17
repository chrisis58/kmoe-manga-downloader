from typing import Optional

class KmdrError(RuntimeError):
    def __init__(self, message: str, solution: Optional[list[str]] = None, *args: object, **kwargs: object):
        super().__init__(message, *args, **kwargs)
        self.message = message

        self._solution = "" if solution is None else "\n[bold cyan]推荐解决方法:[/bold cyan] \n" + "\n".join(f"[cyan]>>> {sol}[/cyan]" for sol in solution)

class LoginError(KmdrError):
    def __init__(self, message, solution: Optional[list[str]] = None):
        super().__init__(message, solution)

    def __str__(self):
        return f"{self.message}\n{self._solution}"