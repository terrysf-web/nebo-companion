# Morning

A brief every morning and a planner every month, on a machine that is always
on, delivered to the tablet.

- **06:00 daily** — reads your Google calendars, unread mail and tasks across
  every account, adds the weather, has Claude turn it into a short brief, and
  writes it as **HTML** (to read) and **PDF** (to write on).
- **1st of each month** — builds next month's **planner PDF**: cover, year
  overview, month grids, weekly spreads, a page per day, and a linked
  meeting-note section. Every page is one tap from every other page.
- Both land in Nextcloud, and both stay downloadable from `http://<ip>:9000`
  even when the upload fails.

The PDFs are sized 5:3 landscape — a TCL NXTPAPER-class tablet screen — so a
page fills the display and you write straight onto it.

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
**Build planner** button.

## Planner PDF

```bash
docker compose run --rm --entrypoint python morning main.py --planner-only
```

The planner works the way the popular digital planners do:

| Page | What's on it |
|---|---|
| Cover | year, and a tap target for every month |
| Year | 12 mini calendars, every date links to its day page |
| Month | grid with your real calendar entries printed in, goals, notes |
| Week | seven columns, weekly focus, habit tracker |
| Day | hourly schedule, Top 3, to-dos, notes, link to the meeting log |
| Notes | numbered index → one meeting-note page each (discussion, decisions, action items) |

Navigation is on every page: **Year / Month / Week / Day / Notes** top right,
and JAN–DEC tabs down the right edge when the file covers more than one month.

## Daily brief PDF

The 06:00 brief is also a page you write on: printed brief down the left,
an empty hour-by-hour plan in the middle, Top 3 and notes on the right, plus a
blank second page. Open it in Nebo (or any notes app) and plan the day by hand
next to the brief instead of copying it somewhere else.

## Commands

```bash
python main.py                    # today's brief: HTML + PDF, upload
python main.py --planner-only     # next month's planner
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
| `BRIEF_HOUR` / `BRIEF_MINUTE` | when the daily brief runs |
| `PLANNER_PAGE` | `tablet` (5:3), `a4`, `a5` |
| `PLANNER_MONTHS` | months per planner file; 12 gives a full year with month tabs |
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
