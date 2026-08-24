"""Mint tokens/<account>.json on a machine with a browser (your Mac).

    python3 app/auth_setup.py personal
    python3 app/auth_setup.py work

Needs an OAuth client. Either drop the downloaded client secret at
tokens/credentials.json, or put GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET in .env.
Copy the resulting json into the NAS's tokens/ folder — the name you pass here
is the name that has to appear in ACCOUNTS.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config  # noqa: E402
from app.google_api import SCOPES  # noqa: E402


def client_config(cfg) -> dict:
    secrets = cfg.tokens_dir / "credentials.json"
    if secrets.exists():
        return json.loads(secrets.read_text(encoding="utf-8"))
    if cfg.google_client_id and cfg.google_client_secret:
        return {
            "installed": {
                "client_id": cfg.google_client_id,
                "client_secret": cfg.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
    raise SystemExit(
        "No OAuth client found.\n"
        "  Either put the downloaded client secret at tokens/credentials.json,\n"
        "  or set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env.\n"
        "  Create one at https://console.cloud.google.com/apis/credentials\n"
        "  (application type: Desktop app), and enable the Calendar, Gmail and\n"
        "  Tasks APIs for that project."
    )


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 app/auth_setup.py <account-name>")

    account = sys.argv[1].strip()
    cfg = load_config()
    cfg.tokens_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.token_path(account)

    if out.exists():
        answer = input(f"{out} already exists. Replace it? [y/N] ").strip().lower()
        if answer != "y":
            raise SystemExit("left it alone")

    flow = InstalledAppFlow.from_client_config(client_config(cfg), SCOPES)
    print(f"\nA browser will open. Sign in as the {account!r} Google account.\n")
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    if not creds.refresh_token:
        raise SystemExit(
            "Google returned no refresh token, so this file would stop working "
            "within the hour. Remove this app at "
            "https://myaccount.google.com/permissions and run it again."
        )

    out.write_text(creds.to_json(), encoding="utf-8")
    print(f"wrote {out}")
    print(f"copy it to the NAS's tokens/ folder and make sure ACCOUNTS contains {account!r}")


if __name__ == "__main__":
    main()
