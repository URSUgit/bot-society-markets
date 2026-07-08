from __future__ import annotations

import json
from urllib.error import HTTPError

import pytest

from api.app import nvidia_nim
from api.app.nvidia_nim import NimConfigurationError, NimRateLimiter, NvidiaNimClient


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_nim_client_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    client = NvidiaNimClient(api_key="", max_retries_per_model=0)

    with pytest.raises(NimConfigurationError):
        client.ask("hello")


def test_nim_client_routes_task_and_json_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout: int):
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse(
            {
                "model": "writer/palmyra-fin-70b-32k",
                "choices": [{"message": {"content": '{"sentiment": 0.4}'}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 7, "total_tokens": 19},
            }
        )

    monkeypatch.setattr(nvidia_nim, "urlopen", fake_urlopen)
    client = NvidiaNimClient(api_key="test-key", timeout_seconds=9, max_retries_per_model=0)

    response = client.ask(
        "Classify this market headline.",
        task_type="finance",
        system_prompt="Return JSON only.",
        json_mode=True,
    )

    payload = captured["payload"]
    assert captured["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert captured["timeout"] == 9
    assert payload["model"] == "writer/palmyra-fin-70b-32k"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["messages"][0] == {"role": "system", "content": "Return JSON only."}
    assert response.json() == {"sentiment": 0.4}
    assert response.usage.total_tokens == 19


def test_nim_client_falls_back_after_503(monkeypatch: pytest.MonkeyPatch) -> None:
    requested_models: list[str] = []

    def fake_urlopen(request, timeout: int):
        payload = json.loads(request.data.decode("utf-8"))
        requested_models.append(payload["model"])
        if len(requested_models) == 1:
            raise HTTPError(request.full_url, 503, "workers busy", hdrs=None, fp=None)
        return FakeResponse(
            {
                "model": payload["model"],
                "choices": [{"message": {"content": "fallback ok"}}],
            }
        )

    monkeypatch.setattr(nvidia_nim, "urlopen", fake_urlopen)
    monkeypatch.setattr(nvidia_nim.time, "sleep", lambda seconds: None)
    client = NvidiaNimClient(api_key="test-key", max_retries_per_model=0)

    response = client.ask("hello", task_type="chat")

    assert requested_models[:2] == [
        "deepseek-ai/deepseek-v4-flash",
        "nvidia/nemotron-3-super-120b-a12b",
    ]
    assert response.content == "fallback ok"
    assert response.model == "nvidia/nemotron-3-super-120b-a12b"


def test_nim_try_ask_degrades_gracefully_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    client = NvidiaNimClient(api_key="", max_retries_per_model=0)

    assert client.try_ask("headline", task_type="classification") is None


def test_nim_rate_limiter_stays_under_per_minute_limit() -> None:
    now = 0.0
    sleeps: list[float] = []

    def clock() -> float:
        return now

    def fake_sleep(seconds: float) -> None:
        nonlocal now
        sleeps.append(seconds)
        now += seconds

    limiter = NimRateLimiter(requests_per_minute=40, clock=clock, sleep=fake_sleep)

    limiter.wait()
    limiter.wait()
    limiter.wait()

    assert sleeps == [1.5, 1.5]
