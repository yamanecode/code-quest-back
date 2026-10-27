import httpx

from app.core.ports import LLMError

TIMEOUT_SECONDS = 30
TEMPERATURE = 0.3


class OpenAICompatibleClient:
    """Any provider that exposes the OpenAI chat-completions endpoint, hosted or local."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str,
        reasoning_effort: str = "",
        *,
        http: httpx.Client | None = None,
    ) -> None:
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.http = http or httpx.Client(timeout=TIMEOUT_SECONDS)

    def complete(self, system: str, user: str, *, max_tokens: int) -> str:
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": TEMPERATURE,
        }
        # Reasoning models spend max_tokens on hidden thinking; "low" keeps room for the answer.
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        headers = {"Authorization": f"Bearer {self.api_key}"}
        # Error messages name only the failure type: the prompt must never reach the logs.
        try:
            response = self.http.post(self.url, json=body, headers=headers)
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
        except httpx.HTTPError as error:
            raise LLMError(f"request failed: {type(error).__name__}") from error
        except (ValueError, LookupError, TypeError) as error:
            raise LLMError("unexpected response shape") from error
        if not isinstance(text, str):
            raise LLMError("unexpected response shape")
        return text
