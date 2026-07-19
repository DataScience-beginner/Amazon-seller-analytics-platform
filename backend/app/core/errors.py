from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ApplicationError(Exception):
    """Expected application failure safe to expose through the API contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = dict(details or {})


class NotFoundError(ApplicationError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            "resource_not_found",
            f"{resource} was not found",
            status_code=404,
        )


class ConflictError(ApplicationError):
    def __init__(
        self, code: str, message: str, *, details: Mapping[str, Any] | None = None
    ) -> None:
        super().__init__(code, message, status_code=409, details=details)
