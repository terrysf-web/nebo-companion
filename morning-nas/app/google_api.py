"""Read calendar and mail for each configured Google account.

Tokens live in tokens/<account>.json in the format google-auth writes, so an
expired access token refreshes itself. One broken account never takes the
whole brief down — it comes back as an error string on that account.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import Config

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/tasks.readonly",
]


@dataclass
class Event:
    account: str
    label: str
    summary: str
    start: datetime | date
    end: datetime | date | None
    location: str = ""
    all_day: bool = False

    @property
    def when(self) -> str:
        if self.all_day or not isinstance(self.start, datetime):
            return "all day"
        text = self.start.strftime("%H:%M")
        if isinstance(self.end, datetime):
            text += f"–{self.end.strftime('%H:%M')}"
        return text

    def line(self) -> str:
        bits = [self.when, self.summary]
        if self.location:
            bits.append(f"@ {self.location}")
        return "  ".join(bits)


@dataclass
class Mail:
    account: str
    label: str
    sender: str
    subject: str
    snippet: str


@dataclass
class Task:
    account: str
    label: str
    title: str
    due: date | None


@dataclass
class AccountData:
    account: str
    label: str
    events: list[Event] = field(default_factory=list)
    mails: list[Mail] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def load_credentials(path: Path) -> Credentials:
    creds = Credentials.from_authorized_user_file(str(path), SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _parse(value: dict) -> tuple[datetime | date, bool]:
    if "dateTime" in value:
        return datetime.fromisoformat(value["dateTime"]), False
    return date.fromisoformat(value["date"]), True


def fetch_events(
    creds: Credentials, account: str, label: str, start: datetime, days: int
) -> list[Event]:
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    end = start + timedelta(days=days)
    calendars = service.calendarList().list(maxResults=50).execute().get("items", [])
    out: list[Event] = []
    for cal in calendars:
        if cal.get("selected") is False:
            continue
        items = (
            service.events()
            .list(
                calendarId=cal["id"],
                timeMin=start.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=50,
            )
            .execute()
            .get("items", [])
        )
        for item in items:
            if item.get("status") == "cancelled":
                continue
            when, all_day = _parse(item.get("start", {}))
            until, _ = _parse(item.get("end", {})) if item.get("end") else (None, False)
            out.append(
                Event(
                    account=account,
                    label=label,
                    summary=item.get("summary", "(no title)"),
                    start=when,
                    end=until,
                    location=(item.get("location") or "").split(",")[0][:40],
                    all_day=all_day,
                )
            )
    out.sort(key=lambda e: (e.start.isoformat() if hasattr(e.start, "isoformat") else ""))
    return out


def fetch_mail(creds: Credentials, account: str, label: str, limit: int) -> list[Mail]:
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    listed = (
        service.users()
        .messages()
        .list(userId="me", q="is:unread newer_than:2d -category:promotions",
              maxResults=limit)
        .execute()
        .get("messages", [])
    )
    out: list[Mail] = []
    for ref in listed:
        msg = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=ref["id"],
                format="metadata",
                metadataHeaders=["From", "Subject"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        sender = headers.get("From", "")
        if "<" in sender:
            sender = sender.split("<")[0].strip().strip('"') or sender
        out.append(
            Mail(
                account=account,
                label=label,
                sender=sender[:40],
                subject=headers.get("Subject", "(no subject)")[:120],
                snippet=(msg.get("snippet") or "")[:200],
            )
        )
    return out


def fetch_tasks(creds: Credentials, account: str, label: str) -> list[Task]:
    service = build("tasks", "v1", credentials=creds, cache_discovery=False)
    out: list[Task] = []
    for tasklist in service.tasklists().list(maxResults=10).execute().get("items", []):
        items = (
            service.tasks()
            .list(tasklist=tasklist["id"], showCompleted=False, maxResults=30)
            .execute()
            .get("items", [])
        )
        for item in items:
            due = None
            if item.get("due"):
                try:
                    due = datetime.fromisoformat(item["due"].replace("Z", "+00:00")).date()
                except ValueError:
                    due = None
            out.append(
                Task(account=account, label=label, title=item.get("title", "")[:120], due=due)
            )
    return out


def collect(cfg: Config, start: datetime) -> list[AccountData]:
    """Everything the brief needs, per account, best-effort."""
    results: list[AccountData] = []
    for account in cfg.accounts:
        label = cfg.label(account)
        data = AccountData(account=account, label=label)
        path = cfg.token_path(account)

        if not path.exists():
            data.errors.append(
                f"tokens/{account}.json not found — run "
                f"`python3 app/auth_setup.py {account}` and copy the file in, "
                f"or drop {account} from ACCOUNTS in docker-compose.yml"
            )
            results.append(data)
            continue

        try:
            creds = load_credentials(path)
        except Exception as exc:  # noqa: BLE001 - any auth failure, keep going
            data.errors.append(f"could not load tokens/{account}.json: {exc}")
            results.append(data)
            continue

        for name, fn in (
            ("calendar", lambda: fetch_events(creds, account, label, start, cfg.lookahead_days)),
            ("mail", lambda: fetch_mail(creds, account, label, cfg.mail_limit)),
            ("tasks", lambda: fetch_tasks(creds, account, label)),
        ):
            try:
                value = fn()
            except HttpError as exc:
                data.errors.append(f"{name}: {exc.status_code} {exc.reason}")
                continue
            except Exception as exc:  # noqa: BLE001
                data.errors.append(f"{name}: {exc}")
                continue
            if name == "calendar":
                data.events = value
            elif name == "mail":
                data.mails = value
            else:
                data.tasks = value

        results.append(data)
    return results


def collect_events_only(cfg: Config, start: datetime, days: int) -> list[Event]:
    """Just the calendar, across every account — used to seed the planner."""
    out: list[Event] = []
    for account in cfg.accounts:
        path = cfg.token_path(account)
        if not path.exists():
            continue
        try:
            creds = load_credentials(path)
            out.extend(fetch_events(creds, account, cfg.label(account), start, days))
        except Exception as exc:  # noqa: BLE001 - skip the account, keep the rest
            log.warning("planner: skipping %s (%s)", account, exc)
    return out
