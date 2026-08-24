"""Nextcloud WebDAV upload.

If the upload fails, the brief and the planner are still on disk and still
downloadable from the web UI on :9000 — so the job here is mostly to say
exactly *why* it failed, in terms of the setting that is wrong.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import requests
from requests.auth import HTTPBasicAuth

from .config import Config

log = logging.getLogger(__name__)

TIMEOUT = 60

# What each WebDAV status actually means when someone is setting this up.
HINTS = {
    401: "Authentication failed. Check NC_USER and NC_PASS. If the account has "
         "two-factor authentication, NC_PASS must be an app password from "
         "Nextcloud → Settings → Security, not the login password.",
    403: "Permission denied. Check that the user can write to the folder and "
         "that Nextcloud is not in maintenance/read-only mode.",
    404: "Path not found. NC_URL must be the Nextcloud root "
         "(e.g. http://192.168.0.10:8080) — do not include '/remote.php/...'.",
    405: "Method not allowed. NC_URL is probably pointing at something that is "
         "not Nextcloud (a reverse-proxy default page, for instance).",
    409: "Parent folder missing. Check NC_DIR.",
    413: "File too large for the server's upload limit.",
    423: "Resource locked — another client is writing to the same file.",
    507: "The Nextcloud account is out of storage.",
}


class UploadError(RuntimeError):
    """Upload failed. The message carries the likely cause."""


@dataclass
class Target:
    base: str
    auth: HTTPBasicAuth
    root: str  # remote.php/dav/files/<user>


def _target(cfg: Config) -> Target:
    if not (cfg.nc_url and cfg.nc_user and cfg.nc_pass):
        raise UploadError(
            "NC_URL / NC_USER / NC_PASS are not all set. Fill them in in .env, "
            "or set NC_UPLOAD=0 to turn uploading off."
        )
    if "localhost" in cfg.nc_url or "127.0.0.1" in cfg.nc_url:
        raise UploadError(
            f"NC_URL is {cfg.nc_url}. Inside the container localhost means the "
            "container itself — use the machine's real IP."
        )
    return Target(
        base=cfg.nc_url,
        auth=HTTPBasicAuth(cfg.nc_user, cfg.nc_pass),
        root=f"remote.php/dav/files/{quote(cfg.nc_user)}",
    )


def _describe(res: requests.Response) -> str:
    body = (res.text or "").strip()
    if len(body) > 300:
        body = body[:300] + "…"
    parts = [f"HTTP {res.status_code} {res.reason}"]
    if HINTS.get(res.status_code):
        parts.append(HINTS[res.status_code])
    if body:
        parts.append(f"response: {body}")
    return " — ".join(parts)


def _mkcol(t: Target, folder: str) -> None:
    """Create each folder level in turn; 405 means it already exists."""
    walked: list[str] = []
    for part in [p for p in folder.split("/") if p]:
        walked.append(part)
        url = f"{t.base}/{t.root}/{quote('/'.join(walked))}"
        res = requests.request("MKCOL", url, auth=t.auth, timeout=TIMEOUT)
        if res.status_code in (201, 405, 301, 302):
            continue
        raise UploadError(f"could not create '{'/'.join(walked)}' — {_describe(res)}")


def upload(cfg: Config, path: Path, subdir: str = "") -> str:
    """Upload one file and return its remote path."""
    t = _target(cfg)
    folder = "/".join(p for p in (cfg.nc_dir, subdir) if p)
    if folder:
        _mkcol(t, folder)

    remote = "/".join(p for p in (folder, path.name) if p)
    url = f"{t.base}/{t.root}/{quote(remote)}"

    try:
        with path.open("rb") as fh:
            res = requests.put(url, data=fh, auth=t.auth, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise UploadError(
            f"could not reach {cfg.nc_url} ({exc.__class__.__name__}). Check the "
            "host and port, and that the container can route to them."
        ) from exc

    if res.status_code not in (200, 201, 204):
        raise UploadError(f"upload of '{remote}' failed — {_describe(res)}")

    log.info("uploaded to Nextcloud: %s", remote)
    return remote


def try_upload(cfg: Config, path: Path, subdir: str = "") -> str | None:
    """Never raises — a failed upload must not lose the brief."""
    if not cfg.nc_upload:
        log.info("NC_UPLOAD=0, skipping upload of %s", path.name)
        return None
    try:
        return upload(cfg, path, subdir)
    except UploadError as exc:
        log.warning("upload failed: %s", exc)
        return None


def check(cfg: Config) -> list[str]:
    """Diagnostics for `main.py --check`, as lines meant for a human."""
    lines: list[str] = []
    try:
        t = _target(cfg)
    except UploadError as exc:
        return [f"✗ configuration: {exc}"]

    lines.append(f"· NC_URL   {cfg.nc_url}")
    lines.append(f"· NC_USER  {cfg.nc_user}")
    lines.append(f"· folder   {cfg.nc_dir or '(root)'}")

    url = f"{t.base}/{t.root}/"
    try:
        res = requests.request(
            "PROPFIND", url, auth=t.auth, headers={"Depth": "0"}, timeout=TIMEOUT
        )
    except requests.RequestException as exc:
        lines.append(f"✗ cannot connect: {exc.__class__.__name__}: {exc}")
        return lines

    if res.status_code in (200, 207):
        lines.append("✓ login and WebDAV access work")
    else:
        lines.append(f"✗ WebDAV access failed — {_describe(res)}")
        return lines

    probe = f"{t.base}/{t.root}/{quote(cfg.nc_dir)}" if cfg.nc_dir else url.rstrip("/")
    try:
        if cfg.nc_dir:
            _mkcol(t, cfg.nc_dir)
        res = requests.put(
            f"{probe}/.morning-check", data=b"ok", auth=t.auth, timeout=TIMEOUT
        )
        if res.status_code in (200, 201, 204):
            lines.append("✓ write access works — planner and brief uploads will land")
            requests.delete(f"{probe}/.morning-check", auth=t.auth, timeout=TIMEOUT)
        else:
            lines.append(f"✗ write failed — {_describe(res)}")
    except (UploadError, requests.RequestException) as exc:
        lines.append(f"✗ write failed — {exc}")
    return lines
