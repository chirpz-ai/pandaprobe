"""Unit tests for the LLM engine and provider registry (no API calls)."""

import json
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import BaseModel

from app.infrastructure.llm.providers import (
    PROVIDERS,
    check_provider_credentials,
    get_available_providers,
    resolve_model_string,
    provider_key_from_model,
)


def test_providers_registry_has_expected_keys() -> None:
    assert "openai" in PROVIDERS
    assert "anthropic" in PROVIDERS
    assert "google_genai" in PROVIDERS
    assert "vertex_ai" in PROVIDERS


def test_resolve_model_string_adds_prefix() -> None:
    assert resolve_model_string("gpt-4o-mini") == "openai/gpt-4o-mini"
    assert resolve_model_string("claude-3-5-sonnet-20241022") == "anthropic/claude-3-5-sonnet-20241022"
    assert resolve_model_string("gemini-2.5-flash") == "gemini/gemini-2.5-flash"


def test_resolve_model_string_keeps_existing_prefix() -> None:
    assert resolve_model_string("openai/gpt-4o") == "openai/gpt-4o"
    assert resolve_model_string("vertex_ai/gemini-pro") == "vertex_ai/gemini-pro"


def test_provider_key_from_model() -> None:
    assert provider_key_from_model("openai/gpt-4o") == "openai"
    assert provider_key_from_model("anthropic/claude-3-haiku") == "anthropic"
    assert provider_key_from_model("gemini/gemini-pro") == "google_genai"
    assert provider_key_from_model("vertex_ai/gemini-pro") == "vertex_ai"


def test_check_credentials_missing() -> None:
    ok, msg = check_provider_credentials("openai")
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_check_credentials_unknown_provider() -> None:
    ok, msg = check_provider_credentials("unknown_provider")
    assert ok is False
    assert "Unknown provider" in msg


def test_get_available_providers_returns_list() -> None:
    providers = get_available_providers()
    assert isinstance(providers, list)
    assert len(providers) == len(PROVIDERS)
    for p in providers:
        assert "key" in p
        assert "available" in p


@pytest.mark.parametrize(
    "model",
    ["vertex_ai/gemini-3.5-flash-lite", "vertex_ai/gemini-3.8-flash", "gemini/gemini-3.5-flash-lite"],
)
async def test_new_gemini_judges_use_litellm_structured_output(model, monkeypatch) -> None:
    """Exercise the installed SDK's real routing and JSON transformation, without API calls."""
    from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler
    from litellm.llms.vertex_ai.vertex_llm_base import VertexBase

    from app.infrastructure.llm.engine import LLMEngine

    class Verdict(BaseModel):
        score: float

    monkeypatch.setattr(LLMEngine, "_sync_credentials", lambda self: None)
    # Background logging is outside this routing/serialization contract and must
    # not outlive pytest's per-test event loops.
    monkeypatch.setattr(
        GLOBAL_LOGGING_WORKER, "ensure_initialized_and_enqueue", lambda async_coroutine: async_coroutine.close()
    )
    monkeypatch.setenv("VERTEXAI_PROJECT", "test-project")
    monkeypatch.setenv("VERTEXAI_LOCATION", "global")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        VertexBase, "_ensure_access_token_async", AsyncMock(return_value=("test-token", "test-project"))
    )
    requests = []

    async def post(self, url, **kwargs):
        body = kwargs["json"]
        requests.append((url, body))
        return httpx.Response(
            200,
            request=httpx.Request("POST", url),
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": '{"score": 0.9}'}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5, "totalTokenCount": 15},
            },
        )

    monkeypatch.setattr(AsyncHTTPHandler, "post", post)
    verdict = await LLMEngine()._call(model, "Evaluate this answer.", Verdict, 1.0)
    assert verdict.score == 0.9
    assert len(requests) == 1  # No unstructured fallback needed.
    url, body = requests[0]
    assert f"/models/{model.split('/', 1)[1]}:generateContent" in url
    if model.startswith("vertex_ai/"):
        assert "aiplatform.googleapis.com/" in url
        assert "/locations/global/" in url
    assert body["generationConfig"]["response_mime_type"] == "application/json"
    assert "score" in body["generationConfig"]["response_json_schema"]["properties"]


def test_default_judge_model_is_gemini_flash_lite() -> None:
    from app.registry.settings import Settings

    assert Settings.model_fields["EVAL_LLM_MODEL"].default == "vertex_ai/gemini-3.5-flash-lite"


@pytest.mark.parametrize("model", ["gpt-6-luna", "claude-haiku-4-5"])
async def test_optional_judges_use_supported_litellm_requests(model, monkeypatch) -> None:
    """Verify picker IDs, provider routing and real SDK request serialization."""
    import litellm
    from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER

    from app.infrastructure.llm.engine import LLMEngine

    class Verdict(BaseModel):
        score: float

    monkeypatch.setattr(LLMEngine, "_sync_credentials", lambda self: None)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        GLOBAL_LOGGING_WORKER, "ensure_initialized_and_enqueue", lambda async_coroutine: async_coroutine.close()
    )
    resolved = resolve_model_string(model)
    assert litellm.get_llm_provider(resolved)[:2] == (model, provider_key_from_model(model))
    assert model in litellm.model_cost
    requests = []

    async def send(self, request, **kwargs):
        body = json.loads(request.content)
        requests.append((request, body))
        if model.startswith("gpt-"):
            payload = {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": '{"score": 0.9}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            }
        else:
            content = [{"type": "text", "text": '{"score": 0.9}'}]
            if body.get("tools"):
                content = [
                    {"type": "tool_use", "id": "toolu_test", "name": body["tools"][0]["name"], "input": {"score": 0.9}}
                ]
            payload = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": content,
                "stop_reason": "tool_use" if body.get("tools") else "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
        return httpx.Response(200, request=request, json=payload)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    verdict = await LLMEngine()._call(resolved, "Evaluate this answer.", Verdict, 1.0)
    assert verdict.score == 0.9
    assert len(requests) == 1
    request, body = requests[0]
    assert body["model"] == model
    if model.startswith("gpt-"):
        assert request.url.host == "api.openai.com"
        assert "score" in body["response_format"]["json_schema"]["schema"]["properties"]
    else:
        assert request.url.host == "api.anthropic.com"
        assert "score" in body["output_format"]["schema"]["properties"]
