from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import random
import time
from typing import Callable, Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_CHAT_COMPLETIONS_PATH = "/chat/completions"
NIM_RATE_LIMIT_PER_MINUTE = 40

NimTaskType = Literal["chat", "coding", "reasoning", "finance", "translation", "classification"]

NIM_MODEL_CHAINS: dict[str, tuple[str, ...]] = {
    "chat": (
        "deepseek-ai/deepseek-v4-flash",
        "nvidia/nemotron-3-super-120b-a12b",
        "meta/llama-3.3-70b-instruct",
    ),
    "coding": (
        "deepseek-ai/deepseek-v4-flash",
        "deepseek-ai/deepseek-v4-pro",
        "nvidia/nemotron-3-super-120b-a12b",
    ),
    "reasoning": (
        "nvidia/nemotron-3-ultra-550b-a55b",
        "qwen/qwen3.5-397b-a17b",
        "nvidia/nemotron-3-super-120b-a12b",
    ),
    "finance": (
        "writer/palmyra-fin-70b-32k",
        "nvidia/nemotron-3-super-120b-a12b",
        "meta/llama-3.3-70b-instruct",
    ),
    "translation": (
        "z-ai/glm-5.2",
        "meta/llama-3.3-70b-instruct",
        "nvidia/nemotron-3-super-120b-a12b",
    ),
    "classification": (
        "meta/llama-3.3-70b-instruct",
        "nvidia/nemotron-nano-3-30b-a3b",
        "nvidia/nemotron-3-super-120b-a12b",
    ),
}


@dataclass(slots=True)
class NimUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(slots=True)
class NimResponse:
    content: str
    model: str
    task_type: str
    usage: NimUsage = field(default_factory=NimUsage)
    raw: dict[str, object] = field(default_factory=dict)

    def json(self) -> dict[str, object]:
        return json.loads(self.content)


class NimClientError(RuntimeError):
    pass


class NimConfigurationError(NimClientError):
    pass


class NimTransientError(NimClientError):
    pass


class NimRateLimiter:
    def __init__(
        self,
        *,
        requests_per_minute: int = NIM_RATE_LIMIT_PER_MINUTE,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be at least 1")
        self.interval_seconds = 60.0 / requests_per_minute
        self.clock = clock
        self.sleep = sleep
        self._next_allowed_at = 0.0

    def wait(self) -> None:
        now = self.clock()
        delay = self._next_allowed_at - now
        if delay > 0:
            self.sleep(delay)
            now = self.clock()
        self._next_allowed_at = max(now, self._next_allowed_at) + self.interval_seconds


class NvidiaNimClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 30,
        requests_per_minute: int = NIM_RATE_LIMIT_PER_MINUTE,
        max_retries_per_model: int = 2,
        backoff_base_seconds: float = 0.75,
        rate_limiter: NimRateLimiter | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("NVIDIA_API_KEY")
        self.base_url = (base_url or os.getenv("NVIDIA_NIM_BASE_URL") or NIM_BASE_URL).rstrip("/")
        self.timeout_seconds = max(1, timeout_seconds)
        self.max_retries_per_model = max(0, max_retries_per_model)
        self.backoff_base_seconds = max(0.05, backoff_base_seconds)
        self.rate_limiter = rate_limiter or NimRateLimiter(requests_per_minute=requests_per_minute)

    def ask(
        self,
        prompt: str,
        task_type: NimTaskType | str = "chat",
        *,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 800,
        json_mode: bool = False,
        model_chain: tuple[str, ...] | None = None,
    ) -> NimResponse:
        if not self.api_key:
            raise NimConfigurationError("NVIDIA_API_KEY is not set")
        normalized_task = str(task_type or "chat").strip().lower()
        models = model_chain or NIM_MODEL_CHAINS.get(normalized_task) or NIM_MODEL_CHAINS["chat"]
        if not models:
            raise NimConfigurationError("No NVIDIA NIM models configured")

        last_error: Exception | None = None
        for model in models:
            for attempt in range(self.max_retries_per_model + 1):
                try:
                    return self._chat_completion(
                        model=model,
                        task_type=normalized_task,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        json_mode=json_mode,
                    )
                except NimTransientError as exc:
                    last_error = exc
                    if attempt < self.max_retries_per_model:
                        self._sleep_before_retry(attempt)
                        continue
                    break
                except NimClientError:
                    raise
        raise NimTransientError(f"NVIDIA NIM request failed for all fallback models: {last_error}") from last_error

    def try_ask(
        self,
        prompt: str,
        task_type: NimTaskType | str = "chat",
        **kwargs: object,
    ) -> NimResponse | None:
        try:
            return self.ask(prompt, task_type, **kwargs)
        except NimClientError:
            return None

    def _chat_completion(
        self,
        *,
        model: str,
        task_type: str,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> NimResponse:
        payload: dict[str, object] = {
            "model": model,
            "messages": self._messages(prompt, system_prompt),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        request = Request(
            f"{self.base_url}{NIM_CHAT_COMPLETIONS_PATH}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        self.rate_limiter.wait()
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code in {429, 503}:
                raise NimTransientError(f"NVIDIA NIM transient HTTP {exc.code}") from exc
            raise NimClientError(f"NVIDIA NIM HTTP {exc.code}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise NimTransientError(f"NVIDIA NIM transport failure: {exc.__class__.__name__}") from exc

        if not isinstance(response_payload, dict):
            raise NimClientError("NVIDIA NIM returned an invalid response payload")
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise NimClientError("NVIDIA NIM response did not include choices")
        first_choice = choices[0] if isinstance(choices[0], dict) else {}
        message = first_choice.get("message") if isinstance(first_choice, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise NimClientError("NVIDIA NIM response did not include message content")
        usage_payload = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
        return NimResponse(
            content=content,
            model=str(response_payload.get("model") or model),
            task_type=task_type,
            usage=NimUsage(
                prompt_tokens=self._optional_int(usage_payload.get("prompt_tokens")),
                completion_tokens=self._optional_int(usage_payload.get("completion_tokens")),
                total_tokens=self._optional_int(usage_payload.get("total_tokens")),
            ),
            raw=response_payload,
        )

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self.backoff_base_seconds * (2 ** attempt)
        delay += random.uniform(0, min(0.25, delay / 3))
        time.sleep(delay)

    @staticmethod
    def _messages(prompt: str, system_prompt: str | None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    @staticmethod
    def _optional_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None


def ask(prompt: str, task_type: NimTaskType | str = "chat", **kwargs: object) -> NimResponse:
    return NvidiaNimClient().ask(prompt, task_type, **kwargs)


def try_ask(prompt: str, task_type: NimTaskType | str = "chat", **kwargs: object) -> NimResponse | None:
    return NvidiaNimClient().try_ask(prompt, task_type, **kwargs)
