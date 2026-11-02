from typing import Protocol


class LLMError(Exception):
    """The language model could not answer (timeout, HTTP error or unusable reply)."""


class LLMClient(Protocol):
    def complete(
        self, system: str, user: str, *, max_tokens: int, timeout_seconds: float | None = None
    ) -> str:
        """The model's reply; `timeout_seconds=None` uses the adapter's default."""
        ...
