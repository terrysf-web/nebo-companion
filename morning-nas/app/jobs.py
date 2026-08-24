"""The two jobs the service runs: the daily brief and the monthly planner.

Both are also what the CLI and the web buttons call, so there is exactly one
code path per job.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from pathlib import Path

from . import google_api, nextcloud, render, store
from .brief import Brief, build
from .briefpdf import build_brief_pdf
from .config import Config
from .planner import build_planner, next_month

log = logging.getLogger(__name__)


def run_brief(cfg: Config, when: date | None = None, upload: bool = True) -> Brief:
    brief = build(cfg, when)
    store.save(cfg, brief)
    html = render.write_html(cfg, brief, store.html_path(cfg, brief.day))
    pdf = build_brief_pdf(cfg, brief, store.pdf_path(cfg, brief.day))

    if upload:
        for path in (html, pdf):
            nextcloud.try_upload(cfg, path, subdir="briefs")

    for problem in brief.problems:
        log.warning("brief problem: %s", problem)
    return brief


def run_planner(
    cfg: Config, month: date | None = None, upload: bool = True
) -> Path:
    month = month or next_month(date.today())
    events = _month_events(cfg, month)
    path = build_planner(cfg, month, events)
    if upload:
        nextcloud.try_upload(cfg, path, subdir="planners")
    return path


def _month_events(cfg: Config, month: date) -> dict[date, list[str]]:
    """Print known calendar entries into the month grid — best effort only."""
    start = datetime.combine(month, time.min, tzinfo=cfg.tz)
    span = (next_month(month) - month).days + 7
    out: dict[date, list[str]] = {}
    try:
        accounts = google_api.collect_events_only(cfg, start, span)
    except Exception as exc:  # noqa: BLE001 - a blank planner still beats no planner
        log.warning("could not read calendars for the planner: %s", exc)
        return out

    for event in accounts:
        when = event.start.date() if hasattr(event.start, "date") else event.start
        if not isinstance(when, date):
            continue
        label = event.summary if event.all_day else f"{event.when.split('–')[0]} {event.summary}"
        out.setdefault(when, []).append(label)
    for day in out:
        out[day] = sorted(out[day])[:3]
    return out
