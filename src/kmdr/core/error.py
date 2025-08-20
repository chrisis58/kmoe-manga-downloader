from typing import Optional

class KmdrError(RuntimeError):
    def __init__(self, message: str, solution: Optional[list[str]] = None, *args: object, **kwargs: object):
        super().__init__(message, *args, **kwargs)
        self.message = message

        self._solution = "" if solution is None else "\nSuggested Solution: \n" + "\n".join(f">>> {sol}" for sol in solution)

class LoginError(KmdrError):
    def __init__(self, message, solution: Optional[list[str]] = None):
        super().__init__(message, solution)

    def __str__(self):
        return f"{self.message}\n{self._solution}"