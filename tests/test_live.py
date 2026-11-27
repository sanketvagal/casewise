"""The live provider clients: timeouts and which errors are retried."""

import types as pytypes

import pytest

# The live providers are an optional extra that CI does not install.
genai = pytest.importorskip("google.genai")
groq = pytest.importorskip("groq")
httpx = pytest.importorskip("httpx")
httpx2 = pytest.importorskip("httpx2")

from casewise import live  # noqa: E402


def test_the_groq_client_has_a_request_timeout(monkeypatch):
    made = {}

    class FakeGroq:
        def __init__(self, **kwargs):
            made.update(kwargs)

    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(groq, "Groq", FakeGroq)

    live._groq_chat()

    # With no timeout, a stalled request can hang a run (as one Gemini call once did).
    assert made.get("timeout") == live.GROQ_TIMEOUT_S


@pytest.mark.parametrize(
    "error", [httpx.ReadTimeout("slow"), httpx2.ReadTimeout("slow")], ids=["httpx", "httpx2"]
)
def test_gemini_retries_a_transport_error_from_either_http_library(monkeypatch, error):
    calls = []

    class FakeModels:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise error
            return pytypes.SimpleNamespace(text="ok", usage_metadata=None)

    class FakeClient:
        def __init__(self, **kwargs):
            self.models = FakeModels()

    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(genai, "Client", FakeClient)
    monkeypatch.setattr(live.time, "sleep", lambda seconds: None)

    result = live._gemini_chat()("gemini-model", [{"role": "user", "content": "hi"}])

    assert result.text == "ok"
    assert len(calls) == 2
