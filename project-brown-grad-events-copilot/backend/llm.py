"""Provider-agnostic LLM wrapper.

Goal: one function, `complete_json(...)`, that returns a JSON string regardless of
whether you're on OpenAI or Anthropic. Kept deliberately small and transparent
(no heavy framework) so it's easy to read and reason about — and easy to swap the
provider via the LLM_PROVIDER env var.

Every call records token counts, latency, and estimated cost via backend.telemetry
using the `label` param to tag call type (e.g. "enrich", "extract", "blurb").
"""

from __future__ import annotations

import os
import time

from dotenv import load_dotenv

from . import telemetry

load_dotenv()

DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")


def complete_json(
    system: str,
    user: str,
    *,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.0,
    label: str = "other",
) -> str:
    """Send a chat request and return the model's raw text response (expected JSON).

    temperature defaults to 0.0 — for extraction we want determinism, not creativity.
    label tags this call in telemetry (e.g. "enrich", "extract", "blurb", "enrich-repair").
    """
    provider = (provider or DEFAULT_PROVIDER).lower()
    model = model or DEFAULT_MODEL

    if provider == "openai":
        return _openai_json(system, user, model, temperature, label)
    if provider == "anthropic":
        return _anthropic_json(system, user, model, temperature, label)
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (expected 'openai' or 'anthropic')")


def _openai_json(
    system: str, user: str, model: str, temperature: float, label: str
) -> str:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    latency_ms = (time.perf_counter() - t0) * 1000
    if resp.usage:
        telemetry.record_call(
            label=label,
            model=model,
            tokens_in=resp.usage.prompt_tokens,
            tokens_out=resp.usage.completion_tokens,
            latency_ms=latency_ms,
        )
    return resp.choices[0].message.content or "{}"


def _anthropic_json(
    system: str, user: str, model: str, temperature: float, label: str
) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    # Anthropic has no json_object mode; we instruct via system + prefill "{".
    t0 = time.perf_counter()
    resp = client.messages.create(
        model=model,
        temperature=temperature,
        max_tokens=4096,
        system=system + "\n\nRespond with a single valid JSON object and nothing else.",
        messages=[
            {"role": "user", "content": user},
            {"role": "assistant", "content": "{"},
        ],
    )
    latency_ms = (time.perf_counter() - t0) * 1000
    telemetry.record_call(
        label=label,
        model=model,
        tokens_in=resp.usage.input_tokens,
        tokens_out=resp.usage.output_tokens,
        latency_ms=latency_ms,
    )
    text = "".join(block.text for block in resp.content if block.type == "text")
    return "{" + text  # re-attach the prefill brace
