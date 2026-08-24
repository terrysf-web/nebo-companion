# Morning

A brief every morning on a machine that is always on, shaped to be written on
by hand in Nebo and read back by the Nebo Companion app in this repository.

**06:00 daily** — reads your Google calendars, unread mail and tasks across
every account, adds the weather, has Claude turn it into a short brief, and
writes it three ways:

| File | For |
|---|---|
| `.txt` | pasting into a **Nebo page** — this is the one that closes the loop |
| `.html` | reading on any screen, with a **Copy for Nebo** button |
| `.pdf` | writing on directly, if you prefer a PDF app (`BRIEF_PDF=0` to skip) |

All of them land in Nextcloud and stay downloadable from `http://<ip>:9000`
even when the upload fails.

## The Nebo loop

1. Morning: tap **오늘 브리핑 열기** in Nebo Companion — it reads today's
   `<date>.txt` straight out of the folder you picked once. Pick the folder the
   briefs actually sync into: `<NC_DIR>/briefs` (default `Morning/briefs`) in
   the Nextcloud app's local copy — the app looks in that folder only, not in
   sub-folders. (Or open `http://<ip>:9000` and tap **Copy for Nebo**.)
2. Paste it into a Nebo page. The brief sits above a line of dashes; below it
   are hour guides and empty space.
3. Write the day's plan **below the line**, by hand, in Nebo.
4. Convert to text and share the page to **Nebo Companion**. It reads back only
   what is below the divider, so the brief itself never turns into duplicate
   tasks, and the hour guides are ignored. Events go to Google Calendar,
   to-dos to the app, reminders to the device.

The file name is the other half of the contract: the app looks for
`<today>.txt`, which is what `store.text_path` writes.

The divider is the contract between the two halves: `DIVIDER` in
`app/nebotext.py` and `dividerLine` in `CaptureParser.kt`. Change one, change
the other.

## What you need

- this folder (or `morning-nas.tar.gz`)
- `.env` — API key, Nextcloud address/account/password
- `tokens/personal.json`, `tokens/work.json` — copy from the old NAS. If you
  don't have them, mint new ones on the Mac with
  `python3 app/auth_setup.py <name>`
- Docker, on a machine that stays on 24 hours a day

## Install

```bash
tar xzf morning-nas.tar.gz
cd morning-nas
cp .env.example .env      # fill in the values
mkdir -p tokens           # put the token json files here
docker compose up -d --build
docker compose run --rm --entrypoint python morning main.py
```

That last line builds today's brief straight away, so you can see it work
without waiting for 06:00.

## Check

- `ACCOUNTS` in `docker-compose.yml` must match the token file names
  (`personal.json` → `personal`)
- `NC_URL` must be the real IP, not `localhost` — inside a container
  `localhost` is the container itself

If anything is off:

```bash
docker compose run --rm --entrypoint python morning main.py --check
```

It prints each setting, whether each token file exists, and — for Nextcloud —
whether login, WebDAV access and **write access** actually work, naming the
setting to fix for each failure.

## Access

- `http://<machine-ip>:9000`
- from outside → `tailscale serve --bg --set-path / http://<machine-ip>:9000`

The page lists every brief and planner, with a **Run brief now** and a
**Build planner** button. Each brief links to its Nebo text, and the brief page
itself has a **Copy for Nebo** button.

## Planner PDF (optional)

Nebo is a poor host for a hyperlinked planner — internal links only respond to
a finger, not the stylus — so the monthly planner is **off by default**
(`PLANNER_ENABLED=0`). It is still there for a PDF-first app such as Xodo,
Noteshelf or Flexcil, where the tab navigation works as intended:

```bash
# next month only
docker compose run --rm --entrypoint python morning main.py --planner-only

# today's month through the end of December, in one file
docker compose run --rm --entrypoint python morning main.py \
  --planner-only --date 2026-08-01 --through 2026-12

# or a fixed number of months
docker compose run --rm --entrypoint python morning main.py \
  --planner-only --months 12
```

