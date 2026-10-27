import json

import httpx
import pytest

from app.core.config import Settings
from app.core.ports import LLMError
from app.infra.llm.factory import build_llm_client
from app.infra.llm.fake import FakeLLMClient
from app.infra.llm.openai_compatible import TIMEOUT_SECONDS, OpenAICompatibleClient


def client_answering(handler) -> OpenAICompatibleClient:
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenAICompatibleClient("https://llm.example/v1/", "modelo-x", "chave-123", http=http)


def chat_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}]})


def test_T_AI_OPENAI_01_posts_chat_completion_and_returns_the_text():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return chat_reply("Pense no primeiro passo.")

    reply = client_answering(handler).complete("sistema", "usuário", max_tokens=120)

    assert reply == "Pense no primeiro passo."
    request = seen[0]
    assert str(request.url) == "https://llm.example/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer chave-123"
    assert json.loads(request.content) == {
        "model": "modelo-x",
        "messages": [
            {"role": "system", "content": "sistema"},
            {"role": "user", "content": "usuário"},
        ],
        "max_tokens": 120,
        "temperature": 0.3,
    }


def test_T_AI_OPENAI_01c_sends_reasoning_effort_only_when_configured():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return chat_reply("ok")

    http = httpx.Client(transport=httpx.MockTransport(handler))
    with_effort = OpenAICompatibleClient("https://llm.example/v1", "m", "k", "low", http=http)
    with_effort.complete("s", "u", max_tokens=10)
    client_answering(handler).complete("s", "u", max_tokens=10)

    assert bodies[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in bodies[1]


def test_T_AI_OPENAI_01b_default_http_client_times_out_after_30_seconds():
    client = OpenAICompatibleClient("https://llm.example/v1", "m", "k")

    assert TIMEOUT_SECONDS == 30
    assert client.http.timeout == httpx.Timeout(30)


def test_T_AI_OPENAI_02_http_error_becomes_llm_error():
    client = client_answering(lambda request: httpx.Response(500, text="erro interno"))

    with pytest.raises(LLMError):
        client.complete("s", "u", max_tokens=10)


def test_T_AI_OPENAI_02b_timeout_becomes_llm_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(LLMError):
        client_answering(handler).complete("s", "u", max_tokens=10)


@pytest.mark.parametrize(
    "body",
    [{}, {"choices": []}, {"choices": [{"message": {"content": None}}]}, ["not", "a", "dict"]],
)
def test_T_AI_OPENAI_03_unexpected_response_shape_becomes_llm_error(body):
    client = client_answering(lambda request: httpx.Response(200, json=body))

    with pytest.raises(LLMError):
        client.complete("s", "u", max_tokens=10)


def test_T_AI_OPENAI_03b_non_json_response_becomes_llm_error():
    client = client_answering(lambda request: httpx.Response(200, text="<html>"))

    with pytest.raises(LLMError):
        client.complete("s", "u", max_tokens=10)


def settings(**values) -> Settings:
    return Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://x", JWT_SECRET="s", **values)


def test_T_AI_FACTORY_01_provider_is_chosen_by_settings(tmp_path):
    log = tmp_path / "llm.jsonl"

    fake = build_llm_client(settings(LLM_PROVIDER="fake", FAKE_LLM_LOG=str(log)))
    real = build_llm_client(
        settings(
            LLM_PROVIDER="openai_compatible",
            LLM_BASE_URL="https://llm.example/v1",
            LLM_MODEL="m",
            LLM_API_KEY="k",
        )
    )

    assert isinstance(fake, FakeLLMClient)
    assert fake.log_path == str(log)
    assert isinstance(real, OpenAICompatibleClient)
    assert real.url == "https://llm.example/v1/chat/completions"
    assert build_llm_client(settings(FAKE_LLM_LOG="")).log_path is None
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        build_llm_client(settings(LLM_PROVIDER="outro"))


def test_T_AI_FAKE_00_scripted_replies_in_order_and_prompts_recorded():
    fake = FakeLLMClient(replies=["primeira", LLMError("falhou"), "terceira"])

    assert fake.complete("s1", "u1", max_tokens=5) == "primeira"
    with pytest.raises(LLMError):
        fake.complete("s2", "u2", max_tokens=5)
    assert fake.complete("s3", "u3", max_tokens=5) == "terceira"
    with pytest.raises(LLMError):
        fake.complete("s4", "u4", max_tokens=5)  # queue empty: behaves like a provider failure

    assert [(p.system, p.user) for p in fake.prompts] == [
        ("s1", "u1"),
        ("s2", "u2"),
        ("s3", "u3"),
        ("s4", "u4"),
    ]
