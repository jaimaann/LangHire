"""Unit tests for backend/core/llm_factory.py.

Exercises every provider branch of create_llm (asserting returned object
type / key attributes), the unknown-provider error, the _PatchedSession
wrapper, and test_connection's success / timeout / decompression branches.

No real network or AWS calls are made: constructors here are inert, and
test_connection's ``llm.ainvoke`` is always mocked. boto3.Session is patched
for the bedrock branch.
"""
import asyncio
import zlib

import pytest

from core import llm_factory
from browser_use.llm import (
    ChatOpenAI,
    ChatAnthropic,
    ChatAWSBedrock,
    ChatGoogle,
    ChatOllama,
)
from browser_use.llm.exceptions import ModelProviderError


# ── _PatchedSession ──────────────────────────────────────────────────────────

def test_patched_session_injects_config_default():
    """_PatchedSession.client injects the config when none is supplied."""
    calls = {}

    class FakeSession:
        region_name = "us-west-2"

        def client(self, service_name, **kwargs):
            calls["service"] = service_name
            calls["config"] = kwargs.get("config")
            return "client-obj"

    sentinel = object()
    ps = llm_factory._PatchedSession(FakeSession(), sentinel)
    out = ps.client("bedrock-runtime")
    assert out == "client-obj"
    assert calls["service"] == "bedrock-runtime"
    assert calls["config"] is sentinel


def test_patched_session_respects_explicit_config():
    """An explicit config passed to client() is not overridden."""
    class FakeSession:
        def client(self, service_name, **kwargs):
            return kwargs["config"]

    ps = llm_factory._PatchedSession(FakeSession(), object())
    explicit = object()
    assert ps.client("svc", config=explicit) is explicit


def test_patched_session_delegates_attributes():
    """Unknown attributes proxy to the wrapped session."""
    class FakeSession:
        region_name = "eu-central-1"

    ps = llm_factory._PatchedSession(FakeSession(), object())
    assert ps.region_name == "eu-central-1"


# ── create_llm: provider branches ────────────────────────────────────────────

def test_create_llm_openai():
    """openai provider yields a ChatOpenAI with the configured model."""
    llm = llm_factory.create_llm(
        {"provider": "openai", "openai": {"api_key": " sk-x ", "model": "gpt-4o-mini"}}
    )
    assert isinstance(llm, ChatOpenAI)
    assert llm.model == "gpt-4o-mini"
    # openai default base_url should be unset (None).
    assert getattr(llm, "base_url", None) is None


def test_create_llm_openai_defaults_when_missing():
    """A bare openai settings dict falls back to provider defaults."""
    llm = llm_factory.create_llm({"provider": "openai"})
    assert isinstance(llm, ChatOpenAI)
    assert llm.model == "gpt-4o"


def test_create_llm_default_provider_is_openai():
    """No provider key defaults to the openai branch."""
    llm = llm_factory.create_llm({})
    assert isinstance(llm, ChatOpenAI)
    assert llm.model == "gpt-4o"


def test_create_llm_anthropic():
    """anthropic provider yields a ChatAnthropic with the configured model."""
    llm = llm_factory.create_llm(
        {"provider": "anthropic", "anthropic": {"api_key": "k", "model": "claude-3"}}
    )
    assert isinstance(llm, ChatAnthropic)
    assert llm.model == "claude-3"


def test_create_llm_anthropic_default_model():
    """anthropic with empty sub-config uses the default model."""
    llm = llm_factory.create_llm({"provider": "anthropic"})
    assert isinstance(llm, ChatAnthropic)
    assert llm.model == "claude-sonnet-4-5"


def test_create_llm_ollama():
    """ollama yields ChatOllama with native host, model, and options."""
    llm = llm_factory.create_llm(
        {"provider": "ollama", "ollama": {"base_url": "http://myhost:11434/", "model": "gemma3:4b"}}
    )
    assert isinstance(llm, ChatOllama)
    assert llm.model == "gemma3:4b"
    # Trailing slash stripped, and NOT the /v1 OpenAI shim.
    assert llm.host == "http://myhost:11434"
    assert "/v1" not in llm.host
    assert llm.ollama_options["num_ctx"] == 32768
    assert llm.ollama_options["num_predict"] == 4096
    assert llm.ollama_options["temperature"] == 0.0


def test_create_llm_ollama_defaults():
    """ollama with no model falls back to llama3.1 and the default host."""
    llm = llm_factory.create_llm({"provider": "ollama", "ollama": {"model": ""}})
    assert isinstance(llm, ChatOllama)
    assert llm.model == "llama3.1"
    assert llm.host == "http://localhost:11434"


