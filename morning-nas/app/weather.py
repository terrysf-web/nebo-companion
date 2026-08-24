"""Today's weather from OpenWeatherMap. Optional — no key, no section."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import requests

from .config import Config

log = logging.getLogger(__name__)

CURRENT = "https://api.openweathermap.org/data/2.5/weather"
FORECAST = "https://api.openweathermap.org/data/2.5/forecast"
TIMEOUT = 20


@dataclass
class Weather:
    place: str
    now_c: float
    low_c: float
    high_c: float
    description: str
    rain_chance: int
    windy: bool

    def line(self) -> str:
        text = (
            f"{self.place}  {self.now_c:.0f}°C now, "
            f"{self.low_c:.0f}–{self.high_c:.0f}°C, {self.description}"
        )
        if self.rain_chance >= 30:
            text += f", {self.rain_chance}% chance of rain"
        if self.windy:
            text += ", windy"
        return text


def fetch(cfg: Config) -> Weather | None:
    if not cfg.owm_api_key:
        return None
    params = {
        "lat": cfg.lat,
        "lon": cfg.lon,
        "appid": cfg.owm_api_key,
        "units": "metric",
    }
    try:
        now = requests.get(CURRENT, params=params, timeout=TIMEOUT)
        now.raise_for_status()
        soon = requests.get(FORECAST, params=params, timeout=TIMEOUT)
        soon.raise_for_status()
    except requests.RequestException as exc:
        log.warning("weather unavailable: %s", exc)
        return None

    current = now.json()
    today = datetime.now(cfg.tz).date()
    temps: list[float] = []
    pops: list[float] = []
    gusts: list[float] = []
    for slot in soon.json().get("list", []):
        when = datetime.fromtimestamp(slot["dt"], cfg.tz)
        if when.date() != today:
            continue
        temps.append(slot["main"]["temp"])
        pops.append(slot.get("pop", 0))
        gusts.append(slot.get("wind", {}).get("speed", 0))

    now_c = current["main"]["temp"]
    return Weather(
        place=cfg.place or current.get("name", ""),
        now_c=now_c,
        low_c=min(temps or [current["main"]["temp_min"]]),
        high_c=max(temps or [current["main"]["temp_max"]]),
        description=(current.get("weather") or [{}])[0].get("description", ""),
        rain_chance=int(round(max(pops or [0]) * 100)),
        windy=max(gusts or [0]) >= 8,
    )
