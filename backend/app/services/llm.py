"""LLM service — live OpenAI-compatible when a key exists, deterministic
evidence-grounded templates otherwise. `llm_mode` is always surfaced so the UI
can show "synthetic reasoning" honestly.
"""

from __future__ import annotations

import logging

from app.config import get_settings

log = logging.getLogger("earthpulse.llm")


def llm_mode() -> str:
    s = get_settings()
    return "live" if s.llm_enabled else "fallback"


async def complete(system: str, user: str, temperature: float = 0.3) -> tuple[str, str]:
    """Returns (text, mode). Never raises when offline."""
    s = get_settings()
    if not s.llm_enabled:
        return "", "fallback"
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{s.llm_base_url}/chat/completions",
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
                json={
                    "model": s.llm_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"], "live"
    except Exception:
        log.warning("LLM call failed — falling back to templates", exc_info=True)
        return "", "fallback"
