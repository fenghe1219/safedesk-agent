from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from typing import Any

import httpx

from app.core.config import settings

LLM_TRANSPORT: httpx.AsyncBaseTransport | None = None


class LLMError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LLMOutputError(LLMError):
    def __init__(self, message: str) -> None:
        super().__init__("LLM_INVALID_OUTPUT", message)


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    base_url: str
    api_key: str
    model: str
    timeout_seconds: float
    temperature: float
    max_output_tokens: int
    input_cost_per_million: float
    output_cost_per_million: float

    @property
    def enabled(self) -> bool:
        return self.provider == "openai_compatible" and bool(self.base_url and self.model)

    def with_model(self, model: str | None, provider: str | None = None) -> LLMConfig:
        return replace(
            self,
            provider=provider or self.provider,
            model=model or self.model,
        )


@dataclass(frozen=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    estimated: bool = True


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str
    usage: LLMUsage
    latency_ms: int


def get_llm_config(
    *, model: str | None = None, provider: str | None = None
) -> LLMConfig:
    config = LLMConfig(
        provider=settings.llm_provider.strip().lower(),
        base_url=settings.llm_base_url.strip(),
        api_key=settings.llm_api_key.strip(),
        model=settings.llm_model.strip(),
        timeout_seconds=settings.llm_timeout_seconds,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        input_cost_per_million=settings.llm_input_cost_per_million,
        output_cost_per_million=settings.llm_output_cost_per_million,
    )
    return config.with_model(model, provider)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 2)


async def chat_completion(
    config: LLMConfig,
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
) -> LLMResponse:
    if not config.enabled:
        raise LLMError("LLM_DISABLED", "未配置可用的 OpenAI-compatible 模型")
    selected_model = model or config.model
    started = time.perf_counter()
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    payload = {
        "model": selected_model,
        "messages": messages,
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
    }
    try:
        async with httpx.AsyncClient(
            timeout=config.timeout_seconds,
            transport=LLM_TRANSPORT,
        ) as client:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
    except httpx.TimeoutException as exc:
        raise LLMError("LLM_TIMEOUT", "模型调用超时") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        raise LLMError(
            "LLM_HTTP_ERROR", f"模型服务返回 {exc.response.status_code}: {detail}"
        ) from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise LLMError("LLM_UNAVAILABLE", f"模型服务不可用: {exc}") from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMOutputError("模型响应缺少 choices[0].message.content") from exc
    if not isinstance(content, str) or not content.strip():
        raise LLMOutputError("模型返回了空内容")

    raw_usage = body.get("usage") or {}
    input_tokens = int(raw_usage.get("prompt_tokens") or 0)
    output_tokens = int(raw_usage.get("completion_tokens") or 0)
    estimated = not bool(raw_usage)
    if estimated:
        input_tokens = sum(estimate_tokens(message.get("content", "")) for message in messages)
        output_tokens = estimate_tokens(content)
    total_tokens = int(raw_usage.get("total_tokens") or input_tokens + output_tokens)
    cost = round(
        input_tokens * config.input_cost_per_million / 1_000_000
        + output_tokens * config.output_cost_per_million / 1_000_000,
        8,
    )
    return LLMResponse(
        content=content.strip(),
        model=str(body.get("model") or selected_model),
        usage=LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost,
            estimated=estimated,
        ),
        latency_ms=max(1, round((time.perf_counter() - started) * 1000)),
    )


def parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise LLMOutputError("模型输出不是 JSON 对象")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"模型 JSON 解析失败: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise LLMOutputError("模型 JSON 顶层必须是对象")
    return value
