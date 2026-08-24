"""Every environment variable, read in one place."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Also read .env when running outside the container (e.g. auth_setup.py on a Mac).
load_dotenv(BASE_DIR / ".env", override=False)


def _int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    try:
        return int(raw)
    except ValueError:
        return default


def _flag(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Config:
    tz: ZoneInfo
    tz_name: str

    tokens_dir: Path
    data_dir: Path
    brief_dir: Path
    planner_dir: Path

    accounts: tuple[str, ...]

    anthropic_api_key: str
    anthropic_model: str

    owm_api_key: str
    lat: float
    lon: float
    place: str

    nc_url: str
    nc_user: str
    nc_pass: str
    nc_dir: str
    nc_upload: bool

    google_client_id: str
    google_client_secret: str

    brief_hour: int
    brief_minute: int
    planner_hour: int
    planner_minute: int
    lookahead_days: int
    mail_limit: int
    port: int

    lang: str
    brief_pdf: bool
    planner_enabled: bool
    planner_page: str
    planner_start_hour: int
    planner_end_hour: int
    planner_week_start: str
    planner_months: int
    planner_meeting_pages: int
    planner_habits: tuple[str, ...]

    def label(self, account: str) -> str:
        env = os.getenv(f"ACCOUNT_LABEL_{account.upper()}")
        if env:
            return env
        return {"personal": "Personal", "work": "Work"}.get(account, account)

    def token_path(self, account: str) -> Path:
        return self.tokens_dir / f"{account}.json"


def load_config() -> Config:
    tz_name = os.getenv("TZ") or "Asia/Seoul"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:  # noqa: BLE001 - a bad TZ must not take the service down
        tz_name, tz = "Asia/Seoul", ZoneInfo("Asia/Seoul")

    data_dir = Path(os.getenv("DATA_DIR") or (BASE_DIR / "data"))
    accounts = tuple(
        part.strip()
        for part in (os.getenv("ACCOUNTS") or "personal").split(",")
        if part.strip()
    )

    return Config(
        tz=tz,
        tz_name=tz_name,
        tokens_dir=Path(os.getenv("TOKENS_DIR") or (BASE_DIR / "tokens")),
        data_dir=data_dir,
        brief_dir=data_dir / "briefs",
        planner_dir=data_dir / "planners",
        accounts=accounts,
        anthropic_api_key=(os.getenv("ANTHROPIC_API_KEY") or "").strip(),
        anthropic_model=(os.getenv("ANTHROPIC_MODEL") or "claude-opus-5").strip(),
        owm_api_key=(os.getenv("OWM_API_KEY") or "").strip(),
        lat=float(os.getenv("WEATHER_LAT") or 37.5665),
        lon=float(os.getenv("WEATHER_LON") or 126.9780),
        place=(os.getenv("WEATHER_PLACE") or "서울").strip(),
        nc_url=(os.getenv("NC_URL") or "").strip().rstrip("/"),
        nc_user=(os.getenv("NC_USER") or "").strip(),
        nc_pass=os.getenv("NC_PASS") or "",
        nc_dir=(os.getenv("NC_DIR") or "Morning").strip().strip("/"),
        nc_upload=_flag("NC_UPLOAD", True),
        google_client_id=(os.getenv("GOOGLE_CLIENT_ID") or "").strip(),
        google_client_secret=(os.getenv("GOOGLE_CLIENT_SECRET") or "").strip(),
        brief_hour=_int("BRIEF_HOUR", 6),
        brief_minute=_int("BRIEF_MINUTE", 0),
        planner_hour=_int("PLANNER_HOUR", 5),
        planner_minute=_int("PLANNER_MINUTE", 30),
        lookahead_days=_int("LOOKAHEAD_DAYS", 3),
        mail_limit=_int("MAIL_LIMIT", 12),
        port=_int("PORT", 9000),
        lang=(os.getenv("LANG_OUT") or "en").strip().lower(),
        brief_pdf=_flag("BRIEF_PDF", True),
        planner_enabled=_flag("PLANNER_ENABLED", False),
        planner_page=(os.getenv("PLANNER_PAGE") or "tablet").strip().lower(),
        planner_start_hour=_int("PLANNER_START_HOUR", 6),
        planner_end_hour=_int("PLANNER_END_HOUR", 22),
        planner_week_start=(os.getenv("PLANNER_WEEK_START") or "mon").strip().lower(),
        planner_months=_int("PLANNER_MONTHS", 1),
        planner_meeting_pages=_int("PLANNER_MEETING_PAGES", 12),
        planner_habits=tuple(
            part.strip()
            for part in (
                os.getenv("PLANNER_HABITS") or "Move,Read,Deep work,Sleep 7h"
            ).split(",")
            if part.strip()
        ),
    )
