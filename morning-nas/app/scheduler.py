"""Container entrypoint: the schedule plus the web UI, in one process.

    brief    every day at BRIEF_HOUR:BRIEF_MINUTE
    planner  on the 1st of each month at PLANNER_HOUR:PLANNER_MINUTE

Runs the brief once at startup if today's is missing, so a NAS that was off
overnight still has a brief waiting when you pick up the tablet.
"""

from __future__ import annotations

import logging
from datetime import date

import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import jobs, store
from .config import load_config
from .web import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("morning")


def _safely(name: str, fn, *args) -> None:
    try:
        fn(*args)
        log.info("%s finished", name)
    except Exception:  # noqa: BLE001 - one bad run must not stop the schedule
        log.exception("%s failed", name)


def main() -> None:
    cfg = load_config()
    cfg.brief_dir.mkdir(parents=True, exist_ok=True)
    cfg.planner_dir.mkdir(parents=True, exist_ok=True)

    scheduler = BackgroundScheduler(timezone=cfg.tz)
    scheduler.add_job(
        lambda: _safely("brief", jobs.run_brief, cfg),
        CronTrigger(hour=cfg.brief_hour, minute=cfg.brief_minute, timezone=cfg.tz),
        id="brief",
        misfire_grace_time=3600,
        coalesce=True,
    )
    if cfg.planner_enabled:
        scheduler.add_job(
            lambda: _safely("planner", jobs.run_planner, cfg),
            CronTrigger(
                day=1, hour=cfg.planner_hour, minute=cfg.planner_minute, timezone=cfg.tz
            ),
            id="planner",
            misfire_grace_time=6 * 3600,
            coalesce=True,
        )
    scheduler.start()

    log.info("brief at %02d:%02d daily (%s)", cfg.brief_hour, cfg.brief_minute, cfg.tz_name)
    if cfg.planner_enabled:
        log.info(
            "planner on the 1st at %02d:%02d", cfg.planner_hour, cfg.planner_minute
        )
    log.info("accounts: %s", ", ".join(cfg.accounts) or "(none)")

    if store.load(cfg, date.today()) is None:
        log.info("no brief for today yet — building one now")
        _safely("catch-up brief", jobs.run_brief, cfg)

    uvicorn.run(
        create_app(cfg),
        host="0.0.0.0",
        port=cfg.port,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
