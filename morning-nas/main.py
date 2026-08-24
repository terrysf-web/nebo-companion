"""Command line entry point.

    python main.py                    build today's brief (HTML + PDF), upload
    python main.py --planner-only     build next month's planner PDF
    python main.py --date 2026-09-04  build the brief for a specific day
    python main.py --no-upload        skip Nextcloud
    python main.py --check            check the setup and the Nextcloud upload
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from app import jobs, nextcloud, store
from app.config import load_config
from app.planner import next_month

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("morning")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="main.py", description="Morning brief and planner")
    parser.add_argument("--planner-only", action="store_true",
                        help="only build the planner PDF")
    parser.add_argument("--brief-only", action="store_true",
                        help="only build the brief (the default)")
    parser.add_argument("--date", metavar="YYYY-MM-DD",
                        help="which day to build (brief) or which month (planner)")
    parser.add_argument("--no-upload", action="store_true",
                        help="do not upload to Nextcloud")
    parser.add_argument("--check", action="store_true",
                        help="check configuration and the Nextcloud connection")
    return parser.parse_args(argv)


def check(cfg) -> int:
    print("Configuration")
    print(f"· timezone   {cfg.tz_name}")
    print(f"· accounts   {', '.join(cfg.accounts) or '(none)'}")
    for account in cfg.accounts:
        path = cfg.token_path(account)
        print(f"    {'✓' if path.exists() else '✗'} {path}")
    print(f"· model      {cfg.anthropic_model}"
          f"{'' if cfg.anthropic_api_key else '   (no ANTHROPIC_API_KEY — brief will be unsummarised)'}")
    print(f"· weather    {'on' if cfg.owm_api_key else 'off (no OWM_API_KEY)'}")
    print(f"· data       {cfg.data_dir}")
    print(f"· planner    {cfg.planner_page} page, {cfg.planner_months} month(s), "
          f"{cfg.planner_meeting_pages} meeting pages")
    print()
    print("Nextcloud")
    if not cfg.nc_upload:
        print("· NC_UPLOAD=0 — uploads are off")
        return 0
    for line in nextcloud.check(cfg):
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_config()
    upload = not args.no_upload

    if args.check:
        return check(cfg)

    when = date.fromisoformat(args.date) if args.date else None

    if args.planner_only:
        path = jobs.run_planner(cfg, (when or next_month(date.today())).replace(day=1), upload)
        print(path)
        return 0

    brief = jobs.run_brief(cfg, when, upload)
    print(store.html_path(cfg, brief.day))
    print(store.pdf_path(cfg, brief.day))
    for problem in brief.problems:
        print(f"! {problem}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
