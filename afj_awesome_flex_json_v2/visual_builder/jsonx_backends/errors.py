from __future__ import annotations

from typing import Any


class JsonXProviderError(RuntimeError):
    """Provider failure with safe diagnostics suitable for the JsonX UI."""

    def __init__(
        self,
        message: str,
        *,
        provider: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.diagnostics = {"provider": provider, **(diagnostics or {})}
