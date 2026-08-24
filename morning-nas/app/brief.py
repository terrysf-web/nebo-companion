"""Assemble the morning brief: gather -> summarise -> a plain data object."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any

from . import google_api, weather
from .config import Config
from .summarize import Summary, summarize

log = logging.getLogger(__name__)


@dataclass
class Brief:
    day: str
    generated_at: str
    weather: str = ""
    headline: str = ""
    priorities: list[str] = field(default_factory=list)
    timeline: list[dict[str, str]] = field(default_factory=list)
    watch: list[str] = field(default_factory=list)
    closing: str = ""
    today: list[str] = field(default_factory=list)
    upcoming: list[str] = field(default_factory=list)
    mail: list[dict[str, str]] = field(default_factory=list)
    tasks: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    source: str = "claude"

    @property
    def date(self) -> date:
        return date.fromisoformat(self.day)

    def title(self) -> str:
        return self.date.strftime("%A, %B %-d")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Brief":
        known = {k: v for k, v in payload.items() if k in cls.__dataclass_fields__}
        return cls(**known)


def _prompt(
    cfg: Config,
    when: date,
    accounts: list[google_api.AccountData],
    sky: weather.Weather | None,
) -> str:
    lines: list[str] = [
        f"Today is {when.strftime('%A %d %B %Y')}.",
        f"Timezone {cfg.tz_name}.",
    ]
    if sky:
        lines.append(f"Weather: {sky.line()}")

    for data in accounts:
        lines.append(f"\n== {data.label} ==")
        today = [e for e in data.events if _event_date(e) == when]
        later = [e for e in data.events if _event_date(e) and _event_date(e) > when]

        lines.append("Today's calendar:")
        if today:
            lines.extend(f"  - {e.line()}" for e in today)
        else:
            lines.append("  (nothing)")

        if later:
            lines.append("Next few days:")
            for e in later[:8]:
                lines.append(f"  - {_event_date(e)} {e.line()}")

        if data.tasks:
            lines.append("Open tasks:")
            for t in data.tasks[:10]:
                due = f" (due {t.due})" if t.due else ""
                lines.append(f"  - {t.title}{due}")

        if data.mails:
            lines.append("Unread mail:")
            for m in data.mails:
                lines.append(f"  - {m.sender}: {m.subject}")

    return "\n".join(lines)


def _event_date(event: google_api.Event) -> date | None:
    start = event.start
    if isinstance(start, datetime):
        return start.date()
    if isinstance(start, date):
        return start
    return None


def build(cfg: Config, when: date | None = None) -> Brief:
    now = datetime.now(cfg.tz)
    when = when or now.date()
    start = datetime.combine(when, time.min, tzinfo=cfg.tz)

    accounts = google_api.collect(cfg, start)
    sky = weather.fetch(cfg)
    prompt = _prompt(cfg, when, accounts, sky)
    summary: Summary = summarize(cfg, prompt)

    brief = Brief(
        day=when.isoformat(),
        generated_at=now.isoformat(timespec="seconds"),
        weather=sky.line() if sky else "",
        headline=summary.headline,
        priorities=summary.priorities,
        timeline=summary.timeline,
        watch=summary.watch,
        closing=summary.closing,
        source=summary.source,
    )
    if summary.error:
        brief.problems.append(f"summary: {summary.error}")

    for data in accounts:
        brief.problems.extend(f"{data.label}: {msg}" for msg in data.errors)
        for event in data.events:
            day = _event_date(event)
            if day == when:
                brief.today.append(f"{data.label} · {event.line()}")
            elif day and when < day <= when + timedelta(days=cfg.lookahead_days):
                brief.upcoming.append(f"{day.strftime('%a %d')} · {event.line()}")
        for mail in data.mails:
            brief.mail.append(
                {"account": data.label, "from": mail.sender, "subject": mail.subject}
            )
        for task in data.tasks:
            due = f" (due {task.due})" if task.due else ""
            brief.tasks.append(f"{data.label} · {task.title}{due}")

    brief.today.sort()
    brief.upcoming.sort()

    # No model, no problem: fall back to something readable built from the data.
    if not brief.headline:
        count = len(brief.today)
        brief.headline = (
            f"{count} event{'s' if count != 1 else ''} today"
            + (f", {len(brief.mail)} unread" if brief.mail else "")
        )
    if not brief.timeline:
        brief.timeline = [
            {"time": line.split("·")[-1].strip()[:5], "what": line.split("·")[-1].strip()[5:].strip()}
            for line in brief.today[:6]
        ]

    log.info("brief for %s built (%s)", brief.day, brief.source)
    return brief