def test_create_llm_gemini():
    """gemini provider yields a ChatGoogle with the configured model."""
    llm = llm_factory.create_llm(
        {"provider": "gemini", "gemini": {"api_key": " AIza-x ", "model": "gemini-2.5-flash"}}
    )
    assert isinstance(llm, ChatGoogle)
    assert llm.model == "gemini-2.5-flash"
    # api_key is stripped of surrounding whitespace.
    assert llm.api_key == "AIza-x"


def test_create_llm_gemini_default_model():
    """gemini with empty sub-config uses the default model."""
    llm = llm_factory.create_llm({"provider": "gemini"})
    assert isinstance(llm, ChatGoogle)
    assert llm.model == "gemini-2.5-pro"


def test_create_llm_openrouter():
    """openrouter yields ChatOpenAI pointed at the OpenRouter base_url."""
    llm = llm_factory.create_llm(
        {"provider": "openrouter", "openrouter": {"api_key": " key ", "model": "x/y"}}
    )
    assert isinstance(llm, ChatOpenAI)
    assert llm.model == "x/y"
    assert llm.base_url == "https://openrouter.ai/api/v1"


def test_create_llm_openrouter_default_model():
    """openrouter default model is openai/gpt-4o."""
    llm = llm_factory.create_llm({"provider": "openrouter"})
    assert isinstance(llm, ChatOpenAI)
    assert llm.model == "openai/gpt-4o"
    assert llm.base_url == "https://openrouter.ai/api/v1"


def test_create_llm_openai_compatible():
    """openai_compatible yields ChatOpenAI with a custom base_url."""
    llm = llm_factory.create_llm(
        {
            "provider": "openai_compatible",
            "openai_compatible": {"model": "local", "api_key": "tok", "base_url": "http://h/v1"},
        }
    )
    assert isinstance(llm, ChatOpenAI)
    assert llm.model == "local"
    assert llm.base_url == "http://h/v1"


def test_create_llm_openai_compatible_defaults():
    """openai_compatible with empty key falls back to the 'not-needed' token."""
    llm = llm_factory.create_llm(
        {"provider": "openai_compatible", "openai_compatible": {"base_url": "http://h/v1"}}
    )
    assert isinstance(llm, ChatOpenAI)
    assert llm.model == "default"


def test_create_llm_unknown_provider_raises():
    """An unrecognised provider raises a descriptive ValueError."""
    with pytest.raises(ValueError, match="Unknown LLM provider: mystery"):
        llm_factory.create_llm({"provider": "mystery"})


# ── create_llm: bedrock branch (boto3 mocked) ────────────────────────────────

@pytest.fixture
def fake_boto3(monkeypatch):
    """Patch boto3.Session inside llm_factory so no real AWS is touched."""
    captured = {}

    class FakeSession:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

        def client(self, *a, **k):  # pragma: no cover - not called by tests
            return object()

    import boto3
    monkeypatch.setattr(boto3, "Session", FakeSession)
    return captured


def test_create_llm_bedrock_profile_mode(fake_boto3):
    """bedrock in profile mode builds a profile-based session and wraps it."""
    llm = llm_factory.create_llm(
        {"provider": "bedrock", "bedrock": {"region": "eu-west-1", "model": "us.anthropic.x", "profile_name": "prod"}}
    )
    assert isinstance(llm, ChatAWSBedrock)
    assert llm.model == "us.anthropic.x"
    assert isinstance(llm.session, llm_factory._PatchedSession)
    assert fake_boto3["kwargs"] == {"profile_name": "prod", "region_name": "eu-west-1"}


def test_create_llm_bedrock_profile_default_name(fake_boto3):
    """bedrock without auth_mode defaults to the 'default' profile."""
    llm_factory.create_llm({"provider": "bedrock", "bedrock": {}})
    assert fake_boto3["kwargs"]["profile_name"] == "default"
    assert fake_boto3["kwargs"]["region_name"] == "us-west-2"


def test_create_llm_bedrock_keys_mode(fake_boto3):
    """bedrock with auth_mode=keys + creds builds a key-based session."""
    llm = llm_factory.create_llm(
        {
            "provider": "bedrock",
            "bedrock": {
                "auth_mode": "keys",
                "access_key": "AKIA",
                "secret_key": "SECRET",
                "region": "ap-south-1",
                "model": "m",
            },
        }
    )
    assert isinstance(llm, ChatAWSBedrock)
    assert fake_boto3["kwargs"] == {
        "aws_access_key_id": "AKIA",
        "aws_secret_access_key": "SECRET",
        "region_name": "ap-south-1",
    }


