"""Provider-agnostic LLM wrapper.

Goal: one function, `complete_json(...)`, that returns a JSON string regardless of
whether you're on OpenAI or Anthropic. Kept deliberately small and transparent
(no heavy framework) so it's easy to read and reason about — and easy to swap the
provider via the LLM_PROVIDER env var.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

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
) -> str:
    """Send a chat request and return the model's raw text response (expected JSON).

    temperature defaults to 0.0 — for extraction we want determinism, not creativity.
    """
    provider = (provider or DEFAULT_PROVIDER).lower()
    model = model or DEFAULT_MODEL

    if provider == "openai":
        return _openai_json(system, user, model, temperature)
    if provider == "anthropic":
        return _anthropic_json(system, user, model, temperature)
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (expected 'openai' or 'anthropic')")


def _openai_json(system: str, user: str, model: str, temperature: float) -> str:
    from openai import OpenAI

    client = OpenAI()  # reads OPENAI_API_KEY
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content or "{}"


def _anthropic_json(system: str, user: str, model: str, temperature: float) -> str:
    import anthropic

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    # Anthropic has no json_object mode; we instruct via system + prefill "{".
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
    text = "".join(block.text for block in resp.content if block.type == "text")
    return "{" + text  # re-attach the prefill brace
