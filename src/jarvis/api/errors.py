"""API-layer exceptions (mapped to HTTP in ``app``)."""


class ForbiddenError(Exception):
    """Caller is authenticated but not allowed to perform the action."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)
