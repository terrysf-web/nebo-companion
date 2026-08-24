"""Turn the raw calendar/mail/weather dump into a short morning brief.

Claude does the summarising. If there is no API key, or the call fails, the
brief still gets built from the raw data — the service never goes dark just
because the model is unreachable.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .config import Config

log = logging.getLogger(__name__)

MAX_TOKENS = 8000
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM = """You write one person's morning brief. They read it on a tablet at
06:00 and then plan their day by hand on the page underneath it.

Be specific and short. Name real meetings, people and deadlines from the data.
Never invent anything that is not in the input. No greetings, no filler, no
motivational lines, no restating the whole calendar — they can see the calendar.

Return ONLY a JSON object, no prose around it, with these keys:
  "headline"   - one sentence, under 90 characters, what today actually is
  "priorities" - 2 or 3 strings, the things that must happen today
  "timeline"   - up to 6 objects {"time": "09:30", "what": "..."}, in order;
                 use "" for time when something has no fixed hour
  "watch"      - 0 to 3 strings: conflicts, prep needed, mail that needs a reply,
                 anything about to slip
  "closing"    - one short sentence, plain and practical

Write in %(language)s."""

LANGUAGES = {"en": "English", "ko": "Korean"}


@dataclass
class Summary:
    headline: str = ""
    priorities: list[str] = field(default_factory=list)
    timeline: list[dict[str, str]] = field(default_factory=list)
    watch: list[str] = field(default_factory=list)
    closing: str = ""
    source: str = "claude"
    error: str = ""

    def is_empty(self) -> bool:
        return not (self.headline or self.priorities or self.timeline)


def _coerce(payload: dict[str, Any]) -> Summary:
    def strings(key: str, limit: int) -> list[str]:
        raw = payload.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        return [str(item).strip() for item in raw if str(item).strip()][:limit]

    timeline: list[dict[str, str]] = []
    for row in (payload.get("timeline") or [])[:6]:
        if isinstance(row, dict):
            timeline.append(
                {"time": str(row.get("time", "")).strip(), "what": str(row.get("what", "")).strip()}
            )
        elif isinstance(row, str):
            timeline.append({"time": "", "what": row.strip()})

    return Summary(
        headline=str(payload.get("headline", "")).strip(),
        priorities=strings("priorities", 3),
        timeline=[row for row in timeline if row["what"]],
        watch=strings("watch", 3),
        closing=str(payload.get("closing", "")).strip(),
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    """Models occasionally wrap JSON in prose or a code fence. Dig it out."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _call(client: anthropic.Anthropic, cfg: Config, prompt: str) -> str:
    system = SYSTEM % {"language": LANGUAGES.get(cfg.lang, "English")}
    kwargs: dict[str, Any] = {
        "model": cfg.anthropic_model,
        "max_tokens": MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "adaptive"},
    }
    try:
        # Server-side fallbacks: if a safety classifier declines the request,
        # another model answers instead of the brief coming back empty.
        response = client.beta.messages.create(
            betas=[FALLBACK_BETA], fallbacks="default", **kwargs
        )
    except anthropic.BadRequestError:
        log.info("fallbacks beta unavailable, retrying without it")
        response = client.messages.create(**kwargs)

    if getattr(response, "stop_reason", None) == "refusal":
        detail = getattr(response, "stop_details", None)
        raise RuntimeError(f"model declined to answer ({getattr(detail, 'category', 'unknown')})")

    return "".join(block.text for block in response.content if block.type == "text")


def summarize(cfg: Config, prompt: str) -> Summary:
    if not cfg.anthropic_api_key:
        return Summary(source="raw", error="ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=cfg.anthropic_api_key, max_retries=3)
    try:
        text = _call(client, cfg, prompt)
    except anthropic.APIStatusError as exc:
        log.warning("Claude call failed: %s", exc)
        return Summary(source="raw", error=f"{exc.status_code} {exc.message}")
    except anthropic.APIConnectionError as exc:
        log.warning("Claude unreachable: %s", exc)
        return Summary(source="raw", error=f"could not reach the API: {exc}")
    except Exception as exc:  # noqa: BLE001 - never let the brief fail entirely
        log.warning("Claude call failed: %s", exc)
        return Summary(source="raw", error=str(exc))

    payload = _extract_json(text)
    if payload is None:
        log.warning("could not parse the model's JSON, keeping the raw text")
        return Summary(headline=text.strip()[:200], source="claude-text")

    summary = _coerce(payload)
    if summary.is_empty():
        return Summary(source="raw", error="model returned an empty brief")
    return summary