def test_create_llm_bedrock_keys_mode_missing_creds_uses_profile(fake_boto3):
    """auth_mode=keys but missing secret falls through to profile auth."""
    llm_factory.create_llm(
        {"provider": "bedrock", "bedrock": {"auth_mode": "keys", "access_key": "AKIA"}}
    )
    # No secret_key -> profile branch.
    assert "profile_name" in fake_boto3["kwargs"]


# ── test_connection ──────────────────────────────────────────────────────────

class _FakeResponse:
    def __init__(self, completion):
        self.completion = completion


class _FakeLLM:
    def __init__(self, behavior):
        self._behavior = behavior

    async def ainvoke(self, messages):
        return await self._behavior(messages)


async def test_test_connection_success():
    """A successful ainvoke returns the formatted completion text."""
    async def ok(messages):
        return _FakeResponse("hello")

    out = await llm_factory.test_connection(_FakeLLM(ok))
    assert out == "Model responded: hello"


async def test_test_connection_timeout(monkeypatch):
    """A TimeoutError surfaces as a friendly RuntimeError."""
    async def slow(messages):
        raise asyncio.TimeoutError

    with pytest.raises(RuntimeError, match="timed out after 60 seconds"):
        await llm_factory.test_connection(_FakeLLM(slow))


async def test_test_connection_decompression_error():
    """A zlib.error is translated into the proxy/VPN guidance RuntimeError."""
    async def bad(messages):
        raise zlib.error("Error -3 decompressing")

    with pytest.raises(RuntimeError, match="Decompression error"):
        await llm_factory.test_connection(_FakeLLM(bad))


async def test_test_connection_wait_for_timeout(monkeypatch):
    """A real asyncio.wait_for timeout (slow model) is handled."""
    async def hang(messages):
        await asyncio.sleep(5)
        return _FakeResponse("late")

    # Make wait_for time out immediately instead of waiting 60s.
    async def fast_wait_for(awaitable, timeout):
        # Close the un-awaited coroutine to avoid warnings, then raise.
        if asyncio.iscoroutine(awaitable):
            awaitable.close()
        raise asyncio.TimeoutError

    # test_connection imports asyncio locally; patch the module attribute.
    monkeypatch.setattr(asyncio, "wait_for", fast_wait_for)
    with pytest.raises(RuntimeError, match="timed out"):
        await llm_factory.test_connection(_FakeLLM(hang))


# ── test_connection: friendly error branches (#48) ───────────────────────────

async def test_test_connection_invalid_key_by_status_code():
    """A 401 ModelProviderError maps to the invalid-API-key message."""
    async def bad(messages):
        raise ModelProviderError("Something went wrong", status_code=401)

    with pytest.raises(RuntimeError, match="Invalid API key"):
        await llm_factory.test_connection(_FakeLLM(bad))


async def test_test_connection_invalid_key_by_message():
    """An auth-related message (no helpful code) still maps to invalid-key."""
    async def bad(messages):
        raise ModelProviderError("Incorrect API_KEY provided", status_code=400)

    with pytest.raises(RuntimeError, match="Invalid API key"):
        await llm_factory.test_connection(_FakeLLM(bad))


async def test_test_connection_rate_limit_by_status_code():
    """A 429 maps to the rate-limit / quota message."""
    async def bad(messages):
        raise ModelProviderError("slow down", status_code=429)

    with pytest.raises(RuntimeError, match="Rate limit or quota exceeded"):
        await llm_factory.test_connection(_FakeLLM(bad))


async def test_test_connection_quota_by_message():
    """A quota message maps to the rate-limit / quota guidance."""
    async def bad(messages):
        raise ModelProviderError("You exceeded your current quota", status_code=403)

    # 403 is auth-first, so message-only quota detection is exercised via a
    # non-auth status code.
    async def quota(messages):
        raise ModelProviderError("Resource has been exhausted (quota)", status_code=500)

    with pytest.raises(RuntimeError, match="Rate limit or quota exceeded"):
        await llm_factory.test_connection(_FakeLLM(quota))


async def test_test_connection_network_error():
    """A connection error maps to the reach-the-API guidance."""
    async def bad(messages):
        raise ConnectionError("Failed to establish a new connection")

    with pytest.raises(RuntimeError, match="Cannot reach the API"):
        await llm_factory.test_connection(_FakeLLM(bad))


async def test_test_connection_generic_error_passthrough():
    """An unclassifiable error surfaces its raw message."""
    async def bad(messages):
        raise ValueError("totally unexpected boom")

    with pytest.raises(RuntimeError, match="totally unexpected boom"):
        await llm_factory.test_connection(_FakeLLM(bad))
