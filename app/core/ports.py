from typing import Protocol


class LLMError(Exception):
    """The language model could not answer (timeout, HTTP error or unusable reply)."""


class LLMClient(Protocol):
    def complete(self, system: str, user: str, *, max_tokens: int) -> str: ...
