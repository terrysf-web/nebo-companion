"""The small web UI on :9000.

Deliberately plain: a list of briefs, a list of planners, and two buttons.
Everything is downloadable from here, so a failed Nextcloud upload never means
a lost brief or planner.
"""

from __future__ import annotations

import logging
import threading
from datetime import date

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from . import jobs, render, store
from .config import Config, load_config

log = logging.getLogger(__name__)

_lock = threading.Lock()
_running: set[str] = set()


def _guard(name: str, fn, *args, **kwargs) -> None:
    """Run a job unless one of the same kind is already in flight."""
    with _lock:
        if name in _running:
            log.info("%s already running, ignoring the request", name)
            return
        _running.add(name)
    try:
        fn(*args, **kwargs)
    except Exception:  # noqa: BLE001 - a failed button press must not kill the server
        log.exception("%s failed", name)
    finally:
        with _lock:
            _running.discard(name)


def create_app(cfg: Config | None = None) -> FastAPI:
    cfg = cfg or load_config()
    app = FastAPI(title="Morning", docs_url=None, redoc_url=None)
    env = render.environment()

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        page = env.get_template("index.html").render(
            cfg=cfg,
            days=store.recent(cfg),
            planners=[p.name for p in store.planners(cfg)],
            running=bool(_running),
            problems=_startup_problems(cfg),
        )
        return HTMLResponse(page)

    @app.get("/brief/{day}.pdf")
    def brief_pdf(day: str) -> FileResponse:
        path = store.pdf_path(cfg, day)
        if not path.exists():
            stored = store.load(cfg, day)
            if stored is None:
                raise HTTPException(status_code=404, detail=f"no brief for {day}")
            from .briefpdf import build_brief_pdf

            build_brief_pdf(cfg, stored, path)
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.get("/brief/{day}", response_class=HTMLResponse)
    def brief(day: str) -> HTMLResponse:
        path = store.html_path(cfg, day)
        if path.exists():
            return HTMLResponse(path.read_text(encoding="utf-8"))
        stored = store.load(cfg, day)
        if stored is None:
            raise HTTPException(status_code=404, detail=f"no brief for {day}")
        return HTMLResponse(render.to_html(cfg, stored))

    @app.get("/planner/{name}")
    def planner(name: str) -> FileResponse:
        path = (cfg.planner_dir / name).resolve()
        if not path.is_file() or cfg.planner_dir.resolve() not in path.parents:
            raise HTTPException(status_code=404, detail="no such planner")
        return FileResponse(path, media_type="application/pdf", filename=path.name)

    @app.post("/run")
    def run(background: BackgroundTasks) -> RedirectResponse:
        background.add_task(_guard, "brief", jobs.run_brief, cfg)
        return RedirectResponse("/", status_code=303)

    @app.post("/planner")
    def make_planner(background: BackgroundTasks) -> RedirectResponse:
        background.add_task(_guard, "planner", jobs.run_planner, cfg)
        return RedirectResponse("/", status_code=303)

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse(
            {
                "ok": True,
                "today": date.today().isoformat(),
                "accounts": list(cfg.accounts),
                "briefs": len(store.recent(cfg, limit=999)),
                "running": sorted(_running),
            }
        )

    return app


def _startup_problems(cfg: Config) -> list[str]:
    """The mistakes that actually happen when someone sets this up."""
    problems: list[str] = []
    missing = [a for a in cfg.accounts if not cfg.token_path(a).exists()]
    if missing:
        problems.append(
            "No token file for: "
            + ", ".join(missing)
            + ". ACCOUNTS must match the file names in tokens/ "
            "(personal.json -> personal)."
        )
    if not cfg.anthropic_api_key:
        problems.append("ANTHROPIC_API_KEY is empty — briefs will be unsummarised.")
    if cfg.nc_upload and ("localhost" in cfg.nc_url or "127.0.0.1" in cfg.nc_url):
        problems.append(
            "NC_URL points at localhost, which inside the container means the "
            "container itself. Use the machine's real IP."
        )
    if cfg.nc_upload and not (cfg.nc_url and cfg.nc_user and cfg.nc_pass):
        problems.append("Nextcloud details are incomplete — uploads will be skipped.")
    return problems


app = create_app()
