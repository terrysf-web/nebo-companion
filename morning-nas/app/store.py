"""Briefs on disk, one JSON + one HTML + one PDF per day."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from .brief import Brief
from .config import Config

log = logging.getLogger(__name__)


def json_path(cfg: Config, day: date | str) -> Path:
    day = day if isinstance(day, str) else day.isoformat()
    return cfg.brief_dir / f"{day}.json"


def html_path(cfg: Config, day: date | str) -> Path:
    day = day if isinstance(day, str) else day.isoformat()
    return cfg.brief_dir / f"{day}.html"


def pdf_path(cfg: Config, day: date | str) -> Path:
    day = day if isinstance(day, str) else day.isoformat()
    return cfg.brief_dir / f"{day}.pdf"


def save(cfg: Config, brief: Brief) -> Path:
    path = json_path(cfg, brief.day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(brief.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return path


def load(cfg: Config, day: date | str) -> Brief | None:
    path = json_path(cfg, day)
    if not path.exists():
        return None
    try:
        return Brief.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError) as exc:
        log.warning("could not read %s: %s", path, exc)
        return None


def recent(cfg: Config, limit: int = 30) -> list[str]:
    """Newest first, as YYYY-MM-DD strings."""
    if not cfg.brief_dir.exists():
        return []
    days = sorted((p.stem for p in cfg.brief_dir.glob("*.json")), reverse=True)
    return days[:limit]


def planners(cfg: Config) -> list[Path]:
    if not cfg.planner_dir.exists():
        return []
    return sorted(cfg.planner_dir.glob("*.pdf"), reverse=True)
