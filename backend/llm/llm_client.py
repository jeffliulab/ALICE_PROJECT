"""LLM API client — Ollama (or any OpenAI-compatible endpoint)."""

from __future__ import annotations

import logging
import time
from typing import Optional

from openai import OpenAI

from backend.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

log = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from thinking model output."""
    import re
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        log.info("LLM client: model=%s base_url=%s", LLM_MODEL, LLM_BASE_URL)
    return _client


def ChatGPT_single_request(prompt: str) -> str:
    """Simple single-prompt request (used by plan's revise_identity etc)."""
    return chat_completion([{"role": "user", "content": prompt}])


def chat_completion(
    messages: list[dict[str, str]],
    model: str = LLM_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    retries: int = 2,
) -> str:
    client = _get_client()
    effective_tokens = max(max_tokens, 512)
    last_err = None
    for attempt in range(retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=effective_tokens,
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("LLM returned None content")
            # Strip thinking model tags (Qwen3 wraps output in <think>...</think>)
            content = _strip_think_tags(content)
            return content.strip()
        except Exception as e:
            last_err = e
            log.warning("LLM attempt %d failed: %s", attempt + 1, e)
            if attempt < retries:
                time.sleep(1 * (attempt + 1))
    raise last_err


def generate_prompt(prompt_input: list[str], prompt_template_path: str) -> str:
    """Fill a prompt template file with input values.

    Template uses !<INPUT {n}>! placeholders.
    """
    from pathlib import Path
    template_file = Path(__file__).resolve().parent.parent / prompt_template_path
    if not template_file.exists():
        # Fallback: return inputs as concatenated string
        return "\n".join(prompt_input)
    template = template_file.read_text(encoding="utf-8")
    for i, val in enumerate(prompt_input):
        template = template.replace(f"!<INPUT {i}>!", str(val))
    return template


def safe_generate_response(prompt, gpt_param, retries, fail_safe,
                            validate_fn, cleanup_fn):
    """Generate LLM response with validation, cleanup, and fail-safe.

    Matches the original paper's safe_generate_response pattern.
    """
    for attempt in range(retries):
        try:
            response = chat_completion(
                [{"role": "user", "content": prompt}],
                temperature=gpt_param.get("temperature", 0.7),
                max_tokens=gpt_param.get("max_tokens", 1024),
            )
            if validate_fn(response, prompt):
                return cleanup_fn(response, prompt)
        except Exception as e:
            log.warning("safe_generate attempt %d: %s", attempt + 1, e)
            time.sleep(1)
    return fail_safe
