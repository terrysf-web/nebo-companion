"""Render a brief to standalone HTML."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import nebotext
from .brief import Brief
from .config import Config

TEMPLATES = Path(__file__).resolve().parent / "templates"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def environment() -> Environment:
    return _env


def to_html(cfg: Config, brief: Brief) -> str:
    return _env.get_template("brief.html").render(
        brief=brief, cfg=cfg, nebo_text=nebotext.to_text(cfg, brief)
    )


def write_html(cfg: Config, brief: Brief, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_html(cfg, brief), encoding="utf-8")
    return path