A multi-month file gets tabs for exactly the months it contains — a span that
crosses a new year is labelled with the year on each tab.

The planner works the way the popular digital planners do:

| Page | What's on it |
|---|---|
| Cover | the span, and a tap target for every month in the file |
| Year | a mini calendar per month, every date links to its day page |
| Month | grid with your real calendar entries printed in, goals, notes |
| Week | seven columns, weekly focus, habit tracker |
| Day | hourly schedule, Top 3, to-dos, notes, link to the meeting log |
| Notes | numbered index → one meeting-note page each (discussion, decisions, action items) |

Navigation is on every page: **Year / Month / Week / Day / Notes** top right,
and one month tab per month down the right edge when the file covers more than
one month.

## Daily brief PDF

The 06:00 brief is also a page you write on: printed brief down the left,
an empty hour-by-hour plan in the middle, Top 3 and notes on the right, plus a
blank second page. Open it in Nebo (or any notes app) and plan the day by hand
next to the brief instead of copying it somewhere else.

## Commands

```bash
python main.py                    # today's brief: HTML + PDF, upload
python main.py --planner-only     # next month's planner
python main.py --planner-only --months 12
python main.py --planner-only --date 2026-08-01 --through 2026-12
python main.py --date 2026-09-04  # a specific day
python main.py --no-upload        # skip Nextcloud
python main.py --check            # check the setup
```

Prefix each with `docker compose run --rm --entrypoint python morning` to run
it in the container.

## Settings

Everything lives in `.env` (see `.env.example`). The ones that matter most:

| Variable | Meaning |
|---|---|
| `ANTHROPIC_API_KEY` | without it the brief is still built, just not summarised |
| `OWM_API_KEY` | OpenWeatherMap; empty means no weather section |
| `NC_URL` / `NC_USER` / `NC_PASS` | Nextcloud; `NC_UPLOAD=0` turns uploading off |
| `LANG_OUT` | `en` or `ko` — language of the brief |
| `BRIEF_PDF` | also write the write-on-it PDF of the brief (default on) |
| `PLANNER_ENABLED` | build the planner PDF on the 1st (default off) |
| `BRIEF_HOUR` / `BRIEF_MINUTE` | when the daily brief runs |
| `PLANNER_PAGE` | `tablet` (5:3), `a4`, `a5` |
| `PLANNER_MONTHS` | months per planner file for the scheduled monthly build; `--months` / `--through` override it for a one-off |
| `PLANNER_MEETING_PAGES` | how many meeting-note pages to append |
| `PLANNER_HABITS` | habit tracker rows on the weekly page |

If two-factor authentication is on for the Nextcloud account, `NC_PASS` has to
be an **app password** (Settings → Security), not the login password.

## Google tokens

On a machine with a browser:

```bash
pip install -r requirements.txt
python3 app/auth_setup.py personal
python3 app/auth_setup.py work
```

It needs an OAuth client: either put the downloaded client secret at
`tokens/credentials.json`, or set `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
in `.env`. Create one at
[console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials)
as a **Desktop app**, and enable the Calendar, Gmail and Tasks APIs on that
project. Access is read-only.

Copy the resulting `tokens/<name>.json` onto the NAS. The name you pass is the
name that has to appear in `ACCOUNTS`.

## When something breaks

The service is built so one failure never costs you the brief:

- no API key, or the model is unreachable → the brief is still built from the
  raw calendar and mail
- one Google account broken → the other accounts still report, and the reason
  appears under *Needs attention*
- Nextcloud upload fails → files stay on disk and stay downloadable at `:9000`,
  with the exact cause in the log and in `--check`
- NAS was off overnight → the missing brief is built at startup

Data lives in `data/` (briefs and planners) and `tokens/` — both are mounted
from the host, so `docker compose down` loses nothing.
